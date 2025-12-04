"""
Integration tests for complete bias calculator with funding rate fetching.
Feature: LIQHEAT-005
Task: T020 - Implement complete bias calculator
TDD: Red phase
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from src.models.funding.adjustment_config import AdjustmentConfigModel
from src.models.funding.bias_adjustment import BiasAdjustment
from src.models.funding.funding_rate import FundingRate

# These imports will fail initially (TDD Red phase)
from src.services.funding.complete_calculator import CompleteBiasCalculator


class TestCompleteBiasCalculator:
    """Test suite for complete bias calculator."""

    @pytest.mark.asyncio
    async def test_calculate_bias_with_funding_fetch(self):
        """Test complete calculation flow from API to bias adjustment."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            sensitivity=50.0,
            max_adjustment=0.20,
        )
        calculator = CompleteBiasCalculator(config)

        # Mock funding rate response
        funding_time = datetime.now(timezone.utc)
        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),  # 0.03%
            funding_time=funding_time,
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            # Act
            adjustment = await calculator.calculate_bias_adjustment(
                "BTCUSDT", total_oi=Decimal("1000000")
            )

            # Assert
            assert isinstance(adjustment, BiasAdjustment)
            assert adjustment.symbol == "BTCUSDT"
            assert adjustment.long_oi > adjustment.short_oi  # Positive funding = more longs
            assert adjustment.confidence_score > Decimal("0.05")  # Low funding = low confidence
            mock_fetch.assert_called_once_with("BTCUSDT")

    @pytest.mark.asyncio
    async def test_calculate_bias_with_cache(self):
        """Test that cached values are used when available."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            cache_ttl_seconds=300,
        )
        calculator = CompleteBiasCalculator(config)

        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0005"),
            funding_time=datetime.now(timezone.utc),
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            # Act - First call fetches from API
            adj1 = await calculator.calculate_bias_adjustment(
                "BTCUSDT", total_oi=Decimal("1000000")
            )

            # Act - Second call should use cache
            adj2 = await calculator.calculate_bias_adjustment(
                "BTCUSDT", total_oi=Decimal("1000000")
            )

            # Assert
            assert adj1.long_oi == adj2.long_oi
            assert adj1.short_oi == adj2.short_oi
            mock_fetch.assert_called_once()  # Only one API call

    @pytest.mark.asyncio
    async def test_calculate_bias_when_disabled(self):
        """Test that neutral adjustment is returned when feature is disabled."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=False,
            symbol="BTCUSDT",
        )
        calculator = CompleteBiasCalculator(config)

        # Act
        adjustment = await calculator.calculate_bias_adjustment(
            "BTCUSDT", total_oi=Decimal("1000000")
        )

        # Assert
        assert adjustment.long_oi == Decimal("500000")  # 50/50 split
        assert adjustment.short_oi == Decimal("500000")
        assert adjustment.confidence_score == Decimal("0.5")  # Neutral confidence

    @pytest.mark.asyncio
    async def test_calculate_bias_with_error_fallback(self):
        """Test fallback to cached value when API fails."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
        )
        calculator = CompleteBiasCalculator(config)

        # First, populate cache with successful fetch
        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time=datetime.now(timezone.utc),
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding
            # Populate cache
            await calculator.calculate_bias_adjustment("BTCUSDT", total_oi=Decimal("1000000"))

        # Now test with API failure
        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("API down")

            # Act - Should use cached value
            adjustment = await calculator.calculate_bias_adjustment(
                "BTCUSDT", total_oi=Decimal("1000000")
            )

            # Assert
            assert adjustment is not None
            assert adjustment.symbol == "BTCUSDT"
            # Should use last known funding rate

    @pytest.mark.asyncio
    async def test_calculate_bias_extreme_funding(self):
        """Test handling of extreme funding rates."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            max_adjustment=0.20,
            outlier_cap=0.10,
            extreme_alert_threshold=0.01,  # 1% threshold
        )
        calculator = CompleteBiasCalculator(config)

        # Mock extreme funding rate
        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.02"),  # 2% - extreme (above 1% threshold)
            funding_time=datetime.now(timezone.utc),
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            # Act
            adjustment = await calculator.calculate_bias_adjustment(
                "BTCUSDT", total_oi=Decimal("1000000")
            )

            # Assert
            assert adjustment.long_ratio <= Decimal("0.7")  # Max adjustment applied
            assert adjustment.short_ratio >= Decimal("0.3")
            assert adjustment.metadata.get("extreme_funding") is True

    def test_sync_get_last_adjustment(self):
        """Test synchronous retrieval of last adjustment."""
        # Arrange
        config = AdjustmentConfigModel(enabled=True, symbol="BTCUSDT")
        calculator = CompleteBiasCalculator(config)

        # Manually set last adjustment
        test_adjustment = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            symbol="BTCUSDT",
            long_ratio=Decimal("0.55"),
            short_ratio=Decimal("0.45"),
            total_oi=Decimal("1000000"),
            long_oi=Decimal("550000"),
            short_oi=Decimal("450000"),
            confidence_score=Decimal("0.75"),
        )
        calculator._last_adjustment = test_adjustment

        # Act
        last = calculator.get_last_adjustment()

        # Assert
        assert last == test_adjustment

    @pytest.mark.asyncio
    async def test_calculate_with_custom_parameters(self):
        """Test calculation with custom sensitivity and max adjustment."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            sensitivity=100.0,  # High sensitivity
            max_adjustment=0.10,  # Low max adjustment
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

            # Act
            adjustment = await calculator.calculate_bias_adjustment(
                "BTCUSDT", total_oi=Decimal("1000000")
            )

            # Assert
            # With high sensitivity but low max, should hit the cap
            assert adjustment.long_ratio <= Decimal("0.60")  # Max 10% from 50%
            assert adjustment.short_ratio >= Decimal("0.40")
