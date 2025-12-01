"""
Alert manager for validation suite.

Triggers alerts when validation runs receive C or F grades.
"""

from typing import List

from src.models.validation_run import ValidationGrade, ValidationRun
from src.models.validation_test import ValidationTest
from src.validation.logger import logger


class AlertManager:
    """
    Manages alert triggers for validation failures.

    Sends notifications when validation grades indicate model degradation.
    """

    def __init__(self, email_handler=None):
        """
        Initialize alert manager.

        Args:
            email_handler: Optional email handler for notifications
        """
        self.email_handler = email_handler
        self.alert_triggers = [ValidationGrade.C, ValidationGrade.F]

    def should_trigger_alert(self, run: ValidationRun) -> bool:
        """
        Determine if validation run should trigger an alert.

        Args:
            run: ValidationRun instance

        Returns:
            True if alert should be triggered
        """
        if not run.overall_grade:
            logger.warning(f"Run {run.run_id} has no grade - skipping alert check")
            return False

        should_alert = run.overall_grade in self.alert_triggers

        if should_alert:
            logger.warning(
                f"Alert triggered: Run {run.run_id} received grade {run.overall_grade.value}"
            )
        else:
            logger.debug(
                f"No alert needed: Run {run.run_id} received grade {run.overall_grade.value}"
            )

        return should_alert

    def process_run(self, run: ValidationRun, tests: List[ValidationTest]) -> bool:
        """
        Process validation run and trigger alerts if needed.

        Args:
            run: ValidationRun instance
            tests: List of ValidationTest results

        Returns:
            True if alert was triggered and sent successfully
        """
        if not self.should_trigger_alert(run):
            return False

        logger.info(f"Processing alert for run {run.run_id} (grade: {run.overall_grade.value})")

        # Build alert context
        alert_context = self._build_alert_context(run, tests)

        # Send alerts
        success = self._send_alerts(alert_context)

        if success:
            logger.info(f"Alert sent successfully for run {run.run_id}")
        else:
            logger.error(f"Failed to send alert for run {run.run_id}")

        return success

    def _build_alert_context(self, run: ValidationRun, tests: List[ValidationTest]) -> dict:
        """
        Build alert context with relevant information.

        Args:
            run: ValidationRun instance
            tests: List of ValidationTest results

        Returns:
            Dict with alert context
        """
        # Identify failed tests
        failed_tests = [t for t in tests if not t.passed]

        # Build context
        context = {
            "run_id": run.run_id,
            "model_name": run.model_name,
            "grade": run.overall_grade.value if run.overall_grade else "N/A",
            "score": float(run.overall_score) if run.overall_score else 0.0,
            "status": run.status.value if run.status else "unknown",
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "duration_seconds": run.duration_seconds,
            "total_tests": len(tests),
            "failed_tests": len(failed_tests),
            "failed_test_names": [t.test_name for t in failed_tests],
            "error_message": run.error_message,
        }

        # Add test details
        test_details = []
        for test in tests:
            test_detail = {
                "name": test.test_name,
                "type": test.test_type.value if test.test_type else "unknown",
                "passed": test.passed,
                "score": float(test.score),
                "weight": float(test.weight),
                "error": test.error_message,
            }
            test_details.append(test_detail)

        context["test_details"] = test_details

        return context

    def _send_alerts(self, alert_context: dict) -> bool:
        """
        Send alerts via configured channels.

        Args:
            alert_context: Dict with alert information

        Returns:
            True if all alerts sent successfully
        """
        success = True

        # Send email alert if handler configured
        if self.email_handler:
            try:
                email_sent = self.email_handler.send_alert(alert_context)
                if not email_sent:
                    logger.error("Email alert failed")
                    success = False
            except Exception as e:
                logger.error(f"Error sending email alert: {e}", exc_info=True)
                success = False
        else:
            logger.warning("No email handler configured - skipping email alert")

        # Future: Could add other alert channels here
        # - Slack webhook
        # - PagerDuty
        # - Discord webhook
        # - SMS via Twilio

        return success

    def get_alert_summary(self, run: ValidationRun, tests: List[ValidationTest]) -> str:
        """
        Generate human-readable alert summary.

        Args:
            run: ValidationRun instance
            tests: List of ValidationTest results

        Returns:
            Formatted alert summary string
        """
        failed_tests = [t for t in tests if not t.passed]

        lines = [
            "=" * 60,
            "🚨 VALIDATION ALERT 🚨",
            "=" * 60,
            f"Model: {run.model_name}",
            f"Grade: {run.overall_grade.value if run.overall_grade else 'N/A'}",
            f"Score: {run.overall_score:.2f}/100" if run.overall_score else "Score: N/A",
            f"Run ID: {run.run_id}",
            "",
            "Failed Tests:",
        ]

        for test in failed_tests:
            lines.append(
                f"  ❌ {test.test_name}: {test.score:.1f}/100 (weight: {test.weight * 100:.0f}%)"
            )
            if test.error_message:
                lines.append(f"     Error: {test.error_message}")

        lines.extend(
            [
                "",
                "Action Required:",
                "  1. Review failed test diagnostics",
                "  2. Investigate model performance degradation",
                "  3. Check data quality and completeness",
                "  4. Consider retraining or parameter adjustment",
                "",
                "=" * 60,
            ]
        )

        return "\n".join(lines)
