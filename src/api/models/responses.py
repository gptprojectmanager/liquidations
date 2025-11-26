"""
Response models for margin API.

Pydantic models for API responses.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from src.models.tier_display import TierComparisonTable, TierDisplay


class TierDetailsResponse(BaseModel):
    """Tier details in API response."""

    tier_number: int
    min_notional: str
    max_notional: str
    margin_rate: str
    maintenance_amount: str
    max_leverage: str


class CalculateMarginResponse(BaseModel):
    """Response model for margin calculation."""

    symbol: str = Field(..., description="Trading pair symbol")
    notional: str = Field(..., description="Position notional value")
    margin: str = Field(..., description="Required maintenance margin")
    tier: int = Field(..., description="Margin tier number")
    margin_rate: str = Field(..., description="Margin rate as percentage")
    maintenance_amount: str = Field(..., description="Maintenance amount (MA)")

    # Optional fields
    liquidation_price: Optional[str] = Field(None, description="Liquidation price if calculated")
    tier_details: Optional[TierDetailsResponse] = Field(None, description="Full tier information")
    display: Optional[TierDisplay] = Field(None, description="User-friendly display format")


class BatchCalculateResponse(BaseModel):
    """Response model for batch calculation."""

    results: List[CalculateMarginResponse] = Field(..., description="List of calculation results")
    total_count: int = Field(..., description="Total number of calculations")
    success_count: int = Field(..., description="Number of successful calculations")


class TierInfo(BaseModel):
    """Single tier information."""

    tier_number: int
    min_notional: str
    max_notional: str
    margin_rate: str
    maintenance_amount: str
    max_leverage: str


class TiersResponse(BaseModel):
    """Response model for tiers endpoint."""

    symbol: str = Field(..., description="Trading pair symbol")
    tiers: List[TierInfo] = Field(..., description="List of margin tiers")
    comparison_table: Optional[TierComparisonTable] = Field(
        None, description="Comparison table format"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
