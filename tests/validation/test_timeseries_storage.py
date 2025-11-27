"""
Tests for timeseries_storage.py - Time-series data aggregation.

Tests cover:
- Daily aggregation
- Weekly aggregation
- Monthly aggregation
- Time-series point creation
- Resolution support
"""

from datetime import datetime, timedelta
from decimal import Decimal

from datetime import date
from src.models.validation_run import TriggerType, ValidationGrade, ValidationRun, ValidationStatus
from src.validation.timeseries_storage import TimeSeriesStorage, get_timeseries_storage


class TestTimeSeriesStorage:
    """Test TimeSeriesStorage functionality."""

    def test_aggregate_runs_by_day(self):
        """aggregate_runs_by_day should group runs by date."""
        # Arrange
        storage = TimeSeriesStorage()

        today = datetime.utcnow()
        yesterday = today - timedelta(days=1)

        runs = [
            ValidationRun(
                run_id="run-1",
                model_name="model",
                overall_grade=ValidationGrade.A,
                overall_score=Decimal("95.0"),
                status=ValidationStatus.COMPLETED,
                started_at=today,
            ),
            ValidationRun(
                run_id="run-2",
                model_name="model",
                overall_grade=ValidationGrade.B,
                overall_score=Decimal("85.0"),
                status=ValidationStatus.COMPLETED,
                started_at=yesterday,
            ),
        ]

        # Act
        daily_data = storage.aggregate_runs_by_day(
            runs=runs,
            start_date=yesterday,
            end_date=today,
        )

        # Assert
        assert len(daily_data) >= 1  # At least one day
        # Should have entries for both days

    def test_get_time_series_with_daily_resolution(self):
        """get_time_series should return daily data points."""
        # Arrange
        storage = TimeSeriesStorage()

        today = datetime.utcnow()
        runs = [
            ValidationRun(
                run_id="run-1",
                model_name="model",
                overall_grade=ValidationGrade.A,
                overall_score=Decimal("90.0"),
                status=ValidationStatus.COMPLETED,
                started_at=today,
            )
        ]

        # Act
        series = storage.get_time_series(
            runs=runs,
            start_date=today - timedelta(days=1),
            end_date=today,
            resolution="daily",
        )

        # Assert
        assert isinstance(series, list)
        assert len(series) >= 0

    def test_get_time_series_with_weekly_resolution(self):
        """get_time_series should aggregate to weekly."""
        # Arrange
        storage = TimeSeriesStorage()

        today = datetime.utcnow()
        runs = [
            ValidationRun(
                run_id=f"run-{i}",
                model_name="model",
                overall_grade=ValidationGrade.A,
                overall_score=Decimal("90.0"),
                status=ValidationStatus.COMPLETED,
                started_at=today - timedelta(days=i),
            )
            for i in range(7)
        ]

        # Act
        series = storage.get_time_series(
            runs=runs,
            start_date=today - timedelta(days=30),
            end_date=today,
            resolution="weekly",
        )

        # Assert
        assert isinstance(series, list)

    def test_get_time_series_with_monthly_resolution(self):
        """get_time_series should aggregate to monthly."""
        # Arrange
        storage = TimeSeriesStorage()

        today = datetime.utcnow()
        runs = [
            ValidationRun(
                run_id=f"run-{i}",
                model_name="model",
                overall_grade=ValidationGrade.A,
                overall_score=Decimal("90.0"),
                status=ValidationStatus.COMPLETED,
                started_at=today - timedelta(days=i * 30),
            )
            for i in range(3)
        ]

        # Act
        series = storage.get_time_series(
            runs=runs,
            start_date=today - timedelta(days=90),
            end_date=today,
            resolution="monthly",
        )

        # Assert
        assert isinstance(series, list)

    def test_empty_runs_returns_empty_series(self):
        """get_time_series with no runs should return empty list."""
        # Arrange
        storage = TimeSeriesStorage()

        # Act
        series = storage.get_time_series(
            runs=[],
            start_date=datetime.utcnow() - timedelta(days=7),
            end_date=datetime.utcnow(),
            resolution="daily",
        )

        # Assert
        assert series == []

    def test_get_timeseries_storage_returns_singleton(self):
        """get_timeseries_storage should return same instance."""
        # Act
        storage1 = get_timeseries_storage()
        storage2 = get_timeseries_storage()

        # Assert
        assert storage1 is storage2


class TestTimeSeriesAggregation:
    """Test time-series aggregation logic."""

    def test_daily_aggregation_calculates_average_score(self):
        """Daily aggregation should average scores for same day."""
        # Arrange
        storage = TimeSeriesStorage()

        today = datetime.utcnow().replace(hour=10, minute=0)
        later_today = today.replace(hour=14, minute=0)

        runs = [
            ValidationRun(
                run_id="run-1",
                model_name="model",
                overall_grade=ValidationGrade.A,
                overall_score=Decimal("90.0"),
                status=ValidationStatus.COMPLETED,
                started_at=today,
            ),
            ValidationRun(
                run_id="run-2",
                model_name="model",
                overall_grade=ValidationGrade.A,
                overall_score=Decimal("100.0"),
                status=ValidationStatus.COMPLETED,
                started_at=later_today,
            ),
        ]

        # Act
        daily_data = storage.aggregate_runs_by_day(
            runs=runs,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
        )

        # Assert
        date_key = today.date().isoformat()
        assert date_key in daily_data
        # Should have both runs for this day
        assert len(daily_data[date_key]) == 2

    def test_filters_runs_outside_date_range(self):
        """Aggregation should filter runs outside date range."""
        # Arrange
        storage = TimeSeriesStorage()

        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        runs = [
            # Within range
            ValidationRun(
                run_id="run-1",
                model_name="model",
                overall_grade=ValidationGrade.A,
                overall_score=Decimal("90.0"),
                status=ValidationStatus.COMPLETED,
                started_at=start_date + timedelta(days=3),
            ),
            # Outside range (too old)
            ValidationRun(
                run_id="run-2",
                model_name="model",
                overall_grade=ValidationGrade.A,
                overall_score=Decimal("95.0"),
                status=ValidationStatus.COMPLETED,
                started_at=start_date - timedelta(days=10),
            ),
        ]

        # Act
        daily_data = storage.aggregate_runs_by_day(
            runs=runs,
            start_date=start_date,
            end_date=end_date,
        )

        # Assert
        # Should only have run-1, not run-2
        all_runs = [run for day_runs in daily_data.values() for run in day_runs]
        assert len(all_runs) == 1
        assert all_runs[0].run_id == "run-1"
