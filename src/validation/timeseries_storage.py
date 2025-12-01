"""
Time-series storage optimization for validation results.

Optimizes storage and retrieval of historical validation data.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from src.validation.logger import logger


class TimeSeriesPoint:
    """Single time-series data point."""

    def __init__(
        self,
        timestamp: datetime,
        model_name: str,
        score: Decimal,
        grade: str,
        test_scores: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize time-series point.

        Args:
            timestamp: Point timestamp
            model_name: Model name
            score: Overall score
            grade: Overall grade
            test_scores: Dict mapping test_type to score
        """
        self.timestamp = timestamp
        self.model_name = model_name
        self.score = score
        self.grade = grade
        self.test_scores = test_scores or {}


class TimeSeriesStorage:
    """
    Optimized storage for time-series validation data.

    Provides efficient storage and retrieval for trend analysis.
    """

    def __init__(self):
        """Initialize time-series storage."""
        logger.info("TimeSeriesStorage initialized")

    def aggregate_runs_by_day(
        self,
        runs: List,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, List[TimeSeriesPoint]]:
        """
        Aggregate validation runs by day.

        Args:
            runs: List of ValidationRun instances
            start_date: Start date for aggregation
            end_date: End date for aggregation

        Returns:
            Dict mapping date_string to list of TimeSeriesPoint
        """
        logger.info(f"Aggregating runs by day: {start_date.date()} to {end_date.date()}")

        # Group runs by date
        daily_data: Dict[str, List[TimeSeriesPoint]] = {}

        for run in runs:
            # Skip runs outside date range
            if run.started_at < start_date or run.started_at > end_date:
                continue

            # Get date key (YYYY-MM-DD)
            date_key = run.started_at.date().isoformat()

            # Create time-series point
            point = TimeSeriesPoint(
                timestamp=run.started_at,
                model_name=run.model_name,
                score=run.overall_score if run.overall_score else Decimal("0"),
                grade=run.overall_grade.value if run.overall_grade else "N/A",
            )

            # Add to daily data
            if date_key not in daily_data:
                daily_data[date_key] = []

            daily_data[date_key].append(point)

        logger.info(f"Aggregated {len(runs)} runs into {len(daily_data)} days")

        return daily_data

    def calculate_daily_averages(
        self,
        daily_data: Dict[str, List[TimeSeriesPoint]],
    ) -> Dict[str, Dict]:
        """
        Calculate daily average scores.

        Args:
            daily_data: Dict mapping date to list of TimeSeriesPoint

        Returns:
            Dict mapping date to average metrics
        """
        logger.info(f"Calculating daily averages for {len(daily_data)} days")

        averages = {}

        for date_key, points in daily_data.items():
            if not points:
                continue

            # Calculate average score
            scores = [float(p.score) for p in points]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            # Count grades
            grade_counts = {}
            for point in points:
                grade = point.grade
                grade_counts[grade] = grade_counts.get(grade, 0) + 1

            # Most common grade
            most_common_grade = max(grade_counts.items(), key=lambda x: x[1])[0]

            averages[date_key] = {
                "date": date_key,
                "count": len(points),
                "avg_score": avg_score,
                "min_score": min(scores) if scores else 0,
                "max_score": max(scores) if scores else 0,
                "most_common_grade": most_common_grade,
                "grade_distribution": grade_counts,
            }

        logger.info(f"Calculated averages for {len(averages)} days")

        return averages

    def get_time_series(
        self,
        runs: List,
        start_date: datetime,
        end_date: datetime,
        resolution: str = "daily",
    ) -> List[Dict]:
        """
        Get time-series data for trend visualization.

        Args:
            runs: List of ValidationRun instances
            start_date: Start date
            end_date: End date
            resolution: Time resolution ('daily', 'weekly', 'monthly')

        Returns:
            List of time-series data points
        """
        logger.info(
            f"Generating {resolution} time-series: {start_date.date()} to {end_date.date()}"
        )

        if resolution == "daily":
            return self._get_daily_series(runs, start_date, end_date)
        elif resolution == "weekly":
            return self._get_weekly_series(runs, start_date, end_date)
        elif resolution == "monthly":
            return self._get_monthly_series(runs, start_date, end_date)
        else:
            logger.warning(f"Unknown resolution: {resolution}, using daily")
            return self._get_daily_series(runs, start_date, end_date)

    def _get_daily_series(
        self,
        runs: List,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict]:
        """Get daily time-series data."""
        daily_data = self.aggregate_runs_by_day(runs, start_date, end_date)
        averages = self.calculate_daily_averages(daily_data)

        # Convert to list sorted by date
        series = [averages[date] for date in sorted(averages.keys())]

        return series

    def _get_weekly_series(
        self,
        runs: List,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict]:
        """Get weekly time-series data."""
        # Group by week
        weekly_data: Dict[str, List] = {}

        for run in runs:
            if run.started_at < start_date or run.started_at > end_date:
                continue

            # Get week key (YYYY-WW)
            year = run.started_at.isocalendar()[0]
            week = run.started_at.isocalendar()[1]
            week_key = f"{year}-W{week:02d}"

            if week_key not in weekly_data:
                weekly_data[week_key] = []

            weekly_data[week_key].append(run)

        # Calculate weekly averages
        series = []
        for week_key in sorted(weekly_data.keys()):
            week_runs = weekly_data[week_key]

            scores = [float(r.overall_score) if r.overall_score else 0.0 for r in week_runs]

            avg_score = sum(scores) / len(scores) if scores else 0.0

            series.append(
                {
                    "week": week_key,
                    "count": len(week_runs),
                    "avg_score": avg_score,
                    "min_score": min(scores) if scores else 0,
                    "max_score": max(scores) if scores else 0,
                }
            )

        return series

    def _get_monthly_series(
        self,
        runs: List,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict]:
        """Get monthly time-series data."""
        # Group by month
        monthly_data: Dict[str, List] = {}

        for run in runs:
            if run.started_at < start_date or run.started_at > end_date:
                continue

            # Get month key (YYYY-MM)
            month_key = run.started_at.strftime("%Y-%m")

            if month_key not in monthly_data:
                monthly_data[month_key] = []

            monthly_data[month_key].append(run)

        # Calculate monthly averages
        series = []
        for month_key in sorted(monthly_data.keys()):
            month_runs = monthly_data[month_key]

            scores = [float(r.overall_score) if r.overall_score else 0.0 for r in month_runs]

            avg_score = sum(scores) / len(scores) if scores else 0.0

            series.append(
                {
                    "month": month_key,
                    "count": len(month_runs),
                    "avg_score": avg_score,
                    "min_score": min(scores) if scores else 0,
                    "max_score": max(scores) if scores else 0,
                }
            )

        return series

    def optimize_storage(self, runs: List, retention_days: int = 90) -> dict:
        """
        Optimize storage by aggregating old data.

        Args:
            runs: List of ValidationRun instances
            retention_days: Days to keep full-resolution data

        Returns:
            Dict with optimization statistics
        """
        logger.info(f"Optimizing storage: retention={retention_days}d")

        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Separate recent and old runs
        recent_runs = [r for r in runs if r.started_at >= cutoff_date]
        old_runs = [r for r in runs if r.started_at < cutoff_date]

        logger.info(f"Storage optimization: {len(recent_runs)} recent, {len(old_runs)} old runs")

        stats = {
            "total_runs": len(runs),
            "recent_runs": len(recent_runs),
            "old_runs": len(old_runs),
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": retention_days,
        }

        return stats


# Global storage instance
_global_storage: Optional[TimeSeriesStorage] = None


def get_timeseries_storage() -> TimeSeriesStorage:
    """
    Get global time-series storage instance (singleton).

    Returns:
        TimeSeriesStorage instance
    """
    global _global_storage

    if _global_storage is None:
        _global_storage = TimeSeriesStorage()

    return _global_storage
