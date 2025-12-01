"""
Unit tests for FundingRate model.
Feature: LIQHEAT-005
Task: T010 - Test FundingRate model
TDD: Red phase
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

# These imports will fail initially (TDD Red phase)
from src.models.funding.funding_rate import FundingRate


class TestFundingRateModel:
    """Test suite for FundingRate model."""

    def test_create_valid_funding_rate(self):
        """Test creating a valid funding rate."""
        # Arrange
        funding_time = datetime.now(timezone.utc)

        # Act
        funding = FundingRate(
            symbol="BTCUSDT", rate=Decimal("0.0003"), funding_time=funding_time, source="binance"
        )

        # Assert
        assert funding.symbol == "BTCUSDT"
        assert funding.rate == Decimal("0.0003")
        assert funding.funding_time == funding_time
        assert funding.source == "binance"

    def test_funding_rate_validation_symbol_pattern(self):
        """Test that symbol must match USDT pattern."""
        # Arrange
        funding_time = datetime.now(timezone.utc)

        # Act & Assert
        with pytest.raises(ValueError, match="symbol"):
            FundingRate(
                symbol="BTCUSD",  # Missing T
                rate=Decimal("0.0003"),
                funding_time=funding_time,
            )

    def test_funding_rate_validation_rate_bounds(self):
        """Test that rate must be within valid bounds."""
        # Arrange
        funding_time = datetime.now(timezone.utc)

        # Act & Assert - Too high
        with pytest.raises(ValueError, match="rate"):
            FundingRate(
                symbol="BTCUSDT",
                rate=Decimal("0.15"),  # 15% is too high
                funding_time=funding_time,
            )

        # Act & Assert - Too low
        with pytest.raises(ValueError, match="rate"):
            FundingRate(
                symbol="BTCUSDT",
                rate=Decimal("-0.15"),  # -15% is too low
                funding_time=funding_time,
            )

    def test_funding_rate_percentage_property(self):
        """Test percentage conversion property."""
        # Arrange & Act
        funding = FundingRate(
            symbol="BTCUSDT", rate=Decimal("0.0003"), funding_time=datetime.now(timezone.utc)
        )

        # Assert
        assert funding.rate_percentage == Decimal("0.03")  # 0.03%

    def test_funding_rate_is_positive_negative_neutral(self):
        """Test funding rate classification properties."""
        # Arrange
        funding_time = datetime.now(timezone.utc)

        # Test positive
        positive = FundingRate(symbol="BTCUSDT", rate=Decimal("0.0003"), funding_time=funding_time)
        assert positive.is_positive is True
        assert positive.is_negative is False
        assert positive.is_neutral is False

        # Test negative
        negative = FundingRate(symbol="BTCUSDT", rate=Decimal("-0.0003"), funding_time=funding_time)
        assert negative.is_positive is False
        assert negative.is_negative is True
        assert negative.is_neutral is False

        # Test neutral
        neutral = FundingRate(symbol="BTCUSDT", rate=Decimal("0.0"), funding_time=funding_time)
        assert neutral.is_positive is False
        assert neutral.is_negative is False
        assert neutral.is_neutral is True

    def test_funding_rate_from_binance_response(self):
        """Test creating FundingRate from Binance API response."""
        # Arrange
        binance_response = {
            "symbol": "BTCUSDT",
            "fundingRate": "0.00030000",
            "fundingTime": 1735689600000,  # Unix timestamp in ms
            "markPrice": "95432.12345678",
        }

        # Act
        funding = FundingRate.from_binance(binance_response)

        # Assert
        assert funding.symbol == "BTCUSDT"
        assert funding.rate == Decimal("0.0003")
        assert funding.source == "binance"
        assert isinstance(funding.funding_time, datetime)

    def test_funding_rate_to_dict(self):
        """Test converting FundingRate to dictionary."""
        # Arrange
        funding_time = datetime(2025, 12, 1, 8, 0, 0, tzinfo=timezone.utc)
        funding = FundingRate(symbol="BTCUSDT", rate=Decimal("0.0003"), funding_time=funding_time)

        # Act
        result = funding.to_dict()

        # Assert
        assert result["symbol"] == "BTCUSDT"
        assert result["rate"] == "0.0003"
        assert result["rate_percentage"] == "0.0300"  # Decimal preserves precision
        assert result["funding_time"] == funding_time.isoformat()
        assert result["source"] == "binance"
        assert result["is_positive"] is True

    def test_funding_rate_comparison(self):
        """Test comparing funding rates by time."""
        # Arrange
        earlier = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time=datetime(2025, 12, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        later = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0002"),
            funding_time=datetime(2025, 12, 1, 8, 0, 0, tzinfo=timezone.utc),
        )

        # Act & Assert
        assert earlier < later
        assert later > earlier
        assert earlier != later
