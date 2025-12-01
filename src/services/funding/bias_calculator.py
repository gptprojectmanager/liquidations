"""
Bias calculator service for funding rate-based position adjustment.
Feature: LIQHEAT-005
Task: T019 - Implement BiasCalculator class
"""

from decimal import Decimal
from typing import Optional

from src.models.funding.bias_adjustment import BiasAdjustment
from src.services.funding.math_utils import (
    calculate_confidence,
    tanh_conversion,
    validate_oi_conservation,
)


class BiasCalculator:
    """
    Calculates position bias adjustments from funding rates.

    Uses tanh transformation to convert funding rates into smooth,
    continuous long/short ratio adjustments while maintaining
    total open interest conservation.
    """

    def __init__(
        self,
        scale_factor: float = 50.0,
        max_adjustment: float = 0.20,
        outlier_cap: Optional[float] = 0.10,
    ):
        """
        Initialize the bias calculator.

        Args:
            scale_factor: Sensitivity to funding rate changes (10.0 to 100.0)
            max_adjustment: Maximum deviation from 50/50 (0.10 to 0.30)
            outlier_cap: Cap for extreme funding rates (optional)
        """
        # Validate parameters
        if not 10.0 <= scale_factor <= 100.0:
            raise ValueError(f"scale_factor {scale_factor} out of range [10.0, 100.0]")

        if not 0.10 <= max_adjustment <= 0.30:
            raise ValueError(f"max_adjustment {max_adjustment} out of range [0.10, 0.30]")

        self.scale_factor = scale_factor
        self.max_adjustment = max_adjustment
        self.outlier_cap = outlier_cap

    def calculate(self, funding_rate: Decimal) -> BiasAdjustment:
        """
        Calculate bias adjustment from funding rate.

        Args:
            funding_rate: The funding rate (e.g., 0.0003 for 0.03%)

        Returns:
            BiasAdjustment with calculated long/short ratios

        Raises:
            ValueError: If funding rate is outside valid range
        """
        # Validate input
        if not isinstance(funding_rate, Decimal):
            funding_rate = Decimal(str(funding_rate))

        # Apply outlier capping if configured
        capped_rate = self._apply_outlier_cap(funding_rate)

        # Calculate ratios using tanh transformation
        long_ratio, short_ratio = tanh_conversion(
            capped_rate, self.scale_factor, self.max_adjustment
        )

        # Validate OI conservation
        if not validate_oi_conservation(long_ratio, short_ratio):
            raise ValueError(f"OI conservation failed: {long_ratio} + {short_ratio} != 1.0")

        # Calculate confidence score
        confidence = calculate_confidence(capped_rate)

        # Create and return adjustment
        return BiasAdjustment(
            funding_input=funding_rate,
            long_ratio=long_ratio,
            short_ratio=short_ratio,
            confidence=confidence,
            scale_factor=self.scale_factor,
            max_adjustment=self.max_adjustment,
        )

    def _apply_outlier_cap(self, funding_rate: Decimal) -> Decimal:
        """
        Apply outlier capping to extreme funding rates.

        Args:
            funding_rate: The raw funding rate

        Returns:
            Capped funding rate
        """
        if self.outlier_cap is None:
            return funding_rate

        cap = Decimal(str(self.outlier_cap))

        if funding_rate > cap:
            return cap
        elif funding_rate < -cap:
            return -cap

        return funding_rate

    def calculate_batch(self, funding_rates: list[Decimal]) -> list[BiasAdjustment]:
        """
        Calculate bias adjustments for multiple funding rates.

        Args:
            funding_rates: List of funding rates

        Returns:
            List of BiasAdjustment objects
        """
        return [self.calculate(rate) for rate in funding_rates]

    def with_config(
        self, scale_factor: Optional[float] = None, max_adjustment: Optional[float] = None
    ) -> "BiasCalculator":
        """
        Create a new calculator with modified configuration.

        Args:
            scale_factor: New scale factor (or keep current)
            max_adjustment: New max adjustment (or keep current)

        Returns:
            New BiasCalculator instance with updated config
        """
        return BiasCalculator(
            scale_factor=scale_factor or self.scale_factor,
            max_adjustment=max_adjustment or self.max_adjustment,
            outlier_cap=self.outlier_cap,
        )
