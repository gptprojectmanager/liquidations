"""
Display formatting service for margin tier information.

Provides user-friendly formatting of tier data for UI consumption,
including tooltips, warnings, and formatted strings.
"""

from decimal import Decimal
from typing import Optional

from src.models.margin_tier import MarginTier
from src.models.tier_config import TierConfiguration
from src.models.tier_display import (
    TierChangePreview,
    TierComparisonRow,
    TierComparisonTable,
    TierDisplay,
)
from src.services.margin_calculator import MarginCalculator


class DisplayFormatter:
    """
    Formats margin tier information for display to users.

    Converts technical Decimal values and tier data into
    user-friendly strings with proper formatting, tooltips,
    and warnings.
    """

    def __init__(self, config: TierConfiguration):
        """
        Initialize display formatter.

        Args:
            config: Tier configuration to format
        """
        self.config = config
        self.calculator = MarginCalculator(config)

    def format_tier_info(self, notional: Decimal) -> TierDisplay:
        """
        Format tier information for current position.

        Args:
            notional: Position size (notional value)

        Returns:
            TierDisplay with formatted information
        """
        tier = self.calculator.get_tier_for_position(notional)
        margin = self.calculator.calculate_margin(notional)

        # Get next tier info (if exists)
        next_tier_threshold = None
        distance_to_next_tier = None

        tier_index = self.config.tiers.index(tier)
        if tier_index < len(self.config.tiers) - 1:
            next_tier = self.config.tiers[tier_index + 1]
            # Next tier starts at min_notional + 0.01
            next_tier_threshold = self._format_currency(next_tier.min_notional + Decimal("0.01"))
            distance = next_tier.min_notional + Decimal("0.01") - notional
            distance_to_next_tier = self._format_currency(distance)

        # Calculate max leverage (1 / margin_rate)
        max_leverage = int(Decimal("1") / tier.margin_rate)

        # Generate tooltip
        tooltip = self._generate_tooltip(notional, tier)

        # Generate warning if near boundary
        warning = self._generate_boundary_warning(notional, tier)

        return TierDisplay(
            tier_number=tier.tier_number,
            margin_rate_percent=self._format_percentage(tier.margin_rate),
            maintenance_amount=self._format_currency(tier.maintenance_amount),
            maintenance_margin=self._format_currency(margin),
            current_position=self._format_currency(notional),
            tier_range=f"{self._format_currency(tier.min_notional)} - {self._format_currency(tier.max_notional)}",
            next_tier_threshold=next_tier_threshold,
            distance_to_next_tier=distance_to_next_tier,
            max_leverage=f"{max_leverage}x",
            tooltip=tooltip,
            warning=warning,
        )

    def preview_tier_change(
        self,
        old_notional: Decimal,
        new_notional: Decimal,
    ) -> TierChangePreview:
        """
        Preview impact of position size change.

        Args:
            old_notional: Current position size
            new_notional: New position size

        Returns:
            TierChangePreview with change impact
        """
        old_tier = self.calculator.get_tier_for_position(old_notional)
        new_tier = self.calculator.get_tier_for_position(new_notional)

        old_margin = self.calculator.calculate_margin(old_notional)
        new_margin = self.calculator.calculate_margin(new_notional)

        margin_increase = new_margin - old_margin
        margin_increase_percent = margin_increase / old_margin * Decimal("100")

        # Calculate tier boundaries crossed
        tiers_crossed = abs(new_tier.tier_number - old_tier.tier_number)
        crosses_boundary = old_tier.tier_number != new_tier.tier_number

        # Determine boundary crossed
        boundary_crossed = None
        if crosses_boundary:
            if new_tier.tier_number > old_tier.tier_number:
                # Upward transition - crossed into new_tier
                boundary_crossed = self._format_currency(new_tier.min_notional)
            else:
                # Downward transition - crossed into old_tier
                boundary_crossed = self._format_currency(old_tier.min_notional)

        # Calculate max leverages
        old_max_lev = int(Decimal("1") / old_tier.margin_rate)
        new_max_lev = int(Decimal("1") / new_tier.margin_rate)
        leverage_reduced = new_max_lev < old_max_lev

        # Determine if improvement (lower tier = better)
        is_improvement = new_tier.tier_number < old_tier.tier_number

        # Determine warning level
        warning_level = self._determine_warning_level(tiers_crossed, is_improvement)

        # Generate message
        message = self._generate_tier_change_message(
            old_tier, new_tier, margin_increase, crosses_boundary
        )

        return TierChangePreview(
            old_tier=old_tier.tier_number,
            new_tier=new_tier.tier_number,
            crosses_boundary=crosses_boundary,
            tiers_crossed=tiers_crossed,
            boundary_crossed=boundary_crossed,
            old_margin_rate=self._format_percentage(old_tier.margin_rate),
            new_margin_rate=self._format_percentage(new_tier.margin_rate),
            margin_increase=self._format_currency(margin_increase),
            margin_increase_percent=f"{margin_increase_percent:.1f}%",
            old_max_leverage=f"{old_max_lev}x",
            new_max_leverage=f"{new_max_lev}x",
            leverage_reduced=leverage_reduced,
            is_improvement=is_improvement,
            warning_level=warning_level,
            message=message,
        )

    def preview_tier_change_with_liquidation(
        self,
        old_notional: Decimal,
        new_notional: Decimal,
        entry_price: Decimal,
        leverage: Decimal,
        side: str,
    ) -> TierChangePreview:
        """
        Preview tier change with liquidation price impact.

        Args:
            old_notional: Current position size
            new_notional: New position size
            entry_price: Entry price
            leverage: Leverage used
            side: 'long' or 'short'

        Returns:
            TierChangePreview with liquidation prices
        """
        # Get base preview
        preview = self.preview_tier_change(old_notional, new_notional)

        # Calculate position sizes
        old_position_size = old_notional / entry_price
        new_position_size = new_notional / entry_price

        # Calculate liquidation prices
        old_liq = self.calculator.calculate_liquidation_price(
            entry_price, old_position_size, leverage, side
        )
        new_liq = self.calculator.calculate_liquidation_price(
            entry_price, new_position_size, leverage, side
        )

        # Update preview with liquidation info
        preview.old_liquidation_price = self._format_currency(old_liq)
        preview.new_liquidation_price = self._format_currency(new_liq)

        return preview

    def get_tier_tooltip(self, notional: Decimal) -> str:
        """
        Generate educational tooltip for tier.

        Args:
            notional: Position size

        Returns:
            Markdown-formatted tooltip text
        """
        tier = self.calculator.get_tier_for_position(notional)
        return self._generate_tooltip(notional, tier)

    def tier_breakdown(self, notional: Decimal) -> dict:
        """
        Provide detailed breakdown of margin calculation.

        Args:
            notional: Position size

        Returns:
            Dictionary with calculation breakdown
        """
        tier = self.calculator.get_tier_for_position(notional)
        margin = self.calculator.calculate_margin(notional)

        # Calculate components
        rate_component = notional * tier.margin_rate
        ma_component = tier.maintenance_amount

        return {
            "notional": self._format_currency(notional),
            "tier": tier.tier_number,
            "margin_rate": self._format_percentage(tier.margin_rate),
            "rate_component": self._format_currency(rate_component),
            "maintenance_amount": self._format_currency(ma_component),
            "total_margin": self._format_currency(margin),
            "formula": f"{self._format_currency(notional)} × {self._format_percentage(tier.margin_rate)} - {self._format_currency(ma_component)} = {self._format_currency(margin)}",
        }

    def generate_tier_comparison_table(
        self,
        symbol: str,
        current_notional: Optional[Decimal] = None,
    ) -> TierComparisonTable:
        """
        Generate comparison table of all tiers.

        Args:
            symbol: Trading pair symbol
            current_notional: Current position size (optional)

        Returns:
            TierComparisonTable with all tiers
        """
        current_tier_number = None
        if current_notional:
            current_tier = self.calculator.get_tier_for_position(current_notional)
            current_tier_number = current_tier.tier_number

        rows = []
        for tier in self.config.tiers:
            max_lev = int(Decimal("1") / tier.margin_rate)
            is_current = tier.tier_number == current_tier_number if current_tier_number else False

            row = TierComparisonRow(
                tier_number=tier.tier_number,
                notional_range=f"{self._format_currency(tier.min_notional)} - {self._format_currency(tier.max_notional)}",
                margin_rate=self._format_percentage(tier.margin_rate),
                maintenance_amount=self._format_currency(tier.maintenance_amount),
                max_leverage=f"{max_lev}x",
                is_current=is_current,
            )
            rows.append(row)

        return TierComparisonTable(
            symbol=symbol,
            current_position=self._format_currency(current_notional) if current_notional else "N/A",
            current_tier=current_tier_number or 0,
            tiers=rows,
        )

    # Private helper methods

    def _format_currency(self, amount: Decimal) -> str:
        """Format Decimal as currency string."""
        # Round to 2 decimal places
        rounded = amount.quantize(Decimal("0.01"))
        # Add thousands separator
        return f"${rounded:,.2f}"

    def _format_percentage(self, rate: Decimal) -> str:
        """Format Decimal rate as percentage string."""
        percent = rate * Decimal("100")
        # Use 1 decimal place for cleaner display
        return f"{percent:.1f}%"

    def _generate_tooltip(self, notional: Decimal, tier: MarginTier) -> str:
        """Generate educational tooltip text."""
        tier_index = self.config.tiers.index(tier)
        is_max_tier = tier_index == len(self.config.tiers) - 1

        max_lev = int(Decimal("1") / tier.margin_rate)

        # Base explanation
        tooltip = f"**Tier {tier.tier_number}** applies to positions from {self._format_currency(tier.min_notional)} to {self._format_currency(tier.max_notional)}.\n\n"
        tooltip += f"**Maintenance Margin Rate**: {self._format_percentage(tier.margin_rate)}\n"
        tooltip += f"**Maximum Leverage**: {max_lev}x\n\n"

        # Check if near boundary and add warning
        if not is_max_tier:
            tier_range = tier.max_notional - tier.min_notional
            distance_from_max = tier.max_notional - notional
            percent_from_max = (distance_from_max / tier_range) * Decimal("100")

            if percent_from_max <= Decimal("10"):  # Within 10% of next tier
                next_tier = self.config.tiers[tier_index + 1]
                tooltip += f"⚠️ **You are approaching Tier {next_tier.tier_number}** ({self._format_currency(distance_from_max)} away). Margin rate will increase to {self._format_percentage(next_tier.margin_rate)}.\n\n"

        # Explain formula
        tooltip += "Your maintenance margin is calculated as:\n"
        tooltip += f"`margin = position × {self._format_percentage(tier.margin_rate)} - {self._format_currency(tier.maintenance_amount)}`\n\n"

        # Show example calculation with actual position
        margin_example = notional * tier.margin_rate - tier.maintenance_amount
        tooltip += f"For your position of {self._format_currency(notional)}:\n"
        tooltip += f"`margin = {self._format_currency(notional)} × {self._format_percentage(tier.margin_rate)} - {self._format_currency(tier.maintenance_amount)} = {self._format_currency(margin_example)}`\n\n"

        # Explain continuity
        tooltip += "The formula ensures *continuous* margin requirements - no sudden jumps when crossing tier boundaries.\n\n"

        # Next tier preview or max tier note
        if not is_max_tier:
            next_tier = self.config.tiers[tier_index + 1]
            next_max_lev = int(Decimal("1") / next_tier.margin_rate)
            tooltip += f"**Next Tier ({tier.tier_number + 1})**: Above {self._format_currency(next_tier.min_notional)}, margin rate increases to {self._format_percentage(next_tier.margin_rate)} (max {next_max_lev}x leverage).\n\n"
        else:
            tooltip += f"**Highest Tier**: You're in the maximum tier. Positions above {self._format_currency(tier.max_notional)} stay in this tier.\n\n"

        # Liquidation impact
        tooltip += "Higher margin rates mean higher liquidation risk for leveraged positions.\n\n"

        # Risk disclaimer
        tooltip += "*Margin requirements are subject to change. Learn more in [Binance documentation](https://www.binance.com/en/support/faq/liquidation).*"

        return tooltip

    def _generate_boundary_warning(
        self,
        notional: Decimal,
        tier: MarginTier,
    ) -> Optional[str]:
        """Generate warning if near tier boundary."""
        tier_index = self.config.tiers.index(tier)

        # Check if near upper boundary (within 5%)
        tier_range = tier.max_notional - tier.min_notional
        distance_from_max = tier.max_notional - notional
        percent_from_max = (distance_from_max / tier_range) * Decimal("100")

        if percent_from_max <= Decimal("5") and tier_index < len(self.config.tiers) - 1:
            next_tier = self.config.tiers[tier_index + 1]
            return (
                f"⚠️ Approaching Tier {next_tier.tier_number} boundary. "
                f"Margin rate will increase to {self._format_percentage(next_tier.margin_rate)} "
                f"above {self._format_currency(next_tier.min_notional)}."
            )

        return None

    def _determine_warning_level(
        self,
        tiers_crossed: int,
        is_improvement: bool,
    ) -> str:
        """Determine warning severity level."""
        if is_improvement:
            return "info"  # Improvement is always just info
        if tiers_crossed == 0:
            return "info"  # Same tier
        elif tiers_crossed == 1:
            return "warning"  # One tier jump
        else:
            return "critical"  # Multiple tier jump

    def _generate_tier_change_message(
        self,
        old_tier: MarginTier,
        new_tier: MarginTier,
        margin_increase: Decimal,
        crosses_boundary: bool,
    ) -> str:
        """Generate user-friendly tier change message."""
        if not crosses_boundary:
            # Same tier
            return (
                f"Position remains in Tier {old_tier.tier_number}. "
                f"Margin requirement increased by {self._format_currency(margin_increase)}."
            )

        if new_tier.tier_number > old_tier.tier_number:
            # Upward (worse) transition
            return (
                f"Position increased from Tier {old_tier.tier_number} to Tier {new_tier.tier_number}. "
                f"Margin requirement increased by {self._format_currency(margin_increase)} "
                f"({self._format_percentage((margin_increase / (new_tier.margin_rate * new_tier.min_notional)) * Decimal('100'))})."
            )
        else:
            # Downward (better) transition
            margin_decrease = abs(margin_increase)
            return (
                f"Position decreased from Tier {old_tier.tier_number} to Tier {new_tier.tier_number}. "
                f"Margin requirement decreased by {self._format_currency(margin_decrease)}. "
                f"✓ Lower margin requirements."
            )
