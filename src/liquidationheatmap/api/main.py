"""FastAPI application for liquidation heatmap API."""

from decimal import Decimal
from typing import Literal

from fastapi import FastAPI, Query
from pydantic import BaseModel

from ..ingestion.db_service import DuckDBService
from ..models.binance_standard import BinanceStandardModel
from ..models.ensemble import EnsembleModel

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


@app.get("/liquidations/heatmap")
async def get_heatmap(
    symbol: str = Query("BTCUSDT", description="Trading pair symbol"),
    model: Literal["binance_standard", "ensemble"] = Query(
        "ensemble", description="Liquidation model to use"
    ),
    timeframe: str = Query("1d", description="Time bucket size", pattern="^(1h|4h|12h|1d|7d|30d)$"),
):
    """Get pre-aggregated heatmap data for visualization.

    Returns heatmap buckets with density (count) and volume for each
    time+price bucket combination.

    Args:
        symbol: Trading pair (e.g., BTCUSDT)
        model: Liquidation model (binance_standard or ensemble)
        timeframe: Time bucket size (1h, 4h, 12h, 1d, 7d, 30d)

    Returns:
        HeatmapResponse with data points and metadata
    """
    from .heatmap_models import HeatmapDataPoint, HeatmapMetadata, HeatmapResponse

    # Connect to database
    db = DuckDBService()

    try:
        # Query heatmap cache
        query = """
        SELECT 
            time_bucket,
            price_bucket,
            density,
            volume
        FROM heatmap_cache
        WHERE symbol = ? AND model = ?
        ORDER BY time_bucket, price_bucket
        """

        df = db.conn.execute(query, [symbol, model]).df()

        if df.empty:
            # Return empty response if no data
            return HeatmapResponse(
                symbol=symbol,
                model=model,
                timeframe=timeframe,
                current_price=None,
                data=[],
                metadata=HeatmapMetadata(
                    total_volume=0.0,
                    highest_density_price=0.0,
                    num_buckets=0,
                    data_quality_score=0.0,
                    time_range_hours=0.0,
                ),
            )

        # Convert to HeatmapDataPoint objects
        data_points = [
            HeatmapDataPoint(
                time=row["time_bucket"],
                price_bucket=float(row["price_bucket"]),
                density=int(row["density"]),
                volume=float(row["volume"]),
            )
            for _, row in df.iterrows()
        ]

        # Calculate metadata
        total_volume = float(df["volume"].sum())
        highest_density_idx = df["density"].idxmax()
        highest_density_price = float(df.loc[highest_density_idx, "price_bucket"])
        num_buckets = len(df)

        # Calculate time range
        time_range = df["time_bucket"].max() - df["time_bucket"].min()
        time_range_hours = time_range.total_seconds() / 3600 if time_range else 0.0

        # Simple data quality score (1.0 = complete, lower = gaps)
        # Could be enhanced with gap detection
        data_quality_score = min(1.0, num_buckets / max(1, time_range_hours))

        # Get current price (from latest Open Interest data)
        current_price_query = """
        SELECT open_interest_value / open_interest_contracts AS price
        FROM open_interest_history
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """
        current_price_result = db.conn.execute(current_price_query, [symbol]).fetchone()
        current_price = float(current_price_result[0]) if current_price_result else None

        metadata = HeatmapMetadata(
            total_volume=total_volume,
            highest_density_price=highest_density_price,
            num_buckets=num_buckets,
            data_quality_score=data_quality_score,
            time_range_hours=time_range_hours,
        )

        return HeatmapResponse(
            symbol=symbol,
            model=model,
            timeframe=timeframe,
            current_price=current_price,
            data=data_points,
            metadata=metadata,
        )

    finally:
        db.close()


@app.get("/liquidations/history")
async def get_liquidation_history(
    symbol: str = Query("BTCUSDT", description="Trading pair symbol"),
):
    """Get historical liquidation data from database (T047)."""
    return []
