"""FastAPI application for liquidation heatmap API."""

import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from decimal import Decimal
from typing import Literal, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..ingestion.db_service import DuckDBService
from ..models.binance_standard import BinanceStandardModel
from ..models.ensemble import EnsembleModel
from ..models.funding_adjusted import FundingAdjustedModel

app = FastAPI(
    title="Liquidation Heatmap API",
    description="Calculate and visualize cryptocurrency liquidation levels",
    version="0.1.0",
)

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for frontend dashboards
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


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
    model: Literal["aggtrades", "openinterest"] = Query(
        "openinterest",
        description="Calculation model: aggtrades (legacy) or openinterest (OI-based, recommended)",
    ),
    timeframe: int = Query(30, description="Timeframe in days"),
    whale_threshold: float = Query(
        500000.0,
        description="Minimum trade size in USD (CURRENTLY FIXED AT $500K - parameter non-functional due to pre-aggregated cache limitation)",
        ge=0.0,
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
    # Get real-time current price from Binance API
    import json
    from datetime import datetime, timedelta
    from urllib.request import urlopen

    try:
        with urlopen(
            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5
        ) as resp:
            data = json.loads(resp.read().decode())
            current_price = float(data["price"])
    except:
        # Fallback to historical price if API fails
        with DuckDBService() as db_fallback:
            price_decimal, _ = db_fallback.get_latest_open_interest(symbol)
            current_price = float(price_decimal)

    # Dynamic bin size based on timeframe (Coinglass approach)
    if timeframe <= 7:
        bin_size = 200.0  # 7d: High granularity
    elif timeframe <= 30:
        bin_size = 500.0  # 30d: Medium granularity
    else:  # 90 days
        bin_size = 1500.0  # 90d: Low granularity

    # Choose calculation model
    with DuckDBService() as db:
        if model == "openinterest":
            # OI-based model: distributes current Open Interest based on volume profile
            # This is the RECOMMENDED model - more realistic than aggTrades
            bins_df = db.calculate_liquidations_oi_based(
                symbol=symbol,
                current_price=current_price,
                bin_size=bin_size,
                lookback_days=timeframe,  # Use API timeframe parameter
                whale_threshold=whale_threshold,  # Configurable threshold (requires cache rebuild)
            )

            # Rename columns to match expected format
            if not bins_df.empty and "liq_price" in bins_df.columns:
                # OI model returns liq_price - bin it and aggregate
                # CRITICAL FIX: Use liq_price (actual liquidation levels), not price_bucket (entry prices)!
                import numpy as np

                # Bin liquidation prices to bin_size intervals
                bins_df["liq_price_binned"] = (
                    np.round(bins_df["liq_price"] / bin_size) * bin_size
                ).astype(int)

                # Aggregate by binned liquidation price, leverage, and side
                bins_df = (
                    bins_df.groupby(["liq_price_binned", "leverage", "side"])
                    .agg(
                        {
                            "volume": "sum",
                        }
                    )
                    .reset_index()
                )
                bins_df["count"] = 1  # Placeholder count
                bins_df.rename(
                    columns={"volume": "total_volume", "liq_price_binned": "price_bucket"},
                    inplace=True,
                )
        else:  # model == "aggtrades"
            # Legacy aggTrades-based model (kept for comparison)
            # NOTE: This model counts ALL trades (opens + closes), inflating volumes ~17x
            end_time = datetime.now().isoformat()
            start_time = (datetime.now() - timedelta(days=timeframe)).isoformat()

            bins_df = db.calculate_liquidations_sql(
                symbol=symbol,
                current_price=current_price,
                bin_size=bin_size,
                min_gross_value=500000.0,  # $500k whale trades
                start_datetime=start_time,
                end_datetime=end_time,
            )

    logger = logging.getLogger(__name__)
    logger.info(f"SQL returned {len(bins_df)} aggregated bins")

    # Convert DataFrame to API response format
    long_liqs = []
    short_liqs = []

    for _, row in bins_df.iterrows():
        liq_entry = {
            "price_level": str(row["price_bucket"]),
            "volume": str(row["total_volume"]),
            "count": int(row["count"]),
            "leverage": f"{int(row['leverage'])}x",
        }

        if row["side"] == "buy":  # Long positions
            long_liqs.append(liq_entry)
        else:  # Short positions
            short_liqs.append(liq_entry)

    # Sort: longs descending (high to low), shorts ascending (low to high)
    long_liqs = sorted(long_liqs, key=lambda x: float(x["price_level"]), reverse=True)
    short_liqs = sorted(short_liqs, key=lambda x: float(x["price_level"]))

    logger.info(f"Formatted response: {len(long_liqs)} long, {len(short_liqs)} short")

    return LiquidationResponse(
        symbol=symbol,
        model=model,
        current_price=str(current_price),
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
    start: Optional[str] = Query(None, description="Start datetime (ISO format)"),
    end: Optional[str] = Query(None, description="End datetime (ISO format)"),
    aggregate: bool = Query(False, description="Aggregate by timestamp and side"),
):
    """Get historical liquidation data from database (T047).

    Query actual liquidation events stored in liquidation_history table.
    Supports date filtering and aggregation for time-series analysis.

    Args:
        symbol: Trading pair (e.g., BTCUSDT)
        start: Optional start datetime filter
        end: Optional end datetime filter
        aggregate: If true, group by timestamp and side with totals

    Returns:
        List of historical liquidation records or aggregated data
    """
    db = DuckDBService()

    try:
        if aggregate:
            # Aggregated query for time-series visualization
            query = """
            SELECT
                timestamp,
                side,
                SUM(quantity) as total_volume,
                COUNT(*) as num_levels,
                AVG(price) as avg_price
            FROM liquidation_history
            WHERE symbol = ?
            """

            params = [symbol]

            if start:
                query += " AND timestamp >= ?"
                params.append(start)

            if end:
                query += " AND timestamp <= ?"
                params.append(end)

            query += " GROUP BY timestamp, side ORDER BY timestamp, side"

            df = db.conn.execute(query, params).df()

            return [
                {
                    "timestamp": str(rec["timestamp"]),
                    "side": rec["side"],
                    "total_volume": float(rec["total_volume"]),
                    "num_levels": int(rec["num_levels"]),
                    "avg_price": float(rec["avg_price"]),
                }
                for rec in df.to_dict(orient="records")
            ]

        else:
            # Raw historical records
            query = """
            SELECT timestamp, symbol, price, quantity, side, leverage, model
            FROM liquidation_history
            WHERE symbol = ?
            """

            params = [symbol]

            if start:
                query += " AND timestamp >= ?"
                params.append(start)

            if end:
                query += " AND timestamp <= ?"
                params.append(end)

            query += " ORDER BY timestamp DESC, side, leverage"

            df = db.conn.execute(query, params).df()

            return [
                {
                    "timestamp": str(rec["timestamp"]),
                    "symbol": rec["symbol"],
                    "price": float(rec["price"]),
                    "quantity": float(rec["quantity"]),
                    "side": rec["side"],
                    "leverage": int(rec["leverage"]),
                    "model": rec["model"],
                }
                for rec in df.to_dict(orient="records")
            ]

    finally:
        db.close()


@app.get("/liquidations/compare-models")
async def compare_models(
    symbol: str = Query("BTCUSDT", description="Trading pair symbol"),
):
    """Compare predictions from all models (T036).

    Returns predictions from binance_standard, funding_adjusted, and ensemble models.
    """
    # Fetch data from DuckDB
    with DuckDBService() as db:
        current_price, open_interest = db.get_latest_open_interest(symbol)
        funding_rate = db.get_latest_funding_rate(symbol)

    # Initialize all 3 models
    binance_model = BinanceStandardModel()
    funding_model = FundingAdjustedModel()
    ensemble_model = EnsembleModel()

    models_data = []

    # Run each model and collect results
    for model in [binance_model, funding_model, ensemble_model]:
        liquidations = model.calculate_liquidations(
            current_price=current_price,
            open_interest=open_interest,
            symbol=symbol,
        )

        # Calculate average confidence
        if liquidations:
            avg_conf = sum(liq.confidence for liq in liquidations) / len(liquidations)
        else:
            avg_conf = Decimal("0")

        # Format levels for response
        levels = [
            {
                "price_level": str(liq.price_level),
                "volume": str(liq.liquidation_volume),
                "leverage": liq.leverage_tier,
                "confidence": str(liq.confidence),
                "side": liq.side,
            }
            for liq in liquidations
        ]

        models_data.append(
            {
                "name": model.model_name,
                "levels": levels,
                "avg_confidence": avg_conf,
            }
        )

    # Calculate agreement percentage (simplified)
    # Check if models agree within 5% on average liquidation prices
    if len(models_data) >= 2:
        # Get average liquidation prices from each model
        avg_prices = []
        for model_data in models_data:
            if model_data["levels"]:
                prices = [Decimal(level["price_level"]) for level in model_data["levels"]]
                avg_prices.append(sum(prices) / len(prices))

        if len(avg_prices) >= 2:
            # Calculate coefficient of variation
            mean_price = sum(avg_prices) / len(avg_prices)
            if mean_price > 0:
                std_dev = (
                    sum((p - mean_price) ** 2 for p in avg_prices) / len(avg_prices)
                ) ** Decimal("0.5")
                cv = (std_dev / mean_price) * 100
                # Agreement is high when CV is low
                agreement = max(Decimal("0"), 100 - (cv * 20))  # Scale CV to 0-100
            else:
                agreement = Decimal("0")
        else:
            agreement = Decimal("100")
    else:
        agreement = Decimal("100")

    return {
        "symbol": symbol,
        "current_price": current_price,
        "models": models_data,
        "agreement_percentage": agreement,
    }
