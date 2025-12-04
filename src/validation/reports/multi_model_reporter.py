"""
Multi-model report generation.

Generates separate reports for different models and aggregates results.
"""

from typing import Dict, List

from src.models.validation_report import ReportFormat, ValidationReport
from src.models.validation_run import ValidationRun
from src.models.validation_test import ValidationTest
from src.validation.logger import logger
from src.validation.reports.json_reporter import JSONReporter
from src.validation.reports.text_reporter import TextReporter


class MultiModelReporter:
    """
    Generates validation reports for multiple models.

    Creates separate reports per model and aggregate comparison reports.
    """

    def __init__(self):
        """Initialize multi-model reporter."""
        self.json_reporter = JSONReporter()
        self.text_reporter = TextReporter()

        logger.info("MultiModelReporter initialized")

    def generate_model_reports(
        self,
        runs: Dict[str, ValidationRun],
        tests: Dict[str, List[ValidationTest]],
        formats: List[ReportFormat] = None,
    ) -> Dict[str, List[ValidationReport]]:
        """
        Generate reports for multiple models.

        Args:
            runs: Dict mapping model_name to ValidationRun
            tests: Dict mapping model_name to List[ValidationTest]
            formats: Report formats to generate (default: JSON and TEXT)

        Returns:
            Dict mapping model_name to list of reports
        """
        if formats is None:
            formats = [ReportFormat.JSON, ReportFormat.TEXT]

        logger.info(f"Generating reports for {len(runs)} models in {len(formats)} formats")

        all_reports: Dict[str, List[ValidationReport]] = {}

        for model_name, run in runs.items():
            model_tests = tests.get(model_name, [])
            model_reports = []

            logger.debug(f"Generating reports for model: {model_name}")

            # Generate each requested format
            for format in formats:
                if format == ReportFormat.JSON:
                    report = self.json_reporter.generate_report(run, model_tests)
                    model_reports.append(report)

                elif format == ReportFormat.TEXT:
                    report = self.text_reporter.generate_report(run, model_tests)
                    model_reports.append(report)

                else:
                    logger.warning(f"Unsupported format: {format} - skipping")

            all_reports[model_name] = model_reports

            logger.info(
                f"Generated {len(model_reports)} reports for model {model_name} "
                f"(grade={run.overall_grade.value if run.overall_grade else 'N/A'})"
            )

        return all_reports

    def generate_comparison_summary(
        self,
        runs: Dict[str, ValidationRun],
        tests: Dict[str, List[ValidationTest]],
    ) -> str:
        """
        Generate comparison summary across models.

        Args:
            runs: Dict mapping model_name to ValidationRun
            tests: Dict mapping model_name to List[ValidationTest]

        Returns:
            Formatted comparison summary
        """
        logger.info(f"Generating comparison summary for {len(runs)} models")

        lines = [
            "=" * 100,
            "MULTI-MODEL VALIDATION COMPARISON".center(100),
            "=" * 100,
            "",
        ]

        # Summary table header
        lines.append(f"{'Model':<30} {'Grade':<10} {'Score':<10} {'Status':<15} {'Duration':<10}")
        lines.append("-" * 100)

        # Sort by score (descending)
        sorted_models = sorted(
            runs.items(),
            key=lambda x: float(x[1].overall_score) if x[1].overall_score else 0,
            reverse=True,
        )

        # Add model rows
        for model_name, run in sorted_models:
            grade = run.overall_grade.value if run.overall_grade else "N/A"
            score = f"{run.overall_score:.2f}" if run.overall_score else "N/A"
            status = run.status.value if run.status else "unknown"
            duration = f"{run.duration_seconds}s" if run.duration_seconds else "N/A"

            # Grade emoji
            emoji = {"A": "🌟", "B": "✅", "C": "⚠️", "F": "❌"}.get(grade, "")

            lines.append(
                f"{model_name:<30} {emoji} {grade:<8} {score:<10} {status:<15} {duration:<10}"
            )

        lines.append("")
        lines.append("=" * 100)
        lines.append("")

        # Detailed comparison by test type
        lines.append("TEST PERFORMANCE COMPARISON")
        lines.append("-" * 100)

        # Get all unique test types
        all_test_types = set()
        for model_tests in tests.values():
            for test in model_tests:
                if test.test_type:
                    all_test_types.add(test.test_type.value)

        # Compare each test type
        for test_type in sorted(all_test_types):
            lines.append(f"\n{test_type.upper()}:")
            lines.append(f"{'Model':<30} {'Score':<10} {'Passed':<10} {'Weight':<10}")
            lines.append("-" * 100)

            for model_name in sorted(runs.keys()):
                model_tests = tests.get(model_name, [])

                # Find test of this type
                test = next(
                    (t for t in model_tests if t.test_type and t.test_type.value == test_type), None
                )

                if test:
                    score = f"{test.score:.2f}"
                    passed = "✅ Yes" if test.passed else "❌ No"
                    weight = f"{test.weight * 100:.0f}%"
                else:
                    score = "N/A"
                    passed = "N/A"
                    weight = "N/A"

                lines.append(f"{model_name:<30} {score:<10} {passed:<10} {weight:<10}")

        lines.append("")
        lines.append("=" * 100)

        # Statistics
        total_models = len(runs)
        grade_counts = {}
        for run in runs.values():
            if run.overall_grade:
                grade = run.overall_grade.value
                grade_counts[grade] = grade_counts.get(grade, 0) + 1

        lines.append("\nSTATISTICS")
        lines.append("-" * 100)
        lines.append(f"Total Models: {total_models}")

        for grade in ["A", "B", "C", "F"]:
            count = grade_counts.get(grade, 0)
            pct = (count / total_models * 100) if total_models > 0 else 0
            lines.append(f"Grade {grade}: {count} ({pct:.1f}%)")

        lines.append("")
        lines.append("=" * 100)

        return "\n".join(lines)

    def get_best_model(
        self,
        runs: Dict[str, ValidationRun],
    ) -> tuple[str, ValidationRun]:
        """
        Get best performing model.

        Args:
            runs: Dict mapping model_name to ValidationRun

        Returns:
            Tuple of (model_name, ValidationRun) for best model
        """
        if not runs:
            logger.warning("No runs provided for best model selection")
            return None, None

        # Sort by score (descending)
        best_model = max(
            runs.items(),
            key=lambda x: float(x[1].overall_score) if x[1].overall_score else 0,
        )

        logger.info(
            f"Best model: {best_model[0]} "
            f"(score={best_model[1].overall_score:.2f}, "
            f"grade={best_model[1].overall_grade.value if best_model[1].overall_grade else 'N/A'})"
        )

        return best_model

    def get_failing_models(
        self,
        runs: Dict[str, ValidationRun],
    ) -> List[str]:
        """
        Get list of failing models (grade C or F).

        Args:
            runs: Dict mapping model_name to ValidationRun

        Returns:
            List of model names with failing grades
        """
        failing = []

        for model_name, run in runs.items():
            if run.overall_grade and run.overall_grade.value in ["C", "F"]:
                failing.append(model_name)

        logger.info(f"Failing models: {len(failing)}/{len(runs)}")

        return failing
