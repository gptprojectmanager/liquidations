"""
Unit tests for MaintenanceCalculator service.

Tests the derivation of maintenance amounts that ensure continuity.
"""

from decimal import Decimal

from src.config.precision import ZERO
from src.services.maintenance_calculator import MaintenanceCalculator, TierSpec


class TestMaintenanceCalculator:
    """Test suite for MaintenanceCalculator."""

    def test_first_tier_has_zero_ma(self):
        """First tier should always have MA = 0."""
        specs = [
            TierSpec(1, Decimal("0"), Decimal("50000"), Decimal("0.005")),
        ]

        result = MaintenanceCalculator.calculate_maintenance_amount(specs)

        assert result[0][1] == ZERO

    def test_second_tier_ma_calculation(self):
        """Test MA calculation for second tier."""
        specs = [
            TierSpec(1, Decimal("0"), Decimal("50000"), Decimal("0.005")),
            TierSpec(2, Decimal("50000"), Decimal("250000"), Decimal("0.010")),
        ]

        result = MaintenanceCalculator.calculate_maintenance_amount(specs)

        # MA[2] = 0 + 50000 * (0.010 - 0.005) = 250
        expected_ma2 = Decimal("250")
        assert result[1][1] == expected_ma2

    def test_third_tier_ma_calculation(self):
        """Test MA calculation for third tier."""
        specs = [
            TierSpec(1, Decimal("0"), Decimal("50000"), Decimal("0.005")),
            TierSpec(2, Decimal("50000"), Decimal("250000"), Decimal("0.010")),
            TierSpec(3, Decimal("250000"), Decimal("1000000"), Decimal("0.025")),
        ]

        result = MaintenanceCalculator.calculate_maintenance_amount(specs)

        # MA[2] = 250
        # MA[3] = 250 + 250000 * (0.025 - 0.010) = 250 + 3750 = 4000
        expected_ma3 = Decimal("4000")
        assert result[2][1] == expected_ma3

    def test_binance_tier_derivation(self):
        """Test derivation of all 5 Binance tiers."""
        tiers = MaintenanceCalculator.derive_binance_tiers()

        assert len(tiers) == 5

        # Expected MAs for Binance tiers
        expected_mas = [
            Decimal("0"),  # Tier 1
            Decimal("250"),  # Tier 2
            Decimal("4000"),  # Tier 3
            Decimal("29000"),  # Tier 4
            Decimal("529000"),  # Tier 5
        ]

        for i, (spec, ma) in enumerate(tiers):
            assert ma == expected_mas[i], (
                f"Tier {i + 1} MA mismatch: got {ma}, expected {expected_mas[i]}"
            )

    def test_continuity_validation_passes(self):
        """Test that Binance tiers pass continuity validation."""
        tiers = MaintenanceCalculator.derive_binance_tiers()
        validation = MaintenanceCalculator.validate_continuity(tiers)

        # All boundaries should be continuous
        assert all(validation.values()), f"Some boundaries not continuous: {validation}"

    def test_continuity_at_50k_boundary(self):
        """Test mathematical continuity at $50k boundary."""
        tiers = MaintenanceCalculator.derive_binance_tiers()

        tier1_spec, ma1 = tiers[0]
        tier2_spec, ma2 = tiers[1]

        boundary = Decimal("50000")

        # Calculate margin from both sides
        margin_left = boundary * tier1_spec.margin_rate - ma1
        margin_right = boundary * tier2_spec.margin_rate - ma2

        # Should be identical
        assert margin_left == margin_right
        assert margin_left == Decimal("250")

    def test_continuity_at_250k_boundary(self):
        """Test mathematical continuity at $250k boundary."""
        tiers = MaintenanceCalculator.derive_binance_tiers()

        tier2_spec, ma2 = tiers[1]
        tier3_spec, ma3 = tiers[2]

        boundary = Decimal("250000")

        margin_left = boundary * tier2_spec.margin_rate - ma2
        margin_right = boundary * tier3_spec.margin_rate - ma3

        assert margin_left == margin_right
        assert margin_left == Decimal("2250")

    def test_continuity_at_1m_boundary(self):
        """Test mathematical continuity at $1M boundary."""
        tiers = MaintenanceCalculator.derive_binance_tiers()

        tier3_spec, ma3 = tiers[2]
        tier4_spec, ma4 = tiers[3]

        boundary = Decimal("1000000")

        margin_left = boundary * tier3_spec.margin_rate - ma3
        margin_right = boundary * tier4_spec.margin_rate - ma4

        assert margin_left == margin_right
        assert margin_left == Decimal("21000")

    def test_continuity_at_10m_boundary(self):
        """Test mathematical continuity at $10M boundary."""
        tiers = MaintenanceCalculator.derive_binance_tiers()

        tier4_spec, ma4 = tiers[3]
        tier5_spec, ma5 = tiers[4]

        boundary = Decimal("10000000")

        margin_left = boundary * tier4_spec.margin_rate - ma4
        margin_right = boundary * tier5_spec.margin_rate - ma5

        assert margin_left == margin_right
        assert margin_left == Decimal("471000")

    def test_unsorted_tiers_get_sorted(self):
        """Test that tiers are automatically sorted by min_notional."""
        specs = [
            TierSpec(2, Decimal("50000"), Decimal("250000"), Decimal("0.010")),
            TierSpec(1, Decimal("0"), Decimal("50000"), Decimal("0.005")),
        ]

        result = MaintenanceCalculator.calculate_maintenance_amount(specs)

        # Should be sorted by min_notional
        assert result[0][0].tier_number == 1
        assert result[1][0].tier_number == 2

    def test_custom_tiers_continuity(self):
        """Test MA calculation for custom tier structure."""
        specs = [
            TierSpec(1, Decimal("0"), Decimal("100000"), Decimal("0.01")),
            TierSpec(2, Decimal("100000"), Decimal("500000"), Decimal("0.02")),
            TierSpec(3, Decimal("500000"), Decimal("2000000"), Decimal("0.05")),
        ]

        result = MaintenanceCalculator.calculate_maintenance_amount(specs)

        # MA[1] = 0
        # MA[2] = 0 + 100000 * (0.02 - 0.01) = 1000
        # MA[3] = 1000 + 500000 * (0.05 - 0.02) = 1000 + 15000 = 16000

        assert result[0][1] == Decimal("0")
        assert result[1][1] == Decimal("1000")
        assert result[2][1] == Decimal("16000")

        # Verify continuity
        validation = MaintenanceCalculator.validate_continuity(result)
        assert all(validation.values())

    def test_ma_formula_property(self):
        """Test that MA formula maintains the continuity property."""
        tiers = MaintenanceCalculator.derive_binance_tiers()

        for i in range(len(tiers) - 1):
            spec1, ma1 = tiers[i]
            spec2, ma2 = tiers[i + 1]

            boundary = spec1.max_notional

            # The continuity condition:
            # boundary * rate1 - MA1 = boundary * rate2 - MA2
            # Rearranging: MA2 = MA1 + boundary * (rate2 - rate1)

            expected_ma2 = ma1 + boundary * (spec2.margin_rate - spec1.margin_rate)

            assert ma2 == expected_ma2, f"MA formula violation at tier {i + 1}/{i + 2} boundary"

    def test_print_derivation_proof(self, capsys):
        """Test that derivation proof prints correctly."""
        MaintenanceCalculator.print_derivation_proof()

        captured = capsys.readouterr()

        # Check that output contains expected elements
        assert "MAINTENANCE AMOUNT DERIVATION" in captured.out
        assert "Tier 1:" in captured.out
        assert "Tier 5:" in captured.out
        assert "VALIDATION: All boundaries continuous ✓" in captured.out
