"""FastAPI application for liquidation heatmap API."""

import json
import logging
import os
import time
from collections import defaultdict
from decimal import Decimal
from typing import Literal, Optional
from urllib.request import urlopen

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

# =============================================================================
# CACHING LAYER (T058-T060)
# =============================================================================


class HeatmapCache:
    """In-memory cache with TTL for heatmap timeseries responses.

    T058: Add in-memory cache layer with TTL to API endpoint
    T059: Implement cache-first query strategy
    T060: Add cache metrics logging for hit/miss ratio
    """

    def __init__(self, ttl_seconds: int = 300, max_size: int = 100):
        """Initialize cache.

        Args:
            ttl_seconds: Time-to-live for cache entries (default: 5 minutes)
            max_size: Maximum number of cache entries
        """
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: dict[str, tuple[float, any]] = {}  # key -> (expiry_time, value)
        self._hits = 0
        self._misses = 0

    def _make_key(
        self,
        symbol: str,
        start_time: Optional[str],
        end_time: Optional[str],
        interval: str,
        price_bin_size: float,
        leverage_weights: Optional[str],
    ) -> str:
        """Create cache key from request parameters."""
        return f"{symbol}:{start_time}:{end_time}:{interval}:{price_bin_size}:{leverage_weights}"

    def get(
        self,
        symbol: str,
        start_time: Optional[str],
        end_time: Optional[str],
        interval: str,
        price_bin_size: float,
        leverage_weights: Optional[str],
    ) -> Optional[any]:
        """Get cached response if exists and not expired."""
        key = self._make_key(
            symbol, start_time, end_time, interval, price_bin_size, leverage_weights
        )
        if key in self._cache:
            expiry, value = self._cache[key]
            if time.time() < expiry:
                self._hits += 1
                return value
            else:
                # Expired, remove from cache
                del self._cache[key]

        self._misses += 1
        return None

    def set(
        self,
        symbol: str,
        start_time: Optional[str],
        end_time: Optional[str],
        interval: str,
        price_bin_size: float,
        leverage_weights: Optional[str],
        value: any,
    ) -> None:
        """Store response in cache."""
        # Evict oldest entries if at max size
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]

        key = self._make_key(
            symbol, start_time, end_time, interval, price_bin_size, leverage_weights
        )
        expiry = time.time() + self.ttl_seconds
        self._cache[key] = (expiry, value)

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_requests": total,
            "hit_rate_percent": round(hit_rate, 2),
            "cached_entries": len(self._cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
        }

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0


# Global heatmap cache instance (TTL from env or default 5 minutes)
_heatmap_cache = HeatmapCache(
    ttl_seconds=int(os.getenv("LH_CACHE_TTL", "300")),
    max_size=int(os.getenv("LH_CACHE_MAX_SIZE", "100")),
)


# Simple rate limiter (in-memory, suitable for single-server deployments)
class SimpleRateLimiter:
    """Simple in-memory rate limiter using sliding window."""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.window_size = 60  # 1 minute
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, ip: str) -> tuple[bool, int]:
        """Check if request from IP is allowed. Returns (allowed, retry_after)."""
        now = time.time()
        cutoff = now - self.window_size

        # Clean old requests for this IP
        self.requests[ip] = [t for t in self.requests[ip] if t > cutoff]

        # Check limit
        if len(self.requests[ip]) >= self.requests_per_minute:
            oldest = min(self.requests[ip]) if self.requests[ip] else now
            retry_after = int(oldest + self.window_size - now) + 1
            return False, retry_after

        # Record request
        self.requests[ip].append(now)

        # Periodic cleanup: remove stale IPs to prevent memory leak
        # Only run cleanup every ~100 requests to avoid performance impact
        if len(self.requests) > 1000:
            stale_ips = [ip_key for ip_key, timestamps in self.requests.items() if not timestamps]
            for stale_ip in stale_ips:
                del self.requests[stale_ip]

        return True, 0


# Global rate limiter instance
_rate_limiter = SimpleRateLimiter(requests_per_minute=int(os.getenv("RATE_LIMIT_RPM", "120")))


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limiting."""

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting if disabled
        if os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "false":
            return await call_next(request)

        # Skip health endpoint
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        allowed, retry_after = _rate_limiter.is_allowed(client_ip)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        return response


def get_cors_origins() -> list[str]:
    """Get CORS allowed origins from environment.

    In production, set CORS_ALLOWED_ORIGINS to comma-separated list of origins.
    Example: CORS_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com

    Returns:
        List of allowed origins. Defaults to ["*"] for development.
    """
    origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if origins_env:
        return [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    # Development default - allow all origins
    return ["*"]


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from ..ingestion.db_service import DuckDBService
from ..models.binance_standard import BinanceStandardModel
from ..models.ensemble import EnsembleModel
from ..models.funding_adjusted import FundingAdjustedModel

# Supported trading pairs (whitelist)
SUPPORTED_SYMBOLS = {
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "XRPUSDT",
    "SOLUSDT",
    "DOTUSDT",
    "MATICUSDT",
    "LINKUSDT",
}

app = FastAPI(
    title="Liquidation Heatmap API",
    description="Calculate and visualize cryptocurrency liquidation levels",
    version="0.1.0",
)

# Rate limiting middleware (configurable via RATE_LIMIT_RPM and RATE_LIMIT_ENABLED env vars)
app.add_middleware(RateLimitMiddleware)

# CORS middleware (configurable via CORS_ALLOWED_ORIGINS env var)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
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


@app.get("/cache/stats")
async def get_cache_stats():
    """Get heatmap cache statistics (T060).

    Returns cache hit/miss ratio and other metrics for monitoring.

    Returns:
        dict: Cache statistics including hit rate
    """
    return _heatmap_cache.get_stats()


@app.delete("/cache/clear")
async def clear_cache():
    """Clear the heatmap cache.

    Useful for forcing recalculation after data updates.

    Returns:
        dict: Confirmation message
    """
    _heatmap_cache.clear()
    return {"message": "Cache cleared", "status": "ok"}


@app.get(
    "/liquidations/levels",
    response_model=LiquidationResponse,
    deprecated=True,
    description="**DEPRECATED**: Use `/liquidations/heatmap-timeseries` instead for "
    "time-evolving heatmap with correct position lifecycle modeling.",
)
async def get_liquidation_levels(
    response: Response,
    symbol: str = Query(
        ...,
        description="Trading pair symbol (e.g., BTCUSDT, ETHUSDT)",
        pattern="^[A-Z]{6,12}$",
        examples=["BTCUSDT"],
    ),
    model: str = Query(
        "openinterest",
        description="Calculation model (reserved for future extensions, currently only 'openinterest' supported)",
    ),
    timeframe: int = Query(
        ..., ge=1, le=365, description="Timeframe in days (1-365)", examples=[30]
    ),
    whale_threshold: float = Query(
        500000.0,
        description="Minimum trade size in USD (CURRENTLY FIXED AT $500K - parameter non-functional due to pre-aggregated cache limitation)",
        ge=0.0,
    ),
):
    """Calculate liquidation levels using Open Interest distribution model.

    **DEPRECATED**: This endpoint uses static liquidation levels that do not
    account for position consumption when price crosses them. Use the
    `/liquidations/heatmap-timeseries` endpoint instead for accurate
    time-evolving heatmap data.

    Returns liquidations BELOW current price (long positions) and
    ABOVE current price (short positions).

    The OI-based model distributes current Open Interest across historical
    volume profile, providing more realistic liquidation estimates than
    legacy trade-counting approaches.

    Args:
        symbol: Trading pair (default: BTCUSDT)
        model: Calculation model (currently only 'openinterest')
        timeframe: Lookback period in days (1, 7, 30, or 90)
        whale_threshold: Minimum position size filter

    Returns:
        LiquidationResponse with long and short liquidations
    """
    # Add deprecation warning header
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2025-06-01"
    response.headers["Link"] = '</liquidations/heatmap-timeseries>; rel="successor-version"'
    # Validate symbol against whitelist
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid symbol '{symbol}'. Supported symbols: {sorted(SUPPORTED_SYMBOLS)}",
        )

    # Get real-time current price from Binance API

    try:
        with urlopen(
            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5
        ) as resp:
            data = json.loads(resp.read().decode())
            current_price = float(data["price"])
    except Exception as e:
        # Fallback to historical price if API fails
        logging.warning(f"Binance API price fetch failed for {symbol}: {e}")
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

    # Calculate liquidations using OI-based model
    with DuckDBService() as db:
        # OI-based model: distributes current Open Interest based on volume profile
        bins_df = db.calculate_liquidations_oi_based(
            symbol=symbol,
            current_price=current_price,
            bin_size=bin_size,
            lookback_days=timeframe,
            whale_threshold=whale_threshold,
        )

        # Bin liquidation prices and aggregate
        if not bins_df.empty and "liq_price" in bins_df.columns:
            # CRITICAL: Use liq_price (actual liquidation levels), not price_bucket (entry prices)
            bins_df["liq_price_binned"] = (
                np.round(bins_df["liq_price"] / bin_size) * bin_size
            ).astype(int)

            # Aggregate by binned liquidation price, leverage, and side
            bins_df = (
                bins_df.groupby(["liq_price_binned", "leverage", "side"])
                .agg({"volume": "sum"})
                .reset_index()
            )
            bins_df["count"] = 1  # Placeholder count
            bins_df.rename(
                columns={"volume": "total_volume", "liq_price_binned": "price_bucket"},
                inplace=True,
            )

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
    symbol: str = Query(
        ...,
        description="Trading pair symbol (e.g., BTCUSDT, ETHUSDT)",
        pattern="^[A-Z]{6,12}$",
        examples=["BTCUSDT"],
    ),
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
    # Validate symbol against whitelist
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid symbol '{symbol}'. Supported symbols: {sorted(SUPPORTED_SYMBOLS)}",
        )

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
        # Check if liquidation_history table exists
        table_check = db.conn.execute("""
            SELECT COUNT(*) as count
            FROM information_schema.tables
            WHERE table_name = 'liquidation_history'
        """).fetchone()

        # If table doesn't exist, return empty list
        if table_check[0] == 0:
            return []

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
        _ = db.get_latest_funding_rate(symbol)  # Reserved for future use

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


@app.get("/prices/klines")
async def get_klines(
    symbol: str = Query(
        "BTCUSDT",
        description="Trading pair symbol",
        pattern="^[A-Z]{6,12}$",
    ),
    interval: Literal["5m", "15m"] = Query("15m", description="Kline interval"),
    limit: int = Query(100, ge=10, le=500, description="Number of klines to return"),
):
    """Get OHLC price data for visualization overlay.

    Returns candlestick/kline data from DuckDB for the specified symbol and interval.
    Used to overlay price action on the liquidation heatmap.

    Args:
        symbol: Trading pair (e.g., BTCUSDT)
        interval: Kline interval (5m or 15m)
        limit: Number of klines to return (10-500)

    Returns:
        List of OHLC data points with timestamp, open, high, low, close, volume
    """
    # Validate symbol
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid symbol '{symbol}'. Supported: {sorted(SUPPORTED_SYMBOLS)}",
        )

    db = DuckDBService()

    try:
        table_name = f"klines_{interval}_history"

        query = f"""
        SELECT
            open_time as timestamp,
            CAST(open AS DOUBLE) as open,
            CAST(high AS DOUBLE) as high,
            CAST(low AS DOUBLE) as low,
            CAST(close AS DOUBLE) as close,
            CAST(volume AS DOUBLE) as volume
        FROM {table_name}
        WHERE symbol = ?
        ORDER BY open_time DESC
        LIMIT ?
        """

        df = db.conn.execute(query, [symbol, limit]).df()

        if df.empty:
            return {"symbol": symbol, "interval": interval, "data": []}

        # Sort ascending for chart display
        df = df.sort_values("timestamp")

        klines = [
            {
                "timestamp": row["timestamp"].isoformat(),
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
            }
            for _, row in df.iterrows()
        ]

        return {
            "symbol": symbol,
            "interval": interval,
            "count": len(klines),
            "data": klines,
        }

    except Exception as e:
        logger.error(f"Error fetching klines: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    finally:
        db.close()


# =============================================================================
# TIME-EVOLVING HEATMAP ENDPOINT (Feature 008)
# =============================================================================


class HeatmapLevel(BaseModel):
    """Single price level in heatmap snapshot."""

    price: float
    long_density: float
    short_density: float


class HeatmapSnapshotResponse(BaseModel):
    """Heatmap state at a single timestamp."""

    timestamp: str
    levels: list[HeatmapLevel]
    positions_created: int
    positions_consumed: int


class HeatmapTimeseriesMetadata(BaseModel):
    """Metadata for heatmap timeseries response."""

    symbol: str
    start_time: str
    end_time: str
    interval: str
    total_snapshots: int
    price_range: dict
    total_long_volume: float
    total_short_volume: float
    total_consumed: int


class HeatmapTimeseriesResponse(BaseModel):
    """Response model for time-evolving heatmap endpoint."""

    data: list[HeatmapSnapshotResponse]
    meta: HeatmapTimeseriesMetadata


class LeverageWeightsParseError(ValueError):
    """Raised when leverage_weights query param is invalid."""

    pass


# Valid leverage tiers (must match LiquidationLevel validation)
VALID_LEVERAGE_TIERS = {5, 10, 25, 50, 100}


def parse_leverage_weights(weights_str: str | None) -> list[tuple[int, Decimal]] | None:
    """Parse leverage weights from query string.

    Format: "5:15,10:30,25:25,50:20,100:10"

    Args:
        weights_str: Query string in format "leverage:weight,..."

    Returns:
        List of (leverage, weight) tuples, or None for defaults

    Raises:
        LeverageWeightsParseError: If the format is invalid or leverage values
            are not in valid tiers (5, 10, 25, 50, 100)
    """
    if not weights_str:
        return None

    try:
        weights = []
        total = Decimal("0")
        for pair in weights_str.split(","):
            parts = pair.split(":")
            if len(parts) != 2:
                raise LeverageWeightsParseError(
                    f"Invalid format: '{pair}'. Expected 'leverage:weight'"
                )
            leverage_str, weight_str = parts
            leverage = int(leverage_str)
            weight = Decimal(weight_str)

            # Validate leverage is a valid tier
            if leverage not in VALID_LEVERAGE_TIERS:
                raise LeverageWeightsParseError(
                    f"Invalid leverage '{leverage}'. Must be one of: {sorted(VALID_LEVERAGE_TIERS)}"
                )

            # Validate weight is non-negative
            if weight < 0:
                raise LeverageWeightsParseError(
                    f"Invalid weight '{weight}' for leverage {leverage}. Weights must be non-negative."
                )

            weights.append((leverage, weight))
            total += weight

        # Normalize weights to sum to 1.0
        if total > 0:
            weights = [(lev, w / total) for lev, w in weights]
        elif weights:
            # All zero weights - invalid
            raise LeverageWeightsParseError("All weights are zero. At least one must be positive.")

        return weights
    except LeverageWeightsParseError:
        raise
    except Exception as e:
        raise LeverageWeightsParseError(f"Invalid leverage_weights: {weights_str} - {e}")


@app.get("/liquidations/heatmap-timeseries", response_model=HeatmapTimeseriesResponse)
async def get_heatmap_timeseries(
    symbol: str = Query(
        ...,
        description="Trading pair symbol (e.g., BTCUSDT)",
        pattern="^[A-Z]{6,12}$",
        examples=["BTCUSDT"],
    ),
    start_time: Optional[str] = Query(
        None,
        description="Start of time range (ISO 8601). Defaults to 7 days ago.",
    ),
    end_time: Optional[str] = Query(
        None,
        description="End of time range (ISO 8601). Defaults to now.",
    ),
    interval: Literal["5m", "15m", "1h", "4h"] = Query(
        "15m",
        description="Time interval for snapshots",
    ),
    price_bin_size: float = Query(
        100,
        ge=1,
        le=1000,
        description="Price bucket size in USD",
    ),
    leverage_weights: Optional[str] = Query(
        None,
        description="Custom leverage weights: '5:15,10:30,25:25,50:20,100:10'",
    ),
):
    """Get time-evolving liquidation heatmap.

    Returns a time series of liquidation density snapshots where liquidation
    levels are consumed when price crosses them. This is the new implementation
    that correctly models position lifecycle.

    **DEPRECATION NOTICE**: The `/liquidations/levels` endpoint is deprecated.
    Use this endpoint for accurate time-varying heatmap data.

    **CACHING**: Responses are cached for 5 minutes (configurable via LH_CACHE_TTL).
    Use GET /cache/stats to monitor cache performance.

    Args:
        symbol: Trading pair (e.g., BTCUSDT)
        start_time: Start of time range (ISO 8601, defaults to 7 days ago)
        end_time: End of time range (ISO 8601, defaults to now)
        interval: Time interval for snapshots (5m, 15m, 1h, 4h)
        price_bin_size: Price bucket size in USD for aggregation
        leverage_weights: Custom leverage distribution weights

    Returns:
        HeatmapTimeseriesResponse with snapshots and metadata
    """
    from dataclasses import dataclass
    from datetime import datetime, timedelta

    from ..models.time_evolving_heatmap import calculate_time_evolving_heatmap

    # T059: Check cache first (cache-first query strategy)
    cached_response = _heatmap_cache.get(
        symbol, start_time, end_time, interval, price_bin_size, leverage_weights
    )
    if cached_response is not None:
        logger.debug(f"Cache HIT for {symbol} heatmap-timeseries")
        return cached_response

    logger.debug(f"Cache MISS for {symbol} heatmap-timeseries - computing...")

    # Validate symbol against whitelist
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid symbol '{symbol}'. Supported: {sorted(SUPPORTED_SYMBOLS)}",
        )

    # Parse time range
    try:
        if end_time:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00")).replace(tzinfo=None)
        else:
            end_dt = datetime.now()

        if start_time:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        else:
            start_dt = end_dt - timedelta(days=7)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid time format: {e}")

    # Parse leverage weights
    try:
        weights = parse_leverage_weights(leverage_weights)
    except LeverageWeightsParseError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Determine kline table based on interval
    interval_table_map = {
        "5m": "klines_5m_history",
        "15m": "klines_15m_history",
        "1h": "klines_5m_history",  # Aggregate from 5m
        "4h": "klines_5m_history",  # Aggregate from 5m
    }
    kline_table = interval_table_map.get(interval, "klines_15m_history")

    # Mock candle class for algorithm
    @dataclass
    class Candle:
        open_time: datetime
        open: Decimal
        high: Decimal
        low: Decimal
        close: Decimal
        volume: Decimal

    db = DuckDBService()

    try:
        # Query candles
        candle_query = f"""
        SELECT
            open_time,
            CAST(open AS DECIMAL(18,8)) as open,
            CAST(high AS DECIMAL(18,8)) as high,
            CAST(low AS DECIMAL(18,8)) as low,
            CAST(close AS DECIMAL(18,8)) as close,
            CAST(volume AS DECIMAL(18,8)) as volume
        FROM {kline_table}
        WHERE symbol = ? AND open_time >= ? AND open_time <= ?
        ORDER BY open_time
        """

        candles_df = db.conn.execute(candle_query, [symbol, start_dt, end_dt]).df()

        if candles_df.empty:
            return HeatmapTimeseriesResponse(
                data=[],
                meta=HeatmapTimeseriesMetadata(
                    symbol=symbol,
                    start_time=start_dt.isoformat(),
                    end_time=end_dt.isoformat(),
                    interval=interval,
                    total_snapshots=0,
                    price_range={"min": 0, "max": 0},
                    total_long_volume=0.0,
                    total_short_volume=0.0,
                    total_consumed=0,
                ),
            )

        # Query OI data with delta calculation
        oi_query = """
        SELECT
            timestamp,
            open_interest_value,
            open_interest_value - LAG(open_interest_value) OVER (ORDER BY timestamp) as oi_delta
        FROM open_interest_history
        WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp
        """

        oi_df = db.conn.execute(oi_query, [symbol, start_dt, end_dt]).df()

        # Convert to candle objects
        candles = [
            Candle(
                open_time=row["open_time"].to_pydatetime()
                if hasattr(row["open_time"], "to_pydatetime")
                else row["open_time"],
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=Decimal(str(row["volume"])),
            )
            for _, row in candles_df.iterrows()
        ]

        # Match OI deltas to candles (approximate by nearest timestamp)
        oi_deltas = []
        oi_timestamps = oi_df["timestamp"].tolist() if not oi_df.empty else []
        oi_values = oi_df["oi_delta"].fillna(0).tolist() if not oi_df.empty else []

        for candle in candles:
            # Find closest OI data point within 15-min window
            delta = Decimal("0")
            min_diff = float("inf")
            if oi_timestamps:
                for i, oi_ts in enumerate(oi_timestamps):
                    oi_ts_dt = oi_ts.to_pydatetime() if hasattr(oi_ts, "to_pydatetime") else oi_ts
                    diff = abs((candle.open_time - oi_ts_dt).total_seconds())
                    if diff < 900 and diff < min_diff:  # 15 min window, closest match
                        min_diff = diff
                        delta = Decimal(str(oi_values[i])) if oi_values[i] else Decimal("0")
            oi_deltas.append(delta)

        # Calculate time-evolving heatmap
        snapshots = calculate_time_evolving_heatmap(
            candles=candles,
            oi_deltas=oi_deltas,
            symbol=symbol,
            leverage_weights=weights,
            price_bucket_size=Decimal(str(price_bin_size)),
        )

        # Convert to response format
        response_data = []
        total_consumed = 0
        total_long = 0.0
        total_short = 0.0
        all_prices = []

        for snapshot in snapshots:
            levels = []
            for cell in snapshot.cells.values():
                if cell.total_density > 0:
                    levels.append(
                        HeatmapLevel(
                            price=float(cell.price_bucket),
                            long_density=float(cell.long_density),
                            short_density=float(cell.short_density),
                        )
                    )
                    all_prices.append(float(cell.price_bucket))

            response_data.append(
                HeatmapSnapshotResponse(
                    timestamp=snapshot.timestamp.isoformat(),
                    levels=sorted(levels, key=lambda x: x.price),
                    positions_created=snapshot.positions_created,
                    positions_consumed=snapshot.positions_consumed,
                )
            )

            total_consumed += snapshot.positions_consumed
            total_long += float(snapshot.total_long_volume)
            total_short += float(snapshot.total_short_volume)

        price_range = {
            "min": min(all_prices) if all_prices else 0,
            "max": max(all_prices) if all_prices else 0,
        }

        response = HeatmapTimeseriesResponse(
            data=response_data,
            meta=HeatmapTimeseriesMetadata(
                symbol=symbol,
                start_time=start_dt.isoformat(),
                end_time=end_dt.isoformat(),
                interval=interval,
                total_snapshots=len(snapshots),
                price_range=price_range,
                total_long_volume=total_long,
                total_short_volume=total_short,
                total_consumed=total_consumed,
            ),
        )

        # T059: Cache the response for future requests
        _heatmap_cache.set(
            symbol, start_time, end_time, interval, price_bin_size, leverage_weights, response
        )
        logger.debug(f"Cached response for {symbol} heatmap-timeseries")

        return response

    except Exception as e:
        logger.error(f"Error calculating heatmap timeseries: {e}")
        raise HTTPException(status_code=500, detail=f"Calculation error: {e}")

    finally:
        db.close()
