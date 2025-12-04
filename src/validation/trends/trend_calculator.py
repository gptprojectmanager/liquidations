"""
Trend calculator for validation metrics.

Calculates trends for each validation metric over time.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.validation.logger import logger


class TrendDirection(str):
    """Trend direction indicators."""

    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    INSUFFICIENT_DATA = "insufficient_data"


class TrendCalculator:
    """
    Calculates trends for validation metrics.

    Analyzes historical data to identify performance trends.
    """

    def __init__(self, min_data_points: int = 7):
        """
        Initialize trend calculator.

        Args:
            min_data_points: Minimum points required for trend analysis
        """
        self.min_data_points = min_data_points
        logger.info(f"TrendCalculator initialized (min_points={min_data_points})")

    def calculate_score_trend(
        self,
        scores: List[Tuple[datetime, float]],
    ) -> Dict:
        """
        Calculate trend for overall scores.

        Args:
            scores: List of (timestamp, score) tuples

        Returns:
            Dict with trend analysis
        """
        if len(scores) < self.min_data_points:
            logger.warning(f"Insufficient data for trend: {len(scores)} < {self.min_data_points}")
            return {
                "direction": TrendDirection.INSUFFICIENT_DATA,
                "slope": None,
                "change_percent": None,
                "data_points": len(scores),
            }

        # Sort by timestamp
        sorted_scores = sorted(scores, key=lambda x: x[0])

        # Calculate linear regression slope
        slope = self._calculate_slope(sorted_scores)

        # Calculate change percentage (first to last)
        first_score = sorted_scores[0][1]
        last_score = sorted_scores[-1][1]

        if first_score > 0:
            change_percent = ((last_score - first_score) / first_score) * 100
        else:
            change_percent = 0

        # Determine direction
        direction = self._determine_direction(slope, change_percent)

        trend = {
            "direction": direction,
            "slope": slope,
            "change_percent": change_percent,
            "data_points": len(scores),
            "first_score": first_score,
            "last_score": last_score,
            "min_score": min(s[1] for s in sorted_scores),
            "max_score": max(s[1] for s in sorted_scores),
            "avg_score": sum(s[1] for s in sorted_scores) / len(sorted_scores),
        }

        logger.info(f"Score trend: {direction}, slope={slope:.4f}, change={change_percent:.2f}%")

        return trend

    def calculate_test_trend(
        self,
        test_type: str,
        test_scores: List[Tuple[datetime, float]],
    ) -> Dict:
        """
        Calculate trend for specific test type.

        Args:
            test_type: Type of test
            test_scores: List of (timestamp, score) tuples for this test

        Returns:
            Dict with test-specific trend analysis
        """
        logger.info(f"Calculating trend for {test_type}")

        # Use same logic as score trend
        trend = self.calculate_score_trend(test_scores)
        trend["test_type"] = test_type

        return trend

    def calculate_grade_trend(
        self,
        grades: List[Tuple[datetime, str]],
    ) -> Dict:
        """
        Calculate trend for grade distribution.

        Args:
            grades: List of (timestamp, grade) tuples

        Returns:
            Dict with grade trend analysis
        """
        if len(grades) < self.min_data_points:
            return {
                "direction": TrendDirection.INSUFFICIENT_DATA,
                "data_points": len(grades),
            }

        # Sort by timestamp
        sorted_grades = sorted(grades, key=lambda x: x[0])

        # Convert grades to numeric scores (A=4, B=3, C=2, F=0)
        grade_values = {
            "A": 4.0,
            "B": 3.0,
            "C": 2.0,
            "F": 0.0,
        }

        numeric_grades = [(ts, grade_values.get(grade, 0.0)) for ts, grade in sorted_grades]

        # Calculate trend on numeric values
        slope = self._calculate_slope(numeric_grades)

        # Count grade distribution
        grade_counts = {}
        for _, grade in sorted_grades:
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

        # Most common grade
        most_common = max(grade_counts.items(), key=lambda x: x[1])[0]

        # Direction based on numeric slope
        if slope > 0.05:
            direction = TrendDirection.IMPROVING
        elif slope < -0.05:
            direction = TrendDirection.DEGRADING
        else:
            direction = TrendDirection.STABLE

        trend = {
            "direction": direction,
            "slope": slope,
            "data_points": len(grades),
            "grade_distribution": grade_counts,
            "most_common_grade": most_common,
            "first_grade": sorted_grades[0][1],
            "last_grade": sorted_grades[-1][1],
        }

        logger.info(
            f"Grade trend: {direction}, most_common={most_common}, distribution={grade_counts}"
        )

        return trend

    def calculate_multi_metric_trends(
        self,
        runs: List,
    ) -> Dict[str, Dict]:
        """
        Calculate trends for all metrics from validation runs.

        Args:
            runs: List of ValidationRun instances

        Returns:
            Dict mapping metric_name to trend analysis
        """
        logger.info(f"Calculating multi-metric trends for {len(runs)} runs")

        # Extract overall scores
        scores = [(run.started_at, float(run.overall_score)) for run in runs if run.overall_score]

        # Extract grades
        grades = [(run.started_at, run.overall_grade.value) for run in runs if run.overall_grade]

        trends = {
            "overall_score": self.calculate_score_trend(scores),
            "overall_grade": self.calculate_grade_trend(grades),
        }

        logger.info(f"Calculated trends for {len(trends)} metrics")

        return trends

    def _calculate_slope(
        self,
        data_points: List[Tuple[datetime, float]],
    ) -> float:
        """
        Calculate slope using linear regression.

        Args:
            data_points: List of (timestamp, value) tuples

        Returns:
            Slope value
        """
        if len(data_points) < 2:
            return 0.0

        # Convert timestamps to numeric (days from first point)
        first_time = data_points[0][0]
        x_values = [
            (ts - first_time).total_seconds() / (24 * 3600)  # Days
            for ts, _ in data_points
        ]
        y_values = [val for _, val in data_points]

        # Calculate means
        x_mean = sum(x_values) / len(x_values)
        y_mean = sum(y_values) / len(y_values)

        # Calculate slope
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)

        if denominator == 0:
            return 0.0

        slope = numerator / denominator

        return slope

    def _determine_direction(
        self,
        slope: float,
        change_percent: float,
    ) -> str:
        """
        Determine trend direction from slope and change.

        Args:
            slope: Linear regression slope
            change_percent: Percentage change

        Returns:
            TrendDirection value
        """
        # Thresholds
        SLOPE_THRESHOLD = 0.1  # Per day
        CHANGE_THRESHOLD = 5.0  # Percent

        if slope > SLOPE_THRESHOLD and change_percent > CHANGE_THRESHOLD:
            return TrendDirection.IMPROVING
        elif slope < -SLOPE_THRESHOLD and change_percent < -CHANGE_THRESHOLD:
            return TrendDirection.DEGRADING
        else:
            return TrendDirection.STABLE


# Global calculator instance
_global_calculator: Optional[TrendCalculator] = None


def get_trend_calculator() -> TrendCalculator:
    """
    Get global trend calculator instance (singleton).

    Returns:
        TrendCalculator instance
    """
    global _global_calculator

    if _global_calculator is None:
        _global_calculator = TrendCalculator()

    return _global_calculator
