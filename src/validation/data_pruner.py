"""
Historical data pruning job for validation results.

Automatically prunes old data according to retention policy.
"""

from datetime import datetime

from src.validation.logger import logger
from src.validation.retention_policy import get_retention_policy
from src.validation.storage import ValidationStorage


class DataPruner:
    """
    Prunes old validation data according to retention policy.

    Runs as scheduled job to maintain data storage within limits.
    """

    def __init__(self, dry_run: bool = False):
        """
        Initialize data pruner.

        Args:
            dry_run: If True, only simulate pruning without deleting
        """
        self.dry_run = dry_run
        self.retention_policy = get_retention_policy()

        logger.info(f"DataPruner initialized (dry_run={dry_run})")

    def prune_all(self) -> dict:
        """
        Prune all data types according to retention policy.

        Returns:
            Dict with pruning statistics
        """
        logger.info("Starting data pruning job")
        start_time = datetime.utcnow()

        stats = {
            "started_at": start_time.isoformat(),
            "dry_run": self.dry_run,
        }

        # Prune runs
        run_stats = self.prune_runs()
        stats["runs"] = run_stats

        # Prune reports
        report_stats = self.prune_reports()
        stats["reports"] = report_stats

        # Prune tests
        test_stats = self.prune_tests()
        stats["tests"] = test_stats

        # Calculate total duration
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        stats["completed_at"] = end_time.isoformat()
        stats["duration_seconds"] = duration

        total_deleted = (
            run_stats.get("deleted", 0)
            + report_stats.get("deleted", 0)
            + test_stats.get("deleted", 0)
        )

        logger.info(
            f"Data pruning completed: {total_deleted} items deleted in {duration:.1f}s "
            f"(dry_run={self.dry_run})"
        )

        return stats

    def prune_runs(self) -> dict:
        """
        Prune old validation runs.

        Returns:
            Dict with pruning statistics
        """
        logger.info("Pruning validation runs")

        cutoff_date = self.retention_policy.get_run_cutoff_date()

        with ValidationStorage() as storage:
            # Get runs to delete
            old_runs = storage.get_runs_before_date(cutoff_date)

            if not old_runs:
                logger.info("No runs to prune")
                return {"total": 0, "deleted": 0, "cutoff_date": cutoff_date.isoformat()}

            if self.dry_run:
                logger.info(f"DRY RUN: Would delete {len(old_runs)} runs")
                deleted = 0
            else:
                # Delete runs
                deleted = 0
                for run in old_runs:
                    try:
                        storage.delete_run(run.run_id)
                        deleted += 1
                    except Exception as e:
                        logger.error(f"Failed to delete run {run.run_id}: {e}")

                logger.info(f"Deleted {deleted}/{len(old_runs)} validation runs")

        return {
            "total": len(old_runs),
            "deleted": deleted,
            "cutoff_date": cutoff_date.isoformat(),
        }

    def prune_reports(self) -> dict:
        """
        Prune old validation reports.

        Returns:
            Dict with pruning statistics
        """
        logger.info("Pruning validation reports")

        cutoff_date = self.retention_policy.get_report_cutoff_date()

        with ValidationStorage() as storage:
            # Get reports to delete
            old_reports = storage.get_reports_before_date(cutoff_date)

            if not old_reports:
                logger.info("No reports to prune")
                return {"total": 0, "deleted": 0, "cutoff_date": cutoff_date.isoformat()}

            if self.dry_run:
                logger.info(f"DRY RUN: Would delete {len(old_reports)} reports")
                deleted = 0
            else:
                # Delete reports
                deleted = 0
                for report in old_reports:
                    try:
                        storage.delete_report(report.report_id)
                        deleted += 1
                    except Exception as e:
                        logger.error(f"Failed to delete report {report.report_id}: {e}")

                logger.info(f"Deleted {deleted}/{len(old_reports)} validation reports")

        return {
            "total": len(old_reports),
            "deleted": deleted,
            "cutoff_date": cutoff_date.isoformat(),
        }

    def prune_tests(self) -> dict:
        """
        Prune old validation tests.

        Returns:
            Dict with pruning statistics
        """
        logger.info("Pruning validation tests")

        # Tests are tied to runs, so use same cutoff
        cutoff_date = self.retention_policy.get_run_cutoff_date()

        with ValidationStorage() as storage:
            # Get tests to delete (from runs older than cutoff)
            old_tests = storage.get_tests_before_date(cutoff_date)

            if not old_tests:
                logger.info("No tests to prune")
                return {"total": 0, "deleted": 0, "cutoff_date": cutoff_date.isoformat()}

            if self.dry_run:
                logger.info(f"DRY RUN: Would delete {len(old_tests)} tests")
                deleted = 0
            else:
                # Delete tests
                deleted = 0
                for test in old_tests:
                    try:
                        storage.delete_test(test.test_id)
                        deleted += 1
                    except Exception as e:
                        logger.error(f"Failed to delete test {test.test_id}: {e}")

                logger.info(f"Deleted {deleted}/{len(old_tests)} validation tests")

        return {
            "total": len(old_tests),
            "deleted": deleted,
            "cutoff_date": cutoff_date.isoformat(),
        }

    def get_pruning_preview(self) -> dict:
        """
        Preview what would be pruned without deleting.

        Returns:
            Dict with pruning preview statistics
        """
        logger.info("Generating pruning preview")

        # Temporarily set dry_run
        original_dry_run = self.dry_run
        self.dry_run = True

        # Run pruning in dry-run mode
        stats = self.prune_all()

        # Restore dry_run setting
        self.dry_run = original_dry_run

        return stats


def schedule_pruning_job():
    """
    Schedule automatic data pruning job.

    Runs daily at configured time to maintain storage.
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler()

    # Schedule daily pruning at 3 AM UTC
    trigger = CronTrigger(
        hour=3,
        minute=0,
        timezone="UTC",
    )

    def run_pruning():
        """Execute pruning job."""
        logger.info("Scheduled pruning job starting")
        try:
            pruner = DataPruner(dry_run=False)
            stats = pruner.prune_all()

            logger.info(
                f"Scheduled pruning completed: "
                f"runs={stats['runs']['deleted']}, "
                f"reports={stats['reports']['deleted']}, "
                f"tests={stats['tests']['deleted']}"
            )
        except Exception as e:
            logger.error(f"Scheduled pruning failed: {e}", exc_info=True)

    scheduler.add_job(
        run_pruning,
        trigger=trigger,
        id="validation_data_pruning",
        max_instances=1,  # Prevent concurrent runs
        replace_existing=True,
    )

    scheduler.start()

    logger.info("Pruning job scheduled: Daily at 03:00 UTC")

    return scheduler
