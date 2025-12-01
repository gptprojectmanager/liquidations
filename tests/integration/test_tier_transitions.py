"""
Integration tests for tier boundary transitions.

Tests positions near tier boundaries to verify:
- Mathematical continuity (no sudden jumps)
- Smooth margin transitions
- Correct tier selection at boundaries
- Precision at critical points
"""

from decimal import Decimal

import pytest

from src.models.tier_config import TierConfiguration
from src.services.maintenance_calculator import MaintenanceCalculator
from src.services.margin_calculator import MarginCalculator


class TestTierTransitions:
    """Test suite for tier boundary transition behavior."""

    @pytest.fixture
    def binance_config(self) -> TierConfiguration:
        """Create Binance tier configuration with derived MAs."""
        tiers_with_ma = MaintenanceCalculator.derive_binance_tiers()

        from src.models.margin_tier import MarginTier

        tiers = [
            MarginTier(
                symbol="BTCUSDT",
                tier_number=spec.tier_number,
                min_notional=spec.min_notional,
                max_notional=spec.max_notional,
                margin_rate=spec.margin_rate,
                maintenance_amount=ma,
            )
            for spec, ma in tiers_with_ma
        ]

        return TierConfiguration(
            symbol="BTCUSDT",
            version="binance-2025-v1",
            tiers=tiers,
        )

    def test_tier_3_to_4_transition_999k_to_1001k(self, binance_config):
        """
        Test smooth transition from Tier 3 to Tier 4 at $1M boundary.

        User Story 1 Acceptance Criteria:
        - Position just below boundary: $999,000 (Tier 3)
        - Position just above boundary: $1,001,000 (Tier 4)
        - Margin difference should be small and continuous
        - No sudden jumps in margin requirement
        """
        calculator = MarginCalculator(binance_config)

        # Position $1k below boundary (Tier 3)
        position_below = Decimal("999000")
        margin_below = calculator.calculate_margin(position_below)

        # Position $1k above boundary (Tier 4)
        position_above = Decimal("1001000")
        margin_above = calculator.calculate_margin(position_above)

        # Calculate expected margins
        # Tier 3: $999k * 0.025 - $4,000 = $20,975
        # Tier 4: $1,001k * 0.05 - $29,000 = $21,050
        expected_below = Decimal("20975")
        expected_above = Decimal("21050")

        assert margin_below == expected_below, (
            f"Margin below boundary incorrect: got ${margin_below}, expected ${expected_below}"
        )
        assert margin_above == expected_above, (
            f"Margin above boundary incorrect: got ${margin_above}, expected ${expected_above}"
        )

        # Verify smooth transition (margin difference should be small)
        margin_diff = margin_above - margin_below
        expected_diff = Decimal("75")  # $21,050 - $20,975

        assert margin_diff == expected_diff, (
            f"Transition not smooth: margin jumped by ${margin_diff}, expected ${expected_diff}"
        )

        # Verify no sudden percentage change (should be <1% change per $1k)
        percent_change = (margin_diff / margin_below) * 100
        assert percent_change < Decimal("1"), (
            f"Margin changed by {percent_change}% across $2k transition (should be <1%)"
        )

    def test_exact_1m_boundary_continuity(self, binance_config):
        """
        Test exact $1M boundary point.

        Continuity Test:
        - At exactly $1,000,000:
        - Tier 3 calculation: $1M * 0.025 - $4,000 = $21,000
        - Tier 4 calculation: $1M * 0.05 - $29,000 = $21,000
        - Both must produce identical result
        """
        calculator = MarginCalculator(binance_config)
        boundary = Decimal("1000000")

        margin_at_boundary = calculator.calculate_margin(boundary)
        expected_margin = Decimal("21000")

        assert margin_at_boundary == expected_margin, (
            f"Boundary continuity broken: got ${margin_at_boundary}, expected ${expected_margin}"
        )

    def test_all_boundary_continuity(self, binance_config):
        """
        Test continuity at all 4 tier boundaries.

        Boundaries:
        - $50k (Tier 1 → Tier 2): $250
        - $250k (Tier 2 → Tier 3): $2,250
        - $1M (Tier 3 → Tier 4): $21,000
        - $10M (Tier 4 → Tier 5): $471,000
        """
        calculator = MarginCalculator(binance_config)

        boundaries = [
            (Decimal("50000"), Decimal("250")),
            (Decimal("250000"), Decimal("2250")),
            (Decimal("1000000"), Decimal("21000")),
            (Decimal("10000000"), Decimal("471000")),
        ]

        for boundary, expected_margin in boundaries:
            margin = calculator.calculate_margin(boundary)

            assert margin == expected_margin, (
                f"Continuity broken at ${boundary}: got ${margin}, expected ${expected_margin}"
            )

    def test_micro_transitions_around_1m(self, binance_config):
        """
        Test micro-transitions around $1M boundary.

        Fine-Grained Test:
        - Test positions: $999,990, $999,995, $1,000,000, $1,000,005, $1,000,010
        - Verify smooth, linear-like progression
        - No discontinuities or jumps
        """
        calculator = MarginCalculator(binance_config)

        positions = [
            Decimal("999990"),
            Decimal("999995"),
            Decimal("1000000"),
            Decimal("1000005"),
            Decimal("1000010"),
        ]

        margins = [calculator.calculate_margin(pos) for pos in positions]

        # Verify all margins are strictly increasing
        for i in range(len(margins) - 1):
            assert margins[i] < margins[i + 1], (
                f"Margin not increasing: ${positions[i]} → ${margins[i]}, "
                f"${positions[i + 1]} → ${margins[i + 1]}"
            )

        # Verify rate of change is reasonable (no sudden jumps)
        for i in range(len(margins) - 1):
            delta_margin = margins[i + 1] - margins[i]
            delta_position = positions[i + 1] - positions[i]

            # Effective rate should be between 2.5% and 5% (between tier rates)
            effective_rate = delta_margin / delta_position

            assert Decimal("0.025") <= effective_rate <= Decimal("0.05"), (
                f"Effective rate {effective_rate} out of bounds at ${positions[i]}"
            )

    def test_transition_from_tier_1_to_2(self, binance_config):
        """
        Test transition at $50k boundary (Tier 1 → Tier 2).

        Low-End Transition:
        - $49,000 (Tier 1): $49k * 0.005 - $0 = $245
        - $51,000 (Tier 2): $51k * 0.010 - $250 = $260
        """
        calculator = MarginCalculator(binance_config)

        position_tier1 = Decimal("49000")
        position_tier2 = Decimal("51000")

        margin_tier1 = calculator.calculate_margin(position_tier1)
        margin_tier2 = calculator.calculate_margin(position_tier2)

        expected_tier1 = Decimal("245")  # 49k * 0.005
        expected_tier2 = Decimal("260")  # 51k * 0.01 - 250

        assert margin_tier1 == expected_tier1
        assert margin_tier2 == expected_tier2

        # Verify smooth transition ($15 increase for $2k position increase)
        margin_diff = margin_tier2 - margin_tier1
        assert margin_diff == Decimal("15")

    def test_transition_from_tier_2_to_3(self, binance_config):
        """
        Test transition at $250k boundary (Tier 2 → Tier 3).

        Mid-Range Transition:
        - $248,000 (Tier 2): $248k * 0.010 - $250 = $2,230
        - $252,000 (Tier 3): $252k * 0.025 - $4,000 = $2,300
        """
        calculator = MarginCalculator(binance_config)

        position_tier2 = Decimal("248000")
        position_tier3 = Decimal("252000")

        margin_tier2 = calculator.calculate_margin(position_tier2)
        margin_tier3 = calculator.calculate_margin(position_tier3)

        expected_tier2 = Decimal("2230")  # 248k * 0.01 - 250
        expected_tier3 = Decimal("2300")  # 252k * 0.025 - 4000

        assert margin_tier2 == expected_tier2
        assert margin_tier3 == expected_tier3

        # Verify smooth transition ($70 increase for $4k position increase)
        margin_diff = margin_tier3 - margin_tier2
        assert margin_diff == Decimal("70")

    def test_transition_from_tier_4_to_5(self, binance_config):
        """
        Test transition at $10M boundary (Tier 4 → Tier 5).

        High-End Transition:
        - $9,900,000 (Tier 4): $9.9M * 0.05 - $29,000 = $466,000
        - $10,100,000 (Tier 5): $10.1M * 0.10 - $529,000 = $481,000
        """
        calculator = MarginCalculator(binance_config)

        position_tier4 = Decimal("9900000")
        position_tier5 = Decimal("10100000")

        margin_tier4 = calculator.calculate_margin(position_tier4)
        margin_tier5 = calculator.calculate_margin(position_tier5)

        expected_tier4 = Decimal("466000")  # 9.9M * 0.05 - 29k
        expected_tier5 = Decimal("481000")  # 10.1M * 0.1 - 529k

        assert margin_tier4 == expected_tier4
        assert margin_tier5 == expected_tier5

        # Verify smooth transition ($15k increase for $200k position increase)
        margin_diff = margin_tier5 - margin_tier4
        assert margin_diff == Decimal("15000")

    def test_sequential_tier_walk(self, binance_config):
        """
        Test walking through all tiers sequentially.

        Full Range Test:
        - Start at $10k (Tier 1)
        - Walk through representative positions in each tier
        - Verify margins always increase monotonically
        """
        calculator = MarginCalculator(binance_config)

        positions = [
            Decimal("10000"),  # Tier 1
            Decimal("50000"),  # Tier 1 → Tier 2 boundary
            Decimal("100000"),  # Tier 2
            Decimal("250000"),  # Tier 2 → Tier 3 boundary
            Decimal("500000"),  # Tier 3
            Decimal("1000000"),  # Tier 3 → Tier 4 boundary
            Decimal("5000000"),  # Tier 4
            Decimal("10000000"),  # Tier 4 → Tier 5 boundary
            Decimal("20000000"),  # Tier 5
        ]

        margins = [calculator.calculate_margin(pos) for pos in positions]

        # Verify strictly increasing margins
        for i in range(len(margins) - 1):
            assert margins[i] < margins[i + 1], (
                f"Margin not monotonic: ${positions[i]} → ${margins[i]}, "
                f"${positions[i + 1]} → ${margins[i + 1]}"
            )
