"""
TDD RED: Tests for ValidationTest model.

Tests individual validation test results within a run.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from src.models.validation_test import ValidationTest


class TestValidationTestModel:
    """Test suite for ValidationTest Pydantic model."""

    def test_create_validation_test_with_minimal_fields(self):
        """
        Test creating ValidationTest with required fields only.

        GIVEN minimal required fields
        WHEN creating a ValidationTest
        THEN model should validate successfully
        """
        test = ValidationTest(
            test_id="test-001",
            run_id="run-001",
            test_type="funding_correlation",
            test_name="Funding Rate Correlation Test",
            passed=True,
            score=Decimal("85.5"),
            weight=Decimal("0.40"),
            executed_at=datetime.utcnow(),
        )

        assert test.test_id == "test-001"
        assert test.run_id == "run-001"
        assert test.test_type == "funding_correlation"
        assert test.passed is True
        assert test.score == Decimal("85.5")
        assert test.weight == Decimal("0.40")

    def test_validation_test_type_must_be_valid(self):
        """
        Test that test_type must be one of valid values.

        GIVEN invalid test type
        WHEN creating ValidationTest
        THEN should raise validation error
        """
        with pytest.raises(ValueError):
            ValidationTest(
                test_id="test-002",
                run_id="run-001",
                test_type="invalid_test_type",  # Invalid
                test_name="Test",
                passed=False,
                score=Decimal("0"),
                weight=Decimal("0.33"),
                executed_at=datetime.utcnow(),
            )

    def test_validation_test_score_must_be_0_to_100(self):
        """
        Test that score must be between 0 and 100.

        GIVEN score outside valid range
        WHEN creating ValidationTest
        THEN should raise validation error
        """
        with pytest.raises(ValueError):
            ValidationTest(
                test_id="test-003",
                run_id="run-001",
                test_type="oi_conservation",
                test_name="OI Test",
                passed=False,
                score=Decimal("150.0"),  # Invalid - over 100
                weight=Decimal("0.35"),
                executed_at=datetime.utcnow(),
            )

    def test_validation_test_weight_must_be_0_to_1(self):
        """
        Test that weight must be between 0 and 1.

        GIVEN weight outside valid range
        WHEN creating ValidationTest
        THEN should raise validation error
        """
        with pytest.raises(ValueError):
            ValidationTest(
                test_id="test-004",
                run_id="run-001",
                test_type="directional_positioning",
                test_name="Directional Test",
                passed=True,
                score=Decimal("90.0"),
                weight=Decimal("1.5"),  # Invalid - over 1.0
                executed_at=datetime.utcnow(),
            )

    def test_validation_test_with_metrics_and_diagnostics(self):
        """
        Test creating ValidationTest with statistical metrics.

        GIVEN test with primary/secondary metrics and diagnostics
        WHEN creating ValidationTest
        THEN should store all data correctly
        """
        test = ValidationTest(
            test_id="test-005",
            run_id="run-001",
            test_type="funding_correlation",
            test_name="Funding Correlation",
            passed=True,
            score=Decimal("92.5"),
            weight=Decimal("0.40"),
            primary_metric=Decimal("0.85"),  # Correlation coefficient
            secondary_metric=Decimal("0.001"),  # P-value
            diagnostics={"sample_size": 720, "outliers_removed": 3},
            executed_at=datetime.utcnow(),
            duration_ms=1250,
        )

        assert test.primary_metric == Decimal("0.85")
        assert test.secondary_metric == Decimal("0.001")
        assert test.diagnostics["sample_size"] == 720
        assert test.diagnostics["outliers_removed"] == 3
        assert test.duration_ms == 1250

    def test_validation_test_failed_with_error_message(self):
        """
        Test creating a failed ValidationTest with error details.

        GIVEN test that failed
        WHEN creating with error message
        THEN should store error information
        """
        test = ValidationTest(
            test_id="test-006",
            run_id="run-001",
            test_type="oi_conservation",
            test_name="OI Conservation",
            passed=False,
            score=Decimal("0.0"),
            weight=Decimal("0.35"),
            error_message="Insufficient data: only 50% of expected OI data available",
            executed_at=datetime.utcnow(),
        )

        assert test.passed is False
        assert test.score == Decimal("0.0")
        assert "Insufficient data" in test.error_message

    def test_validation_test_weighted_contribution(self):
        """
        Test calculating weighted contribution to overall score.

        GIVEN test with score and weight
        WHEN calculating contribution
        THEN should return score * weight
        """
        test = ValidationTest(
            test_id="test-007",
            run_id="run-001",
            test_type="funding_correlation",
            test_name="Funding Test",
            passed=True,
            score=Decimal("85.0"),  # 85%
            weight=Decimal("0.40"),  # 40% weight
            executed_at=datetime.utcnow(),
        )

        # Weighted contribution = 85.0 * 0.40 = 34.0
        weighted = test.weighted_contribution()
        assert weighted == Decimal("34.0")
