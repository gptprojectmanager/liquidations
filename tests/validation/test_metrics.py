"""
Tests for metrics.py - KPI and summary metrics calculator.

Tests cover:
- Summary metrics calculation
- KPI calculation
- Test performance metrics
- Reliability metrics
"""

from datetime import datetime, timedelta
from decimal import Decimal

from datetime import date
from src.models.validation_run import TriggerType, ValidationGrade, ValidationRun, ValidationStatus
from src.models.validation_test import ValidationTest
from src.validation.visualization.metrics import MetricsCalculator, get_metrics_calculator


class TestMetricsCalculator:
    """Test MetricsCalculator functionality."""

    def test_calculate_summary_metrics_with_runs(self):
        """Summary metrics should be calculated correctly."""
        # Arrange
        calculator = MetricsCalculator()

        runs = [
            ValidationRun(
                run_id=f"run-{i}",
                model_name="model",
                overall_grade=ValidationGrade.A if i % 2 == 0 else ValidationGrade.B,
                overall_score=Decimal(str(90.0 + i)),
                status=ValidationStatus.COMPLETED,
                started_at=datetime.utcnow() - timedelta(days=i),
            )
            for i in range(10)
        ]

        # Act
        metrics = calculator.calculate_summary_metrics(runs)

        # Assert
        assert metrics["total_runs"] == 10
        assert "score_stats" in metrics
        assert "mean" in metrics["score_stats"]
        assert "grade_distribution" in metrics
        assert "pass_rate" in metrics

    def test_calculate_kpis_compares_periods(self):
        """KPIs should compare first half vs second half."""
        # Arrange
        calculator = MetricsCalculator()

        # First half: avg 80, Second half: avg 90 (improvement)
        runs = [
            ValidationRun(
                run_id=f"run-{i}",
                model_name="model",
                overall_grade=ValidationGrade.B,
                overall_score=Decimal("80.0"),
                status=ValidationStatus.COMPLETED,
                started_at=datetime.utcnow() - timedelta(days=10 - i),
            )
            for i in range(5)
        ] + [
            ValidationRun(
                run_id=f"run-{i + 5}",
                model_name="model",
                overall_grade=ValidationGrade.A,
                overall_score=Decimal("90.0"),
                status=ValidationStatus.COMPLETED,
                started_at=datetime.utcnow() - timedelta(days=5 - i),
            )
            for i in range(5)
        ]

        # Act
        kpis = calculator.calculate_kpis(runs)

        # Assert
        assert "current_score" in kpis
        assert "previous_score" in kpis
        assert "score_change_percent" in kpis
        assert kpis["score_change_percent"] > 0  # Improvement

    def test_calculate_test_performance_groups_by_type(self):
        """Test performance should be grouped by test type."""
        # Arrange
        calculator = MetricsCalculator()

        tests = [
            ValidationTest(
                run_id="run-1",
                test_type=ValidationTestType.FUNDING_CORRELATION,
                score=Decimal("90.0"),
                passed=True,
                details={},
            ),
            ValidationTest(
                run_id="run-2",
                test_type=ValidationTestType.FUNDING_CORRELATION,
                score=Decimal("85.0"),
                passed=True,
                details={},
            ),
            ValidationTest(
                run_id="run-3",
                test_type=ValidationTestType.OI_CONSERVATION,
                score=Decimal("95.0"),
                passed=True,
                details={},
            ),
        ]

        # Act
        performance = calculator.calculate_test_performance(tests)

        # Assert
        assert "funding_correlation" in performance
        assert "oi_conservation" in performance
        assert performance["funding_correlation"]["total_runs"] == 2
        assert performance["oi_conservation"]["total_runs"] == 1

    def test_calculate_reliability_metrics_calculates_rates(self):
        """Reliability metrics should calculate completion/failure rates."""
        # Arrange
        calculator = MetricsCalculator()

        runs = [
            ValidationRun(
                run_id=f"run-{i}",
                model_name="model",
                overall_grade=ValidationGrade.A,
                overall_score=Decimal("90.0"),
                status=ValidationStatus.COMPLETED if i < 8 else ValidationStatus.FAILED,
                started_at=datetime.utcnow(),
            )
            for i in range(10)
        ]

        # Act
        metrics = calculator.calculate_reliability_metrics(runs)

        # Assert
        assert "completion_rate" in metrics
        assert "failure_rate" in metrics
        assert abs(metrics["completion_rate"] - 80.0) < 0.1  # 8/10 = 80%
        assert abs(metrics["failure_rate"] - 20.0) < 0.1  # 2/10 = 20%

    def test_empty_runs_returns_empty_metrics(self):
        """Empty runs should return empty metrics structure."""
        # Arrange
        calculator = MetricsCalculator()

        # Act
        metrics = calculator.calculate_summary_metrics([])

        # Assert
        assert metrics["total_runs"] == 0
        assert metrics["pass_rate"] == 0

    def test_get_metrics_calculator_returns_singleton(self):
        """get_metrics_calculator should return same instance."""
        # Act
        calc1 = get_metrics_calculator()
        calc2 = get_metrics_calculator()

        # Assert
        assert calc1 is calc2
