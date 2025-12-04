"""
TDD RED: Tests for ValidationRun model.

Tests validation run data model creation, status tracking, and scoring.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.models.validation_run import ValidationRun


class TestValidationRunModel:
    """Test suite for ValidationRun Pydantic model."""

    def test_create_validation_run_with_minimal_fields(self):
        """
        Test creating ValidationRun with only required fields.

        GIVEN minimal required fields
        WHEN creating a ValidationRun
        THEN model should validate and set defaults
        """
        run = ValidationRun(
            run_id="test-run-001",
            model_name="liquidation_model_v1",
            trigger_type="manual",
            started_at=datetime.utcnow(),
            data_start_date=datetime.utcnow().date() - timedelta(days=30),
            data_end_date=datetime.utcnow().date(),
            status="running",
        )

        assert run.run_id == "test-run-001"
        assert run.model_name == "liquidation_model_v1"
        assert run.trigger_type == "manual"
        assert run.status == "running"
        assert run.overall_grade is None
        assert run.overall_score is None

    def test_validation_run_status_must_be_valid(self):
        """
        Test that status must be one of valid values.

        GIVEN invalid status value
        WHEN creating ValidationRun
        THEN should raise validation error
        """
        with pytest.raises(ValueError):
            ValidationRun(
                run_id="test-run-002",
                model_name="model",
                trigger_type="manual",
                started_at=datetime.utcnow(),
                data_start_date=datetime.utcnow().date(),
                data_end_date=datetime.utcnow().date(),
                status="invalid_status",  # Invalid
            )

    def test_validation_run_with_completed_status_requires_results(self):
        """
        Test that completed runs should have grade and score.

        GIVEN completed validation run
        WHEN creating with results
        THEN should accept grade and score
        """
        run = ValidationRun(
            run_id="test-run-003",
            model_name="model",
            trigger_type="scheduled",
            started_at=datetime.utcnow() - timedelta(minutes=5),
            completed_at=datetime.utcnow(),
            data_start_date=datetime.utcnow().date() - timedelta(days=30),
            data_end_date=datetime.utcnow().date(),
            status="completed",
            overall_grade="A",
            overall_score=Decimal("95.5"),
            duration_seconds=300,
        )

        assert run.status == "completed"
        assert run.overall_grade == "A"
        assert run.overall_score == Decimal("95.5")
        assert run.duration_seconds == 300

    def test_validation_run_calculates_duration_from_timestamps(self):
        """
        Test automatic duration calculation.

        GIVEN started_at and completed_at timestamps
        WHEN accessing duration
        THEN should calculate seconds between timestamps
        """
        started = datetime.utcnow() - timedelta(minutes=5)
        completed = datetime.utcnow()

        run = ValidationRun(
            run_id="test-run-004",
            model_name="model",
            trigger_type="scheduled",
            started_at=started,
            completed_at=completed,
            data_start_date=datetime.utcnow().date(),
            data_end_date=datetime.utcnow().date(),
            status="completed",
        )

        # Should auto-calculate duration
        assert run.duration_seconds is not None
        assert 290 <= run.duration_seconds <= 310  # ~5 minutes with tolerance

    def test_validation_run_grade_must_be_valid(self):
        """
        Test that grade must be A, B, C, or F.

        GIVEN invalid grade
        WHEN creating ValidationRun
        THEN should raise validation error
        """
        with pytest.raises(ValueError):
            ValidationRun(
                run_id="test-run-005",
                model_name="model",
                trigger_type="manual",
                started_at=datetime.utcnow(),
                data_start_date=datetime.utcnow().date(),
                data_end_date=datetime.utcnow().date(),
                status="completed",
                overall_grade="D",  # Invalid - only A, B, C, F allowed
            )

    def test_validation_run_score_must_be_0_to_100(self):
        """
        Test that score must be between 0 and 100.

        GIVEN score outside valid range
        WHEN creating ValidationRun
        THEN should raise validation error
        """
        with pytest.raises(ValueError):
            ValidationRun(
                run_id="test-run-006",
                model_name="model",
                trigger_type="manual",
                started_at=datetime.utcnow(),
                data_start_date=datetime.utcnow().date(),
                data_end_date=datetime.utcnow().date(),
                status="completed",
                overall_score=Decimal("150.0"),  # Invalid - over 100
            )

    def test_validation_run_data_completeness_validation(self):
        """
        Test data completeness percentage validation.

        GIVEN data completeness value
        WHEN creating ValidationRun
        THEN should validate 0-100 range
        """
        run = ValidationRun(
            run_id="test-run-007",
            model_name="model",
            trigger_type="manual",
            started_at=datetime.utcnow(),
            data_start_date=datetime.utcnow().date(),
            data_end_date=datetime.utcnow().date(),
            status="completed",
            data_completeness=Decimal("85.5"),
        )

        assert run.data_completeness == Decimal("85.5")

        # Invalid completeness over 100
        with pytest.raises(ValueError):
            ValidationRun(
                run_id="test-run-008",
                model_name="model",
                trigger_type="manual",
                started_at=datetime.utcnow(),
                data_start_date=datetime.utcnow().date(),
                data_end_date=datetime.utcnow().date(),
                status="running",
                data_completeness=Decimal("150.0"),
            )
