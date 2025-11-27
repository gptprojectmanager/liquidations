"""
JSON report generator for validation suite.

Creates structured JSON reports from validation results.
"""

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List

from src.models.validation_report import ReportFormat, ValidationReport
from src.models.validation_run import ValidationRun
from src.models.validation_test import ValidationTest
from src.validation.logger import logger


class JSONReporter:
    """
    Generates JSON-formatted validation reports.

    Creates structured JSON output with all validation results,
    suitable for API consumption and programmatic processing.
    """

    def generate_report(self, run: ValidationRun, tests: List[ValidationTest]) -> ValidationReport:
        """
        Generate JSON report from validation results.

        Args:
            run: ValidationRun instance
            tests: List of ValidationTest results

        Returns:
            ValidationReport with JSON content
        """
        logger.info(f"Generating JSON report for run {run.run_id}")

        # Build summary dict
        summary = {
            "run_id": run.run_id,
            "model_name": run.model_name,
            "overall_grade": run.overall_grade.value if run.overall_grade else None,
            "overall_score": float(run.overall_score) if run.overall_score else 0.0,
            "status": run.status.value if run.status else "unknown",
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "duration_seconds": run.duration_seconds,
            "data_window": {
                "start": run.data_start_date.isoformat(),
                "end": run.data_end_date.isoformat(),
                "completeness": float(run.data_completeness) if run.data_completeness else None,
            },
        }

        # Build tests list
        tests_data = []
        for test in tests:
            test_data = {
                "test_id": test.test_id,
                "test_type": test.test_type.value if test.test_type else "unknown",
                "test_name": test.test_name,
                "passed": test.passed,
                "score": float(test.score),
                "weight": float(test.weight),
                "weighted_contribution": float(test.weighted_contribution()),
                "primary_metric": float(test.primary_metric) if test.primary_metric else None,
                "secondary_metric": float(test.secondary_metric) if test.secondary_metric else None,
                "diagnostics": test.diagnostics,
                "error_message": test.error_message,
                "duration_ms": test.duration_ms,
            }
            tests_data.append(test_data)

        # Build full report structure
        report_data = {
            "report_metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "format": "json",
                "version": "1.0",
            },
            "summary": summary,
            "tests": tests_data,
            "statistics": self._calculate_statistics(tests),
        }

        # Generate recommendations
        recommendations = self._generate_recommendations(run, tests)

        # Serialize to JSON
        report_content = json.dumps(report_data, indent=2, default=str)

        # Create ValidationReport
        report = ValidationReport(
            report_id=str(uuid.uuid4()),
            run_id=run.run_id,
            format=ReportFormat.JSON,
            report_content=report_content,
            summary=summary,
            recommendations=recommendations,
        )

        logger.info(
            f"JSON report generated: {len(report_content)} bytes, "
            f"{len(tests)} tests, grade={run.overall_grade}"
        )

        return report

    def _calculate_statistics(self, tests: List[ValidationTest]) -> dict:
        """Calculate summary statistics from tests."""
        if not tests:
            return {}

        passed_count = sum(1 for t in tests if t.passed)
        total_count = len(tests)

        return {
            "total_tests": total_count,
            "passed_tests": passed_count,
            "failed_tests": total_count - passed_count,
            "pass_rate": (passed_count / total_count * 100) if total_count > 0 else 0,
            "average_score": sum(float(t.score) for t in tests) / total_count
            if total_count > 0
            else 0,
        }

    def _generate_recommendations(
        self, run: ValidationRun, tests: List[ValidationTest]
    ) -> List[str]:
        """Generate actionable recommendations based on results."""
        recommendations = []

        # Check overall grade
        if run.overall_grade and run.overall_grade.value in ["C", "F"]:
            recommendations.append(
                f"⚠️ Overall grade {run.overall_grade.value} indicates model degradation - "
                "review failed tests"
            )

        # Check individual test failures
        for test in tests:
            if not test.passed:
                if test.test_type.value == "funding_correlation":
                    recommendations.append(
                        "📊 Funding correlation below threshold - check if market "
                        "conditions changed or model drift occurred"
                    )
                elif test.test_type.value == "oi_conservation":
                    recommendations.append(
                        "⚖️ OI conservation error too high - verify position calculation logic"
                    )
                elif test.test_type.value == "directional_positioning":
                    recommendations.append(
                        "🎯 Directional accuracy low - check liquidation price calculation formulas"
                    )

        # Check data completeness
        if run.data_completeness and run.data_completeness < Decimal("80"):
            recommendations.append(
                f"📉 Data completeness only {run.data_completeness}% - results may not be reliable"
            )

        if not recommendations:
            recommendations.append("✅ All validation tests passed - model performing well")

        return recommendations
