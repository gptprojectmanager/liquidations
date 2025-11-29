"""
Tests for API endpoints validation.py - Manual validation triggers.

Tests cover:
- POST /api/validation/run (trigger validation)
- GET /api/validation/status/{run_id} (check status)
- GET /api/validation/report/{run_id} (get report)
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

# Create test app
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.endpoints.validation import router
from src.models.validation_run import TriggerType, ValidationGrade, ValidationRun, ValidationStatus

app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestValidationAPI:
    """Test validation API endpoints."""

    @patch("src.api.endpoints.validation.ValidationStorage")
    @patch("src.validation.test_runner.ValidationTestRunner")
    def test_trigger_validation_returns_202_accepted(self, mock_runner_class, mock_storage):
        """POST /api/validation/run should return 202 Accepted."""
        # Arrange
        mock_runner = Mock()
        mock_runner.run_id = "test-run-123"
        mock_runner_class.return_value = mock_runner

        # Act
        response = client.post(
            "/api/validation/run",
            json={
                "model_name": "liquidation_model_v1",
                "triggered_by": "test_user",
            },
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert data["run_id"] == "test-run-123"
        assert data["status"] == "queued"

    @patch("src.api.endpoints.validation.ValidationStorage")
    def test_get_validation_status_returns_run_status(self, mock_storage_class):
        """GET /api/validation/status/{run_id} should return status."""
        # Arrange
        mock_storage = Mock()
        mock_storage_class.return_value.__enter__.return_value = mock_storage

        test_run_id = "550e8400-e29b-41d4-a716-446655440000"
        test_run = ValidationRun(
            run_id=test_run_id,
            model_name="model",
            overall_grade=ValidationGrade.A,
            overall_score=Decimal("95.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
            completed_at=datetime.utcnow(),
        )

        mock_storage.get_run.return_value = test_run

        # Act
        response = client.get(f"/api/validation/status/{test_run_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == test_run_id
        assert data["status"] == "completed"

    @patch("src.api.endpoints.validation.ValidationStorage")
    def test_get_validation_status_404_for_nonexistent_run(self, mock_storage_class):
        """GET /api/validation/status/{run_id} should return 404 if not found."""
        # Arrange
        mock_storage = Mock()
        mock_storage_class.return_value.__enter__.return_value = mock_storage
        mock_storage.get_run.return_value = None  # Not found

        nonexistent_uuid = "550e8400-e29b-41d4-a716-446655440001"

        # Act
        response = client.get(f"/api/validation/status/{nonexistent_uuid}")

        # Assert
        assert response.status_code == 404

    @patch("src.api.endpoints.validation.ValidationStorage")
    def test_get_validation_report_returns_json_report(self, mock_storage_class):
        """GET /api/validation/report/{run_id} should return JSON report."""
        # Arrange
        mock_storage = Mock()
        mock_storage_class.return_value.__enter__.return_value = mock_storage

        test_run_id = "550e8400-e29b-41d4-a716-446655440000"
        test_run = ValidationRun(
            run_id=test_run_id,
            model_name="model",
            overall_grade=ValidationGrade.A,
            overall_score=Decimal("95.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
            completed_at=datetime.utcnow(),
        )

        mock_storage.get_run.return_value = test_run
        mock_storage.get_tests_for_run.return_value = []
        from src.models.validation_report import ReportFormat

        mock_storage.get_reports_for_run.return_value = [
            Mock(
                report_content='{"test": "data"}',
                format=ReportFormat.JSON,
                run_id=test_run_id,
                summary={},
                recommendations=[],
                created_at=datetime.utcnow(),
            )
        ]

        # Act
        response = client.get(f"/api/validation/report/{test_run_id}?format=json")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "report_content" in data or "test" in data

    @patch("src.api.endpoints.validation.ValidationStorage")
    def test_get_validation_report_400_for_incomplete_run(self, mock_storage_class):
        """GET /api/validation/report should return 400 for incomplete runs."""
        # Arrange
        mock_storage = Mock()
        mock_storage_class.return_value.__enter__.return_value = mock_storage

        test_run_id = "550e8400-e29b-41d4-a716-446655440000"
        test_run = ValidationRun(
            run_id=test_run_id,
            model_name="model",
            overall_grade=None,
            overall_score=None,
            status=ValidationStatus.RUNNING,  # Still running
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        mock_storage.get_run.return_value = test_run

        # Act
        response = client.get(f"/api/validation/report/{test_run_id}")

        # Assert
        assert response.status_code == 400
