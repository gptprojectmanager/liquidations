"""
Unit tests for BiasCalculator - tanh-based funding rate conversion.
Feature: LIQHEAT-005
TDD: Red phase - These tests should fail initially.
"""

from decimal import Decimal

from hypothesis import assume, given
from hypothesis import strategies as st
from src.models.funding.bias_adjustment import BiasAdjustment

# These imports will fail initially (TDD Red phase)
from src.services.funding.bias_calculator import BiasCalculator


class TestBiasCalculator:
    """Test suite for bias calculation from funding rates."""

    def test_tanh_formula_positive_funding(self):
        """Test tanh formula with positive funding rate.

        Given funding rate of +0.03% (3 basis points),
        the long ratio should be approximately 68.1%.
        """
        # Arrange
        calculator = BiasCalculator(scale_factor=50.0, max_adjustment=0.20)
        funding_rate = Decimal("0.0003")  # +0.03%

        # Act
        adjustment = calculator.calculate(funding_rate)

        # Assert
        assert isinstance(adjustment, BiasAdjustment)
        assert 0.680 <= float(adjustment.long_ratio) <= 0.682  # ~68.1%
        assert 0.318 <= float(adjustment.short_ratio) <= 0.320  # ~31.9%
        assert abs(float(adjustment.long_ratio) + float(adjustment.short_ratio) - 1.0) < 1e-10

    def test_tanh_formula_negative_funding(self):
        """Test tanh formula with negative funding rate.

        Given funding rate of -0.02% (-2 basis points),
        the short ratio should be higher than long ratio.
        """
        # Arrange
        calculator = BiasCalculator(scale_factor=50.0, max_adjustment=0.20)
        funding_rate = Decimal("-0.0002")  # -0.02%

        # Act
        adjustment = calculator.calculate(funding_rate)

        # Assert
        assert float(adjustment.long_ratio) < 0.5  # Less than 50%
        assert float(adjustment.short_ratio) > 0.5  # More than 50%
        assert abs(float(adjustment.long_ratio) + float(adjustment.short_ratio) - 1.0) < 1e-10

    def test_tanh_formula_neutral_funding(self):
        """Test tanh formula with neutral (zero) funding rate.

        Should return exactly 50/50 distribution.
        """
        # Arrange
        calculator = BiasCalculator(scale_factor=50.0, max_adjustment=0.20)
        funding_rate = Decimal("0.0")

        # Act
        adjustment = calculator.calculate(funding_rate)

        # Assert
        assert float(adjustment.long_ratio) == 0.5
        assert float(adjustment.short_ratio) == 0.5
        assert adjustment.confidence == 0.0  # No confidence in neutral state

    def test_tanh_formula_extreme_positive(self):
        """Test tanh formula at extreme positive funding rate.

        Should be capped at max_adjustment (70% long).
        """
        # Arrange
        calculator = BiasCalculator(scale_factor=50.0, max_adjustment=0.20)
        funding_rate = Decimal("0.10")  # +10% (extreme)

        # Act
        adjustment = calculator.calculate(funding_rate)

        # Assert
        assert float(adjustment.long_ratio) <= 0.70  # Capped at 70%
        assert float(adjustment.long_ratio) >= 0.69  # Close to cap
        assert float(adjustment.short_ratio) >= 0.30  # At least 30%

    def test_tanh_formula_extreme_negative(self):
        """Test tanh formula at extreme negative funding rate.

        Should be capped at max_adjustment (70% short).
        """
        # Arrange
        calculator = BiasCalculator(scale_factor=50.0, max_adjustment=0.20)
        funding_rate = Decimal("-0.10")  # -10% (extreme)

        # Act
        adjustment = calculator.calculate(funding_rate)

        # Assert
        assert float(adjustment.short_ratio) <= 0.70  # Capped at 70%
        assert float(adjustment.short_ratio) >= 0.69  # Close to cap
        assert float(adjustment.long_ratio) >= 0.30  # At least 30%

    @given(
        funding_rate=st.decimals(min_value=Decimal("-0.10"), max_value=Decimal("0.10"), places=8)
    )
    def test_oi_conservation_property(self, funding_rate):
        """Property test: Total OI must always be conserved.

        For any funding rate, long_ratio + short_ratio = 1.0 exactly.
        """
        # Arrange
        calculator = BiasCalculator(scale_factor=50.0, max_adjustment=0.20)

        # Act
        adjustment = calculator.calculate(funding_rate)

        # Assert - OI conservation
        total = float(adjustment.long_ratio) + float(adjustment.short_ratio)
        assert abs(total - 1.0) < 1e-10, f"OI not conserved: {total} != 1.0"

        # Assert - Bounded ratios
        assert 0.30 <= float(adjustment.long_ratio) <= 0.70
        assert 0.30 <= float(adjustment.short_ratio) <= 0.70

    @given(
        funding_rate=st.decimals(min_value=Decimal("-0.10"), max_value=Decimal("0.10"), places=8)
    )
    def test_tanh_continuity_property(self, funding_rate):
        """Property test: Tanh transformation must be continuous.

        Small changes in funding rate should produce small changes in ratios.
        """
        # Arrange
        calculator = BiasCalculator(scale_factor=50.0, max_adjustment=0.20)
        epsilon = Decimal("0.00001")  # Small change

        # Skip if too close to boundaries
        assume(abs(funding_rate) < Decimal("0.099"))

        # Act
        adjustment1 = calculator.calculate(funding_rate)
        adjustment2 = calculator.calculate(funding_rate + epsilon)

        # Assert - Continuity check
        delta_long = abs(float(adjustment2.long_ratio) - float(adjustment1.long_ratio))
        assert delta_long < 0.01, f"Discontinuous: delta={delta_long} for epsilon={epsilon}"

    def test_confidence_score_calculation(self):
        """Test confidence score scales with funding rate magnitude."""
        # Arrange
        calculator = BiasCalculator(scale_factor=50.0, max_adjustment=0.20)

        # Act & Assert - Higher funding = higher confidence
        adj_high = calculator.calculate(Decimal("0.005"))  # 0.5%
        adj_low = calculator.calculate(Decimal("0.001"))  # 0.1%
        adj_zero = calculator.calculate(Decimal("0.0"))  # 0%

        assert adj_high.confidence > adj_low.confidence
        assert adj_low.confidence > adj_zero.confidence
        assert adj_zero.confidence == 0.0

    def test_custom_scale_factor(self):
        """Test different scale factors affect sensitivity."""
        # Arrange
        funding_rate = Decimal("0.001")  # 0.1%

        # Act
        calc_low = BiasCalculator(scale_factor=25.0, max_adjustment=0.20)
        calc_high = BiasCalculator(scale_factor=100.0, max_adjustment=0.20)

        adj_low = calc_low.calculate(funding_rate)
        adj_high = calc_high.calculate(funding_rate)

        # Assert - Higher scale factor = more sensitive
        deviation_low = abs(float(adj_low.long_ratio) - 0.5)
        deviation_high = abs(float(adj_high.long_ratio) - 0.5)

        assert deviation_high > deviation_low, "Higher scale should be more sensitive"

    def test_custom_max_adjustment(self):
        """Test different max adjustments cap the ratios correctly."""
        # Arrange
        funding_rate = Decimal("0.10")  # Extreme rate to hit cap

        # Act
        calc_10 = BiasCalculator(scale_factor=50.0, max_adjustment=0.10)  # ±10%
        calc_30 = BiasCalculator(scale_factor=50.0, max_adjustment=0.30)  # ±30%

        adj_10 = calc_10.calculate(funding_rate)
        adj_30 = calc_30.calculate(funding_rate)

        # Assert - Different caps applied
        assert float(adj_10.long_ratio) <= 0.60  # 50% + 10%
        assert float(adj_30.long_ratio) <= 0.80  # 50% + 30%
        assert float(adj_30.long_ratio) > float(adj_10.long_ratio)
