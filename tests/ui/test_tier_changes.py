"""
UI tests for tier change detection and display.

Tests scenarios where a trader's position size changes,
causing a tier transition, and verifying the UI shows
appropriate warnings and information.
"""

from decimal import Decimal

import pytest

from src.models.tier_display import TierChangePreview
from src.services.display_formatter import DisplayFormatter
from src.services.tier_loader import TierLoader


class TestTierChanges:
    """Test suite for tier transition display."""

    @pytest.fixture
    def formatter(self) -> DisplayFormatter:
        """Create display formatter with Binance default tiers."""
        config = TierLoader.load_binance_default()
        return DisplayFormatter(config)

    def test_tier_change_200k_to_300k(self, formatter):
        """
        Test tier change display for position increase $200k → $300k.

        Crosses boundary:
        - From: Tier 2 ($50k-$250k @ 1.0%)
        - To: Tier 3 ($250k-$1M @ 2.5%)

        Should show:
        - Old margin rate: 1.0%
        - New margin rate: 2.5%
        - Margin increase: $3,500
        - Warning about higher requirements
        """
        old_position = Decimal("200000")
        new_position = Decimal("300000")

        change = formatter.preview_tier_change(old_position, new_position)

        assert isinstance(change, TierChangePreview)
        assert change.old_tier == 2
        assert change.new_tier == 3
        assert change.old_margin_rate == "1.0%"
        assert change.new_margin_rate == "2.5%"
        assert change.crosses_boundary is True

        # Margin calculation:
        # Old: 200000 * 0.01 - 250 = 1750
        # New: 300000 * 0.025 - 4000 = 3500
        # Increase: 3500 - 1750 = 1750
        assert change.margin_increase == "$1,750.00"

    def test_tier_change_within_same_tier(self, formatter):
        """
        Test that position change within same tier shows no tier transition.

        $100k → $150k both in Tier 2.
        """
        old_position = Decimal("100000")
        new_position = Decimal("150000")

        change = formatter.preview_tier_change(old_position, new_position)

        assert change.old_tier == 2
        assert change.new_tier == 2
        assert change.crosses_boundary is False
        assert change.margin_increase != "$0.00"  # Margin still increases

    def test_tier_change_50k_to_51k(self, formatter):
        """
        Test tier change at exact boundary.

        $50k (Tier 1) → $51k (Tier 2)
        Small position increase but significant rate change.
        """
        old_position = Decimal("50000")
        new_position = Decimal("51000")

        change = formatter.preview_tier_change(old_position, new_position)

        assert change.old_tier == 1
        assert change.new_tier == 2
        assert change.crosses_boundary is True
        assert change.old_margin_rate == "0.5%"
        assert change.new_margin_rate == "1.0%"

    def test_tier_change_downward_shows_benefit(self, formatter):
        """
        Test that reducing position shows margin decrease.

        $300k (Tier 3) → $200k (Tier 2)
        Should show margin reduction as positive outcome.
        """
        old_position = Decimal("300000")
        new_position = Decimal("200000")

        change = formatter.preview_tier_change(old_position, new_position)

        assert change.old_tier == 3
        assert change.new_tier == 2
        assert change.crosses_boundary is True
        assert change.is_improvement is True  # Lower tier = better

        # Margin should decrease
        margin_change = Decimal(change.margin_increase.replace("$", "").replace(",", ""))
        assert margin_change < 0  # Negative = decrease

    def test_tier_change_shows_percentage_increase(self, formatter):
        """
        Test that tier change shows percentage increase in margin.

        Helps traders understand relative impact.
        """
        old_position = Decimal("200000")
        new_position = Decimal("300000")

        change = formatter.preview_tier_change(old_position, new_position)

        # Should include percentage change
        assert change.margin_increase_percent is not None
        # (3500 - 1750) / 1750 * 100 = 100%
        assert "100" in change.margin_increase_percent

    def test_tier_change_multiple_tiers_jumped(self, formatter):
        """
        Test tier change that jumps multiple tiers.

        $50k (Tier 1) → $1.5M (Tier 4)
        Skips Tiers 2 and 3.
        """
        old_position = Decimal("50000")
        new_position = Decimal("1500000")

        change = formatter.preview_tier_change(old_position, new_position)

        assert change.old_tier == 1
        assert change.new_tier == 4
        assert change.tiers_crossed == 3  # Crossed 3 boundaries
        assert change.crosses_boundary is True

    def test_tier_change_warning_severity(self, formatter):
        """
        Test that tier changes have appropriate warning severity.

        - Same tier: info
        - One tier jump: warning
        - Multiple tiers: critical
        """
        # Same tier
        change_same = formatter.preview_tier_change(Decimal("100000"), Decimal("150000"))
        assert change_same.warning_level == "info"

        # One tier jump
        change_one = formatter.preview_tier_change(Decimal("200000"), Decimal("300000"))
        assert change_one.warning_level == "warning"

        # Multiple tier jump
        change_multiple = formatter.preview_tier_change(Decimal("50000"), Decimal("1500000"))
        assert change_multiple.warning_level == "critical"

    def test_tier_change_shows_new_max_leverage(self, formatter):
        """
        Test that tier change shows new maximum leverage.

        Important for traders to know their leverage limits changed.
        """
        old_position = Decimal("50000")  # Tier 1: 200x max
        new_position = Decimal("51000")  # Tier 2: 100x max

        change = formatter.preview_tier_change(old_position, new_position)

        assert change.old_max_leverage == "200x"
        assert change.new_max_leverage == "100x"
        assert change.leverage_reduced is True

    def test_tier_change_includes_actionable_message(self, formatter):
        """
        Test that tier change includes user-friendly message.

        Should explain what happened and what trader should do.
        """
        old_position = Decimal("200000")
        new_position = Decimal("300000")

        change = formatter.preview_tier_change(old_position, new_position)

        assert change.message is not None
        assert "tier 2" in change.message.lower()
        assert "tier 3" in change.message.lower()
        assert "margin requirement" in change.message.lower()

    def test_tier_change_shows_boundary_crossed(self, formatter):
        """
        Test that tier change shows which boundary was crossed.

        Helps traders understand the threshold.
        """
        old_position = Decimal("200000")
        new_position = Decimal("300000")

        change = formatter.preview_tier_change(old_position, new_position)

        assert change.boundary_crossed == "$250,000.00"

    def test_tier_change_calculates_liquidation_price_impact(self, formatter):
        """
        Test that tier change shows impact on liquidation price.

        Higher tier = higher margin = lower liquidation price for longs.
        """
        old_position = Decimal("200000")
        new_position = Decimal("300000")

        # Assume BTC entry at $50k, 5x leverage
        entry_price = Decimal("50000")
        leverage = Decimal("5")

        change = formatter.preview_tier_change_with_liquidation(
            old_position, new_position, entry_price, leverage, "long"
        )

        # Should show old vs new liquidation price
        assert change.old_liquidation_price is not None
        assert change.new_liquidation_price is not None

        # Liquidation prices should be different due to tier change
        old_liq = Decimal(change.old_liquidation_price.replace("$", "").replace(",", ""))
        new_liq = Decimal(change.new_liquidation_price.replace("$", "").replace(",", ""))
        assert old_liq != new_liq  # Changed due to different tier/position size

    def test_tier_change_json_serializable(self, formatter):
        """
        Test that TierChangePreview can be serialized to JSON.

        Important for API responses.
        """
        old_position = Decimal("200000")
        new_position = Decimal("300000")

        change = formatter.preview_tier_change(old_position, new_position)

        # Should be able to convert to dict
        change_dict = change.model_dump()

        assert isinstance(change_dict, dict)
        assert "old_tier" in change_dict
        assert "new_tier" in change_dict
        assert "crosses_boundary" in change_dict
