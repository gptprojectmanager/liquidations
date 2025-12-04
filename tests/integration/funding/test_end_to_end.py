"""
End-to-end integration tests for funding rate bias adjustment.
Tests complete workflows from API fetching to bias calculation.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from src.models.funding.adjustment_config import AdjustmentConfigModel
from src.models.funding.funding_rate import FundingRate
from src.services.funding.complete_calculator import CompleteBiasCalculator


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    @pytest.mark.asyncio
    async def test_complete_bias_calculation_flow(self):
        """Test complete flow from config to bias adjustment."""
        # Step 1: Create configuration
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            sensitivity=50.0,
            max_adjustment=0.20,
            cache_ttl_seconds=300,
        )

        # Step 2: Initialize calculator
        calculator = CompleteBiasCalculator(config)

        # Step 3: Mock Binance API response
        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            # Step 4: Calculate bias adjustment
            total_oi = Decimal("1000000")
            adjustment = await calculator.calculate_bias_adjustment("BTCUSDT", total_oi)

            # Step 5: Verify results
            assert adjustment.symbol == "BTCUSDT"
            assert adjustment.total_oi == total_oi
            assert adjustment.long_oi + adjustment.short_oi == total_oi  # OI conservation
            assert adjustment.long_ratio + adjustment.short_ratio == Decimal("1.0")
            assert Decimal("0.0") <= adjustment.confidence <= Decimal("1.0")

    @pytest.mark.asyncio
    async def test_complete_flow_with_caching(self):
        """Test complete flow with caching enabled."""
        config = AdjustmentConfigModel(enabled=True, cache_ttl_seconds=60)
        calculator = CompleteBiasCalculator(config)

        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0005"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            # First call - should hit API
            result1 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
            assert mock_fetch.call_count == 1

            # Second call - should use cache
            result2 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("2000000"))

            # Should have same ratios (from cached funding rate)
            assert result1.long_ratio == result2.long_ratio
            assert result1.short_ratio == result2.short_ratio

            # But different OI values
            assert result1.total_oi != result2.total_oi

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(self):
        """Test fallback to neutral when API fails."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        # Mock API failure
        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            # Should fallback to neutral
            result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

            assert result.long_ratio == Decimal("0.5")
            assert result.short_ratio == Decimal("0.5")
            assert result.metadata.get("neutral") is True  # Neutral fallback flag

    @pytest.mark.asyncio
    async def test_disabled_config_flow(self):
        """Test flow when bias adjustment is disabled."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        # Should return neutral without calling API
        result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

        assert result.long_ratio == Decimal("0.5")
        assert result.short_ratio == Decimal("0.5")


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    @pytest.mark.asyncio
    async def test_bull_market_scenario(self):
        """Test bias adjustment in bull market (positive funding)."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        # Bull market: high positive funding rate
        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0008"),  # 0.08% - very bullish
            funding_time="2025-12-02T12:00:00+00:00",
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("10000000"))

            # Should favor long positions heavily
            assert result.long_ratio > Decimal("0.6"), (
                f"Long ratio {result.long_ratio} should be > 0.6 in bull market"
            )
            assert result.short_ratio < Decimal("0.4")

            # OI conservation must hold
            assert result.long_oi + result.short_oi == result.total_oi

    @pytest.mark.asyncio
    async def test_bear_market_scenario(self):
        """Test bias adjustment in bear market (negative funding)."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        # Bear market: high negative funding rate
        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("-0.0007"),  # -0.07% - very bearish
            funding_time="2025-12-02T12:00:00+00:00",
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("10000000"))

            # Should favor short positions heavily
            assert result.short_ratio > Decimal("0.6"), (
                f"Short ratio {result.short_ratio} should be > 0.6 in bear market"
            )
            assert result.long_ratio < Decimal("0.4")

            # OI conservation must hold
            assert result.long_oi + result.short_oi == result.total_oi

    @pytest.mark.asyncio
    async def test_neutral_market_scenario(self):
        """Test bias adjustment in neutral market (near-zero funding)."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        # Neutral market: very small funding rate
        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.00001"),  # 0.001% - neutral
            funding_time="2025-12-02T12:00:00+00:00",
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("10000000"))

            # Should be close to 50/50
            assert abs(result.long_ratio - Decimal("0.5")) < Decimal("0.05")
            assert abs(result.short_ratio - Decimal("0.5")) < Decimal("0.05")

    @pytest.mark.asyncio
    async def test_multiple_symbols_sequential(self):
        """Test calculating bias for multiple symbols sequentially."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        rates = [Decimal("0.0003"), Decimal("-0.0002"), Decimal("0.0001")]

        results = []
        for symbol, rate in zip(symbols, rates):
            mock_funding = FundingRate(
                symbol=symbol,
                rate=rate,
                funding_time="2025-12-02T12:00:00+00:00",
            )

            with patch.object(
                calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
            ) as mock_fetch:
                mock_fetch.return_value = mock_funding
                result = await calculator.calculate_bias_adjustment(symbol, Decimal("1000000"))
                results.append(result)

        # All should maintain OI conservation
        for result in results:
            assert result.long_oi + result.short_oi == result.total_oi

        # Different funding rates should give different ratios
        assert results[0].long_ratio != results[1].long_ratio

    @pytest.mark.asyncio
    async def test_large_oi_values(self):
        """Test with very large OI values (billions)."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        # Test with 5 billion OI
        large_oi = Decimal("5000000000")

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            result = await calculator.calculate_bias_adjustment("BTCUSDT", large_oi)

            # Should handle large numbers without overflow
            assert result.total_oi == large_oi
            assert result.long_oi + result.short_oi == large_oi
            assert result.long_oi > Decimal("0")
            assert result.short_oi > Decimal("0")


class TestErrorRecovery:
    """Test error handling and recovery."""

    @pytest.mark.asyncio
    async def test_recovery_from_network_error(self):
        """Test recovery from transient network errors."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        # First call fails, second succeeds
        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            # Simulate retry scenario - first fails, then succeeds
            mock_fetch.side_effect = [Exception("Network error"), mock_funding]

            # First call - should fallback
            result1 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
            assert result1.long_ratio == Decimal("0.5")  # Neutral fallback

            # Clear cache to force new fetch
            calculator._fetcher._cache.clear()

            # Second call - should succeed
            result2 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
            assert result2.long_ratio > Decimal("0.5")  # Biased (positive funding)

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test graceful degradation when services are unavailable."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("Service unavailable")

            # Should degrade gracefully to neutral
            result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

            # Should still return valid result
            assert result is not None
            assert result.long_ratio == Decimal("0.5")
            assert result.short_ratio == Decimal("0.5")
            assert result.total_oi == Decimal("1000000")

    @pytest.mark.asyncio
    async def test_invalid_oi_handling(self):
        """Test handling of invalid OI values."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        # Negative OI should be handled
        with pytest.raises(Exception):
            await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("-1000"))

        # Zero OI - should work
        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("0"))
            assert result.total_oi == Decimal("0")
            assert result.long_oi == Decimal("0")
            assert result.short_oi == Decimal("0")


class TestPerformance:
    """Test performance characteristics."""

    @pytest.mark.asyncio
    async def test_calculation_performance(self):
        """Test that calculations are fast enough."""
        import time

        config = AdjustmentConfigModel(enabled=False)  # Skip API for speed test
        calculator = CompleteBiasCalculator(config)

        # Measure time for 1000 calculations
        start = time.time()

        for i in range(1000):
            await calculator.calculate_bias_adjustment(f"SYM{i}", Decimal(f"{1000000 + i}"))

        elapsed = time.time() - start

        # Should complete 1000 calculations in under 1 second
        assert elapsed < 1.0, f"1000 calculations took {elapsed:.2f}s (should be < 1s)"

        # Average should be < 1ms per calculation
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 1.0, f"Average calculation time {avg_ms:.3f}ms (should be < 1ms)"

    @pytest.mark.asyncio
    async def test_multiple_calculations_stability(self):
        """Test stability with multiple sequential calculations."""
        config = AdjustmentConfigModel(enabled=False)  # Use neutral mode
        calculator = CompleteBiasCalculator(config)

        # Run 100 calculations sequentially
        for i in range(100):
            result = await calculator.calculate_bias_adjustment(
                f"SYMBOL{i}", Decimal(f"{1000000 + i}")
            )

            # All should maintain OI conservation
            assert result.long_oi + result.short_oi == result.total_oi
            # Neutral mode should give 50/50
            assert result.long_ratio == Decimal("0.5")
            assert result.short_ratio == Decimal("0.5")
