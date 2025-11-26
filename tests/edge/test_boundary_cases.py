"""
Edge case tests for tier boundary handling.

Tests positions exactly at tier boundaries, just before, and just after
to ensure no off-by-one errors or precision issues.
"""

from decimal import Decimal

import pytest

from src.models.tier_config import TierConfiguration
from src.services.margin_calculator import MarginCalculator
from src.services.tier_loader import TierLoader


class TestBoundaryCases:
    """Test suite for edge cases at tier boundaries."""

    @pytest.fixture
    def config(self) -> TierConfiguration:
        """Load Binance default configuration."""
        return TierLoader.load_binance_default()

    @pytest.fixture
    def calculator(self, config) -> MarginCalculator:
        """Create margin calculator."""
        return MarginCalculator(config)

    # Tier 1/2 boundary: $50,000

    def test_exactly_at_50k_boundary(self, calculator):
        """
        Test position exactly at $50k boundary.

        $50,000 should be in Tier 1 (using (min, max] logic).
        """
        position = Decimal("50000")
        tier = calculator.get_tier_for_position(position)

        assert tier.tier_number == 1
        assert tier.max_notional == Decimal("50000")

        # Calculate margin
        margin = calculator.calculate_margin(position)
        # Tier 1: 50000 * 0.005 - 0 = 250
        assert margin == Decimal("250")

    def test_one_cent_below_50k(self, calculator):
        """Test position $0.01 below $50k boundary."""
        position = Decimal("49999.99")
        tier = calculator.get_tier_for_position(position)

        assert tier.tier_number == 1

        # Should calculate correctly
        margin = calculator.calculate_margin(position)
        expected = position * Decimal("0.005")
        assert abs(margin - expected) < Decimal("0.01")

    def test_one_cent_above_50k(self, calculator):
        """Test position $0.01 above $50k boundary."""
        position = Decimal("50000.01")
        tier = calculator.get_tier_for_position(position)

        assert tier.tier_number == 2

        # Should calculate correctly with Tier 2 rate and MA
        margin = calculator.calculate_margin(position)
        expected = position * Decimal("0.010") - Decimal("250")
        assert abs(margin - expected) < Decimal("0.01")

    def test_one_dollar_below_50k(self, calculator):
        """Test position $1 below $50k boundary."""
        position = Decimal("49999")
        tier = calculator.get_tier_for_position(position)
        assert tier.tier_number == 1

    def test_one_dollar_above_50k(self, calculator):
        """Test position $1 above $50k boundary."""
        position = Decimal("50001")
        tier = calculator.get_tier_for_position(position)
        assert tier.tier_number == 2

    # Tier 2/3 boundary: $250,000

    def test_exactly_at_250k_boundary(self, calculator):
        """
        Test position exactly at $250k boundary.

        $250,000 should be in Tier 2.
        """
        position = Decimal("250000")
        tier = calculator.get_tier_for_position(position)

        assert tier.tier_number == 2
        assert tier.max_notional == Decimal("250000")

        # Calculate margin
        margin = calculator.calculate_margin(position)
        # Tier 2: 250000 * 0.010 - 250 = 2250
        assert margin == Decimal("2250")

    def test_one_cent_below_250k(self, calculator):
        """Test position $0.01 below $250k boundary."""
        position = Decimal("249999.99")
        tier = calculator.get_tier_for_position(position)
        assert tier.tier_number == 2

    def test_one_cent_above_250k(self, calculator):
        """Test position $0.01 above $250k boundary."""
        position = Decimal("250000.01")
        tier = calculator.get_tier_for_position(position)
        assert tier.tier_number == 3

    # Tier 3/4 boundary: $1,000,000

    def test_exactly_at_1m_boundary(self, calculator):
        """
        Test position exactly at $1M boundary.

        $1,000,000 should be in Tier 3.
        """
        position = Decimal("1000000")
        tier = calculator.get_tier_for_position(position)

        assert tier.tier_number == 3
        assert tier.max_notional == Decimal("1000000")

        # Calculate margin
        margin = calculator.calculate_margin(position)
        # Tier 3: 1000000 * 0.025 - 4000 = 21000
        assert margin == Decimal("21000")

    def test_one_cent_below_1m(self, calculator):
        """Test position $0.01 below $1M boundary."""
        position = Decimal("999999.99")
        tier = calculator.get_tier_for_position(position)
        assert tier.tier_number == 3

    def test_one_cent_above_1m(self, calculator):
        """Test position $0.01 above $1M boundary."""
        position = Decimal("1000000.01")
        tier = calculator.get_tier_for_position(position)
        assert tier.tier_number == 4

    # Tier 4/5 boundary: $10,000,000

    def test_exactly_at_10m_boundary(self, calculator):
        """
        Test position exactly at $10M boundary.

        $10,000,000 should be in Tier 4.
        """
        position = Decimal("10000000")
        tier = calculator.get_tier_for_position(position)

        assert tier.tier_number == 4
        assert tier.max_notional == Decimal("10000000")

        # Calculate margin
        margin = calculator.calculate_margin(position)
        # Tier 4: 10000000 * 0.050 - 29000 = 471000
        assert margin == Decimal("471000")

    def test_one_cent_below_10m(self, calculator):
        """Test position $0.01 below $10M boundary."""
        position = Decimal("9999999.99")
        tier = calculator.get_tier_for_position(position)
        assert tier.tier_number == 4

    def test_one_cent_above_10m(self, calculator):
        """Test position $0.01 above $10M boundary."""
        position = Decimal("10000000.01")
        tier = calculator.get_tier_for_position(position)
        assert tier.tier_number == 5

    # Precision edge cases

    def test_micro_amount_above_boundary(self, calculator):
        """Test position with microscopically small amount above boundary."""
        position = Decimal("50000.000001")
        tier = calculator.get_tier_for_position(position)
        assert tier.tier_number == 2

    def test_micro_amount_below_boundary(self, calculator):
        """Test position with microscopically small amount below boundary."""
        position = Decimal("49999.999999")
        tier = calculator.get_tier_for_position(position)
        assert tier.tier_number == 1

    # Zero and negative edge cases

    def test_zero_position(self, calculator):
        """Test that zero position raises error (not in any tier)."""
        position = Decimal("0")

        with pytest.raises(ValueError, match="below minimum tier threshold"):
            calculator.get_tier_for_position(position)

    def test_negative_position_raises_error(self, calculator):
        """Test that negative position raises error."""
        position = Decimal("-1000")

        with pytest.raises(ValueError, match="below minimum tier threshold"):
            calculator.get_tier_for_position(position)

    # Upper limit edge cases

    def test_exactly_at_max_tier_boundary(self, calculator):
        """Test position exactly at maximum tier boundary ($50M)."""
        position = Decimal("50000000")
        tier = calculator.get_tier_for_position(position)

        assert tier.tier_number == 5
        assert tier.max_notional == Decimal("50000000")

    def test_above_max_tier_uses_tier_5(self, calculator):
        """Test position above max tier still uses Tier 5."""
        position = Decimal("100000000")  # $100M
        tier = calculator.get_tier_for_position(position)

        # Should use Tier 5 (highest tier) for positions above max
        assert tier.tier_number == 5

    # Continuity verification at boundaries

    def test_continuity_across_50k_boundary(self, calculator):
        """Verify margin continuity across $50k boundary."""
        just_below = Decimal("50000")  # Tier 1
        just_above = Decimal("50000.01")  # Tier 2

        margin_below = calculator.calculate_margin(just_below)
        margin_above = calculator.calculate_margin(just_above)

        # Difference should be tiny (continuous function)
        difference = abs(margin_above - margin_below)

        # At boundary: T1 gives 250, T2 gives ~250.0001, difference ~0.0001
        assert difference < Decimal("0.01"), f"Discontinuity: {difference}"

    def test_continuity_across_250k_boundary(self, calculator):
        """Verify margin continuity across $250k boundary."""
        just_below = Decimal("250000")  # Tier 2
        just_above = Decimal("250000.01")  # Tier 3

        margin_below = calculator.calculate_margin(just_below)
        margin_above = calculator.calculate_margin(just_above)

        difference = abs(margin_above - margin_below)
        assert difference < Decimal("0.01"), f"Discontinuity: {difference}"

    def test_continuity_across_1m_boundary(self, calculator):
        """Verify margin continuity across $1M boundary."""
        just_below = Decimal("1000000")  # Tier 3
        just_above = Decimal("1000000.01")  # Tier 4

        margin_below = calculator.calculate_margin(just_below)
        margin_above = calculator.calculate_margin(just_above)

        difference = abs(margin_above - margin_below)
        assert difference < Decimal("0.01"), f"Discontinuity: {difference}"

    def test_continuity_across_10m_boundary(self, calculator):
        """Verify margin continuity across $10M boundary."""
        just_below = Decimal("10000000")  # Tier 4
        just_above = Decimal("10000000.01")  # Tier 5

        margin_below = calculator.calculate_margin(just_below)
        margin_above = calculator.calculate_margin(just_above)

        difference = abs(margin_above - margin_below)
        assert difference < Decimal("0.01"), f"Discontinuity: {difference}"

    # String and float conversion edge cases

    def test_boundary_from_string(self, calculator):
        """Test boundary detection works with string input."""
        # Strings should be converted to Decimal internally
        position = "50000"
        tier = calculator.get_tier_for_position(position)
        assert tier.tier_number == 1

    def test_fractional_cents_at_boundary(self, calculator):
        """Test that fractional cents are handled at boundaries."""
        # Position with fractional cents
        position = Decimal("50000.005")
        tier = calculator.get_tier_for_position(position)
        assert tier.tier_number == 2

        # Should calculate without precision loss
        margin = calculator.calculate_margin(position)
        assert isinstance(margin, Decimal)
