"""
UI tests for tier display functionality.

Tests that tier information is correctly formatted and displayed
for retail traders at various position sizes.
"""

from decimal import Decimal

import pytest

from src.models.tier_display import TierDisplay
from src.services.display_formatter import DisplayFormatter
from src.services.tier_loader import TierLoader


class TestTierDisplay:
    """Test suite for tier display functionality."""

    @pytest.fixture
    def formatter(self) -> DisplayFormatter:
        """Create display formatter with Binance default tiers."""
        config = TierLoader.load_binance_default()
        return DisplayFormatter(config)

    def test_tier_display_at_50k_position(self, formatter):
        """
        Test tier display for $50k position (Tier 1).

        Should show:
        - Current tier: 1
        - Margin rate: 0.5%
        - Maintenance margin: $250
        - Next tier threshold: $50,000.01
        """
        position = Decimal("50000")
        display = formatter.format_tier_info(position)

        assert isinstance(display, TierDisplay)
        assert display.tier_number == 1
        assert display.margin_rate_percent == "0.5%"
        assert display.maintenance_margin == "$250.00"
        assert display.next_tier_threshold == "$50,000.01"

    def test_tier_display_at_100k_position(self, formatter):
        """
        Test tier display for $100k position (Tier 2).

        Should show:
        - Current tier: 2
        - Margin rate: 1.0%
        - Maintenance margin: $750
        - Next tier threshold: $250,000.01
        """
        position = Decimal("100000")
        display = formatter.format_tier_info(position)

        assert display.tier_number == 2
        assert display.margin_rate_percent == "1.0%"
        assert display.maintenance_margin == "$750.00"
        assert display.next_tier_threshold == "$250,000.01"

    def test_tier_display_at_max_tier(self, formatter):
        """
        Test tier display for position in maximum tier (Tier 5).

        Should show:
        - Current tier: 5
        - Margin rate: 10.0%
        - Next tier threshold: None (already at max)
        """
        position = Decimal("20000000")  # $20M in Tier 5
        display = formatter.format_tier_info(position)

        assert display.tier_number == 5
        assert display.margin_rate_percent == "10.0%"
        assert display.next_tier_threshold is None  # No higher tier

    def test_tier_display_includes_current_position(self, formatter):
        """
        Test that display includes current position size.

        Helps traders understand their context.
        """
        position = Decimal("50000")
        display = formatter.format_tier_info(position)

        assert display.current_position == "$50,000.00"

    def test_tier_display_shows_tier_range(self, formatter):
        """
        Test that display shows tier's valid range.

        Example: "Tier 1 ($0 - $50,000)"
        """
        position = Decimal("25000")
        display = formatter.format_tier_info(position)

        assert display.tier_range == "$0.00 - $50,000.00"

    def test_tier_display_calculates_distance_to_next_tier(self, formatter):
        """
        Test that display shows distance to next tier.

        For $40k position in Tier 1:
        - Distance to Tier 2: $10,000.01
        """
        position = Decimal("40000")
        display = formatter.format_tier_info(position)

        # Distance to next tier: 50000.01 - 40000 = 10000.01
        assert display.distance_to_next_tier == "$10,000.01"

    def test_tier_display_at_tier_boundary_shows_zero_distance(self, formatter):
        """
        Test display at exact tier boundary.

        At $50k (Tier 1 max), distance to Tier 2 is $0.01
        """
        position = Decimal("50000")
        display = formatter.format_tier_info(position)

        assert display.distance_to_next_tier == "$0.01"

    def test_tier_display_shows_maintenance_amount_offset(self, formatter):
        """
        Test that display shows maintenance amount (MA) offset.

        This helps traders understand the formula:
        margin = notional * rate - MA
        """
        position = Decimal("100000")  # Tier 2
        display = formatter.format_tier_info(position)

        assert display.maintenance_amount == "$250.00"

    def test_tier_display_formatting_with_large_numbers(self, formatter):
        """
        Test that large numbers are formatted with comma separators.

        Example: $1,000,000 not $1000000
        """
        position = Decimal("5000000")  # $5M
        display = formatter.format_tier_info(position)

        assert "," in display.current_position  # Should have comma separator
        assert display.current_position == "$5,000,000.00"

    def test_tier_display_shows_effective_leverage_limit(self, formatter):
        """
        Test that display shows maximum leverage for current tier.

        Max leverage = 1 / margin_rate
        Tier 1 (0.5%) → max 200x
        Tier 2 (1.0%) → max 100x
        """
        # Tier 1: 0.5% rate → 200x max
        position_tier1 = Decimal("25000")
        display_tier1 = formatter.format_tier_info(position_tier1)
        assert display_tier1.max_leverage == "200x"

        # Tier 2: 1.0% rate → 100x max
        position_tier2 = Decimal("100000")
        display_tier2 = formatter.format_tier_info(position_tier2)
        assert display_tier2.max_leverage == "100x"

    def test_tier_display_tooltip_text(self, formatter):
        """
        Test that display includes helpful tooltip text.

        Tooltip should explain what tier means and how it affects margin.
        """
        position = Decimal("50000")
        display = formatter.format_tier_info(position)

        assert display.tooltip is not None
        assert "maintenance margin" in display.tooltip.lower()
        assert "tier" in display.tooltip.lower()

    def test_tier_display_warning_near_boundary(self, formatter):
        """
        Test that display includes warning when near tier boundary.

        If within 5% of next tier, show warning about potential
        margin increase.
        """
        # $48k is 96% of Tier 1 max ($50k) → within 5%
        position_near_boundary = Decimal("48000")
        display_near = formatter.format_tier_info(position_near_boundary)

        assert display_near.warning is not None
        assert "approaching" in display_near.warning.lower()

        # $25k is 50% of Tier 1 max → no warning
        position_far = Decimal("25000")
        display_far = formatter.format_tier_info(position_far)

        assert display_far.warning is None

    def test_tier_display_json_serializable(self, formatter):
        """
        Test that TierDisplay can be serialized to JSON.

        Important for API responses.
        """
        position = Decimal("50000")
        display = formatter.format_tier_info(position)

        # Should be able to convert to dict
        display_dict = display.model_dump()

        assert isinstance(display_dict, dict)
        assert "tier_number" in display_dict
        assert "margin_rate_percent" in display_dict
        assert "current_position" in display_dict
