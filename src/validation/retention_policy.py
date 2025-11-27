"""
Data retention policy for validation results.

Implements 90-day retention with automatic cleanup.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from src.validation.logger import logger


class RetentionPolicy:
    """
    Data retention policy for validation results.

    Manages data lifecycle with configurable retention periods.
    """

    # Default retention periods (days)
    DEFAULT_RUN_RETENTION_DAYS = 90
    DEFAULT_REPORT_RETENTION_DAYS = 90
    DEFAULT_ALERT_RETENTION_DAYS = 30

    def __init__(
        self,
        run_retention_days: int = DEFAULT_RUN_RETENTION_DAYS,
        report_retention_days: int = DEFAULT_REPORT_RETENTION_DAYS,
        alert_retention_days: int = DEFAULT_ALERT_RETENTION_DAYS,
    ):
        """
        Initialize retention policy.

        Args:
            run_retention_days: Days to retain validation runs (default: 90)
            report_retention_days: Days to retain reports (default: 90)
            alert_retention_days: Days to retain alert history (default: 30)
        """
        self.run_retention_days = run_retention_days
        self.report_retention_days = report_retention_days
        self.alert_retention_days = alert_retention_days

        logger.info(
            f"RetentionPolicy initialized: runs={run_retention_days}d, "
            f"reports={report_retention_days}d, alerts={alert_retention_days}d"
        )

    def get_run_cutoff_date(self) -> datetime:
        """
        Get cutoff date for validation runs.

        Returns:
            Datetime before which runs should be deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=self.run_retention_days)
        logger.debug(f"Run cutoff date: {cutoff.isoformat()}")
        return cutoff

    def get_report_cutoff_date(self) -> datetime:
        """
        Get cutoff date for reports.

        Returns:
            Datetime before which reports should be deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=self.report_retention_days)
        logger.debug(f"Report cutoff date: {cutoff.isoformat()}")
        return cutoff

    def get_alert_cutoff_date(self) -> datetime:
        """
        Get cutoff date for alerts.

        Returns:
            Datetime before which alerts should be deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=self.alert_retention_days)
        logger.debug(f"Alert cutoff date: {cutoff.isoformat()}")
        return cutoff

    def should_retain_run(self, created_at: datetime) -> bool:
        """
        Check if validation run should be retained.

        Args:
            created_at: Run creation datetime

        Returns:
            True if should be retained, False if should be deleted
        """
        cutoff = self.get_run_cutoff_date()
        should_retain = created_at >= cutoff

        logger.debug(
            f"Run retention check: created={created_at.isoformat()}, "
            f"cutoff={cutoff.isoformat()}, retain={should_retain}"
        )

        return should_retain

    def should_retain_report(self, created_at: datetime) -> bool:
        """
        Check if report should be retained.

        Args:
            created_at: Report creation datetime

        Returns:
            True if should be retained, False if should be deleted
        """
        cutoff = self.get_report_cutoff_date()
        should_retain = created_at >= cutoff

        logger.debug(
            f"Report retention check: created={created_at.isoformat()}, "
            f"cutoff={cutoff.isoformat()}, retain={should_retain}"
        )

        return should_retain

    def should_retain_alert(self, created_at: datetime) -> bool:
        """
        Check if alert should be retained.

        Args:
            created_at: Alert creation datetime

        Returns:
            True if should be retained, False if should be deleted
        """
        cutoff = self.get_alert_cutoff_date()
        should_retain = created_at >= cutoff

        logger.debug(
            f"Alert retention check: created={created_at.isoformat()}, "
            f"cutoff={cutoff.isoformat()}, retain={should_retain}"
        )

        return should_retain

    def calculate_retention_stats(
        self,
        run_dates: List[datetime],
        report_dates: List[datetime],
        alert_dates: List[datetime],
    ) -> dict:
        """
        Calculate retention statistics for datasets.

        Args:
            run_dates: List of validation run creation dates
            report_dates: List of report creation dates
            alert_dates: List of alert creation dates

        Returns:
            Dict with retention statistics
        """
        run_cutoff = self.get_run_cutoff_date()
        report_cutoff = self.get_report_cutoff_date()
        alert_cutoff = self.get_alert_cutoff_date()

        runs_to_keep = sum(1 for d in run_dates if d >= run_cutoff)
        runs_to_delete = len(run_dates) - runs_to_keep

        reports_to_keep = sum(1 for d in report_dates if d >= report_cutoff)
        reports_to_delete = len(report_dates) - reports_to_keep

        alerts_to_keep = sum(1 for d in alert_dates if d >= alert_cutoff)
        alerts_to_delete = len(alert_dates) - alerts_to_keep

        stats = {
            "runs": {
                "total": len(run_dates),
                "to_keep": runs_to_keep,
                "to_delete": runs_to_delete,
                "retention_days": self.run_retention_days,
                "cutoff_date": run_cutoff.isoformat(),
            },
            "reports": {
                "total": len(report_dates),
                "to_keep": reports_to_keep,
                "to_delete": reports_to_delete,
                "retention_days": self.report_retention_days,
                "cutoff_date": report_cutoff.isoformat(),
            },
            "alerts": {
                "total": len(alert_dates),
                "to_keep": alerts_to_keep,
                "to_delete": alerts_to_delete,
                "retention_days": self.alert_retention_days,
                "cutoff_date": alert_cutoff.isoformat(),
            },
        }

        logger.info(
            f"Retention stats: runs={runs_to_delete}/{len(run_dates)} to delete, "
            f"reports={reports_to_delete}/{len(report_dates)} to delete, "
            f"alerts={alerts_to_delete}/{len(alert_dates)} to delete"
        )

        return stats

    def get_policy_summary(self) -> dict:
        """
        Get retention policy summary.

        Returns:
            Dict with policy details
        """
        return {
            "run_retention_days": self.run_retention_days,
            "report_retention_days": self.report_retention_days,
            "alert_retention_days": self.alert_retention_days,
            "run_cutoff_date": self.get_run_cutoff_date().isoformat(),
            "report_cutoff_date": self.get_report_cutoff_date().isoformat(),
            "alert_cutoff_date": self.get_alert_cutoff_date().isoformat(),
        }


# Global policy instance
_global_policy: Optional[RetentionPolicy] = None


def get_retention_policy() -> RetentionPolicy:
    """
    Get global retention policy instance (singleton).

    Returns:
        RetentionPolicy instance
    """
    global _global_policy

    if _global_policy is None:
        _global_policy = RetentionPolicy()

    return _global_policy


def set_retention_policy(policy: RetentionPolicy) -> None:
    """
    Set global retention policy.

    Args:
        policy: RetentionPolicy instance
    """
    global _global_policy
    _global_policy = policy
    logger.info("Global retention policy updated")
