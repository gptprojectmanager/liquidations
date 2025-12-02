"""
Mathematical utility functions for funding rate bias adjustment.
Feature: LIQHEAT-005
Task: T007 - Implement tanh conversion formula
"""

import math
from decimal import Decimal


def tanh_conversion(
    funding_rate: Decimal, scale_factor: float = 50.0, max_adjustment: float = 0.20
) -> tuple[Decimal, Decimal]:
    """
    Convert funding rate to long/short ratios using tanh function.

    Formula:
        long_ratio = 0.5 + (tanh(funding_rate × scale_factor) × max_adjustment)
        short_ratio = 1.0 - long_ratio

    Args:
        funding_rate: The funding rate to convert (e.g., 0.0003 for 0.03%)
        scale_factor: Sensitivity parameter (default: 50.0)
        max_adjustment: Maximum deviation from 0.5 (default: 0.20 for ±20%)

    Returns:
        Tuple of (long_ratio, short_ratio) as Decimal values

    Mathematical Properties:
        - Continuous for all funding_rate values
        - Bounded output: long_ratio ∈ [0.5 - max_adj, 0.5 + max_adj]
        - OI Conservation: long_ratio + short_ratio = 1.0 exactly
        - Symmetric: f(-x) produces mirror ratios
    """
    # Convert to float for math operations
    rate_float = float(funding_rate)

    # Convert to percentage basis for calculation
    # 0.0003 (0.03%) becomes 0.03 for the formula
    rate_percentage = rate_float * 100

    # Apply tanh transformation
    # tanh is bounded to [-1, 1], ensuring output stays within limits
    tanh_value = math.tanh(rate_percentage * scale_factor)

    # Calculate long ratio
    # Center at 0.5, adjust by tanh result scaled by max_adjustment
    long_ratio_float = 0.5 + (tanh_value * max_adjustment)

    # Ensure short ratio maintains OI conservation
    short_ratio_float = 1.0 - long_ratio_float

    # Convert back to Decimal for precision
    long_ratio = Decimal(str(long_ratio_float))
    short_ratio = Decimal(str(short_ratio_float))

    return long_ratio, short_ratio


def calculate_confidence(funding_rate: Decimal) -> float:
    """
    Calculate confidence score based on funding rate magnitude.

    Higher absolute funding rates indicate stronger market sentiment
    and thus higher confidence in the bias adjustment.

    Args:
        funding_rate: The funding rate

    Returns:
        Confidence score between 0 and 1
    """
    # Use absolute value for confidence
    abs_rate = abs(float(funding_rate))

    # Convert to percentage (multiply by 100)
    abs_rate_percentage = abs_rate * 100

    # Scale confidence: 0 at rate=0, approaching 1 as rate increases
    # Using tanh for smooth scaling (2.0 chosen for good scaling)
    confidence = math.tanh(abs_rate_percentage * 2.0)

    # Ensure bounds
    return min(max(confidence, 0.0), 1.0)


def validate_oi_conservation(
    long_ratio: Decimal, short_ratio: Decimal, tolerance: Decimal = Decimal("1e-10")
) -> bool:
    """
    Validate that OI conservation is maintained.

    Args:
        long_ratio: Long position ratio
        short_ratio: Short position ratio
        tolerance: Acceptable deviation from 1.0

    Returns:
        True if conservation is maintained, False otherwise
    """
    total = long_ratio + short_ratio
    return abs(total - Decimal("1.0")) <= tolerance
