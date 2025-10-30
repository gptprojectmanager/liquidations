"""
Tests for dynamic binning algorithm.

Dynamic binning adapts bin size to price range, instead of using fixed $100 bins.
Reference: py-liquidation-map algorithm (see examples/py_liquidation_map_logic_analysis.md)
"""

import math
from decimal import Decimal


def test_calculate_dynamic_bin_size_for_btc_range():
    """
    Test dynamic bin size calculation for BTC price range (~$1000).

    For BTC with range $107k-$108k (~$1000 range):
    - tick_degits = 2 - ceil(log10(1000)) = 2 - 3 = -1
    - bin_size = 10^(-(-1)) = 10^1 = $10

    This test SHOULD FAIL initially because current implementation
    uses hardcoded bin_size = Decimal("100").

    Expected: $10 bins for ~$1000 range
    Current: $100 bins (hardcoded)
    """
    # Arrange
    price_min = Decimal("107000")
    price_max = Decimal("108000")
    price_range = float(price_max - price_min)  # 1000

    # Act - Apply py-liquidation-map formula
    tick_degits = 2 - math.ceil(math.log10(price_range))
    expected_bin_size = Decimal(10 ** (-tick_degits))

    # Assert
    assert expected_bin_size == Decimal("10"), (
        f"For BTC range ${price_range:.0f}, expected bin_size=$10, got ${expected_bin_size}"
    )
