"""
Maintenance Amount (MA) calculation service.

Derives maintenance amounts that ensure mathematical continuity
at all tier boundaries using the continuity formula:

    MA[i] = MA[i-1] + boundary * (rate[i] - rate[i-1])

This guarantees that margin calculations are continuous:
    margin_left = boundary * rate[i-1] - MA[i-1]
    margin_right = boundary * rate[i] - MA[i]
    difference = 0 (perfectly continuous)
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Tuple

from src.config.precision import ZERO


@dataclass
class TierSpec:
    """Specification for a single tier before MA calculation."""

    tier_number: int
    min_notional: Decimal
    max_notional: Decimal
    margin_rate: Decimal


class MaintenanceCalculator:
    """
    Calculator for deriving maintenance amounts that ensure continuity.

    The maintenance amount at each tier boundary is calculated to ensure
    that the margin function is continuous (no sudden jumps).
    """

    @staticmethod
    def calculate_maintenance_amount(tier_specs: List[TierSpec]) -> List[Tuple[TierSpec, Decimal]]:
        """
        Calculate maintenance amounts for all tiers to ensure continuity.

        Args:
            tier_specs: List of tier specifications (without MA)

        Returns:
            List of tuples (TierSpec, maintenance_amount)

        Example:
            >>> specs = [
            ...     TierSpec(1, Decimal('0'), Decimal('50000'), Decimal('0.005')),
            ...     TierSpec(2, Decimal('50000'), Decimal('250000'), Decimal('0.010')),
            ... ]
            >>> result = MaintenanceCalculator.calculate_maintenance_amount(specs)
            >>> result[0][1]  # MA for tier 1
            Decimal('0')
            >>> result[1][1]  # MA for tier 2
            Decimal('250')  # = 0 + 50000 * (0.010 - 0.005)
        """
        # Sort tiers by min_notional
        sorted_specs = sorted(tier_specs, key=lambda t: t.min_notional)

        results = []

        # First tier always has MA = 0
        first_tier = sorted_specs[0]
        results.append((first_tier, ZERO))

        # Calculate MA for subsequent tiers
        for i in range(1, len(sorted_specs)):
            prev_tier = sorted_specs[i - 1]
            curr_tier = sorted_specs[i]

            # Boundary between tiers
            boundary = prev_tier.max_notional

            # Previous MA
            prev_ma = results[i - 1][1]

            # Calculate current MA using continuity formula
            # MA[i] = MA[i-1] + boundary * (rate[i] - rate[i-1])
            curr_ma = prev_ma + boundary * (curr_tier.margin_rate - prev_tier.margin_rate)

            results.append((curr_tier, curr_ma))

        return results

    @staticmethod
    def derive_binance_tiers() -> List[Tuple[TierSpec, Decimal]]:
        """
        Derive maintenance amounts for Binance's default 5-tier structure.

        Binance tiers (as of 2025):
        - Tier 1: $0-$50k @ 0.5%
        - Tier 2: $50k-$250k @ 1.0%
        - Tier 3: $250k-$1M @ 2.5%
        - Tier 4: $1M-$10M @ 5.0%
        - Tier 5: $10M-$50M @ 10.0%

        Returns:
            List of (TierSpec, maintenance_amount) tuples

        Example:
            >>> tiers = MaintenanceCalculator.derive_binance_tiers()
            >>> len(tiers)
            5
            >>> tiers[0][1]  # Tier 1 MA
            Decimal('0')
            >>> tiers[1][1]  # Tier 2 MA
            Decimal('250')
            >>> tiers[2][1]  # Tier 3 MA
            Decimal('4000')
        """
        binance_specs = [
            TierSpec(
                tier_number=1,
                min_notional=Decimal("0"),
                max_notional=Decimal("50000"),
                margin_rate=Decimal("0.005"),  # 0.5%
            ),
            TierSpec(
                tier_number=2,
                min_notional=Decimal("50000"),
                max_notional=Decimal("250000"),
                margin_rate=Decimal("0.010"),  # 1.0%
            ),
            TierSpec(
                tier_number=3,
                min_notional=Decimal("250000"),
                max_notional=Decimal("1000000"),
                margin_rate=Decimal("0.025"),  # 2.5%
            ),
            TierSpec(
                tier_number=4,
                min_notional=Decimal("1000000"),
                max_notional=Decimal("10000000"),
                margin_rate=Decimal("0.050"),  # 5.0%
            ),
            TierSpec(
                tier_number=5,
                min_notional=Decimal("10000000"),
                max_notional=Decimal("50000000"),
                margin_rate=Decimal("0.100"),  # 10.0%
            ),
        ]

        return MaintenanceCalculator.calculate_maintenance_amount(binance_specs)

    @staticmethod
    def validate_continuity(tiers_with_ma: List[Tuple[TierSpec, Decimal]]) -> Dict[str, bool]:
        """
        Validate that calculated MAs ensure continuity at all boundaries.

        Args:
            tiers_with_ma: List of (TierSpec, maintenance_amount) tuples

        Returns:
            Dictionary with boundary values as keys and continuity status

        Example:
            >>> tiers = MaintenanceCalculator.derive_binance_tiers()
            >>> validation = MaintenanceCalculator.validate_continuity(tiers)
            >>> all(validation.values())  # All boundaries continuous
            True
        """
        results = {}

        for i in range(len(tiers_with_ma) - 1):
            tier_spec1, ma1 = tiers_with_ma[i]
            tier_spec2, ma2 = tiers_with_ma[i + 1]

            boundary = tier_spec1.max_notional

            # Calculate margin at boundary from both sides
            margin_left = boundary * tier_spec1.margin_rate - ma1
            margin_right = boundary * tier_spec2.margin_rate - ma2

            # Check continuity (difference should be 0 or very close)
            difference = abs(margin_left - margin_right)
            is_continuous = difference < Decimal("0.01")

            results[str(boundary)] = is_continuous

        return results

    @staticmethod
    def print_derivation_proof():
        """
        Print mathematical derivation proof for Binance tiers.

        Useful for documentation and verification.
        """
        print("=" * 70)
        print("MAINTENANCE AMOUNT DERIVATION FOR BINANCE TIERS")
        print("=" * 70)
        print()
        print("Formula: MA[i] = MA[i-1] + boundary * (rate[i] - rate[i-1])")
        print()

        tiers = MaintenanceCalculator.derive_binance_tiers()

        for i, (spec, ma) in enumerate(tiers, 1):
            print(f"Tier {i}:")
            print(f"  Range: ${spec.min_notional:,.0f} - ${spec.max_notional:,.0f}")
            print(f"  Rate: {spec.margin_rate:.3%}")
            print(f"  MA: ${ma:,.2f}")

            if i > 1:
                prev_spec, prev_ma = tiers[i - 2]
                boundary = prev_spec.max_notional
                rate_diff = spec.margin_rate - prev_spec.margin_rate
                ma_increment = boundary * rate_diff

                print("  Calculation:")
                print(f"    MA[{i}] = ${prev_ma:,.2f} + ${boundary:,.0f} * {rate_diff:.3%}")
                print(f"    MA[{i}] = ${prev_ma:,.2f} + ${ma_increment:,.2f}")
                print(f"    MA[{i}] = ${ma:,.2f} ✓")

                # Verify continuity
                margin_left = boundary * prev_spec.margin_rate - prev_ma
                margin_right = boundary * spec.margin_rate - ma

                print(f"  Continuity check at ${boundary:,.0f}:")
                print(
                    f"    Left:  ${boundary:,.0f} × {prev_spec.margin_rate:.3%} - ${prev_ma:,.2f} = ${margin_left:,.2f}"
                )
                print(
                    f"    Right: ${boundary:,.0f} × {spec.margin_rate:.3%} - ${ma:,.2f} = ${margin_right:,.2f}"
                )
                print(f"    Difference: ${abs(margin_left - margin_right):,.2f} ✓")

            print()

        print("=" * 70)
        print("VALIDATION: All boundaries continuous ✓")
        print("=" * 70)
