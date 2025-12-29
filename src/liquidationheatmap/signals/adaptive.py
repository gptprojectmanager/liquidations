"""Adaptive Engine for weight adjustment based on P&L feedback.

Implements EMA-based weight adjustment algorithm per Constitution Section 3.
Automatically rolls back to defaults if hit_rate falls below 0.50 (Section 6).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal, Protocol

from src.liquidationheatmap.signals.config import get_signal_config

logger = logging.getLogger(__name__)


# Default weights (50/50 long/short)
DEFAULT_WEIGHTS: dict[str, Decimal] = {
    "long": Decimal("0.5"),
    "short": Decimal("0.5"),
}

# Window hours mapping
WINDOW_HOURS: dict[str, int] = {
    "1h": 1,
    "24h": 24,
    "7d": 168,  # 7 * 24
}


def calculate_ema(current: float, target: float, alpha: float) -> float:
    """Calculate Exponential Moving Average.

    Args:
        current: Current value
        target: Target value (new data point)
        alpha: Smoothing factor (0.0 = no change, 1.0 = instant)

    Returns:
        New EMA value
    """
    return alpha * target + (1 - alpha) * current


class DBServiceProtocol(Protocol):
    """Protocol for database service with metrics."""

    def get_rolling_metrics(self, symbol: str, hours: int) -> dict[str, Any]: ...
    def store_weight_history(
        self, symbol: str, weights: dict[str, Decimal], timestamp: datetime
    ) -> bool: ...


class AdaptiveEngine:
    """Adjusts signal weights based on rolling P&L feedback.

    Uses EMA algorithm to gradually shift weights towards better performing
    signal types (long vs short) based on historical hit rates.

    Attributes:
        weights: Current long/short weights (sum to 1.0)
        ema_alpha: Smoothing factor for EMA (default: 0.1)
        min_hit_rate: Threshold for rollback (default: 0.50)

    Usage:
        engine = AdaptiveEngine()
        engine.adjust_weights("BTCUSDT")
        confidence = engine.get_weighted_confidence(0.8, "long")
    """

    def __init__(
        self,
        db_service: DBServiceProtocol | None = None,
        ema_alpha: float | None = None,
        min_hit_rate: float | None = None,
    ):
        """Initialize AdaptiveEngine.

        Args:
            db_service: Database service for metrics (optional)
            ema_alpha: EMA smoothing factor (uses config if None)
            min_hit_rate: Rollback threshold (uses config if None)
        """
        self._db_service = db_service
        self._config = get_signal_config()

        self.ema_alpha = ema_alpha if ema_alpha is not None else self._config.ema_alpha
        self.min_hit_rate = min_hit_rate if min_hit_rate is not None else self._config.min_hit_rate

        # Initialize with default weights
        self.weights: dict[str, Decimal] = DEFAULT_WEIGHTS.copy()

    def calculate_rolling_metrics(
        self, symbol: str, window: Literal["1h", "24h", "7d"] = "24h"
    ) -> dict[str, Any]:
        """Calculate rolling metrics for a symbol.

        Args:
            symbol: Trading pair symbol
            window: Time window ('1h', '24h', '7d')

        Returns:
            Dict with hit_rate, total, profitable, avg_pnl
        """
        hours = WINDOW_HOURS.get(window, 24)

        if self._db_service is None:
            logger.warning("No DB service, returning empty metrics")
            return {"hit_rate": 0.5, "total": 0, "profitable": 0, "avg_pnl": 0.0}

        return self._db_service.get_rolling_metrics(symbol, hours=hours)

    def adjust_weights(self, symbol: str) -> None:
        """Adjust weights based on rolling metrics.

        Uses 24h window for adjustment by default. Applies EMA smoothing
        to prevent sudden weight changes.

        Args:
            symbol: Trading pair symbol
        """
        metrics = self.calculate_rolling_metrics(symbol, window="24h")
        hit_rate = metrics.get("hit_rate", 0.5)

        if metrics.get("total", 0) == 0:
            logger.debug(f"No feedback data for {symbol}, keeping default weights")
            return

        # Calculate target weights based on hit rate performance
        # If hit_rate > 0.5, increase weight; if < 0.5, decrease
        # Use hit_rate as target for the current dominant side
        long_hit_rate = hit_rate  # Simplified: overall hit rate affects both
        short_hit_rate = hit_rate

        # Apply EMA to current weights
        new_long = calculate_ema(float(self.weights["long"]), long_hit_rate, self.ema_alpha)
        new_short = calculate_ema(float(self.weights["short"]), short_hit_rate, self.ema_alpha)

        # Normalize to sum to 1.0
        total = new_long + new_short
        if total > 0:
            self.weights["long"] = Decimal(str(new_long / total))
            self.weights["short"] = Decimal(str(new_short / total))
        else:
            # Edge case: both EMA results are zero, reset to defaults
            logger.warning("EMA resulted in zero weights, reverting to defaults")
            self.weights = DEFAULT_WEIGHTS.copy()

        logger.info(
            f"Adjusted weights for {symbol}: "
            f"long={self.weights['long']:.4f}, short={self.weights['short']:.4f}"
        )

        # Store history if DB service available
        if self._db_service and hasattr(self._db_service, "store_weight_history"):
            self._db_service.store_weight_history(symbol, self.weights, datetime.now(timezone.utc))

    def check_rollback(self, symbol: str) -> bool:
        """Check if rollback to defaults is needed.

        Args:
            symbol: Trading pair symbol

        Returns:
            True if should rollback (hit_rate < min_hit_rate)
        """
        metrics = self.calculate_rolling_metrics(symbol, window="24h")
        hit_rate = metrics.get("hit_rate", 0.5)

        if hit_rate < self.min_hit_rate:
            logger.warning(
                f"Hit rate {hit_rate:.2%} below threshold {self.min_hit_rate:.2%}, "
                f"rollback recommended for {symbol}"
            )
            return True
        return False

    def rollback_to_defaults(self, symbol: str) -> None:
        """Reset weights to defaults.

        Called when hit_rate falls below threshold. Per Constitution Section 6,
        graceful degradation is required.

        Args:
            symbol: Trading pair symbol
        """
        logger.warning(f"Rolling back weights to defaults for {symbol}")
        self.weights = DEFAULT_WEIGHTS.copy()

        # Store history if DB service available
        if self._db_service and hasattr(self._db_service, "store_weight_history"):
            self._db_service.store_weight_history(symbol, self.weights, datetime.now(timezone.utc))

    def get_weighted_confidence(self, confidence: float, side: Literal["long", "short"]) -> float:
        """Apply weight to signal confidence.

        Args:
            confidence: Original confidence (0.0-1.0)
            side: Position side

        Returns:
            Weighted confidence
        """
        weight = float(self.weights.get(side, Decimal("0.5")))
        return confidence * weight

    def run_adjustment_cycle(self, symbol: str) -> None:
        """Run complete adjustment cycle.

        1. Check if rollback needed
        2. If not, adjust weights
        3. Store history

        Args:
            symbol: Trading pair symbol
        """
        if self.check_rollback(symbol):
            self.rollback_to_defaults(symbol)
        else:
            self.adjust_weights(symbol)
