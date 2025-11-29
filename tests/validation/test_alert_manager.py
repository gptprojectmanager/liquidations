"""
Tests for alert_manager.py - Alert triggering logic.

Tests cover:
- Alert triggering for C/F grades
- Alert context building
- Email handler integration
- Alert suppression logic
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from src.models.validation_run import TriggerType, ValidationGrade, ValidationRun, ValidationStatus
from src.models.validation_test import ValidationTest, ValidationTestType
from src.validation.alerts.alert_manager import AlertManager


class TestAlertManager:
    """Test AlertManager functionality."""

    def test_should_trigger_alert_returns_true_for_grade_c(self):
        """Alert should trigger for grade C."""
        # Arrange
        manager = AlertManager()
        run = ValidationRun(
            run_id="test-run-1",
            model_name="test_model",
            overall_grade=ValidationGrade.C,
            overall_score=Decimal("75.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        # Act
        result = manager.should_trigger_alert(run)

        # Assert
        assert result is True

    def test_should_trigger_alert_returns_true_for_grade_f(self):
        """Alert should trigger for grade F."""
        # Arrange
        manager = AlertManager()
        run = ValidationRun(
            run_id="test-run-2",
            model_name="test_model",
            overall_grade=ValidationGrade.F,
            overall_score=Decimal("50.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        # Act
        result = manager.should_trigger_alert(run)

        # Assert
        assert result is True

    def test_should_trigger_alert_returns_false_for_grade_a(self):
        """Alert should NOT trigger for grade A."""
        # Arrange
        manager = AlertManager()
        run = ValidationRun(
            run_id="test-run-3",
            model_name="test_model",
            overall_grade=ValidationGrade.A,
            overall_score=Decimal("95.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        # Act
        result = manager.should_trigger_alert(run)

        # Assert
        assert result is False

    def test_should_trigger_alert_returns_false_for_grade_b(self):
        """Alert should NOT trigger for grade B."""
        # Arrange
        manager = AlertManager()
        run = ValidationRun(
            run_id="test-run-4",
            model_name="test_model",
            overall_grade=ValidationGrade.B,
            overall_score=Decimal("85.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        # Act
        result = manager.should_trigger_alert(run)

        # Assert
        assert result is False

    def test_should_trigger_alert_returns_false_when_no_grade(self):
        """Alert should NOT trigger when grade is None."""
        # Arrange
        manager = AlertManager()
        run = ValidationRun(
            run_id="test-run-5",
            model_name="test_model",
            overall_grade=None,
            overall_score=None,
            status=ValidationStatus.RUNNING,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        # Act
        result = manager.should_trigger_alert(run)

        # Assert
        assert result is False

    def test_build_alert_context_includes_all_required_fields(self):
        """Alert context should include all necessary information."""
        # Arrange
        manager = AlertManager()
        run = ValidationRun(
            run_id="test-run-6",
            model_name="test_model",
            overall_grade=ValidationGrade.F,
            overall_score=Decimal("45.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
            completed_at=datetime.utcnow(),
            duration_seconds=120,
        )
        tests = [
            ValidationTest(
                test_id="test-1",
                run_id="test-run-6",
                test_type=ValidationTestType.FUNDING_CORRELATION,
                test_name="Funding Correlation Test",
                score=Decimal("40.0"),
                passed=False,
                weight=Decimal("0.33"),
                executed_at=datetime.utcnow(),
                diagnostics={},
            ),
        ]

        # Act
        context = manager._build_alert_context(run, tests)

        # Assert
        assert "run_id" in context
        assert "model_name" in context
        assert "grade" in context
        assert "score" in context
        assert "status" in context
        assert "started_at" in context
        assert "completed_at" in context
        assert "duration_seconds" in context
        assert "test_details" in context
        assert context["run_id"] == "test-run-6"
        assert context["grade"] == "F"
        assert float(context["score"]) == 45.0

    def test_process_run_sends_alert_when_grade_f(self):
        """Process run should send alert for grade F."""
        # Arrange
        mock_email_handler = Mock()
        mock_email_handler.send_alert.return_value = True

        manager = AlertManager(email_handler=mock_email_handler)

        run = ValidationRun(
            run_id="test-run-7",
            model_name="test_model",
            overall_grade=ValidationGrade.F,
            overall_score=Decimal("30.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )
        tests = []

        # Act
        result = manager.process_run(run, tests)

        # Assert
        assert result is True
        mock_email_handler.send_alert.assert_called_once()

    def test_process_run_does_not_send_alert_when_grade_a(self):
        """Process run should NOT send alert for grade A."""
        # Arrange
        mock_email_handler = Mock()
        manager = AlertManager(email_handler=mock_email_handler)

        run = ValidationRun(
            run_id="test-run-8",
            model_name="test_model",
            overall_grade=ValidationGrade.A,
            overall_score=Decimal("95.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )
        tests = []

        # Act
        result = manager.process_run(run, tests)

        # Assert
        assert result is False
        mock_email_handler.send_alert.assert_not_called()

    def test_process_run_handles_email_failure_gracefully(self):
        """Process run should handle email failures without crashing."""
        # Arrange
        mock_email_handler = Mock()
        mock_email_handler.send_alert.side_effect = Exception("SMTP error")

        manager = AlertManager(email_handler=mock_email_handler)

        run = ValidationRun(
            run_id="test-run-9",
            model_name="test_model",
            overall_grade=ValidationGrade.F,
            overall_score=Decimal("20.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )
        tests = []

        # Act
        result = manager.process_run(run, tests)

        # Assert
        assert result is False

    def test_custom_trigger_grades_can_be_configured(self):
        """Alert manager should support custom trigger grades."""
        # Arrange
        manager = AlertManager()
        manager.alert_triggers = [ValidationGrade.F]  # Only F triggers

        run_c = ValidationRun(
            run_id="test-run-10",
            model_name="test_model",
            overall_grade=ValidationGrade.C,
            overall_score=Decimal("75.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        run_f = ValidationRun(
            run_id="test-run-11",
            model_name="test_model",
            overall_grade=ValidationGrade.F,
            overall_score=Decimal("50.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )

        # Act
        result_c = manager.should_trigger_alert(run_c)
        result_f = manager.should_trigger_alert(run_f)

        # Assert
        assert result_c is False  # C should not trigger
        assert result_f is True  # F should trigger

    def test_alert_context_includes_failed_tests_count(self):
        """Alert context should count failed tests."""
        # Arrange
        manager = AlertManager()
        run = ValidationRun(
            run_id="test-run-12",
            model_name="test_model",
            overall_grade=ValidationGrade.F,
            overall_score=Decimal("40.0"),
            status=ValidationStatus.COMPLETED,
            trigger_type=TriggerType.MANUAL,
            started_at=datetime.utcnow(),
            data_start_date=date.today() - timedelta(days=30),
            data_end_date=date.today(),
        )
        tests = [
            ValidationTest(
                test_id="test-2",
                run_id="test-run-12",
                test_type=ValidationTestType.FUNDING_CORRELATION,
                test_name="Funding Correlation Test",
                score=Decimal("50.0"),
                passed=False,
                weight=Decimal("0.33"),
                executed_at=datetime.utcnow(),
                diagnostics={},
            ),
            ValidationTest(
                test_id="test-3",
                run_id="test-run-12",
                test_type=ValidationTestType.OI_CONSERVATION,
                test_name="OI Conservation Test",
                score=Decimal("40.0"),
                passed=False,
                weight=Decimal("0.33"),
                executed_at=datetime.utcnow(),
                diagnostics={},
            ),
            ValidationTest(
                test_id="test-4",
                run_id="test-run-12",
                test_type=ValidationTestType.DIRECTIONAL_POSITIONING,
                test_name="Directional Positioning Test",
                score=Decimal("30.0"),
                passed=False,
                weight=Decimal("0.34"),
                executed_at=datetime.utcnow(),
                diagnostics={},
            ),
        ]

        # Act
        context = manager._build_alert_context(run, tests)

        # Assert
        assert "test_details" in context
        assert len(context["test_details"]) == 3
        failed_tests = [t for t in context["test_details"] if not t["passed"]]
        assert len(failed_tests) == 3
