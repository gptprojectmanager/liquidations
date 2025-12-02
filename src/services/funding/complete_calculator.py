"""
Complete bias calculator that integrates funding rate fetching and bias adjustment calculation.
Feature: LIQHEAT-005
Task: T020 - Implement complete bias calculator
"""

import logging
from decimal import Decimal
from typing import List, Optional

from src.models.funding.adjustment_config import AdjustmentConfigModel
from src.models.funding.bias_adjustment import BiasAdjustment
from src.models.funding.funding_rate import FundingRate
from src.services.funding.bias_calculator import BiasCalculator
from src.services.funding.cache_manager import CacheManager
from src.services.funding.funding_fetcher import FundingFetcher, FundingFetchError

logger = logging.getLogger(__name__)


class CompleteBiasCalculator:
    """
    Complete calculator that fetches funding rates and calculates bias adjustments.

    Implements:
    - T020: Complete bias calculator with funding rate integration
    - T021: Historical smoothing support (to be added)
    - T022: Confidence scoring (integrated)
    """

    def __init__(self, config: AdjustmentConfigModel):
        """
        Initialize complete calculator.

        Args:
            config: Adjustment configuration
        """
        self.config = config
        self._bias_calculator = BiasCalculator(
            scale_factor=config.sensitivity,
            max_adjustment=config.max_adjustment,
            outlier_cap=config.outlier_cap,
        )
        self._fetcher = FundingFetcher(
            cache_ttl=config.cache_ttl_seconds,
            max_retries=3,
            timeout=10,
        )

        # Cache for adjustments
        self._adjustment_cache = CacheManager(ttl_seconds=config.cache_ttl_seconds, max_size=50)

        # Store last adjustment for quick access
        self._last_adjustment: Optional[BiasAdjustment] = None

        # Historical data for smoothing (T021)
        self._history: List[BiasAdjustment] = []
        self._max_history = 10

    async def calculate_bias_adjustment(self, symbol: str, total_oi: Decimal) -> BiasAdjustment:
        """
        Calculate bias adjustment for symbol.

        Args:
            symbol: Trading symbol (e.g., BTCUSDT)
            total_oi: Total open interest

        Returns:
            BiasAdjustment with calculated ratios
        """
        # Check if feature is disabled
        if not self.config.enabled:
            logger.info(f"Bias adjustment disabled for {symbol}")
            return self._create_neutral_adjustment(symbol, total_oi)

        # Check cache first
        cache_key = f"adjustment:{symbol}:{total_oi}"
        cached = self._adjustment_cache.get(cache_key)

        if cached is not None:
            logger.debug(f"Cache hit for adjustment {symbol}")
            return cached

        try:
            # Fetch current funding rate
            funding = await self._fetcher.get_funding_rate(symbol)

            # Calculate bias adjustment
            adjustment = self._calculate_from_funding(funding, total_oi)

            # Cache the result
            self._adjustment_cache.set(cache_key, adjustment)
            self._last_adjustment = adjustment

            # Add to history for smoothing
            self._add_to_history(adjustment)

            return adjustment

        except FundingFetchError as e:
            logger.error(f"Failed to fetch funding rate: {e}")

            # Try to use last known adjustment
            if self._last_adjustment and self._last_adjustment.symbol == symbol:
                logger.warning(f"Using last known adjustment for {symbol}")
                return self._last_adjustment

            # Fall back to neutral
            return self._create_neutral_adjustment(symbol, total_oi)

        except Exception as e:
            logger.error(f"Unexpected error calculating adjustment: {e}")
            return self._create_neutral_adjustment(symbol, total_oi)

    def _calculate_from_funding(self, funding: FundingRate, total_oi: Decimal) -> BiasAdjustment:
        """
        Calculate bias adjustment from funding rate.

        Args:
            funding: Current funding rate
            total_oi: Total open interest

        Returns:
            BiasAdjustment
        """
        # Calculate using BiasCalculator
        adjustment = self._bias_calculator.calculate(funding_rate=funding.rate)

        # Add missing fields for complete BiasAdjustment
        adjustment.symbol = funding.symbol
        adjustment.total_oi = total_oi
        adjustment.long_oi = total_oi * adjustment.long_ratio
        adjustment.short_oi = total_oi * adjustment.short_ratio

        # Set confidence_score (convert float to Decimal)
        adjustment.confidence_score = Decimal(str(adjustment.confidence))

        # Add metadata
        adjustment.metadata = adjustment.metadata or {}
        adjustment.metadata["funding_time"] = funding.funding_time.isoformat()
        adjustment.metadata["funding_rate"] = str(funding.rate)
        adjustment.metadata["funding_source"] = funding.source

        # Check for extreme funding
        if abs(funding.rate) >= self.config.extreme_alert_threshold:
            adjustment.metadata["extreme_funding"] = True
            logger.warning(f"Extreme funding rate detected: {funding.symbol} @ {funding.rate}")

        # Apply outlier cap if configured
        if self.config.outlier_cap and self.config.outlier_cap > 0:
            if adjustment.long_ratio > Decimal(0.5 + self.config.max_adjustment):
                # Cap extreme adjustments
                capped_long = min(
                    adjustment.long_ratio, Decimal(0.5) + Decimal(str(self.config.outlier_cap))
                )
                capped_short = Decimal(1) - capped_long

                adjustment.long_ratio = capped_long
                adjustment.short_ratio = capped_short
                adjustment.long_oi = total_oi * capped_long
                adjustment.short_oi = total_oi * capped_short
                adjustment.metadata["capped"] = True

        return adjustment

    def _create_neutral_adjustment(self, symbol: str, total_oi: Decimal) -> BiasAdjustment:
        """
        Create neutral 50/50 adjustment.

        Args:
            symbol: Trading symbol
            total_oi: Total open interest

        Returns:
            Neutral BiasAdjustment
        """
        return BiasAdjustment(
            funding_input=Decimal("0.0"),  # Neutral funding rate
            symbol=symbol,
            long_ratio=Decimal("0.5"),
            short_ratio=Decimal("0.5"),
            total_oi=total_oi,
            long_oi=total_oi * Decimal("0.5"),
            short_oi=total_oi * Decimal("0.5"),
            confidence_score=Decimal("0.5"),
            metadata={"neutral": True},
        )

    def _add_to_history(self, adjustment: BiasAdjustment) -> None:
        """
        Add adjustment to history for smoothing.

        Args:
            adjustment: Adjustment to add
        """
        self._history.append(adjustment)

        # Trim history to max size
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

    def get_last_adjustment(self) -> Optional[BiasAdjustment]:
        """
        Get last calculated adjustment.

        Returns:
            Last BiasAdjustment or None
        """
        return self._last_adjustment

    def get_history(self, limit: int = 10) -> List[BiasAdjustment]:
        """
        Get historical adjustments.

        Args:
            limit: Maximum number of adjustments to return

        Returns:
            List of recent adjustments
        """
        return self._history[-limit:] if self._history else []

    async def close(self):
        """Close resources."""
        await self._fetcher.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
