"""
Cron job definitions for validation suite.

Defines weekly validation triggers at Sunday 2 AM UTC.
"""

from src.validation.logger import logger
from src.validation.scheduler import ValidationScheduler
from src.validation.storage import ValidationStorage
from src.validation.test_runner import ValidationTestRunner


def run_scheduled_validation(model_name: str, trigger_type: str, triggered_by: str):
    """
    Execute scheduled validation run.

    This function is called by APScheduler on schedule.

    Args:
        model_name: Model to validate
        trigger_type: 'scheduled' or 'manual'
        triggered_by: 'system' or user ID
    """
    logger.info(
        f"Starting {trigger_type} validation run for {model_name} (triggered by: {triggered_by})"
    )

    try:
        # Create test runner
        runner = ValidationTestRunner(
            model_name=model_name, trigger_type=trigger_type, triggered_by=triggered_by
        )

        # Execute validation tests
        # Note: In production, would fetch real data here
        # For now, caller must provide data
        logger.warning("Data fetching not implemented - validation run will be incomplete")

        run, tests = runner.run_all_tests(
            funding_data=None,  # Would fetch from data_fetcher
            oi_data=None,  # Would fetch from data_fetcher
            directional_data=None,  # Would fetch from data_fetcher
        )

        # Persist results
        with ValidationStorage() as storage:
            storage.save_run(run)
            for test in tests:
                storage.save_test(test)

        logger.info(
            f"Validation run completed: {run.run_id}, "
            f"grade={run.overall_grade}, score={run.overall_score}"
        )

        return run

    except Exception as e:
        logger.error(f"Scheduled validation failed: {e}", exc_info=True)
        raise


def setup_weekly_validation(model_name: str = "liquidation_model_v1"):
    """
    Setup weekly validation schedule.

    Configures Sunday 2 AM UTC validation runs.

    Args:
        model_name: Model name to validate

    Returns:
        ValidationScheduler instance
    """
    scheduler = ValidationScheduler()

    # Schedule weekly validation
    job = scheduler.schedule_weekly_validation(
        validation_callback=run_scheduled_validation, model_name=model_name
    )

    logger.info(
        f"Weekly validation configured for {model_name}: "
        f"Every Sunday at 02:00 UTC (job_id: {job.id})"
    )

    return scheduler
