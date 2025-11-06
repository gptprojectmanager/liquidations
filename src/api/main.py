"""
FastAPI application for liquidation levels API.

Minimal implementation for MVP.
"""

from fastapi import FastAPI, Query

from src.models.liquidation import BinanceLiquidationModel

app = FastAPI(
    title="Liquidation Levels API",
    description="Calculate cryptocurrency liquidation levels for multiple leverages",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "liquidation-levels-api"}


@app.get("/liquidations/levels")
async def get_liquidation_levels(
    entry_price: float = Query(..., description="Entry or current price", gt=0),
    leverage_levels: str = Query(
        None, description="Comma-separated leverage values (e.g., '5,10,25')"
    ),
    maintenance_margin_rate: float = Query(
        0.004, description="Maintenance margin rate (default 0.4%)", ge=0, le=1
    ),
):
    """
    Calculate liquidation levels for multiple leverages.

    Args:
        entry_price: Current or entry price
        leverage_levels: Optional comma-separated leverage values (default: [5, 10, 25, 50, 100, 125])
        maintenance_margin_rate: Maintenance margin rate (default: 0.004 = 0.4%)

    Returns:
        JSON with long_liquidations and short_liquidations lists
    """
    # Parse leverage levels if provided
    if leverage_levels:
        leverages = [int(lev.strip()) for lev in leverage_levels.split(",")]
    else:
        leverages = None  # Will use default [5, 10, 25, 50, 100, 125]

    # Calculate liquidations
    model = BinanceLiquidationModel()
    result = model.calculate_liquidation_levels(
        entry_price=entry_price,
        leverage_levels=leverages,
        maintenance_margin_rate=maintenance_margin_rate,
    )

    return result
