"""
Request models for margin API.

Pydantic models for validating API requests.
"""

from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class CalculateMarginRequest(BaseModel):
    """Request model for margin calculation."""

    symbol: str = Field(..., description="Trading pair symbol (e.g., BTCUSDT)")

    # Option 1: Direct notional
    notional: Optional[str] = Field(None, description="Position notional value (USD)")

    # Option 2: Calculate from entry/size
    entry_price: Optional[str] = Field(None, description="Entry price")
    position_size: Optional[str] = Field(None, description="Position size (coins)")
    leverage: Optional[str] = Field(None, description="Leverage (e.g., '10')")
    side: Optional[Literal["long", "short"]] = Field(None, description="Position side")

    # Optional flags
    include_tier_details: bool = Field(False, description="Include full tier information")
    include_display: bool = Field(False, description="Include formatted display strings")

    @field_validator("notional", "entry_price", "position_size", "leverage")
    @classmethod
    def validate_decimal_fields(cls, v):
        """Validate decimal string fields are valid Decimals."""
        if v is not None:
            try:
                Decimal(v)  # Just validate it's a valid decimal, don't check negative here
            except Exception:
                raise ValueError(f"Invalid decimal value: {v}")
        return v

    @model_validator(mode="after")
    def validate_required_fields(self):
        """Validate that either notional OR (entry_price + position_size) is provided."""
        if not self.notional and not (self.entry_price and self.position_size):
            raise ValueError(
                "Must provide either 'notional' or both 'entry_price' and 'position_size'"
            )
        return self

    def get_notional(self) -> Decimal:
        """Calculate notional value from request."""
        if self.notional:
            return Decimal(self.notional)
        elif self.entry_price and self.position_size:
            return Decimal(self.entry_price) * Decimal(self.position_size)
        else:
            # This should never happen due to model_validator, but keep for safety
            raise ValueError("Must provide either 'notional' or 'entry_price' + 'position_size'")


class BatchCalculateRequest(BaseModel):
    """Request model for batch margin calculation."""

    calculations: List[CalculateMarginRequest] = Field(
        ..., description="List of margin calculations to perform"
    )


class GetTiersRequest(BaseModel):
    """Query parameters for get tiers endpoint."""

    format: Optional[Literal["simple", "comparison"]] = Field(
        "simple", description="Response format"
    )
    current_notional: Optional[str] = Field(
        None, description="Current position size for highlighting"
    )
