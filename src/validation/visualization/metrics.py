"""
Performance metrics calculator for visualization.

Calculates summary metrics for dashboard display.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.validation.logger import logger


class MetricsCalculator:
    """
    Calculates performance metrics for visualization.

    Provides summary statistics and KPIs for dashboards.
    """

    def __init__(self):
        """Initialize metrics calculator."""
        logger.info("MetricsCalculator initialized")

    def calculate_summary_metrics(self, runs: List) -> Dict:
        """
        Calculate summary metrics from validation runs.

        Args:
            runs: List of ValidationRun instances

        Returns:
            Dict with summary metrics
        """
        if not runs:
            logger.warning("No runs for metrics calculation")
            return self._empty_metrics()

        logger.info(f"Calculating summary metrics for {len(runs)} runs")

        # Overall statistics
        scores = [float(run.overall_score) for run in runs if run.overall_score]
        grades = [run.overall_grade.value for run in runs if run.overall_grade]

        # Grade distribution
        grade_dist = {}
        for grade in grades:
            grade_dist[grade] = grade_dist.get(grade, 0) + 1

        # Recent performance (last 7 days)
        cutoff = datetime.utcnow() - timedelta(days=7)
        recent_runs = [r for r in runs if r.started_at >= cutoff]
        recent_scores = [float(r.overall_score) for r in recent_runs if r.overall_score]

        metrics = {
            "total_runs": len(runs),
            "score_stats": {
                "mean": sum(scores) / len(scores) if scores else 0,
                "min": min(scores) if scores else 0,
                "max": max(scores) if scores else 0,
                "latest": scores[-1] if scores else 0,
            },
            "grade_distribution": grade_dist,
            "pass_rate": (
                sum(1 for g in grades if g in ["A", "B"]) / len(grades) * 100 if grades else 0
            ),
            "recent_performance": {
                "runs_count": len(recent_runs),
                "avg_score": sum(recent_scores) / len(recent_scores) if recent_scores else 0,
                "days": 7,
            },
        }

        logger.info(f"Summary metrics calculated: {metrics['total_runs']} runs")

        return metrics

    def calculate_kpis(self, runs: List) -> Dict:
        """
        Calculate key performance indicators.

        Args:
            runs: List of ValidationRun instances

        Returns:
            Dict with KPI values
        """
        if not runs:
            return {}

        logger.info(f"Calculating KPIs for {len(runs)} runs")

        # Sort by date
        sorted_runs = sorted(runs, key=lambda x: x.started_at)

        # Current vs previous period comparison
        mid_point = len(sorted_runs) // 2
        first_half = sorted_runs[:mid_point]
        second_half = sorted_runs[mid_point:]

        first_half_scores = [float(r.overall_score) for r in first_half if r.overall_score]
        second_half_scores = [float(r.overall_score) for r in second_half if r.overall_score]

        first_avg = sum(first_half_scores) / len(first_half_scores) if first_half_scores else 0
        second_avg = sum(second_half_scores) / len(second_half_scores) if second_half_scores else 0

        # Calculate change
        if first_avg > 0:
            score_change = ((second_avg - first_avg) / first_avg) * 100
        else:
            score_change = 0

        # Uptime (runs without failures)
        completed_runs = [r for r in runs if r.status and r.status.value == "completed"]
        uptime = len(completed_runs) / len(runs) * 100 if runs else 0

        # Average execution time
        durations = [r.duration_seconds for r in runs if r.duration_seconds]
        avg_duration = sum(durations) / len(durations) if durations else 0

        kpis = {
            "current_score": second_avg,
            "previous_score": first_avg,
            "score_change_percent": score_change,
            "uptime_percent": uptime,
            "avg_execution_seconds": avg_duration,
            "total_validations": len(runs),
        }

        logger.info(f"KPIs calculated: score_change={score_change:.2f}%")

        return kpis

    def calculate_test_performance(self, tests: List) -> Dict[str, Dict]:
        """
        Calculate per-test performance metrics.

        Args:
            tests: List of ValidationTest instances

        Returns:
            Dict mapping test_type to performance metrics
        """
        if not tests:
            return {}

        logger.info(f"Calculating test performance for {len(tests)} tests")

        # Group by test type
        by_type: Dict[str, List] = {}
        for test in tests:
            if test.test_type:
                test_type = test.test_type.value
                if test_type not in by_type:
                    by_type[test_type] = []
                by_type[test_type].append(test)

        # Calculate metrics per type
        performance = {}
        for test_type, type_tests in by_type.items():
            scores = [float(t.score) for t in type_tests]
            passed_count = sum(1 for t in type_tests if t.passed)

            performance[test_type] = {
                "total_runs": len(type_tests),
                "passed_count": passed_count,
                "pass_rate": (passed_count / len(type_tests) * 100) if type_tests else 0,
                "avg_score": sum(scores) / len(scores) if scores else 0,
                "min_score": min(scores) if scores else 0,
                "max_score": max(scores) if scores else 0,
                "latest_score": scores[-1] if scores else 0,
            }

        logger.info(f"Test performance calculated for {len(performance)} test types")

        return performance

    def calculate_reliability_metrics(self, runs: List) -> Dict:
        """
        Calculate reliability and stability metrics.

        Args:
            runs: List of ValidationRun instances

        Returns:
            Dict with reliability metrics
        """
        if not runs:
            return {}

        logger.info(f"Calculating reliability metrics for {len(runs)} runs")

        # Completion rate
        completed = sum(1 for r in runs if r.status and r.status.value == "completed")
        failed = sum(1 for r in runs if r.status and r.status.value == "failed")

        completion_rate = (completed / len(runs) * 100) if runs else 0
        failure_rate = (failed / len(runs) * 100) if runs else 0

        # Score stability (standard deviation)
        scores = [float(r.overall_score) for r in runs if r.overall_score]
        if len(scores) > 1:
            mean = sum(scores) / len(scores)
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            std_dev = variance**0.5
        else:
            std_dev = 0

        # Consecutive failures
        max_consecutive_failures = 0
        current_failures = 0

        for run in sorted(runs, key=lambda x: x.started_at):
            if run.status and run.status.value == "failed":
                current_failures += 1
                max_consecutive_failures = max(max_consecutive_failures, current_failures)
            else:
                current_failures = 0

        metrics = {
            "completion_rate": completion_rate,
            "failure_rate": failure_rate,
            "score_stability": {
                "std_dev": std_dev,
                "coefficient_of_variation": (std_dev / sum(scores) * len(scores)) if scores else 0,
            },
            "max_consecutive_failures": max_consecutive_failures,
            "uptime": completion_rate,
        }

        logger.info(f"Reliability metrics: completion={completion_rate:.1f}%")

        return metrics

    def _empty_metrics(self) -> Dict:
        """Return empty metrics structure."""
        return {
            "total_runs": 0,
            "score_stats": {"mean": 0, "min": 0, "max": 0, "latest": 0},
            "grade_distribution": {},
            "pass_rate": 0,
            "recent_performance": {"runs_count": 0, "avg_score": 0, "days": 7},
        }


# Global metrics calculator instance
_global_calculator: Optional[MetricsCalculator] = None


def get_metrics_calculator() -> MetricsCalculator:
    """
    Get global metrics calculator instance (singleton).

    Returns:
        MetricsCalculator instance
    """
    global _global_calculator

    if _global_calculator is None:
        _global_calculator = MetricsCalculator()

    return _global_calculator
