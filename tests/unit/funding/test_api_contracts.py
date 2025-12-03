"""
API contract compliance and schema validation tests.
Tests Pydantic model contracts, serialization, and field validation.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.models.funding.adjustment_config import AdjustmentConfigModel
from src.models.funding.bias_adjustment import BiasAdjustment
from src.models.funding.funding_rate import FundingRate


class TestFundingRateContract:
    """Test FundingRate model contract compliance."""

    def test_valid_funding_rate_creation(self):
        """Test creating valid FundingRate."""
        rate = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        assert rate.symbol == "BTCUSDT"
        assert rate.rate == Decimal("0.0003")
        assert isinstance(rate.funding_time, datetime)

    def test_symbol_pattern_validation(self):
        """Test symbol must match required pattern."""
        # Valid symbols
        valid_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT"]
        for symbol in valid_symbols:
            rate = FundingRate(
                symbol=symbol,
                rate=Decimal("0.0001"),
                funding_time="2025-12-02T12:00:00+00:00",
            )
            assert rate.symbol == symbol

        # Invalid symbols (should fail pattern validation)
        invalid_symbols = [
            "INVALID",  # Doesn't end with USDT
            "btcusdt",  # Lowercase
            "BTC-USDT",  # Contains hyphen
            "",  # Empty
        ]

        for symbol in invalid_symbols:
            with pytest.raises(ValidationError):
                FundingRate(
                    symbol=symbol,
                    rate=Decimal("0.0001"),
                    funding_time="2025-12-02T12:00:00+00:00",
                )

    def test_rate_bounds_validation(self):
        """Test rate must be within valid bounds [-0.10, 0.10]."""
        # Valid rates at boundaries
        FundingRate(
            symbol="BTCUSDT", rate=Decimal("0.10"), funding_time="2025-12-02T12:00:00+00:00"
        )
        FundingRate(
            symbol="BTCUSDT", rate=Decimal("-0.10"), funding_time="2025-12-02T12:00:00+00:00"
        )
        FundingRate(symbol="BTCUSDT", rate=Decimal("0.0"), funding_time="2025-12-02T12:00:00+00:00")

        # Invalid rates (outside bounds)
        with pytest.raises(ValidationError):
            FundingRate(
                symbol="BTCUSDT", rate=Decimal("0.11"), funding_time="2025-12-02T12:00:00+00:00"
            )

        with pytest.raises(ValidationError):
            FundingRate(
                symbol="BTCUSDT", rate=Decimal("-0.11"), funding_time="2025-12-02T12:00:00+00:00"
            )

    def test_funding_time_parsing(self):
        """Test funding_time accepts various datetime formats."""
        # ISO 8601 with timezone
        rate1 = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0001"),
            funding_time="2025-12-02T12:00:00+00:00",
        )
        assert isinstance(rate1.funding_time, datetime)
        assert rate1.funding_time.tzinfo is not None

        # Datetime object
        dt = datetime(2025, 12, 2, 12, 0, 0, tzinfo=timezone.utc)
        rate2 = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0001"),
            funding_time=dt,
        )
        assert rate2.funding_time == dt

    def test_serialization_roundtrip(self):
        """Test FundingRate serialization/deserialization preserves data."""
        original = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.000375"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        # Serialize to dict
        data = original.model_dump()

        # Deserialize back
        reconstructed = FundingRate(**data)

        # Should be equivalent
        assert reconstructed.symbol == original.symbol
        assert reconstructed.rate == original.rate
        assert reconstructed.funding_time == original.funding_time

    def test_json_serialization(self):
        """Test JSON serialization preserves Decimal precision."""
        rate = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.000375"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        # Serialize to JSON
        json_str = rate.model_dump_json()

        # Deserialize from JSON
        reconstructed = FundingRate.model_validate_json(json_str)

        # Decimal precision should be preserved
        assert reconstructed.rate == rate.rate


class TestBiasAdjustmentContract:
    """Test BiasAdjustment model contract compliance."""

    def test_valid_bias_adjustment_creation(self):
        """Test creating valid BiasAdjustment."""
        adjustment = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=0.75,
        )

        assert adjustment.funding_input == Decimal("0.0003")
        assert adjustment.long_ratio == Decimal("0.6")
        assert adjustment.short_ratio == Decimal("0.4")
        assert adjustment.confidence == 0.75

    def test_optional_fields(self):
        """Test optional fields can be omitted."""
        # Minimal required fields
        adjustment = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=0.5,
        )

        # Optional fields should be None or default
        assert adjustment.symbol is None
        assert adjustment.total_oi is None
        assert adjustment.long_oi is None
        assert adjustment.short_oi is None

    def test_complete_bias_adjustment(self):
        """Test BiasAdjustment with all fields populated."""
        adjustment = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            symbol="BTCUSDT",
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            total_oi=Decimal("1000000"),
            long_oi=Decimal("600000"),
            short_oi=Decimal("400000"),
            confidence=0.75,
            confidence_score=Decimal("0.75"),
            metadata={"source": "binance"},
        )

        # All fields should be populated
        assert adjustment.symbol == "BTCUSDT"
        assert adjustment.total_oi == Decimal("1000000")
        assert adjustment.long_oi == Decimal("600000")
        assert adjustment.short_oi == Decimal("400000")
        assert adjustment.metadata["source"] == "binance"

    def test_ratio_validation(self):
        """Test ratio values must be in [0, 1]."""
        # Valid ratios
        BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.0"),
            short_ratio=Decimal("1.0"),
            confidence=0.5,
        )

        BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("1.0"),
            short_ratio=Decimal("0.0"),
            confidence=0.5,
        )

        # Invalid ratios (outside [0, 1])
        with pytest.raises(ValidationError):
            BiasAdjustment(
                funding_input=Decimal("0.0003"),
                long_ratio=Decimal("1.5"),  # > 1.0
                short_ratio=Decimal("-0.5"),  # < 0.0
                confidence=0.5,
            )

    def test_confidence_bounds(self):
        """Test confidence must be in [0, 1]."""
        # Valid confidence values
        BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=0.0,
        )

        BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=1.0,
        )

        # Invalid confidence (outside [0, 1])
        with pytest.raises(ValidationError):
            BiasAdjustment(
                funding_input=Decimal("0.0003"),
                long_ratio=Decimal("0.6"),
                short_ratio=Decimal("0.4"),
                confidence=1.5,
            )

        with pytest.raises(ValidationError):
            BiasAdjustment(
                funding_input=Decimal("0.0003"),
                long_ratio=Decimal("0.6"),
                short_ratio=Decimal("0.4"),
                confidence=-0.1,
            )

    def test_serialization_preserves_decimal_precision(self):
        """Test serialization preserves Decimal precision."""
        adjustment = BiasAdjustment(
            funding_input=Decimal("0.000375"),
            long_ratio=Decimal("0.6234567890123456"),
            short_ratio=Decimal("0.3765432109876544"),
            confidence=0.875,
            total_oi=Decimal("1234567.89"),
        )

        # Serialize and deserialize
        data = adjustment.model_dump()
        reconstructed = BiasAdjustment(**data)

        # Decimal precision should be preserved
        assert reconstructed.funding_input == adjustment.funding_input
        assert reconstructed.long_ratio == adjustment.long_ratio
        assert reconstructed.short_ratio == adjustment.short_ratio
        assert reconstructed.total_oi == adjustment.total_oi


class TestAdjustmentConfigContract:
    """Test AdjustmentConfigModel contract compliance."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AdjustmentConfigModel()

        # Check defaults
        assert config.enabled is True
        assert config.sensitivity == 50.0
        assert config.max_adjustment == 0.20
        assert config.cache_ttl_seconds == 300
        assert config.smoothing_enabled is False

    def test_sensitivity_bounds(self):
        """Test sensitivity (scale_factor) must be in [10.0, 100.0]."""
        # Valid values
        AdjustmentConfigModel(sensitivity=10.0)
        AdjustmentConfigModel(sensitivity=50.0)
        AdjustmentConfigModel(sensitivity=100.0)

        # Invalid values
        with pytest.raises(ValidationError):
            AdjustmentConfigModel(sensitivity=9.9)

        with pytest.raises(ValidationError):
            AdjustmentConfigModel(sensitivity=100.1)

    def test_max_adjustment_bounds(self):
        """Test max_adjustment must be in [0.10, 0.30]."""
        # Valid values
        AdjustmentConfigModel(max_adjustment=0.10)
        AdjustmentConfigModel(max_adjustment=0.20)
        AdjustmentConfigModel(max_adjustment=0.30)

        # Invalid values
        with pytest.raises(ValidationError):
            AdjustmentConfigModel(max_adjustment=0.09)

        with pytest.raises(ValidationError):
            AdjustmentConfigModel(max_adjustment=0.31)

    def test_cache_ttl_minimum(self):
        """Test cache_ttl_seconds must be >= 60."""
        # Valid values
        AdjustmentConfigModel(cache_ttl_seconds=60)
        AdjustmentConfigModel(cache_ttl_seconds=300)
        AdjustmentConfigModel(cache_ttl_seconds=3600)

        # Invalid values
        with pytest.raises(ValidationError):
            AdjustmentConfigModel(cache_ttl_seconds=59)

        with pytest.raises(ValidationError):
            AdjustmentConfigModel(cache_ttl_seconds=0)

        with pytest.raises(ValidationError):
            AdjustmentConfigModel(cache_ttl_seconds=-1)

    def test_outlier_cap_validation(self):
        """Test outlier_cap must be in [0.05, 0.20]."""
        # Valid values
        AdjustmentConfigModel(outlier_cap=0.05)
        AdjustmentConfigModel(outlier_cap=0.10)
        AdjustmentConfigModel(outlier_cap=0.20)

        # Invalid values
        with pytest.raises(ValidationError):
            AdjustmentConfigModel(outlier_cap=0.04)

        with pytest.raises(ValidationError):
            AdjustmentConfigModel(outlier_cap=0.21)

    def test_extreme_alert_threshold_validation(self):
        """Test extreme_alert_threshold must be in [0.01, 0.10]."""
        # Valid values
        AdjustmentConfigModel(extreme_alert_threshold=0.01)
        AdjustmentConfigModel(extreme_alert_threshold=0.05)
        AdjustmentConfigModel(extreme_alert_threshold=0.10)

        # Invalid values
        with pytest.raises(ValidationError):
            AdjustmentConfigModel(extreme_alert_threshold=0.009)

        with pytest.raises(ValidationError):
            AdjustmentConfigModel(extreme_alert_threshold=0.11)

    def test_smoothing_periods_validation(self):
        """Test smoothing_periods must be in [1, 10]."""
        # Valid values
        AdjustmentConfigModel(smoothing_enabled=True, smoothing_periods=1)
        AdjustmentConfigModel(smoothing_enabled=True, smoothing_periods=5)
        AdjustmentConfigModel(smoothing_enabled=True, smoothing_periods=10)

        # Invalid values
        with pytest.raises(ValidationError):
            AdjustmentConfigModel(smoothing_enabled=True, smoothing_periods=0)

        with pytest.raises(ValidationError):
            AdjustmentConfigModel(smoothing_enabled=True, smoothing_periods=11)

    def test_config_immutability_after_creation(self):
        """Test that config fields can be modified after creation."""
        config = AdjustmentConfigModel(enabled=True, sensitivity=50.0)

        # Should be able to modify
        config.enabled = False
        assert config.enabled is False

        config.sensitivity = 75.0
        assert config.sensitivity == 75.0

    def test_serialization_roundtrip(self):
        """Test config serialization/deserialization."""
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            sensitivity=75.0,
            max_adjustment=0.25,
            cache_ttl_seconds=600,
            smoothing_enabled=True,
            smoothing_periods=5,
        )

        # Serialize
        data = config.model_dump()

        # Deserialize
        reconstructed = AdjustmentConfigModel(**data)

        # Should match original
        assert reconstructed.enabled == config.enabled
        assert reconstructed.symbol == config.symbol
        assert reconstructed.sensitivity == config.sensitivity
        assert reconstructed.max_adjustment == config.max_adjustment
        assert reconstructed.cache_ttl_seconds == config.cache_ttl_seconds
        assert reconstructed.smoothing_enabled == config.smoothing_enabled
        assert reconstructed.smoothing_periods == config.smoothing_periods


class TestTypeCoercion:
    """Test Pydantic type coercion behavior."""

    def test_string_to_decimal_coercion(self):
        """Test that numeric strings are coerced to Decimal."""
        rate = FundingRate(
            symbol="BTCUSDT",
            rate="0.0003",  # String instead of Decimal
            funding_time="2025-12-02T12:00:00+00:00",
        )

        # Should be coerced to Decimal
        assert isinstance(rate.rate, Decimal)
        assert rate.rate == Decimal("0.0003")

    def test_float_to_decimal_coercion(self):
        """Test that floats are coerced to Decimal."""
        adjustment = BiasAdjustment(
            funding_input=0.0003,  # Float instead of Decimal
            long_ratio=0.6,  # Float
            short_ratio=0.4,  # Float
            confidence=0.75,
        )

        # Should be coerced to Decimal
        assert isinstance(adjustment.funding_input, Decimal)
        assert isinstance(adjustment.long_ratio, Decimal)
        assert isinstance(adjustment.short_ratio, Decimal)

    def test_int_to_decimal_coercion(self):
        """Test that ints are coerced to Decimal."""
        adjustment = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.5"),
            short_ratio=Decimal("0.5"),
            confidence=0.5,
            total_oi=1000000,  # Int instead of Decimal
        )

        # Should be coerced to Decimal
        assert isinstance(adjustment.total_oi, Decimal)
        assert adjustment.total_oi == Decimal("1000000")


class TestFieldConstraints:
    """Test field-level constraints and validation."""

    def test_non_negative_oi_values(self):
        """Test OI values must be non-negative."""
        # Valid non-negative values
        BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=0.5,
            total_oi=Decimal("0"),  # Zero is valid
        )

        BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=0.5,
            total_oi=Decimal("1000000"),
        )

        # Negative OI should fail
        with pytest.raises(ValidationError):
            BiasAdjustment(
                funding_input=Decimal("0.0003"),
                long_ratio=Decimal("0.6"),
                short_ratio=Decimal("0.4"),
                confidence=0.5,
                total_oi=Decimal("-1000"),
            )

    def test_metadata_flexible_type(self):
        """Test metadata accepts various dict structures."""
        # Empty dict
        adj1 = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=0.5,
            metadata={},
        )
        assert adj1.metadata == {}

        # Nested structures
        adj2 = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.6"),
            short_ratio=Decimal("0.4"),
            confidence=0.5,
            metadata={
                "source": "binance",
                "nested": {"key": "value"},
                "list": [1, 2, 3],
            },
        )
        assert adj2.metadata["nested"]["key"] == "value"
        assert adj2.metadata["list"] == [1, 2, 3]
