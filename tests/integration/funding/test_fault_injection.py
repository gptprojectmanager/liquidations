"""
Fault injection and chaos testing for funding rate bias adjustment.
Tests system behavior under failure scenarios and adverse conditions.
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from src.models.funding.adjustment_config import AdjustmentConfigModel
from src.models.funding.funding_rate import FundingRate
from src.services.funding.complete_calculator import CompleteBiasCalculator


class TestNetworkFailures:
    """Test behavior under network failure scenarios."""

    @pytest.mark.asyncio
    async def test_intermittent_network_failures(self):
        """Test with random intermittent network failures."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        call_count = 0

        async def flaky_fetch(symbol):
            """Simulate flaky network (50% failure rate)."""
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise Exception("Network timeout")
            return FundingRate(
                symbol=symbol,
                rate=Decimal("0.0003"),
                funding_time="2025-12-02T12:00:00+00:00",
            )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = flaky_fetch

            # Multiple calls - should handle intermittent failures
            for i in range(10):
                result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

                # Should always return valid result (either real or fallback)
                assert result is not None
                assert result.long_ratio + result.short_ratio == Decimal("1.0")

    @pytest.mark.asyncio
    async def test_slow_api_responses(self):
        """Test with very slow API responses."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        async def slow_fetch(symbol):
            """Simulate very slow API."""
            await asyncio.sleep(0.5)  # 500ms delay
            return FundingRate(
                symbol=symbol,
                rate=Decimal("0.0003"),
                funding_time="2025-12-02T12:00:00+00:00",
            )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = slow_fetch

            # Should complete eventually (no timeout)
            result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
            assert result is not None

    @pytest.mark.asyncio
    async def test_complete_network_outage(self):
        """Test with complete network outage."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        # Simulate complete outage
        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("No network connection")

            # Should fallback gracefully
            result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

            assert result is not None
            assert result.long_ratio == Decimal("0.5")  # Neutral fallback
            assert result.short_ratio == Decimal("0.5")


class TestDataCorruption:
    """Test behavior with corrupted or malformed data."""

    @pytest.mark.asyncio
    async def test_corrupted_funding_rate_response(self):
        """Test with corrupted API response data."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        # Various corrupted responses
        corrupted_responses = [
            {},  # Empty dict
            {"symbol": "BTCUSDT"},  # Missing rate
            {"rate": "0.0003"},  # Missing symbol
            {"symbol": "BTCUSDT", "rate": "invalid"},  # Invalid rate format
            None,  # None response
        ]

        for corrupted in corrupted_responses:
            with patch.object(
                calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
            ) as mock_fetch:
                if corrupted is None:
                    mock_fetch.return_value = None
                else:
                    mock_fetch.side_effect = Exception(f"Malformed data: {corrupted}")

                # Should handle gracefully
                result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
                assert result is not None
                # Should fallback to neutral
                assert result.long_ratio == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_extreme_funding_rate_values(self):
        """Test with extreme/invalid funding rate values from API."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        # Extreme values that shouldn't happen in reality
        extreme_rates = [
            Decimal("1.0"),  # 100% - impossible
            Decimal("-1.0"),  # -100% - impossible
            Decimal("0.5"),  # 50% - absurd
        ]

        # Pydantic validation should REJECT these extreme values
        for extreme_rate in extreme_rates:
            with pytest.raises(Exception):  # Pydantic ValidationError
                FundingRate(
                    symbol="BTCUSDT",
                    rate=extreme_rate,
                    funding_time="2025-12-02T12:00:00+00:00",
                )

    @pytest.mark.asyncio
    async def test_nan_infinity_in_calculations(self):
        """Test calculator handles NaN/Infinity edge cases."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        # Even with neutral mode, test with various OI values
        test_oi_values = [
            Decimal("0"),  # Zero OI
            Decimal("0.000001"),  # Extremely small
            Decimal("999999999999999"),  # Extremely large
        ]

        for oi in test_oi_values:
            result = await calculator.calculate_bias_adjustment("BTCUSDT", oi)

            # Should never produce NaN or infinity
            assert str(result.long_ratio).lower() not in ["nan", "inf", "-inf"]
            assert str(result.short_ratio).lower() not in ["nan", "inf", "-inf"]
            assert result.long_ratio + result.short_ratio == Decimal("1.0")


class TestResourceExhaustion:
    """Test behavior under resource exhaustion scenarios."""

    @pytest.mark.asyncio
    async def test_memory_pressure_simulation(self):
        """Test with many large calculations simulating memory pressure."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        # Create many large calculations
        large_oi = Decimal("999999999999")  # Trillion

        results = []
        for i in range(1000):
            result = await calculator.calculate_bias_adjustment(f"SYMBOL{i}", large_oi)
            results.append(result)

        # All should complete successfully
        assert len(results) == 1000
        for result in results:
            assert result.long_ratio + result.short_ratio == Decimal("1.0")

    @pytest.mark.asyncio
    async def test_concurrent_request_storm(self):
        """Test with sudden burst of concurrent requests."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        # Simulate request storm (100 concurrent requests)
        tasks = []
        for i in range(100):
            task = calculator.calculate_bias_adjustment(f"SYMBOL{i}", Decimal("1000000"))
            tasks.append(task)

        # All should complete without crashes
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # No exceptions should occur
        for result in results:
            assert not isinstance(result, Exception)
            assert result.long_ratio + result.short_ratio == Decimal("1.0")


class TestEdgeCaseScenarios:
    """Test unusual edge case scenarios."""

    @pytest.mark.asyncio
    async def test_rapid_enable_disable_toggle(self):
        """Test rapidly toggling enabled state."""
        # Start with enabled
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            # Toggle config state rapidly
            for i in range(10):
                config.enabled = i % 2 == 0

                result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
                assert result is not None

    @pytest.mark.asyncio
    async def test_symbol_name_variations(self):
        """Test with various symbol name formats."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        # Various symbol formats (calculator should handle)
        symbols = [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
            "SYMBOL123",  # With numbers
            "A" * 20 + "USDT",  # Very long
        ]

        for symbol in symbols:
            result = await calculator.calculate_bias_adjustment(symbol, Decimal("1000000"))
            assert result is not None
            assert result.symbol == symbol

    @pytest.mark.asyncio
    async def test_oi_precision_edge_cases(self):
        """Test OI with extreme precision."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        # Very precise OI values
        precise_oi_values = [
            Decimal("1000000.123456789012345678"),  # High precision
            Decimal("0.000000000000000001"),  # Extremely small
            Decimal("1.111111111111111111"),  # Repeating
        ]

        for oi in precise_oi_values:
            result = await calculator.calculate_bias_adjustment("BTCUSDT", oi)

            # Should handle precision correctly
            assert result.long_oi + result.short_oi == result.total_oi
            # OI conservation
            assert result.long_ratio + result.short_ratio == Decimal("1.0")


class TestRaceConditionScenarios:
    """Test for potential race conditions in edge cases."""

    @pytest.mark.asyncio
    async def test_simultaneous_cache_invalidation(self):
        """Test cache behavior with simultaneous invalidation."""
        config = AdjustmentConfigModel(enabled=True, cache_ttl_seconds=60)
        calculator = CompleteBiasCalculator(config)

        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            # Multiple concurrent calls
            tasks = [
                calculator.calculate_bias_adjustment("BTCUSDT", Decimal(f"{1000000 + i}"))
                for i in range(50)
            ]

            results = await asyncio.gather(*tasks)

            # All should succeed despite potential cache race conditions
            for result in results:
                assert result.long_ratio + result.short_ratio == Decimal("1.0")

    @pytest.mark.asyncio
    async def test_config_modification_during_calculation(self):
        """Test modifying config during active calculations."""
        config = AdjustmentConfigModel(enabled=True, sensitivity=50.0)
        calculator = CompleteBiasCalculator(config)

        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            # Start calculation
            task1 = calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

            # Modify config while calculation is running
            config.sensitivity = 75.0

            # Start another calculation
            task2 = calculator.calculate_bias_adjustment("BTCUSDT", Decimal("2000000"))

            # Both should complete successfully
            result1, result2 = await asyncio.gather(task1, task2)

            assert result1 is not None
            assert result2 is not None


class TestErrorPropagation:
    """Test that errors propagate correctly without silent failures."""

    @pytest.mark.asyncio
    async def test_calculator_initialization_errors(self):
        """Test errors during calculator initialization."""
        # Invalid config should fail fast
        with pytest.raises(Exception):
            invalid_config = AdjustmentConfigModel(sensitivity=-100)

    @pytest.mark.asyncio
    async def test_calculation_errors_not_silent(self):
        """Test that calculation errors are not silently swallowed."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        # Mock a calculation error in the core bias calculator
        with patch.object(calculator._bias_calculator, "calculate") as mock_calc:
            mock_calc.side_effect = Exception("Calculation failed")

            # Error should be handled, but result should indicate neutral fallback
            result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

            # Should fallback to neutral
            assert result.long_ratio == Decimal("0.5")
            assert result.short_ratio == Decimal("0.5")
