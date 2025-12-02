"""
Integration tests for historical smoothing in complete calculator.
Feature: LIQHEAT-005
Task: T021 - Add historical smoothing support
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from src.models.funding.adjustment_config import AdjustmentConfigModel
from src.models.funding.funding_rate import FundingRate
from src.services.funding.complete_calculator import CompleteBiasCalculator


class TestSmoothingIntegration:
    """Integration tests for smoothing in complete calculator."""

    @pytest.mark.asyncio
    async def test_calculator_with_smoothing_enabled(self):
        """Test that calculator applies smoothing when enabled."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            smoothing_enabled=True,
            smoothing_periods=3,
            smoothing_weights=[0.5, 0.3, 0.2],
        )
        calculator = CompleteBiasCalculator(config)

        # Mock funding rates with increasing trend
        funding_rates = [
            Decimal("0.0001"),  # First call
            Decimal("0.0002"),  # Second call
            Decimal("0.0003"),  # Third call
        ]

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            # Setup mock to return different rates
            mock_fetch.side_effect = [
                FundingRate(
                    symbol="BTCUSDT",
                    rate=rate,
                    funding_time=datetime.now(timezone.utc),
                )
                for rate in funding_rates
            ]

            # Act - Make multiple calls to build history
            # Clear cache between calls to force recalculation
            adj1 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
            calculator._adjustment_cache.clear()

            adj2 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
            calculator._adjustment_cache.clear()

            adj3 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

            # Assert
            # First adjustment has no history (no smoothing)
            assert adj1.metadata is None or adj1.metadata.get("smoothed") is not True

            # Second adjustment should be smoothed with 1 history item
            assert adj2.metadata and adj2.metadata.get("smoothed") is True

            # Third should use 3 periods total (current + 2 history)
            assert adj3.metadata and adj3.metadata.get("smoothed") is True
            assert adj3.metadata.get("periods_used") == 3  # Current + 2 history = 3 total

            # Later adjustments should have ratios between the extremes due to smoothing
            # adj3 should be between adj1 and raw calculation for 0.0003
            assert adj3.long_ratio > adj1.long_ratio  # Trending up
            assert adj3.long_ratio < Decimal("0.70")  # But smoothed, not extreme

    @pytest.mark.asyncio
    async def test_calculator_without_smoothing(self):
        """Test that calculator doesn't smooth when disabled."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            smoothing_enabled=False,  # Disabled
        )
        calculator = CompleteBiasCalculator(config)

        funding_rates = [Decimal("0.0001"), Decimal("0.0003")]

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = [
                FundingRate(
                    symbol="BTCUSDT",
                    rate=rate,
                    funding_time=datetime.now(timezone.utc),
                )
                for rate in funding_rates
            ]

            # Act
            adj1 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
            adj2 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

            # Assert - No smoothing applied
            assert adj2.metadata is None or adj2.metadata.get("smoothed") is not True

    @pytest.mark.asyncio
    async def test_smoothing_dampens_volatility(self):
        """Test that smoothing reduces adjustment volatility."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            smoothing_enabled=True,
            smoothing_periods=3,
            smoothing_weights=[0.4, 0.35, 0.25],  # More weight on history
        )
        calculator = CompleteBiasCalculator(config)

        # Simulate volatile funding rates
        funding_rates = [
            Decimal("0.0001"),  # Stable
            Decimal("0.0001"),  # Stable
            Decimal("0.01"),  # Extreme spike!
        ]

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = [
                FundingRate(
                    symbol="BTCUSDT",
                    rate=rate,
                    funding_time=datetime.now(timezone.utc),
                )
                for rate in funding_rates
            ]

            # Act - Build stable history then spike
            adj1 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
            calculator._adjustment_cache.clear()

            adj2 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
            calculator._adjustment_cache.clear()

            adj3 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

            # Assert - Spike should be dampened
            # Without smoothing, 0.01 funding would give ~0.70 long ratio
            # With smoothing and stable history, should be much lower
            assert adj3.long_ratio < Decimal("0.65")  # Dampened from extreme
            assert adj3.long_ratio > adj2.long_ratio  # But still increased

    @pytest.mark.asyncio
    async def test_smoothing_with_cache_interaction(self):
        """Test that smoothing works correctly with caching."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            smoothing_enabled=True,
            smoothing_periods=2,
            cache_ttl_seconds=300,
        )
        calculator = CompleteBiasCalculator(config)

        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time=datetime.now(timezone.utc),
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            # Act - First call populates cache
            adj1 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

            # Clear history to simulate new session
            calculator._history.clear()

            # Second call should use cache (no smoothing due to no history)
            adj2 = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

            # Assert
            assert adj1 == adj2  # Same from cache
            mock_fetch.assert_called_once()  # Only one API call
