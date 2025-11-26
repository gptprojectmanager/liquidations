"""
Unit tests for Decimal128 precision in financial calculations.

Tests extreme position sizes to verify:
- No floating-point precision loss
- Accurate calculations at $1B+ scale
- Proper handling of fractional cents
- Decimal arithmetic correctness
"""

from decimal import Decimal, getcontext

from src.config.precision import ZERO, ensure_decimal
from src.models.margin_tier import MarginTier


class TestDecimalPrecision:
    """Test suite for Decimal128 precision guarantees."""

    def test_decimal_context_precision(self):
        """
        Verify that decimal context is set to 28 digits (Decimal128).

        Precision Requirement (FR-008):
        - MUST use Decimal128 precision (28 significant digits)
        - getcontext().prec should be 28
        """
        context = getcontext()

        assert context.prec == 28, f"Decimal precision is {context.prec}, expected 28"

    def test_ensure_decimal_conversion(self):
        """
        Test ensure_decimal() converts various numeric types correctly.

        Type Conversion:
        - int → Decimal
        - float → Decimal (via string to avoid precision loss)
        - str → Decimal
        - Decimal → Decimal (passthrough)
        """
        # Integer conversion
        assert ensure_decimal(1000000) == Decimal("1000000")

        # Float conversion (should go through string)
        assert ensure_decimal(0.005) == Decimal("0.005")

        # String conversion
        assert ensure_decimal("123456.789") == Decimal("123456.789")

        # Decimal passthrough
        original = Decimal("999.99")
        assert ensure_decimal(original) is original

    def test_large_position_no_precision_loss(self):
        """
        Test $1 billion position maintains full precision.

        Large Position Test:
        - Position: $1,000,000,000 (Tier 5 @ 10%)
        - MA: $529,000
        - Expected Margin: $1B * 0.10 - $529,000 = $99,471,000
        - Must be exact, no rounding errors
        """
        tier = MarginTier(
            symbol="BTCUSDT",
            tier_number=5,
            min_notional=Decimal("10000000"),
            max_notional=Decimal("50000000000"),  # $50B max
            margin_rate=Decimal("0.100"),
            maintenance_amount=Decimal("529000"),
        )

        position = Decimal("1000000000")  # $1B
        margin = tier.calculate_margin(position)

        expected = Decimal("99471000")  # $1B * 0.1 - $529k

        # Must be EXACTLY equal (no tolerance)
        assert margin == expected, (
            f"Precision lost at $1B: got ${margin}, expected ${expected}, "
            f"difference: ${abs(margin - expected)}"
        )

    def test_fractional_cents_preserved(self):
        """
        Test that fractional cents are preserved in calculations.

        Fractional Precision:
        - Position: $12,345.67
        - Tier 1 @ 0.5%
        - Expected: $12,345.67 * 0.005 - $0 = $61.72835
        - All 5 decimal places preserved
        """
        tier = MarginTier(
            symbol="BTCUSDT",
            tier_number=1,
            min_notional=Decimal("0"),
            max_notional=Decimal("50000"),
            margin_rate=Decimal("0.005"),
            maintenance_amount=ZERO,
        )

        position = Decimal("12345.67")
        margin = tier.calculate_margin(position)

        expected = Decimal("61.72835")

        assert margin == expected, f"Fractional cents lost: got ${margin}, expected ${expected}"

    def test_micro_position_precision(self):
        """
        Test very small positions (micro positions).

        Micro Position Test:
        - Position: $0.01 (minimum tradable)
        - Tier 1 @ 0.5%
        - Expected: $0.01 * 0.005 = $0.00005 (5 decimal places)
        """
        tier = MarginTier(
            symbol="BTCUSDT",
            tier_number=1,
            min_notional=Decimal("0"),
            max_notional=Decimal("50000"),
            margin_rate=Decimal("0.005"),
            maintenance_amount=ZERO,
        )

        micro_position = Decimal("0.01")
        margin = tier.calculate_margin(micro_position)

        expected = Decimal("0.00005")

        assert margin == expected, (
            f"Micro position precision lost: got ${margin}, expected ${expected}"
        )

    def test_maintenance_amount_subtraction_precision(self):
        """
        Test that MA subtraction preserves precision.

        Subtraction Test:
        - Position: $50,000 (Tier 1 boundary)
        - Rate: 0.5%
        - MA: $0
        - Expected: $50,000 * 0.005 - $0 = $250.00000
        """
        tier = MarginTier(
            symbol="BTCUSDT",
            tier_number=1,
            min_notional=Decimal("0"),
            max_notional=Decimal("50000"),
            margin_rate=Decimal("0.005"),
            maintenance_amount=ZERO,
        )

        position = Decimal("50000")
        margin = tier.calculate_margin(position)

        expected = Decimal("250")

        assert margin == expected
        assert isinstance(margin, Decimal), "Result should be Decimal, not float"

    def test_high_precision_rate(self):
        """
        Test margin rate with high precision.

        High-Precision Rate Test:
        - Position: $1,000,000
        - Rate: 0.025432 (5 decimal places)
        - MA: $4,000
        - Expected: $1,000,000 * 0.025432 - $4,000 = $21,432
        """
        tier = MarginTier(
            symbol="BTCUSDT",
            tier_number=3,
            min_notional=Decimal("250000"),
            max_notional=Decimal("1000000"),
            margin_rate=Decimal("0.025432"),  # High precision rate
            maintenance_amount=Decimal("4000"),
        )

        position = Decimal("1000000")
        margin = tier.calculate_margin(position)

        expected = Decimal("21432")

        assert margin == expected, (
            f"High-precision rate failed: got ${margin}, expected ${expected}"
        )

    def test_repeated_calculations_idempotent(self):
        """
        Test that repeated calculations produce identical results.

        Idempotency Test:
        - Calculate margin for same position 1000 times
        - All results must be EXACTLY identical
        - No accumulation of rounding errors
        """
        tier = MarginTier(
            symbol="BTCUSDT",
            tier_number=4,
            min_notional=Decimal("1000000"),
            max_notional=Decimal("10000000"),
            margin_rate=Decimal("0.050"),
            maintenance_amount=Decimal("29000"),
        )

        position = Decimal("5000000")
        expected = Decimal("221000")

        # Calculate 1000 times
        for _ in range(1000):
            margin = tier.calculate_margin(position)
            assert margin == expected, "Repeated calculation produced different result"

    def test_boundary_calculation_exact(self):
        """
        Test that boundary calculations are exact to the cent.

        Boundary Precision Test:
        - Test all 4 boundaries
        - Each must calculate to exact dollar amount (no fractional cents)
        """
        test_cases = [
            # (position, rate, ma, expected_margin)
            (Decimal("50000"), Decimal("0.005"), ZERO, Decimal("250")),
            (Decimal("50000"), Decimal("0.010"), Decimal("250"), Decimal("250")),
            (Decimal("250000"), Decimal("0.010"), Decimal("250"), Decimal("2250")),
            (Decimal("250000"), Decimal("0.025"), Decimal("4000"), Decimal("2250")),
            (Decimal("1000000"), Decimal("0.025"), Decimal("4000"), Decimal("21000")),
            (Decimal("1000000"), Decimal("0.050"), Decimal("29000"), Decimal("21000")),
            (Decimal("10000000"), Decimal("0.050"), Decimal("29000"), Decimal("471000")),
            (Decimal("10000000"), Decimal("0.100"), Decimal("529000"), Decimal("471000")),
        ]

        for position, rate, ma, expected in test_cases:
            calculated = position * rate - ma

            assert calculated == expected, (
                f"Boundary calculation imprecise: ${position} * {rate} - ${ma} = "
                f"${calculated}, expected ${expected}"
            )

    def test_no_float_contamination(self):
        """
        Test that float operations don't contaminate Decimal calculations.

        Type Safety Test:
        - Ensure all intermediate results are Decimal
        - Verify no implicit float conversion
        """
        tier = MarginTier(
            symbol="BTCUSDT",
            tier_number=2,
            min_notional=Decimal("50000"),
            max_notional=Decimal("250000"),
            margin_rate=Decimal("0.010"),
            maintenance_amount=Decimal("250"),
        )

        position = Decimal("100000")
        margin = tier.calculate_margin(position)

        # Verify result is Decimal
        assert isinstance(margin, Decimal), f"Result is {type(margin)}, not Decimal"

        # Verify intermediate calculation types
        intermediate = position * tier.margin_rate
        assert isinstance(intermediate, Decimal), "Multiplication produced non-Decimal"

        result = intermediate - tier.maintenance_amount
        assert isinstance(result, Decimal), "Subtraction produced non-Decimal"

    def test_extreme_position_size(self):
        """
        Test extremely large position (approaching Decimal128 limits).

        Extreme Test:
        - Position: $999,999,999,999 (~$1 trillion)
        - Tier 5 @ 10%
        - MA: $529,000
        - Expected: $999,999,999,999 * 0.1 - $529,000 = $99,999,470,999.90
        """
        tier = MarginTier(
            symbol="BTCUSDT",
            tier_number=5,
            min_notional=Decimal("10000000"),
            max_notional=Decimal("1000000000000"),  # $1T max
            margin_rate=Decimal("0.100"),
            maintenance_amount=Decimal("529000"),
        )

        extreme_position = Decimal("999999999999")
        margin = tier.calculate_margin(extreme_position)

        expected = Decimal("99999470999.9")

        assert margin == expected, (
            f"Extreme position calculation failed: got ${margin}, expected ${expected}"
        )

    def test_zero_maintenance_amount(self):
        """
        Test tier with zero maintenance amount (Tier 1).

        Zero MA Test:
        - Position: $25,000
        - Tier 1 @ 0.5%
        - MA: $0
        - Expected: $25,000 * 0.005 - $0 = $125
        """
        tier = MarginTier(
            symbol="BTCUSDT",
            tier_number=1,
            min_notional=Decimal("0"),
            max_notional=Decimal("50000"),
            margin_rate=Decimal("0.005"),
            maintenance_amount=ZERO,
        )

        position = Decimal("25000")
        margin = tier.calculate_margin(position)

        expected = Decimal("125")

        assert margin == expected
        assert margin > ZERO, "Margin should be positive"
