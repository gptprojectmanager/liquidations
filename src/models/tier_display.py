"""
Display models for tier information.

Provides user-friendly data structures for presenting margin tier
information to retail traders in UI contexts.
"""

from typing import Optional

from pydantic import BaseModel, Field


class TierDisplay(BaseModel):
    """
    User-friendly tier display information.

    Contains formatted strings and metadata for displaying
    tier information in UI components.
    """

    # Current tier info
    tier_number: int = Field(..., description="Current margin tier (1-5)")
    margin_rate_percent: str = Field(..., description="Margin rate as percentage (e.g., '0.5%')")
    maintenance_amount: str = Field(
        ..., description="Maintenance amount (MA) as formatted currency"
    )
    maintenance_margin: str = Field(
        ..., description="Required maintenance margin as formatted currency"
    )

    # Position context
    current_position: str = Field(..., description="Current position size as formatted currency")
    tier_range: str = Field(..., description="Tier's valid range (e.g., '$0 - $50,000')")

    # Transition info
    next_tier_threshold: Optional[str] = Field(
        None, description="Notional value to reach next tier (None if already at max tier)"
    )
    distance_to_next_tier: Optional[str] = Field(
        None, description="How much more to reach next tier (None if at max tier)"
    )

    # Risk info
    max_leverage: str = Field(..., description="Maximum leverage for this tier (e.g., '200x')")

    # Educational content
    tooltip: Optional[str] = Field(None, description="Tooltip text explaining tier system")
    warning: Optional[str] = Field(
        None, description="Warning message if near tier boundary or other risk"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "tier_number": 1,
                "margin_rate_percent": "0.5%",
                "maintenance_amount": "$0",
                "maintenance_margin": "$250.00",
                "current_position": "$50,000.00",
                "tier_range": "$0 - $50,000",
                "next_tier_threshold": "$50,000.01",
                "distance_to_next_tier": "$0.01",
                "max_leverage": "200x",
                "tooltip": "Tier 1 applies to positions from $0 to $50,000...",
                "warning": None,
            }
        }
    }


class TierChangePreview(BaseModel):
    """
    Preview of tier change impact.

    Shows what happens when position size changes,
    especially when crossing tier boundaries.
    """

    # Tier transition
    old_tier: int = Field(..., description="Current tier number")
    new_tier: int = Field(..., description="New tier number after change")
    crosses_boundary: bool = Field(..., description="Whether this change crosses a tier boundary")
    tiers_crossed: int = Field(0, description="Number of tier boundaries crossed")
    boundary_crossed: Optional[str] = Field(
        None, description="The boundary value that was crossed (formatted currency)"
    )

    # Margin rate changes
    old_margin_rate: str = Field(..., description="Current margin rate as percentage")
    new_margin_rate: str = Field(..., description="New margin rate as percentage")

    # Margin impact
    margin_increase: str = Field(..., description="Margin increase as formatted currency")
    margin_increase_percent: str = Field(..., description="Margin increase as percentage")

    # Leverage impact
    old_max_leverage: str = Field(..., description="Current maximum leverage")
    new_max_leverage: str = Field(..., description="New maximum leverage")
    leverage_reduced: bool = Field(False, description="Whether max leverage was reduced")

    # Quality assessment
    is_improvement: bool = Field(
        False, description="Whether this change is beneficial (lower tier = better)"
    )
    warning_level: str = Field("info", description="Severity: 'info', 'warning', 'critical'")

    # User messaging
    message: str = Field(..., description="User-friendly explanation of change")

    # Liquidation impact (optional)
    old_liquidation_price: Optional[str] = Field(
        None, description="Old liquidation price (if provided)"
    )
    new_liquidation_price: Optional[str] = Field(
        None, description="New liquidation price (if provided)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "old_tier": 2,
                "new_tier": 3,
                "crosses_boundary": True,
                "tiers_crossed": 1,
                "boundary_crossed": "$250,000",
                "old_margin_rate": "1.0%",
                "new_margin_rate": "2.5%",
                "margin_increase": "$1,750.00",
                "margin_increase_percent": "100.0%",
                "old_max_leverage": "100x",
                "new_max_leverage": "40x",
                "leverage_reduced": True,
                "is_improvement": False,
                "warning_level": "warning",
                "message": "Position increased from Tier 2 to Tier 3. Margin requirement increased by $1,750 (100%).",
                "old_liquidation_price": None,
                "new_liquidation_price": None,
            }
        }
    }


class TierComparisonRow(BaseModel):
    """
    Single row in tier comparison table.

    Shows tier characteristics for comparison.
    """

    tier_number: int = Field(..., description="Tier number")
    notional_range: str = Field(..., description="Notional range (e.g., '$0 - $50,000')")
    margin_rate: str = Field(..., description="Margin rate as percentage")
    maintenance_amount: str = Field(..., description="Maintenance amount as formatted currency")
    max_leverage: str = Field(..., description="Maximum leverage")
    is_current: bool = Field(False, description="Whether this is the user's current tier")

    model_config = {
        "json_schema_extra": {
            "example": {
                "tier_number": 1,
                "notional_range": "$0 - $50,000",
                "margin_rate": "0.5%",
                "maintenance_amount": "$0",
                "max_leverage": "200x",
                "is_current": True,
            }
        }
    }


class TierComparisonTable(BaseModel):
    """
    Complete tier comparison table.

    Shows all tiers side-by-side for comparison.
    """

    symbol: str = Field(..., description="Trading pair symbol")
    current_position: str = Field(..., description="Current position size")
    current_tier: int = Field(..., description="Current tier number")
    tiers: list[TierComparisonRow] = Field(..., description="List of all tiers")

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "BTCUSDT",
                "current_position": "$50,000.00",
                "current_tier": 1,
                "tiers": [
                    {
                        "tier_number": 1,
                        "notional_range": "$0 - $50,000",
                        "margin_rate": "0.5%",
                        "maintenance_amount": "$0",
                        "max_leverage": "200x",
                        "is_current": True,
                    }
                ],
            }
        }
    }
