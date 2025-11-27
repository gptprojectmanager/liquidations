"""
Tests for API endpoints trends.py - Dashboard and trend analysis.

Tests cover:
- GET /api/validation/trends (historical trends)
- GET /api/validation/compare (model comparison)
- GET /api/validation/dashboard (aggregated dashboard data)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

# Create test app
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.endpoints.trends import router
from datetime import date, timedelta
from src.models.validation_run import TriggerType, ValidationGrade, ValidationRun, ValidationStatus

app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestTrendsAPI:
    """Test trends API endpoints."""

    @patch("src.api.endpoints.trends.ValidationStorage")
    @patch("src.api.endpoints.trends.get_timeseries_storage")
    @patch("src.api.endpoints.trends.get_trend_calculator")
    def test_get_trends_returns_time_series_data(
        self, mock_trend_calc, mock_ts_storage, mock_storage_class
    ):
        """GET /api/validation/trends should return trend data."""
        # Arrange
        mock_storage = Mock()
        mock_storage_class.return_value.__enter__.return_value = mock_storage

        test_runs = [
            ValidationRun(
                run_id=f"run-{i}",
                model_name="liquidation_model_v1",
                overall_grade=ValidationGrade.A,
                overall_score=Decimal("90.0"),
                status=ValidationStatus.COMPLETED,
                trigger_type=TriggerType.MANUAL,
                started_at=datetime.utcnow() - timedelta(days=i),
                data_start_date=date.today() - timedelta(days=30),
                data_end_date=date.today(),
            )
            for i in range(10)
        ]

        mock_storage.get_runs_in_date_range.return_value = test_runs

        mock_ts = Mock()
        mock_ts.get_time_series.return_value = []
        mock_ts_storage.return_value = mock_ts

        mock_calc = Mock()
        mock_calc.calculate_multi_metric_trends.return_value = {}
        mock_trend_calc.return_value = mock_calc

        # Act
        response = client.get(
            "/api/validation/trends?model_name=liquidation_model_v1&days=90&resolution=daily"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "model_name" in data
        assert "time_series" in data
        assert "trend_analysis" in data

    @patch("src.api.endpoints.trends.ValidationStorage")
    def test_get_trends_404_for_no_runs(self, mock_storage_class):
        """GET /api/validation/trends should return 404 if no runs found."""
        # Arrange
        mock_storage = Mock()
        mock_storage_class.return_value.__enter__.return_value = mock_storage
        mock_storage.get_runs_in_date_range.return_value = []  # No runs

        # Act
        response = client.get("/api/validation/trends?model_name=nonexistent&days=90")

        # Assert
        assert response.status_code == 404

    @patch("src.api.endpoints.trends.ValidationStorage")
    @patch("src.api.endpoints.trends.get_model_comparison")
    def test_compare_models_returns_comparison_data(self, mock_comparison, mock_storage_class):
        """GET /api/validation/compare should return model comparison."""
        # Arrange
        mock_storage = Mock()
        mock_storage_class.return_value.__enter__.return_value = mock_storage

        run1 = ValidationRun(
            run_id="run-1",
            model_name="model1",
            overall_grade=ValidationGrade.A,
            overall_score=Decimal("95.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        run2 = ValidationRun(
            run_id="run-2",
            model_name="model2",
            overall_grade=ValidationGrade.B,
            overall_score=Decimal("85.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        def get_runs_in_date_range(model_name, start_date, end_date):
            if model_name == "model1":
                return [run1]
            elif model_name == "model2":
                return [run2]
            return []

        mock_storage.get_runs_in_date_range.side_effect = get_runs_in_date_range
        mock_storage.get_tests_for_run.return_value = []

        mock_comp = Mock()
        mock_comp.compare_scores.return_value = {"model1": 95.0, "model2": 85.0}
        mock_comp.compare_grades.return_value = {"model1": "A", "model2": "B"}
        mock_comp.rank_models.return_value = [
            ("model1", 95.0, "A"),
            ("model2", 85.0, "B"),
        ]
        mock_comp.get_statistics.return_value = {"mean": 90.0}
        mock_comp.recommend_best_model.return_value = ("model1", "Highest score")
        mock_comparison.return_value = mock_comp

        # Act
        response = client.get("/api/validation/compare?model_names=model1,model2&days=30")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert "comparison_metrics" in data
        assert "rankings" in data
        assert "best_model" in data

    @patch("src.api.endpoints.trends.ValidationStorage")
    @patch("src.api.endpoints.trends.get_timeseries_storage")
    @patch("src.api.endpoints.trends.get_trend_calculator")
    @patch("src.api.endpoints.trends.get_moving_averages")
    @patch("src.api.endpoints.trends.get_degradation_detector")
    def test_get_dashboard_data_aggregates_multiple_sources(
        self, mock_deg, mock_ma, mock_trend, mock_ts, mock_storage_class
    ):
        """GET /api/validation/dashboard should aggregate dashboard data."""
        # Arrange
        mock_storage = Mock()
        mock_storage_class.return_value.__enter__.return_value = mock_storage

        test_run = ValidationRun(
            run_id="run-1",
            model_name="liquidation_model_v1",
            overall_grade=ValidationGrade.A,
            overall_score=Decimal("92.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
            completed_at=datetime.utcnow(),
        )

        mock_storage.get_runs_in_date_range.return_value = [test_run]
        mock_storage.get_tests_for_run.return_value = []

        # Mock all dependencies
        mock_ts.return_value.get_time_series.return_value = []
        mock_trend.return_value.calculate_multi_metric_trends.return_value = {}
        mock_ma.return_value.calculate_all_averages.return_value = {"sma": [], "ema": [], "wma": []}
        mock_deg.return_value.detect_multi_metric_degradation.return_value = {}

        # Act
        response = client.get("/api/validation/dashboard?model_name=liquidation_model_v1&days=90")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "model_name" in data
        assert "latest_run" in data
        assert "trends" in data
        assert "statistics" in data
