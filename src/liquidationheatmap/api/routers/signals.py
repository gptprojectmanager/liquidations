"""Signal status and metrics endpoints.

User Story 4: API Integration for signal monitoring.
"""

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Query

from src.liquidationheatmap.signals import (
    FeedbackDBService,
    SignalMetrics,
    SignalStatus,
    get_redis_client,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])

# Cached last publish timestamp (in-memory)
_last_publish_timestamp: datetime | None = None


def set_last_publish(timestamp: datetime) -> None:
    """Update last publish timestamp (called by SignalPublisher)."""
    global _last_publish_timestamp
    _last_publish_timestamp = timestamp


@router.get("/status", response_model=SignalStatus)
async def get_signal_status():
    """Get signal system status.

    Returns connection state, last publish time, and 24h counts.

    Returns:
        SignalStatus with connected, last_publish, signals_published_24h, feedback_received_24h
    """
    # Check Redis connection
    redis_client = get_redis_client()
    connected = redis_client.is_connected

    # Get feedback count from DuckDB
    feedback_24h = 0
    db_service = None
    try:
        db_service = FeedbackDBService()
        metrics = db_service.get_rolling_metrics("BTCUSDT", hours=24)
        feedback_24h = metrics.get("total", 0)
    except Exception as e:
        logger.warning(f"Could not fetch feedback metrics: {e}")
    finally:
        if db_service is not None:
            db_service.close()

    # Signals published (using cached timestamp, actual count would need Redis MONITOR)
    # This is a simplified implementation - in production, track via metrics
    signals_24h = 0
    if _last_publish_timestamp:
        # Estimate: 96 signals/day = 4 per hour (15min interval)
        # Use max(0, ...) to handle edge case where timestamp is in future (clock skew)
        hours_active = max(
            0,
            min(24, (datetime.now(timezone.utc) - _last_publish_timestamp).total_seconds() / 3600),
        )
        signals_24h = int(hours_active * 4)

    return SignalStatus(
        connected=connected,
        last_publish=_last_publish_timestamp,
        signals_published_24h=signals_24h,
        feedback_received_24h=feedback_24h,
    )


@router.get("/metrics", response_model=SignalMetrics)
async def get_signal_metrics(
    symbol: str = Query(
        "BTCUSDT",
        description="Trading pair symbol",
        pattern="^[A-Z]{6,12}$",
    ),
    window: Literal["1h", "24h", "7d"] = Query(
        "24h",
        description="Metric time window",
    ),
):
    """Get signal performance metrics.

    Returns hit_rate, signal count, and avg_pnl for the specified window.

    Args:
        symbol: Trading pair (e.g., BTCUSDT)
        window: Time window ('1h', '24h', '7d')

    Returns:
        SignalMetrics with hit_rate, total_signals, feedback_count, avg_pnl
    """
    # Map window to hours
    window_hours = {"1h": 1, "24h": 24, "7d": 168}
    hours = window_hours.get(window, 24)

    db_service = None
    try:
        db_service = FeedbackDBService()
        metrics = db_service.get_rolling_metrics(symbol, hours=hours)

        return SignalMetrics(
            symbol=symbol,
            window=window,
            hit_rate=metrics.get("hit_rate", 0.0),
            total_signals=metrics.get("total", 0),
            feedback_count=metrics.get("total", 0),
            avg_pnl=metrics.get("avg_pnl", 0.0),
        )
    except Exception as e:
        logger.error(f"Error fetching metrics for {symbol}: {e}")
        # Return empty metrics on error
        return SignalMetrics(
            symbol=symbol,
            window=window,
            hit_rate=0.0,
            total_signals=0,
            feedback_count=0,
            avg_pnl=0.0,
        )
    finally:
        if db_service is not None:
            db_service.close()


@router.get("/health")
async def signal_health():
    """Health check for signal subsystem.

    Returns:
        dict: Status of Redis connection and signal components
    """
    redis_client = get_redis_client()

    return {
        "status": "ok" if redis_client.is_connected else "degraded",
        "redis_connected": redis_client.is_connected,
        "message": "Signals operational"
        if redis_client.is_connected
        else "Redis unavailable, running in degraded mode",
    }
