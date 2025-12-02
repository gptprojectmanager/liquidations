"""
Property-based testing for funding rate bias adjustment.
Uses Hypothesis to generate random test cases and verify mathematical properties.
"""

from decimal import Decimal

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from src.services.funding.bias_calculator import BiasCalculator
from src.services.funding.math_utils import tanh_conversion, validate_oi_conservation

# Strategy for valid funding rates (within Binance bounds)
valid_funding_rates = st.decimals(
    min_value=Decimal("-0.10"),
    max_value=Decimal("0.10"),
    allow_nan=False,
    allow_infinity=False,
    places=8,
)

# Strategy for scale factors (within allowed range)
valid_scale_factors = st.floats(min_value=10.0, max_value=100.0, allow_nan=False)

# Strategy for max adjustments (within allowed range)
valid_max_adjustments = st.floats(min_value=0.10, max_value=0.30, allow_nan=False)


class TestPropertyBased:
    """Property-based tests using Hypothesis."""

    @given(funding_rate=valid_funding_rates)
    @settings(max_examples=200, deadline=1000)
    def test_oi_conservation_property_always_holds(self, funding_rate):
        """OI conservation MUST hold for ALL valid funding rates."""
        calculator = BiasCalculator()
        result = calculator.calculate(funding_rate)

        # CRITICAL: This MUST be exactly 1.0
        total = result.long_ratio + result.short_ratio
        assert total == Decimal("1.0"), f"OI not conserved: {total} for rate {funding_rate}"

    @given(funding_rate=valid_funding_rates)
    @settings(max_examples=200, deadline=1000)
    def test_ratios_always_within_bounds(self, funding_rate):
        """Long and short ratios MUST always be in [0, 1]."""
        calculator = BiasCalculator()
        result = calculator.calculate(funding_rate)

        assert Decimal("0.0") <= result.long_ratio <= Decimal("1.0"), (
            f"Long ratio out of bounds: {result.long_ratio}"
        )
        assert Decimal("0.0") <= result.short_ratio <= Decimal("1.0"), (
            f"Short ratio out of bounds: {result.short_ratio}"
        )

    @given(funding_rate=valid_funding_rates)
    @settings(max_examples=200, deadline=1000)
    def test_confidence_always_in_range(self, funding_rate):
        """Confidence score MUST always be in [0, 1]."""
        calculator = BiasCalculator()
        result = calculator.calculate(funding_rate)

        assert 0.0 <= result.confidence <= 1.0, f"Confidence out of bounds: {result.confidence}"

    @given(funding_rate=valid_funding_rates)
    @settings(max_examples=100, deadline=1000)
    def test_symmetry_property(self, funding_rate):
        """Positive and negative rates should produce symmetric results."""
        # Skip zero as it's its own symmetric case
        assume(abs(funding_rate) > Decimal("0.0001"))

        calculator = BiasCalculator()
        pos_result = calculator.calculate(funding_rate)
        neg_result = calculator.calculate(-funding_rate)

        # Symmetric within floating point tolerance
        tolerance = Decimal("1e-14")
        assert abs(pos_result.long_ratio - neg_result.short_ratio) < tolerance
        assert abs(pos_result.short_ratio - neg_result.long_ratio) < tolerance

    @given(
        funding_rate=valid_funding_rates,
        scale_factor=valid_scale_factors,
        max_adjustment=valid_max_adjustments,
    )
    @settings(max_examples=100, deadline=1000)
    def test_custom_parameters_maintain_conservation(
        self, funding_rate, scale_factor, max_adjustment
    ):
        """OI conservation MUST hold with ANY valid custom parameters."""
        calculator = BiasCalculator(scale_factor=scale_factor, max_adjustment=max_adjustment)
        result = calculator.calculate(funding_rate)

        # CRITICAL: OI conservation with custom params
        total = result.long_ratio + result.short_ratio
        assert total == Decimal("1.0"), (
            f"OI not conserved with custom params: {total} "
            f"(scale={scale_factor}, max_adj={max_adjustment})"
        )

    @given(funding_rate=valid_funding_rates)
    @settings(max_examples=200, deadline=1000)
    def test_monotonicity_of_long_ratio(self, funding_rate):
        """Long ratio should increase monotonically with funding rate."""
        # Compare with slightly higher rate
        epsilon = Decimal("0.0001")
        higher_rate = min(funding_rate + epsilon, Decimal("0.10"))

        calculator = BiasCalculator()
        result1 = calculator.calculate(funding_rate)
        result2 = calculator.calculate(higher_rate)

        # Long ratio should be non-decreasing
        assert result2.long_ratio >= result1.long_ratio, (
            f"Monotonicity violated: {result1.long_ratio} > {result2.long_ratio}"
        )

    @given(funding_rate=valid_funding_rates)
    @settings(max_examples=100, deadline=1000)
    def test_confidence_increases_with_magnitude(self, funding_rate):
        """Confidence should increase with absolute funding rate magnitude."""
        calculator = BiasCalculator()

        # Test with original and doubled magnitude
        result1 = calculator.calculate(funding_rate)

        # Double the magnitude (staying within bounds)
        doubled_rate = funding_rate * 2
        if abs(doubled_rate) > Decimal("0.10"):
            doubled_rate = Decimal("0.10") if doubled_rate > 0 else Decimal("-0.10")

        assume(abs(doubled_rate) > abs(funding_rate))  # Only test if actually doubled

        result2 = calculator.calculate(doubled_rate)

        # Higher magnitude should give higher confidence
        assert result2.confidence >= result1.confidence, (
            f"Confidence didn't increase with magnitude: "
            f"{result1.confidence} (rate={funding_rate}) > "
            f"{result2.confidence} (rate={doubled_rate})"
        )

    @given(
        funding_rate=valid_funding_rates,
        scale_factor=valid_scale_factors,
    )
    @settings(max_examples=100, deadline=1000)
    def test_tanh_conversion_direct(self, funding_rate, scale_factor):
        """Test tanh_conversion function directly with various parameters."""
        long_ratio, short_ratio = tanh_conversion(funding_rate, scale_factor=scale_factor)

        # OI conservation
        assert long_ratio + short_ratio == Decimal("1.0")

        # Bounds check
        assert Decimal("0.0") <= long_ratio <= Decimal("1.0")
        assert Decimal("0.0") <= short_ratio <= Decimal("1.0")

        # Type check
        assert isinstance(long_ratio, Decimal)
        assert isinstance(short_ratio, Decimal)

    @given(funding_rate=valid_funding_rates)
    @settings(max_examples=50, deadline=1000)
    def test_zero_crossing_behavior(self, funding_rate):
        """Test behavior around zero funding rate (neutral point)."""
        calculator = BiasCalculator()

        # Rates very close to zero should give ratios close to 50/50
        if abs(funding_rate) < Decimal("0.00001"):  # Very close to zero
            result = calculator.calculate(funding_rate)

            # Should be within 2% of neutral (scale factor 50 can still move it a bit)
            assert abs(result.long_ratio - Decimal("0.5")) < Decimal("0.02"), (
                f"Near-zero rate didn't produce neutral ratios: {result.long_ratio}"
            )

    @given(funding_rate=valid_funding_rates)
    @settings(max_examples=100, deadline=1000)
    def test_deterministic_behavior(self, funding_rate):
        """Same input should ALWAYS produce same output (no randomness)."""
        calculator = BiasCalculator()

        result1 = calculator.calculate(funding_rate)
        result2 = calculator.calculate(funding_rate)

        # Should be EXACTLY equal
        assert result1.long_ratio == result2.long_ratio
        assert result1.short_ratio == result2.short_ratio
        assert result1.confidence == result2.confidence


class TestStressConditions:
    """Stress testing with extreme conditions."""

    @given(
        st.lists(
            valid_funding_rates,
            min_size=100,
            max_size=1000,
        )
    )
    @settings(max_examples=10, deadline=5000)
    def test_batch_calculation_stability(self, funding_rates):
        """Test stability with large batch of calculations."""
        calculator = BiasCalculator()

        for rate in funding_rates:
            result = calculator.calculate(rate)

            # Every single calculation must maintain OI conservation
            total = result.long_ratio + result.short_ratio
            assert total == Decimal("1.0"), f"Batch calculation violated OI: {total}"

    def test_rapid_calculator_creation(self):
        """Test creating many calculator instances doesn't cause issues."""
        # Create 1000 calculators rapidly
        calculators = [BiasCalculator() for _ in range(1000)]

        # Test each one works correctly
        test_rate = Decimal("0.0003")
        for calc in calculators:
            result = calc.calculate(test_rate)
            assert result.long_ratio + result.short_ratio == Decimal("1.0")

    @given(funding_rate=valid_funding_rates)
    @settings(max_examples=50, deadline=1000)
    def test_decimal_precision_maintained(self, funding_rate):
        """Verify Decimal precision is maintained throughout calculation."""
        calculator = BiasCalculator()
        result = calculator.calculate(funding_rate)

        # Results should be Decimal type
        assert isinstance(result.long_ratio, Decimal)
        assert isinstance(result.short_ratio, Decimal)
        assert isinstance(result.funding_input, Decimal)

        # String representation should be precise
        long_str = str(result.long_ratio)
        short_str = str(result.short_ratio)

        # Should not contain scientific notation artifacts
        assert "e" not in long_str.lower() or "E" not in long_str
        assert "e" not in short_str.lower() or "E" not in short_str


class TestEdgeCaseValidation:
    """Additional edge case validation."""

    def test_exact_boundary_values(self):
        """Test exact boundary values with high precision."""
        calculator = BiasCalculator()

        # Test exact max boundary
        max_rate = Decimal("0.10")
        result_max = calculator.calculate(max_rate)
        assert result_max.long_ratio + result_max.short_ratio == Decimal("1.0")

        # Test exact min boundary
        min_rate = Decimal("-0.10")
        result_min = calculator.calculate(min_rate)
        assert result_min.long_ratio + result_min.short_ratio == Decimal("1.0")

        # Test exact zero
        zero_rate = Decimal("0.0")
        result_zero = calculator.calculate(zero_rate)
        assert result_zero.long_ratio + result_zero.short_ratio == Decimal("1.0")

    @given(
        st.decimals(
            min_value=Decimal("0.0"),
            max_value=Decimal("0.10"),
            allow_nan=False,
            allow_infinity=False,
            places=18,  # Very high precision
        )
    )
    @settings(max_examples=50, deadline=1000)
    def test_high_precision_inputs(self, funding_rate):
        """Test with very high precision inputs."""
        calculator = BiasCalculator()
        result = calculator.calculate(funding_rate)

        # Even with high-precision inputs, OI conservation must hold
        total = result.long_ratio + result.short_ratio
        assert total == Decimal("1.0")

    def test_validate_oi_conservation_function(self):
        """Test the validate_oi_conservation utility function."""
        # Exact conservation
        assert validate_oi_conservation(Decimal("0.6"), Decimal("0.4"))

        # Within tolerance
        assert validate_oi_conservation(
            Decimal("0.6"), Decimal("0.4") + Decimal("1e-15"), tolerance=Decimal("1e-10")
        )

        # Outside tolerance
        assert not validate_oi_conservation(
            Decimal("0.6"), Decimal("0.5"), tolerance=Decimal("1e-10")
        )
