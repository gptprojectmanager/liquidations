"""
Human-readable text report generator for validation suite.

Creates formatted text reports for console output and email notifications.
"""

import uuid
from datetime import datetime
from typing import List

from src.models.validation_report import ReportFormat, ValidationReport
from src.models.validation_run import ValidationRun
from src.models.validation_test import ValidationTest
from src.validation.logger import logger


class TextReporter:
    """
    Generates human-readable text validation reports.

    Creates formatted text output suitable for console display,
    email notifications, and human review.
    """

    def generate_report(self, run: ValidationRun, tests: List[ValidationTest]) -> ValidationReport:
        """
        Generate text report from validation results.

        Args:
            run: ValidationRun instance
            tests: List of ValidationTest results

        Returns:
            ValidationReport with text content
        """
        logger.info(f"Generating text report for run {run.run_id}")

        # Build report sections
        lines = []
        lines.append(self._header(run))
        lines.append(self._summary(run))
        lines.append(self._test_results(tests))
        lines.append(self._recommendations(run, tests))
        lines.append(self._footer())

        report_content = "\n".join(lines)

        # Build summary dict (same as JSON for consistency)
        summary = {
            "run_id": run.run_id,
            "model_name": run.model_name,
            "overall_grade": run.overall_grade.value if run.overall_grade else None,
            "overall_score": float(run.overall_score) if run.overall_score else 0.0,
            "status": run.status.value if run.status else "unknown",
        }

        # Generate recommendations
        recommendations = self._generate_recommendations(run, tests)

        # Create ValidationReport
        report = ValidationReport(
            report_id=str(uuid.uuid4()),
            run_id=run.run_id,
            format=ReportFormat.TEXT,
            report_content=report_content,
            summary=summary,
            recommendations=recommendations,
        )

        logger.info(f"Text report generated: {len(lines)} lines, grade={run.overall_grade}")

        return report

    def _header(self, run: ValidationRun) -> str:
        """Generate report header."""
        lines = [
            "=" * 80,
            "VALIDATION REPORT".center(80),
            "=" * 80,
            f"Run ID:     {run.run_id}",
            f"Model:      {run.model_name}",
            f"Started:    {run.started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Completed:  {run.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC') if run.completed_at else 'In Progress'}",
            f"Duration:   {run.duration_seconds}s" if run.duration_seconds else "Duration:   N/A",
            "=" * 80,
            "",
        ]
        return "\n".join(lines)

    def _summary(self, run: ValidationRun) -> str:
        """Generate summary section."""
        grade_emoji = {
            "A": "🌟",
            "B": "✅",
            "C": "⚠️",
            "F": "❌",
        }

        grade_str = run.overall_grade.value if run.overall_grade else "N/A"
        emoji = grade_emoji.get(grade_str, "")

        lines = [
            "OVERALL RESULTS",
            "-" * 80,
            f"Grade:      {emoji} {grade_str}",
            f"Score:      {run.overall_score:.2f}/100" if run.overall_score else "Score:      N/A",
            f"Status:     {run.status.value if run.status else 'Unknown'}",
            "",
            "DATA WINDOW",
            "-" * 80,
            f"Period:     {run.data_start_date} to {run.data_end_date}",
            f"Days:       {(run.data_end_date - run.data_start_date).days}",
            f"Completeness: {run.data_completeness:.1f}%"
            if run.data_completeness
            else "Completeness: N/A",
            "",
        ]
        return "\n".join(lines)

    def _test_results(self, tests: List[ValidationTest]) -> str:
        """Generate test results section."""
        lines = [
            "TEST RESULTS",
            "-" * 80,
        ]

        if not tests:
            lines.append("No tests executed")
            lines.append("")
            return "\n".join(lines)

        # Header
        lines.append(f"{'Test Name':<40} {'Status':<10} {'Score':<10} {'Weight':<10}")
        lines.append("-" * 80)

        # Test rows
        for test in tests:
            status = "✅ PASS" if test.passed else "❌ FAIL"
            score_str = f"{test.score:.1f}/100"
            weight_str = f"{test.weight * 100:.0f}%"

            lines.append(f"{test.test_name:<40} {status:<10} {score_str:<10} {weight_str:<10}")

            # Add diagnostics if available
            if test.diagnostics:
                for key, value in test.diagnostics.items():
                    if isinstance(value, float):
                        lines.append(f"  • {key}: {value:.4f}")
                    else:
                        lines.append(f"  • {key}: {value}")

            # Add error message if failed
            if test.error_message:
                lines.append(f"  ⚠️  Error: {test.error_message}")

            lines.append("")

        # Statistics
        passed = sum(1 for t in tests if t.passed)
        total = len(tests)
        pass_rate = (passed / total * 100) if total > 0 else 0

        lines.append("-" * 80)
        lines.append(f"Total Tests:  {total}")
        lines.append(f"Passed:       {passed}")
        lines.append(f"Failed:       {total - passed}")
        lines.append(f"Pass Rate:    {pass_rate:.1f}%")
        lines.append("")

        return "\n".join(lines)

    def _recommendations(self, run: ValidationRun, tests: List[ValidationTest]) -> str:
        """Generate recommendations section."""
        recommendations = self._generate_recommendations(run, tests)

        lines = [
            "RECOMMENDATIONS",
            "-" * 80,
        ]

        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")

        lines.append("")

        return "\n".join(lines)

    def _footer(self) -> str:
        """Generate report footer."""
        lines = [
            "=" * 80,
            f"Report generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "Liquidation Model Validation Suite v1.0",
            "=" * 80,
        ]
        return "\n".join(lines)

    def _generate_recommendations(
        self, run: ValidationRun, tests: List[ValidationTest]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Overall grade recommendations
        if run.overall_grade and run.overall_grade.value == "F":
            recommendations.append(
                "CRITICAL: Grade F indicates severe model issues - immediate review required"
            )
        elif run.overall_grade and run.overall_grade.value == "C":
            recommendations.append(
                "WARNING: Grade C indicates model degradation - investigate failing tests"
            )

        # Test-specific recommendations
        for test in tests:
            if not test.passed:
                if test.test_type.value == "funding_correlation":
                    recommendations.append(
                        "Funding correlation test failed - verify market conditions and model assumptions"
                    )
                elif test.test_type.value == "oi_conservation":
                    recommendations.append(
                        "OI conservation test failed - check position calculation logic for errors"
                    )
                elif test.test_type.value == "directional_positioning":
                    recommendations.append(
                        "Directional test failed - review liquidation price formulas"
                    )

        # Data quality recommendations
        if run.data_completeness and run.data_completeness < 80:
            recommendations.append(
                f"Data completeness {run.data_completeness:.1f}% is low - "
                "consider re-running with more data"
            )

        if not recommendations:
            recommendations.append("All tests passed - model validation successful")

        return recommendations
