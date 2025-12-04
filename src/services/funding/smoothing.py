"""
Historical smoothing for bias adjustments.
Feature: LIQHEAT-005
Task: T021 - Add historical smoothing support
"""

import logging
from decimal import Decimal
from typing import List, Optional

from src.models.funding.adjustment_config import AdjustmentConfigModel
from src.models.funding.bias_adjustment import BiasAdjustment

logger = logging.getLogger(__name__)


class HistoricalSmoother:
    """
    Applies exponential weighted moving average (EWMA) smoothing
    to bias adjustments using historical data.

    Implements:
    - T021: Historical smoothing support
    - Configurable smoothing periods
    - Custom or auto-calculated weights
    - OI conservation guarantee
    """

    def __init__(self, config: AdjustmentConfigModel):
        """
        Initialize smoother with configuration.

        Args:
            config: Adjustment configuration with smoothing settings
        """
        self.config = config
        self._weights: Optional[List[float]] = None

        # Initialize weights if smoothing is enabled
        if config.smoothing_enabled:
            self._initialize_weights()

    def _initialize_weights(self) -> None:
        """Initialize smoothing weights."""
        if self.config.smoothing_weights:
            # Use provided weights
            self._weights = self.config.smoothing_weights

            # Validate weights sum to 1
            total = sum(self._weights)
            if abs(total - 1.0) > 1e-6:
                logger.warning(f"Weights sum to {total}, normalizing...")
                self._weights = [w / total for w in self._weights]
        else:
            # Auto-calculate exponentially decreasing weights
            self._weights = self._calculate_auto_weights()

    def _calculate_auto_weights(self) -> List[float]:
        """
        Calculate automatic exponentially decreasing weights.

        Returns:
            List of weights that sum to 1.0
        """
        periods = self.config.smoothing_periods
        if periods <= 0:
            return []

        # Use exponential decay: weight_i = exp(-alpha * i)
        # where i=0 is current, i=1 is previous, etc.
        alpha = 0.5  # Decay rate (adjustable)

        raw_weights = []
        for i in range(periods):
            weight = pow(2.0, -alpha * i)  # 2^(-alpha * i)
            raw_weights.append(weight)

        # Normalize to sum to 1
        total = sum(raw_weights)
        return [w / total for w in raw_weights]

    def smooth_adjustment(
        self, current: BiasAdjustment, history: List[BiasAdjustment]
    ) -> BiasAdjustment:
        """
        Apply smoothing to current adjustment using historical data.

        Args:
            current: Current bias adjustment
            history: List of historical adjustments (oldest to newest)

        Returns:
            Smoothed BiasAdjustment
        """
        # If smoothing disabled or no history, return current unchanged
        if not self.config.smoothing_enabled or not history:
            return current

        # Combine current with history (newest first)
        all_adjustments = [current] + list(reversed(history))

        # Limit to configured periods
        periods_to_use = min(self.config.smoothing_periods, len(all_adjustments))
        adjustments = all_adjustments[:periods_to_use]

        # Get weights for the actual number of periods
        weights = self.get_weights()[:periods_to_use]

        # Renormalize weights if using fewer periods
        if len(weights) != self.config.smoothing_periods:
            total = sum(weights)
            weights = [w / total for w in weights]

        # Calculate weighted averages
        smoothed_long = Decimal("0")
        smoothed_short = Decimal("0")
        weighted_confidence = 0.0

        for adj, weight in zip(adjustments, weights):
            weight_decimal = Decimal(str(weight))
            smoothed_long += adj.long_ratio * weight_decimal
            smoothed_short += adj.short_ratio * weight_decimal
            weighted_confidence += adj.confidence * weight

        # Ensure OI conservation
        total = smoothed_long + smoothed_short
        if abs(total - Decimal("1.0")) > Decimal("1e-10"):
            # Normalize to ensure exact sum of 1.0
            smoothed_long = smoothed_long / total
            smoothed_short = smoothed_short / total

        # Create smoothed adjustment
        smoothed = BiasAdjustment(
            funding_input=current.funding_input,  # Use current funding rate
            long_ratio=smoothed_long,
            short_ratio=smoothed_short,
            confidence=weighted_confidence,
            scale_factor=current.scale_factor,
            max_adjustment=current.max_adjustment,
        )

        # Copy extended fields if present
        if current.symbol:
            smoothed.symbol = current.symbol
        if current.total_oi:
            smoothed.total_oi = current.total_oi
            smoothed.long_oi = current.total_oi * smoothed_long
            smoothed.short_oi = current.total_oi * smoothed_short
        if current.confidence_score:
            smoothed.confidence_score = Decimal(str(weighted_confidence))
        if current.metadata:
            smoothed.metadata = current.metadata.copy()
            smoothed.metadata["smoothed"] = True
            smoothed.metadata["periods_used"] = periods_to_use

        logger.debug(
            f"Smoothed adjustment: {current.long_ratio:.4f} -> {smoothed.long_ratio:.4f} "
            f"(using {periods_to_use} periods)"
        )

        return smoothed

    def get_weights(self) -> List[float]:
        """
        Get the current smoothing weights.

        Returns:
            List of weights
        """
        if self._weights is None:
            self._weights = self._calculate_auto_weights()
        return self._weights.copy()

    def reset_weights(self) -> None:
        """Reset weights to force recalculation."""
        self._weights = None
        if self.config.smoothing_enabled:
            self._initialize_weights()
