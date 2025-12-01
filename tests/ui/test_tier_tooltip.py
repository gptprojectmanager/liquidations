"""
UI tests for tier tooltip content.

Tests that tooltip provides comprehensive, educational information
about margin tiers to help retail traders understand the system.
"""

from decimal import Decimal

import pytest

from src.services.display_formatter import DisplayFormatter
from src.services.tier_loader import TierLoader


class TestTierTooltip:
    """Test suite for tier tooltip information."""

    @pytest.fixture
    def formatter(self) -> DisplayFormatter:
        """Create display formatter with Binance default tiers."""
        config = TierLoader.load_binance_default()
        return DisplayFormatter(config)

    def test_tooltip_explains_current_tier(self, formatter):
        """
        Test that tooltip explains what the current tier means.

        Should include:
        - Tier number and range
        - Margin rate
        - What tier affects
        """
        position = Decimal("50000")
        tooltip = formatter.get_tier_tooltip(position)

        assert "tier 1" in tooltip.lower()
        assert "0.5%" in tooltip or "0.005" in tooltip
        assert "$0" in tooltip  # Min range
        assert "$50,000" in tooltip  # Max range

    def test_tooltip_explains_maintenance_margin(self, formatter):
        """
        Test that tooltip explains maintenance margin concept.

        Should be educational for retail traders who may not
        understand the maintenance margin system.
        """
        position = Decimal("100000")
        tooltip = formatter.get_tier_tooltip(position)

        assert "maintenance margin" in tooltip.lower()
        assert "liquidation" in tooltip.lower()
        # Should explain the formula
        assert "margin" in tooltip.lower() and "rate" in tooltip.lower()

    def test_tooltip_warns_about_tier_boundaries(self, formatter):
        """
        Test that tooltip warns traders near tier boundaries.

        If position is within 10% of next tier, tooltip should
        include warning about potential margin increase.
        """
        # $48k is 96% of Tier 1 max ($50k)
        position_near = Decimal("48000")
        tooltip_near = formatter.get_tier_tooltip(position_near)

        assert "approaching" in tooltip_near.lower() or "near" in tooltip_near.lower()
        assert "tier 2" in tooltip_near.lower()

        # $25k is 50% of Tier 1 max - no warning
        position_far = Decimal("25000")
        tooltip_far = formatter.get_tier_tooltip(position_far)

        assert "approaching" not in tooltip_far.lower()

    def test_tooltip_shows_formula_explanation(self, formatter):
        """
        Test that tooltip includes formula explanation.

        Helps traders understand how margin is calculated:
        margin = notional * rate - maintenance_amount
        """
        position = Decimal("100000")
        tooltip = formatter.get_tier_tooltip(position)

        # Should show formula components
        assert "notional" in tooltip.lower() or "position" in tooltip.lower()
        assert "rate" in tooltip.lower() or "%" in tooltip
        assert "maintenance" in tooltip.lower()

    def test_tooltip_shows_example_calculation(self, formatter):
        """
        Test that tooltip includes example calculation.

        Concrete example helps traders understand the system.
        """
        position = Decimal("100000")
        tooltip = formatter.get_tier_tooltip(position)

        # Should include numerical example
        assert "$" in tooltip  # Has dollar amounts
        # Should show the actual margin for current position
        assert "100,000" in tooltip or "100000" in tooltip

    def test_tooltip_explains_tier_impact_on_liquidation(self, formatter):
        """
        Test that tooltip explains how tier affects liquidation price.

        Critical information for risk management.
        """
        position = Decimal("100000")
        tooltip = formatter.get_tier_tooltip(position)

        assert "liquidation" in tooltip.lower()
        # Should explain relationship
        assert "higher" in tooltip.lower() or "lower" in tooltip.lower()

    def test_tooltip_mentions_leverage_limits(self, formatter):
        """
        Test that tooltip mentions maximum leverage for tier.

        Tier 1: 200x max
        Tier 2: 100x max
        etc.
        """
        # Tier 1
        position_t1 = Decimal("25000")
        tooltip_t1 = formatter.get_tier_tooltip(position_t1)

        assert "leverage" in tooltip_t1.lower()
        assert "200" in tooltip_t1 or "200x" in tooltip_t1

        # Tier 2
        position_t2 = Decimal("100000")
        tooltip_t2 = formatter.get_tier_tooltip(position_t2)

        assert "100" in tooltip_t2 or "100x" in tooltip_t2

    def test_tooltip_for_tier_5_mentions_max_tier(self, formatter):
        """
        Test that tooltip for Tier 5 mentions it's the highest tier.

        Different messaging since there's no higher tier to warn about.
        """
        position = Decimal("20000000")  # Tier 5
        tooltip = formatter.get_tier_tooltip(position)

        assert "highest" in tooltip.lower() or "maximum" in tooltip.lower()
        assert "tier 5" in tooltip.lower()

    def test_tooltip_uses_plain_language(self, formatter):
        """
        Test that tooltip uses plain, non-technical language.

        Should be understandable by retail traders without
        derivatives trading background.
        """
        position = Decimal("50000")
        tooltip = formatter.get_tier_tooltip(position)

        # Should avoid jargon
        # These are okay: tier, margin, liquidation
        # Should explain: maintenance amount, notional

        # Check that it's not too technical
        assert len(tooltip) > 100  # Substantial explanation
        assert "%" in tooltip  # Uses percentages (familiar to most)

    def test_tooltip_includes_next_tier_preview(self, formatter):
        """
        Test that tooltip previews next tier.

        Shows what happens if position grows.
        """
        position = Decimal("50000")  # Tier 1
        tooltip = formatter.get_tier_tooltip(position)

        # Should mention Tier 2
        assert "tier 2" in tooltip.lower()
        # Should mention Tier 2 rate
        assert "1" in tooltip or "1.0%" in tooltip

    def test_tooltip_different_for_each_tier(self, formatter):
        """
        Test that tooltip is customized for each tier.

        Not generic copy-paste.
        """
        tooltip_t1 = formatter.get_tier_tooltip(Decimal("25000"))
        tooltip_t2 = formatter.get_tier_tooltip(Decimal("100000"))
        tooltip_t3 = formatter.get_tier_tooltip(Decimal("500000"))

        # Should be different
        assert tooltip_t1 != tooltip_t2
        assert tooltip_t2 != tooltip_t3

        # Should mention their respective tier numbers
        assert "tier 1" in tooltip_t1.lower()
        assert "tier 2" in tooltip_t2.lower()
        assert "tier 3" in tooltip_t3.lower()

    def test_tooltip_mentions_continuous_formula(self, formatter):
        """
        Test that tooltip mentions the continuous formula design.

        Unique selling point: margin is continuous across tiers
        (no sudden jumps).
        """
        position = Decimal("50000")
        tooltip = formatter.get_tier_tooltip(position)

        # Should mention continuity or smooth transition
        assert (
            "continuous" in tooltip.lower()
            or "smooth" in tooltip.lower()
            or "no jump" in tooltip.lower()
        )

    def test_tooltip_includes_risk_disclaimer(self, formatter):
        """
        Test that tooltip includes appropriate risk disclaimer.

        Legal protection and ethical transparency.
        """
        position = Decimal("100000")
        tooltip = formatter.get_tier_tooltip(position)

        # Should have some disclaimer language
        assert (
            "risk" in tooltip.lower()
            or "may" in tooltip.lower()
            or "subject to change" in tooltip.lower()
        )

    def test_tooltip_markdown_formatted(self, formatter):
        """
        Test that tooltip uses markdown for rich formatting.

        Helps organize information visually.
        """
        position = Decimal("50000")
        tooltip = formatter.get_tier_tooltip(position)

        # Should have markdown elements
        assert (
            "**" in tooltip  # Bold
            or "*" in tooltip  # Italic
            or "\n" in tooltip  # Line breaks
        )

    def test_tooltip_length_reasonable(self, formatter):
        """
        Test that tooltip is not too long or too short.

        Should be informative but not overwhelming.
        """
        position = Decimal("50000")
        tooltip = formatter.get_tier_tooltip(position)

        # Should be substantial but not a novel
        assert 200 <= len(tooltip) <= 800

    def test_tooltip_includes_link_to_docs(self, formatter):
        """
        Test that tooltip includes link to full documentation.

        For traders who want deeper understanding.
        """
        position = Decimal("50000")
        tooltip = formatter.get_tier_tooltip(position)

        # Should have some reference to docs
        assert (
            "learn more" in tooltip.lower()
            or "documentation" in tooltip.lower()
            or "binance" in tooltip.lower()
        )
