"""
Decimal precision configuration for Tiered Margin calculations.

Ensures 128-bit precision (28 decimal digits) for all financial calculations
to prevent rounding errors in large position calculations.
"""

from decimal import ROUND_HALF_UP, Decimal, getcontext
from functools import wraps
from typing import Any, Callable, TypeVar

# Set global decimal precision to 28 digits (128-bit equivalent)
# This ensures continuity at tier boundaries and accuracy for positions up to $1B
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


def with_decimal_precision(precision: int = 28) -> Callable[[F], F]:
    """
    Decorator to ensure specific decimal precision for a function.

    Args:
        precision: Number of significant digits (default: 28)

    Returns:
        Decorated function with specified precision context
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Save current context
            current_context = getcontext().copy()
            try:
                # Set new precision
                getcontext().prec = precision
                getcontext().rounding = ROUND_HALF_UP
                # Execute function
                return func(*args, **kwargs)
            finally:
                # Restore original context
                setcontext(current_context)

        return wrapper

    return decorator


def ensure_decimal(value: Any) -> Decimal:
    """
    Convert any numeric value to Decimal with proper precision.

    Args:
        value: Numeric value to convert

    Returns:
        Decimal representation of the value

    Raises:
        ValueError: If value cannot be converted to Decimal
    """
    if isinstance(value, Decimal):
        return value

    if isinstance(value, (int, float)):
        # Convert through string to avoid float precision issues
        return Decimal(str(value))

    if isinstance(value, str):
        return Decimal(value)

    raise ValueError(f"Cannot convert {type(value).__name__} to Decimal: {value}")


# Pre-defined common values to avoid repeated conversions
ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")

# Tier-specific precision constants
MIN_NOTIONAL = Decimal("0.01")  # Minimum position size
MAX_NOTIONAL = Decimal("1000000000000")  # Maximum position size ($1T)
CONTINUITY_THRESHOLD = Decimal("0.01")  # Maximum acceptable discontinuity ($0.01)

# Common margin rates as Decimal
TIER_1_RATE = Decimal("0.005")  # 0.5%
TIER_2_RATE = Decimal("0.010")  # 1.0%
TIER_3_RATE = Decimal("0.025")  # 2.5%
TIER_4_RATE = Decimal("0.050")  # 5.0%
TIER_5_RATE = Decimal("0.100")  # 10.0%


def validate_continuity(margin_left: Decimal, margin_right: Decimal) -> bool:
    """
    Validate mathematical continuity at a tier boundary.

    Args:
        margin_left: Margin calculated from lower tier
        margin_right: Margin calculated from upper tier

    Returns:
        True if difference is within continuity threshold
    """
    difference = abs(margin_left - margin_right)
    return difference < CONTINUITY_THRESHOLD


# Import setcontext for context restoration
from decimal import setcontext
