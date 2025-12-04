"""
Input validation and boundary value analysis tests.
Tests invalid inputs, edge cases, and data sanitization.
"""

from decimal import Decimal, InvalidOperation

import pytest

from src.models.funding.adjustment_config import AdjustmentConfigModel
from src.models.funding.bias_adjustment import BiasAdjustment
from src.models.funding.funding_rate import FundingRate
from src.services.funding.bias_calculator import BiasCalculator


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_invalid_funding_rate_types(self):
        """Test rejection of truly invalid funding rate types."""
        calculator = BiasCalculator()

        # Test with types that CANNOT be converted to Decimal
        invalid_inputs = [
            None,  # None
            [],  # List
            {},  # Dict
            "invalid",  # Invalid string
            "abc123",  # Mixed string
        ]

        for invalid_input in invalid_inputs:
            with pytest.raises((TypeError, ValueError, InvalidOperation)):
                calculator.calculate(invalid_input)

    def test_special_float_values_rejected(self):
        """Test that infinity and NaN are rejected."""
        calculator = BiasCalculator()

        # These should fail when converted to Decimal
        with pytest.raises((InvalidOperation, ValueError)):
            calculator.calculate(float("inf"))

        with pytest.raises((InvalidOperation, ValueError)):
            calculator.calculate(float("-inf"))

        with pytest.raises((InvalidOperation, ValueError)):
            calculator.calculate(float("nan"))

    def test_valid_string_conversion(self):
        """Test that valid numeric strings are accepted (design feature)."""
        calculator = BiasCalculator()

        # Valid numeric strings should work
        result = calculator.calculate("0.0003")
        assert result.long_ratio + result.short_ratio == Decimal("1.0")

        # Valid numeric string (negative)
        result = calculator.calculate("-0.0002")
        assert result.long_ratio + result.short_ratio == Decimal("1.0")

    def test_funding_rate_out_of_bounds(self):
        """Test funding rates outside valid range."""
        # Valid range is [-0.10, 0.10]
        out_of_bounds = [
            Decimal("0.11"),  # Just above max
            Decimal("-0.11"),  # Just below min
            Decimal("1.0"),  # Way above
            Decimal("-1.0"),  # Way below
            Decimal("10.0"),  # Extreme positive
            Decimal("-10.0"),  # Extreme negative
        ]

        for rate in out_of_bounds:
            with pytest.raises(Exception):  # Pydantic validation error
                FundingRate(
                    symbol="BTCUSDT",
                    rate=rate,
                    funding_time="2025-12-02T12:00:00+00:00",
                )

    def test_symbol_validation(self):
        """Test symbol pattern validation."""
        valid_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT"]
        invalid_symbols = [
            "INVALID",  # Doesn't match pattern
            "btcusdt",  # Lowercase
            "BTC-USDT",  # Wrong format
            "BTCUSD",  # Missing T
            "",  # Empty
            "A",  # Too short
        ]

        # Valid symbols should work
        for symbol in valid_symbols:
            rate = FundingRate(
                symbol=symbol,
                rate=Decimal("0.0003"),
                funding_time="2025-12-02T12:00:00+00:00",
            )
            assert rate.symbol == symbol

        # Invalid symbols should fail
        for symbol in invalid_symbols:
            with pytest.raises(Exception):
                FundingRate(
                    symbol=symbol,
                    rate=Decimal("0.0003"),
                    funding_time="2025-12-02T12:00:00+00:00",
                )

    def test_scale_factor_validation(self):
        """Test scale factor bounds validation."""
        # Valid range: [10.0, 100.0]
        with pytest.raises(ValueError):
            BiasCalculator(scale_factor=9.9)  # Just below min

        with pytest.raises(ValueError):
            BiasCalculator(scale_factor=100.1)  # Just above max

        with pytest.raises(ValueError):
            BiasCalculator(scale_factor=0.0)  # Zero

        with pytest.raises(ValueError):
            BiasCalculator(scale_factor=-50.0)  # Negative

        # Valid values should work
        BiasCalculator(scale_factor=10.0)  # Min
        BiasCalculator(scale_factor=50.0)  # Middle
        BiasCalculator(scale_factor=100.0)  # Max

    def test_max_adjustment_validation(self):
        """Test max_adjustment bounds validation."""
        # Valid range: [0.10, 0.30]
        with pytest.raises(ValueError):
            BiasCalculator(max_adjustment=0.09)  # Below min

        with pytest.raises(ValueError):
            BiasCalculator(max_adjustment=0.31)  # Above max

        with pytest.raises(ValueError):
            BiasCalculator(max_adjustment=0.0)  # Zero

        with pytest.raises(ValueError):
            BiasCalculator(max_adjustment=-0.2)  # Negative

        # Valid values should work
        BiasCalculator(max_adjustment=0.10)  # Min
        BiasCalculator(max_adjustment=0.20)  # Middle
        BiasCalculator(max_adjustment=0.30)  # Max

    def test_config_validation(self):
        """Test AdjustmentConfigModel validation."""
        # Invalid sensitivity (scale_factor)
        with pytest.raises(Exception):
            AdjustmentConfigModel(sensitivity=5.0)  # Too low

        with pytest.raises(Exception):
            AdjustmentConfigModel(sensitivity=150.0)  # Too high

        # Invalid max_adjustment
        with pytest.raises(Exception):
            AdjustmentConfigModel(max_adjustment=0.05)  # Too low

        with pytest.raises(Exception):
            AdjustmentConfigModel(max_adjustment=0.5)  # Too high

        # Invalid cache_ttl (must be positive)
        with pytest.raises(Exception):
            AdjustmentConfigModel(cache_ttl_seconds=-1)

        # Valid config should work
        config = AdjustmentConfigModel(
            enabled=True,
            sensitivity=50.0,
            max_adjustment=0.20,
            cache_ttl_seconds=300,
        )
        assert config.enabled is True


class TestBoundaryValues:
    """Test exact boundary values and off-by-one errors."""

    def test_funding_rate_exact_boundaries(self):
        """Test exact boundary values for funding rate."""
        calculator = BiasCalculator()

        # Exact boundaries should work
        result_max = calculator.calculate(Decimal("0.10"))  # Exact max
        assert result_max.long_ratio + result_max.short_ratio == Decimal("1.0")

        result_min = calculator.calculate(Decimal("-0.10"))  # Exact min
        assert result_min.long_ratio + result_min.short_ratio == Decimal("1.0")

        result_zero = calculator.calculate(Decimal("0.0"))  # Exact zero
        assert result_zero.long_ratio == Decimal("0.5")
        assert result_zero.short_ratio == Decimal("0.5")

    def test_scale_factor_exact_boundaries(self):
        """Test exact boundary values for scale_factor."""
        # Exact boundaries should work
        calc_min = BiasCalculator(scale_factor=10.0)
        result = calc_min.calculate(Decimal("0.0003"))
        assert result.long_ratio + result.short_ratio == Decimal("1.0")

        calc_max = BiasCalculator(scale_factor=100.0)
        result = calc_max.calculate(Decimal("0.0003"))
        assert result.long_ratio + result.short_ratio == Decimal("1.0")

    def test_max_adjustment_exact_boundaries(self):
        """Test exact boundary values for max_adjustment."""
        # Exact boundaries should work
        calc_min = BiasCalculator(max_adjustment=0.10)
        result = calc_min.calculate(Decimal("0.05"))
        assert result.long_ratio + result.short_ratio == Decimal("1.0")
        # With max_adj=0.10, max deviation is 10%
        assert Decimal("0.40") <= result.long_ratio <= Decimal("0.60")

        calc_max = BiasCalculator(max_adjustment=0.30)
        result = calc_max.calculate(Decimal("0.05"))
        assert result.long_ratio + result.short_ratio == Decimal("1.0")
        # With max_adj=0.30, max deviation is 30%
        assert Decimal("0.20") <= result.long_ratio <= Decimal("0.80")

    def test_oi_boundary_values(self):
        """Test OI with boundary values."""
        # Zero OI (fields optional, not auto-calculated)
        adjustment = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=0.5,
            total_oi=Decimal("0"),
            long_oi=Decimal("0"),
            short_oi=Decimal("0"),
        )
        assert adjustment.total_oi == Decimal("0")
        assert adjustment.long_oi == Decimal("0")
        assert adjustment.short_oi == Decimal("0")

        # Very small OI
        small_oi = Decimal("0.01")
        adjustment = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=0.5,
            total_oi=small_oi,
            long_oi=small_oi * Decimal("0.6"),
            short_oi=small_oi * Decimal("0.4"),
        )
        assert adjustment.long_oi + adjustment.short_oi == adjustment.total_oi

        # Very large OI (billions)
        large_oi = Decimal("999999999999")  # ~1 trillion
        adjustment = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=0.5,
            total_oi=large_oi,
            long_oi=large_oi * Decimal("0.6"),
            short_oi=large_oi * Decimal("0.4"),
        )
        assert adjustment.long_oi + adjustment.short_oi == large_oi

    def test_confidence_boundary_values(self):
        """Test confidence score boundaries."""
        # Zero confidence
        adjustment = BiasAdjustment(
            funding_input=Decimal("0.0"),
            long_ratio=Decimal("0.5"),
            short_ratio=Decimal("0.5"),
            confidence=0.0,
        )
        assert adjustment.confidence == 0.0

        # Max confidence
        adjustment = BiasAdjustment(
            funding_input=Decimal("0.10"),
            long_ratio=Decimal("0.7"),
            short_ratio=Decimal("0.3"),
            confidence=1.0,
        )
        assert adjustment.confidence == 1.0


class TestDataSanitization:
    """Test data sanitization and normalization."""

    def test_decimal_normalization(self):
        """Test Decimal values are properly normalized."""
        calculator = BiasCalculator()

        # Various decimal representations of same value
        rates = [
            Decimal("0.0003"),
            Decimal("0.00030"),
            Decimal("0.000300"),
            Decimal("3e-4"),  # Scientific notation
        ]

        results = [calculator.calculate(rate) for rate in rates]

        # All should give same result
        for i in range(1, len(results)):
            assert results[0].long_ratio == results[i].long_ratio
            assert results[0].short_ratio == results[i].short_ratio

    def test_string_to_decimal_conversion(self):
        """Test FundingRate handles string to Decimal conversion."""
        # FundingRate should accept Decimal
        rate1 = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        # Should also accept numeric strings via Pydantic
        rate2 = FundingRate(
            symbol="BTCUSDT",
            rate="0.0003",
            funding_time="2025-12-02T12:00:00+00:00",
        )

        assert rate1.rate == rate2.rate

    def test_negative_zero_handling(self):
        """Test handling of negative zero."""
        calculator = BiasCalculator()

        # Decimal("-0.0") should be treated as zero
        result = calculator.calculate(Decimal("-0.0"))
        assert result.long_ratio == Decimal("0.5")
        assert result.short_ratio == Decimal("0.5")


class TestErrorMessages:
    """Test error messages are descriptive."""

    def test_scale_factor_error_message(self):
        """Test scale_factor error has descriptive message."""
        with pytest.raises(ValueError) as exc_info:
            BiasCalculator(scale_factor=5.0)

        error_msg = str(exc_info.value)
        assert "scale_factor" in error_msg.lower()
        assert "5.0" in error_msg
        assert "10.0" in error_msg or "100.0" in error_msg  # Should mention valid range

    def test_max_adjustment_error_message(self):
        """Test max_adjustment error has descriptive message."""
        with pytest.raises(ValueError) as exc_info:
            BiasCalculator(max_adjustment=0.5)

        error_msg = str(exc_info.value)
        assert "max_adjustment" in error_msg.lower()
        assert "0.5" in error_msg
        assert "0.10" in error_msg or "0.30" in error_msg  # Should mention valid range


class TestSpecialCases:
    """Test special edge cases and corner cases."""

    def test_funding_rate_precision_edge_cases(self):
        """Test with extremely precise funding rates."""
        calculator = BiasCalculator()

        # Very precise positive
        result = calculator.calculate(Decimal("0.000000000001"))
        assert result.long_ratio + result.short_ratio == Decimal("1.0")

        # Very precise negative
        result = calculator.calculate(Decimal("-0.000000000001"))
        assert result.long_ratio + result.short_ratio == Decimal("1.0")

    def test_ratio_sum_exactly_one(self):
        """Test that ratio sum is EXACTLY 1.0, not approximately."""
        calculator = BiasCalculator()

        # Test many different rates
        test_rates = [
            Decimal("0.0001"),
            Decimal("0.0003"),
            Decimal("0.0005"),
            Decimal("0.001"),
            Decimal("0.01"),
            Decimal("0.05"),
            Decimal("-0.0001"),
            Decimal("-0.0003"),
            Decimal("-0.0005"),
        ]

        for rate in test_rates:
            result = calculator.calculate(rate)
            total = result.long_ratio + result.short_ratio

            # Must be EXACTLY 1.0
            assert total == Decimal("1.0"), f"Rate {rate}: {total} != 1.0"

    def test_metadata_optional_fields(self):
        """Test BiasAdjustment with various metadata combinations."""
        # Minimal fields
        adj1 = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=0.5,
        )
        assert adj1.symbol is None
        assert adj1.total_oi is None

        # With metadata
        adj2 = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=0.5,
            metadata={"source": "test"},
        )
        assert adj2.metadata["source"] == "test"

        # Empty metadata
        adj3 = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=0.5,
            metadata={},
        )
        assert adj3.metadata == {}

    def test_calculator_immutability(self):
        """Test that calculations don't modify calculator state."""
        calculator = BiasCalculator(scale_factor=50.0, max_adjustment=0.20)

        # Store original config
        original_scale = 50.0
        original_max_adj = 0.20

        # Perform calculation
        calculator.calculate(Decimal("0.0003"))

        # Config should be unchanged
        assert calculator.scale_factor == original_scale
        assert calculator.max_adjustment == original_max_adj

        # Multiple calculations shouldn't affect each other
        result1 = calculator.calculate(Decimal("0.0003"))
        result2 = calculator.calculate(Decimal("0.0003"))

        assert result1.long_ratio == result2.long_ratio
        assert result1.short_ratio == result2.short_ratio
