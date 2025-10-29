"""FastAPI application for liquidation heatmap API."""

from decimal import Decimal
from typing import Literal

from fastapi import FastAPI, Query
from pydantic import BaseModel

from ..models.binance_standard import BinanceStandardModel
from ..models.ensemble import EnsembleModel
from ..ingestion.db_service import DuckDBService

app = FastAPI(
    title="Liquidation Heatmap API",
    description="Calculate and visualize cryptocurrency liquidation levels",
    version="0.1.0",
)


class LiquidationResponse(BaseModel):
    """Response model for liquidations endpoint."""

    symbol: str
    model: str
    current_price: Decimal
    long_liquidations: list
    short_liquidations: list


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Status of the API
    """
    return {"status": "ok", "service": "liquidation-heatmap"}


@app.get("/liquidations/levels", response_model=LiquidationResponse)
async def get_liquidation_levels(
    symbol: str = Query("BTCUSDT", description="Trading pair symbol"),
    model: Literal["binance_standard", "ensemble"] = Query(
        "binance_standard", description="Liquidation model to use"
    ),
):
    """Calculate liquidation levels for given symbol and model.

    Returns liquidations BELOW current price (long positions) and
    ABOVE current price (short positions).

    Args:
        symbol: Trading pair (default: BTCUSDT)
        model: Model type (binance_standard or ensemble)

    Returns:
        LiquidationResponse with long and short liquidations
    """
    # Fetch real data from DuckDB
    with DuckDBService() as db:
        current_price, open_interest = db.get_latest_open_interest(symbol)
        funding_rate = db.get_latest_funding_rate(symbol)

    # Select model
    if model == "ensemble":
        liquidation_model = EnsembleModel()
    else:
        liquidation_model = BinanceStandardModel()

    # Calculate liquidations
    liquidations = liquidation_model.calculate_liquidations(
        current_price=current_price,
        open_interest=open_interest,
        symbol=symbol,
    )

    # Separate long (below price) and short (above price)
    long_liqs = [
        {
            "price_level": str(liq.price_level),
            "volume": str(liq.liquidation_volume),
            "leverage": liq.leverage_tier,
            "confidence": str(liq.confidence),
        }
        for liq in liquidations
        if liq.side == "long" and liq.price_level < current_price
    ]

    short_liqs = [
        {
            "price_level": str(liq.price_level),
            "volume": str(liq.liquidation_volume),
            "leverage": liq.leverage_tier,
            "confidence": str(liq.confidence),
        }
        for liq in liquidations
        if liq.side == "short" and liq.price_level > current_price
    ]

    return LiquidationResponse(
        symbol=symbol,
        model=model,
        current_price=current_price,
        long_liquidations=long_liqs,
        short_liquidations=short_liqs,
    )
