"""
APScheduler integration for validation suite.

Manages scheduled and on-demand validation runs.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.validation.constants import (
    VALIDATION_CRON_DAY,
    VALIDATION_CRON_HOUR,
    VALIDATION_CRON_MINUTE,
)
from src.validation.logger import logger


class ValidationScheduler:
    """
    Scheduler for automated validation runs.

    Uses APScheduler to trigger weekly validation at configured times.
    """

    def __init__(self):
        """Initialize scheduler."""
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("Validation scheduler initialized")

    def schedule_weekly_validation(self, validation_callback, model_name: str = "default_model"):
        """
        Schedule weekly validation run.

        Args:
            validation_callback: Function to call for validation
            model_name: Model name to validate
        """
        # Create cron trigger for weekly run
        trigger = CronTrigger(
            day_of_week=VALIDATION_CRON_DAY,  # Sunday = 6
            hour=VALIDATION_CRON_HOUR,  # 2 AM
            minute=VALIDATION_CRON_MINUTE,  # 0
            timezone="UTC",
        )

        # Add job to scheduler
        job = self.scheduler.add_job(
            validation_callback,
            trigger=trigger,
            args=[model_name, "scheduled", "system"],
            id=f"weekly_validation_{model_name}",
            replace_existing=True,
            max_instances=1,  # Prevent concurrent runs
        )

        logger.info(
            f"Scheduled weekly validation for {model_name}: "
            f"day={VALIDATION_CRON_DAY}, hour={VALIDATION_CRON_HOUR}:00 UTC"
        )

        return job

    def trigger_manual_validation(
        self, validation_callback, model_name: str, triggered_by: str = "manual"
    ):
        """
        Trigger immediate validation run.

        Args:
            validation_callback: Function to call for validation
            model_name: Model name to validate
            triggered_by: User ID or identifier
        """
        # Run validation immediately
        job = self.scheduler.add_job(
            validation_callback,
            args=[model_name, "manual", triggered_by],
            id=f"manual_validation_{model_name}_{triggered_by}",
            max_instances=1,
        )

        logger.info(f"Triggered manual validation for {model_name} by {triggered_by}")

        return job

    def get_scheduled_jobs(self):
        """Get list of scheduled jobs."""
        return self.scheduler.get_jobs()

    def remove_job(self, job_id: str):
        """Remove scheduled job by ID."""
        self.scheduler.remove_job(job_id)
        logger.info(f"Removed scheduled job: {job_id}")

    def shutdown(self, wait: bool = True):
        """Shutdown scheduler."""
        self.scheduler.shutdown(wait=wait)
        logger.info("Validation scheduler shutdown")
