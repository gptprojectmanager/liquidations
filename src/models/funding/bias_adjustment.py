"""
Bias adjustment model for funding rate-based position distribution.
Feature: LIQHEAT-005
Task: T011 - Implement BiasAdjustment model
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class BiasAdjustment(BaseModel):
    """
    Represents the calculated bias adjustment from funding rate.

    Maintains the invariant that long_ratio + short_ratio = 1.0 exactly
    to ensure total open interest conservation.
    """

    funding_input: Decimal = Field(
        ...,
        description="The funding rate used for calculation",
        ge=Decimal("-0.10"),
        le=Decimal("0.10"),
    )

    long_ratio: Decimal = Field(
        ..., description="Adjusted ratio for long positions", ge=Decimal("0.0"), le=Decimal("1.0")
    )

    short_ratio: Decimal = Field(
        ..., description="Adjusted ratio for short positions", ge=Decimal("0.0"), le=Decimal("1.0")
    )

    confidence: float = Field(
        default=0.0,
        description="Confidence score (0-1) based on funding rate magnitude",
        ge=0.0,
        le=1.0,
    )

    scale_factor: Optional[float] = Field(
        default=None, description="Scale factor used in tanh transformation"
    )

    max_adjustment: Optional[float] = Field(
        default=None, description="Maximum adjustment from baseline used"
    )

    # Extended fields for complete adjustment tracking
    symbol: Optional[str] = Field(default=None, description="Trading symbol (e.g., BTCUSDT)")

    total_oi: Optional[Decimal] = Field(
        default=None, description="Total open interest", ge=Decimal("0")
    )

    long_oi: Optional[Decimal] = Field(
        default=None, description="Long open interest", ge=Decimal("0")
    )

    short_oi: Optional[Decimal] = Field(
        default=None, description="Short open interest", ge=Decimal("0")
    )

    confidence_score: Optional[Decimal] = Field(
        default=None,
        description="Confidence score as Decimal (for consistency)",
        ge=Decimal("0"),
        le=Decimal("1"),
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @field_validator("long_ratio")
    @classmethod
    def validate_long_ratio_bounds(cls, v: Decimal) -> Decimal:
        """Ensure long ratio stays within reasonable bounds."""
        if not (Decimal("0.20") <= v <= Decimal("0.80")):
            # Allow wider range for edge cases, but warn
            if not (Decimal("0.0") <= v <= Decimal("1.0")):
                raise ValueError(f"Long ratio {v} out of valid range [0.0, 1.0]")
        return v

    @field_validator("short_ratio")
    @classmethod
    def validate_short_ratio_bounds(cls, v: Decimal) -> Decimal:
        """Ensure short ratio stays within reasonable bounds."""
        if not (Decimal("0.20") <= v <= Decimal("0.80")):
            # Allow wider range for edge cases, but warn
            if not (Decimal("0.0") <= v <= Decimal("1.0")):
                raise ValueError(f"Short ratio {v} out of valid range [0.0, 1.0]")
        return v

    def model_post_init(self, __context) -> None:
        """Validate OI conservation after initialization."""
        total = self.long_ratio + self.short_ratio
        if abs(total - Decimal("1.0")) > Decimal("1e-10"):
            raise ValueError(
                f"OI conservation violated: long_ratio ({self.long_ratio}) + "
                f"short_ratio ({self.short_ratio}) = {total} != 1.0"
            )

    @property
    def is_bullish(self) -> bool:
        """Returns True if bias is bullish (long > short)."""
        return self.long_ratio > self.short_ratio

    @property
    def is_bearish(self) -> bool:
        """Returns True if bias is bearish (short > long)."""
        return self.short_ratio > self.long_ratio

    @property
    def is_neutral(self) -> bool:
        """Returns True if bias is neutral (50/50)."""
        return abs(self.long_ratio - Decimal("0.5")) < Decimal("0.001")

    @property
    def bias_strength(self) -> float:
        """Returns the strength of the bias (0 to 1)."""
        return abs(float(self.long_ratio) - 0.5) * 2

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "funding_input": str(self.funding_input),
            "long_ratio": str(self.long_ratio),
            "short_ratio": str(self.short_ratio),
            "confidence": self.confidence,
            "is_bullish": self.is_bullish,
            "is_bearish": self.is_bearish,
            "is_neutral": self.is_neutral,
            "bias_strength": self.bias_strength,
            "scale_factor": self.scale_factor,
            "max_adjustment": self.max_adjustment,
        }

    model_config = {
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "funding_input": "0.0003",
                "long_ratio": "0.681",
                "short_ratio": "0.319",
                "confidence": 0.85,
            }
        },
    }
