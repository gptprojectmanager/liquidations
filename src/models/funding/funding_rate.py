"""
Funding rate data model.
Feature: LIQHEAT-005
Task: T010 - Implement FundingRate model
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class FundingRate(BaseModel):
    """
    Represents a funding rate data point from an exchange.

    Funding rates are periodic payments between long and short
    positions to keep perpetual futures prices aligned with spot.
    """

    symbol: str = Field(
        ..., description="Trading pair symbol (e.g., BTCUSDT)", pattern=r"^[A-Z]{3,10}USDT$"
    )

    rate: Decimal = Field(
        ...,
        description="The funding rate (e.g., 0.0003 for 0.03%)",
        ge=Decimal("-0.10"),
        le=Decimal("0.10"),
    )

    funding_time: datetime = Field(..., description="When this funding rate applies")

    source: str = Field(default="binance", description="Data source for the funding rate")

    mark_price: Optional[Decimal] = Field(default=None, description="Mark price at funding time")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate trading symbol format."""
        if not v.endswith("USDT"):
            raise ValueError(f"symbol {v} must end with USDT")
        return v

    @field_validator("rate")
    @classmethod
    def validate_rate(cls, v: Decimal) -> Decimal:
        """Validate funding rate is within reasonable bounds."""
        if not (-Decimal("0.10") <= v <= Decimal("0.10")):
            raise ValueError(f"rate {v} out of valid range [-0.10, 0.10]")
        return v

    @field_validator("funding_time")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime) -> datetime:
        """Ensure funding_time is timezone-aware (UTC)."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @property
    def rate_percentage(self) -> Decimal:
        """Get funding rate as percentage (e.g., 0.03 for 0.03%)."""
        return self.rate * Decimal("100")

    @property
    def is_positive(self) -> bool:
        """True if funding rate is positive (longs pay shorts)."""
        return self.rate > Decimal("0")

    @property
    def is_negative(self) -> bool:
        """True if funding rate is negative (shorts pay longs)."""
        return self.rate < Decimal("0")

    @property
    def is_neutral(self) -> bool:
        """True if funding rate is zero or very close to zero."""
        return abs(self.rate) < Decimal("0.000001")

    @classmethod
    def from_binance(cls, data: Dict[str, Any]) -> "FundingRate":
        """
        Create FundingRate from Binance API response.

        Args:
            data: Binance funding rate response dict

        Returns:
            FundingRate instance
        """
        # Convert Unix timestamp (ms) to datetime
        timestamp_ms = data.get("fundingTime", data.get("time"))
        funding_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

        return cls(
            symbol=data["symbol"],
            rate=Decimal(data["fundingRate"]),
            funding_time=funding_time,
            source="binance",
            mark_price=Decimal(data["markPrice"]) if "markPrice" in data else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for API responses.

        Returns:
            Dictionary representation
        """
        return {
            "symbol": self.symbol,
            "rate": str(self.rate),
            "rate_percentage": str(self.rate_percentage),
            "funding_time": self.funding_time.isoformat(),
            "source": self.source,
            "mark_price": str(self.mark_price) if self.mark_price else None,
            "is_positive": self.is_positive,
            "is_negative": self.is_negative,
            "is_neutral": self.is_neutral,
        }

    def __lt__(self, other: "FundingRate") -> bool:
        """Compare by funding time for sorting."""
        return self.funding_time < other.funding_time

    def __gt__(self, other: "FundingRate") -> bool:
        """Compare by funding time for sorting."""
        return self.funding_time > other.funding_time

    def __eq__(self, other: object) -> bool:
        """Check equality by symbol, rate, and time."""
        if not isinstance(other, FundingRate):
            return False
        return (
            self.symbol == other.symbol
            and self.rate == other.rate
            and self.funding_time == other.funding_time
        )

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "BTCUSDT",
                "rate": "0.0003",
                "funding_time": "2025-12-01T08:00:00Z",
                "source": "binance",
            }
        }
    }
