"""
Tests for multi_model_reporter.py - Per-model report generation.

Tests cover:
- Multi-model report generation
- Report format support (JSON, TEXT)
- Comparison summary generation
"""

from datetime import datetime, timedelta
from decimal import Decimal

from datetime import date
from src.models.validation_run import TriggerType, ValidationGrade, ValidationRun, ValidationStatus
from src.models.validation_test import ValidationTest
from src.validation.reports.multi_model_reporter import MultiModelReporter, ReportFormat


class TestMultiModelReporter:
    """Test MultiModelReporter functionality."""

    def test_initialization(self):
        """MultiModelReporter should initialize with reporters."""
        # Act
        reporter = MultiModelReporter()

        # Assert
        assert reporter.json_reporter is not None
        assert reporter.text_reporter is not None

    def test_generate_model_reports_for_single_model(self):
        """generate_model_reports should generate reports for single model."""
        # Arrange
        reporter = MultiModelReporter()

        run = ValidationRun(
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

        tests = [
            ValidationTest(
                run_id="run-1",
                test_type=ValidationTestType.FUNDING_CORRELATION,
                score=Decimal("95.0"),
                passed=True,
                details={},
            )
        ]

        runs = {"model1": run}
        all_tests = {"model1": tests}

        # Act
        reports = reporter.generate_model_reports(
            runs=runs,
            tests=all_tests,
            formats=[ReportFormat.JSON],
        )

        # Assert
        assert "model1" in reports
        assert len(reports["model1"]) == 1  # One format
        assert reports["model1"][0].format == ReportFormat.JSON

    def test_generate_model_reports_for_multiple_models(self):
        """generate_model_reports should handle multiple models."""
        # Arrange
        reporter = MultiModelReporter()

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

        runs = {"model1": run1, "model2": run2}
        all_tests = {"model1": [], "model2": []}

        # Act
        reports = reporter.generate_model_reports(
            runs=runs,
            tests=all_tests,
            formats=[ReportFormat.JSON, ReportFormat.TEXT],
        )

        # Assert
        assert "model1" in reports
        assert "model2" in reports
        assert len(reports["model1"]) == 2  # JSON + TEXT
        assert len(reports["model2"]) == 2  # JSON + TEXT

    def test_generate_model_reports_with_json_format(self):
        """Reports should be generated in JSON format."""
        # Arrange
        reporter = MultiModelReporter()

        run = ValidationRun(
            run_id="run-1",
            model_name="model1",
            overall_grade=ValidationGrade.B,
            overall_score=Decimal("88.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        runs = {"model1": run}
        all_tests = {"model1": []}

        # Act
        reports = reporter.generate_model_reports(
            runs=runs,
            tests=all_tests,
            formats=[ReportFormat.JSON],
        )

        # Assert
        json_report = reports["model1"][0]
        assert json_report.format == ReportFormat.JSON
        assert "run_id" in json_report.content or '"run_id"' in json_report.content

    def test_generate_model_reports_with_text_format(self):
        """Reports should be generated in TEXT format."""
        # Arrange
        reporter = MultiModelReporter()

        run = ValidationRun(
            run_id="run-1",
            model_name="model1",
            overall_grade=ValidationGrade.C,
            overall_score=Decimal("75.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        runs = {"model1": run}
        all_tests = {"model1": []}

        # Act
        reports = reporter.generate_model_reports(
            runs=runs,
            tests=all_tests,
            formats=[ReportFormat.TEXT],
        )

        # Assert
        text_report = reports["model1"][0]
        assert text_report.format == ReportFormat.TEXT
        assert "Validation Report" in text_report.content or "VALIDATION" in text_report.content

    def test_generate_comparison_summary_for_multiple_models(self):
        """generate_comparison_summary should create comparison table."""
        # Arrange
        reporter = MultiModelReporter()

        run1 = ValidationRun(
            run_id="run-1",
            model_name="model_a",
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
            model_name="model_b",
            overall_grade=ValidationGrade.B,
            overall_score=Decimal("82.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        runs = {"model_a": run1, "model_b": run2}
        all_tests = {
            "model_a": [
                ValidationTest(
                    run_id="run-1",
                    test_type=ValidationTestType.FUNDING_CORRELATION,
                    score=Decimal("95.0"),
                    passed=True,
                    details={},
                )
            ],
            "model_b": [
                ValidationTest(
                    run_id="run-2",
                    test_type=ValidationTestType.FUNDING_CORRELATION,
                    score=Decimal("80.0"),
                    passed=True,
                    details={},
                )
            ],
        }

        # Act
        summary = reporter.generate_comparison_summary(runs=runs, tests=all_tests)

        # Assert
        assert "model_a" in summary
        assert "model_b" in summary
        assert "95" in summary or "95.0" in summary
        assert "82" in summary or "82.0" in summary

    def test_generate_comparison_summary_includes_grades(self):
        """Comparison summary should include model grades."""
        # Arrange
        reporter = MultiModelReporter()

        run1 = ValidationRun(
            run_id="run-1",
            model_name="best_model",
            overall_grade=ValidationGrade.A,
            overall_score=Decimal("98.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        run2 = ValidationRun(
            run_id="run-2",
            model_name="worst_model",
            overall_grade=ValidationGrade.F,
            overall_score=Decimal("45.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        runs = {"best_model": run1, "worst_model": run2}
        all_tests = {"best_model": [], "worst_model": []}

        # Act
        summary = reporter.generate_comparison_summary(runs=runs, tests=all_tests)

        # Assert
        assert "A" in summary
        assert "F" in summary

    def test_generate_reports_handles_empty_tests(self):
        """Reporter should handle runs with no tests."""
        # Arrange
        reporter = MultiModelReporter()

        run = ValidationRun(
            run_id="run-1",
            model_name="model1",
            overall_grade=ValidationGrade.B,
            overall_score=Decimal("80.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        runs = {"model1": run}
        all_tests = {"model1": []}  # No tests

        # Act
        reports = reporter.generate_model_reports(
            runs=runs,
            tests=all_tests,
            formats=[ReportFormat.JSON],
        )

        # Assert
        assert "model1" in reports
        assert len(reports["model1"]) > 0

    def test_default_formats_when_none_specified(self):
        """Reporter should use default formats when None specified."""
        # Arrange
        reporter = MultiModelReporter()

        run = ValidationRun(
            run_id="run-1",
            model_name="model1",
            overall_grade=ValidationGrade.A,
            overall_score=Decimal("90.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        runs = {"model1": run}
        all_tests = {"model1": []}

        # Act
        reports = reporter.generate_model_reports(
            runs=runs,
            tests=all_tests,
            formats=None,  # Use defaults
        )

        # Assert
        assert "model1" in reports
        # Should have at least JSON format by default
        assert len(reports["model1"]) > 0


class TestReportFormat:
    """Test ReportFormat enum."""

    def test_report_format_values(self):
        """ReportFormat should have expected values."""
        # Assert
        assert ReportFormat.JSON.value == "json"
        assert ReportFormat.TEXT.value == "text"

    def test_report_format_comparison(self):
        """Report formats should be comparable."""
        # Act/Assert
        assert ReportFormat.JSON == ReportFormat.JSON
        assert ReportFormat.JSON != ReportFormat.TEXT
