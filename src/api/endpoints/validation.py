"""
Validation API endpoints for manual validation triggers.

Provides REST API endpoints for triggering validation runs,
checking status, and retrieving reports.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from src.models.validation_run import ValidationStatus
from src.validation.logger import logger
from src.validation.storage import ValidationStorage

router = APIRouter(prefix="/api/validation", tags=["validation"])


# Request/Response Models
class ValidationTriggerRequest(BaseModel):
    """Request to trigger a validation run."""

    model_name: str = Field(..., description="Name of model to validate")
    triggered_by: str = Field(default="api", description="User ID or system identifier")
    data_start_date: Optional[str] = Field(
        None, description="Start date for validation data (ISO format)"
    )
    data_end_date: Optional[str] = Field(
        None, description="End date for validation data (ISO format)"
    )


class ValidationTriggerResponse(BaseModel):
    """Response from validation trigger."""

    run_id: str = Field(..., description="Unique validation run ID")
    status: str = Field(..., description="Initial run status")
    message: str = Field(..., description="Status message")
    estimated_duration_seconds: int = Field(default=300, description="Estimated completion time")


class ValidationStatusResponse(BaseModel):
    """Response with validation run status."""

    run_id: str
    model_name: str
    status: str
    overall_grade: Optional[str] = None
    overall_score: Optional[float] = None
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    error_message: Optional[str] = None


class ValidationReportResponse(BaseModel):
    """Response with validation report."""

    run_id: str
    model_name: str
    format: str
    report_content: str
    summary: dict
    recommendations: list
    generated_at: str


# API Endpoints
@router.post("/run", response_model=ValidationTriggerResponse, status_code=202)
async def trigger_validation(
    request: ValidationTriggerRequest,
    background_tasks: BackgroundTasks,
) -> ValidationTriggerResponse:
    """
    Trigger a manual validation run.

    This endpoint queues a validation run to be executed in the background.
    Use the returned run_id to check status and retrieve results.

    Args:
        request: Validation trigger request
        background_tasks: FastAPI background tasks

    Returns:
        ValidationTriggerResponse with run_id and status

    Example:
        POST /api/validation/run
        {
            "model_name": "liquidation_model_v1",
            "triggered_by": "user@example.com"
        }
    """
    logger.info(
        f"Validation trigger request received: model={request.model_name}, "
        f"triggered_by={request.triggered_by}"
    )

    try:
        # Import here to avoid circular dependency
        from src.validation.test_runner import ValidationTestRunner

        # Create test runner
        runner = ValidationTestRunner(
            model_name=request.model_name,
            trigger_type="manual",
            triggered_by=request.triggered_by,
        )

        run_id = runner.run_id

        # Queue validation run in background
        # Note: In production, this would use the queue manager (T031)
        # For now, run directly in background task
        background_tasks.add_task(
            _execute_validation_background,
            runner=runner,
            run_id=run_id,
        )

        logger.info(f"Validation run queued: {run_id}")

        return ValidationTriggerResponse(
            run_id=run_id,
            status="queued",
            message=f"Validation run {run_id} queued for execution",
            estimated_duration_seconds=300,  # 5 minutes
        )

    except Exception as e:
        logger.error(f"Failed to trigger validation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to trigger validation: {str(e)}")


@router.get("/status/{run_id}", response_model=ValidationStatusResponse)
async def get_validation_status(run_id: str) -> ValidationStatusResponse:
    """
    Get status of a validation run.

    Args:
        run_id: Validation run ID

    Returns:
        ValidationStatusResponse with current status

    Example:
        GET /api/validation/status/550e8400-e29b-41d4-a716-446655440000
    """
    logger.debug(f"Status request for run: {run_id}")

    try:
        # Retrieve run from storage
        with ValidationStorage() as storage:
            run = storage.get_run(run_id)

        if not run:
            raise HTTPException(status_code=404, detail=f"Validation run {run_id} not found")

        return ValidationStatusResponse(
            run_id=run.run_id,
            model_name=run.model_name,
            status=run.status.value if run.status else "unknown",
            overall_grade=run.overall_grade.value if run.overall_grade else None,
            overall_score=float(run.overall_score) if run.overall_score else None,
            started_at=run.started_at.isoformat(),
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
            duration_seconds=run.duration_seconds,
            error_message=run.error_message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get validation status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve validation status: {str(e)}"
        )


@router.get("/report/{run_id}", response_model=ValidationReportResponse)
async def get_validation_report(
    run_id: str,
    format: str = "json",  # json, text, html
) -> ValidationReportResponse:
    """
    Get validation report for a completed run.

    Args:
        run_id: Validation run ID
        format: Report format (json, text, html)

    Returns:
        ValidationReportResponse with report content

    Example:
        GET /api/validation/report/550e8400-e29b-41d4-a716-446655440000?format=json
    """
    logger.debug(f"Report request for run: {run_id}, format: {format}")

    try:
        # Validate format
        if format not in ["json", "text", "html"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid format: {format}. Must be 'json', 'text', or 'html'",
            )

        # Retrieve run and report from storage
        with ValidationStorage() as storage:
            run = storage.get_run(run_id)
            if not run:
                raise HTTPException(status_code=404, detail=f"Validation run {run_id} not found")

            # Check if run is completed
            if run.status != ValidationStatus.COMPLETED:
                raise HTTPException(
                    status_code=400,
                    detail=f"Validation run {run_id} is not completed (status: {run.status.value})",
                )

            # Get report with requested format
            reports = storage.get_reports_for_run(run_id)

            # Find report with requested format
            report = None
            for r in reports:
                if r.format.value == format:
                    report = r
                    break

            if not report:
                raise HTTPException(
                    status_code=404,
                    detail=f"Report with format '{format}' not found for run {run_id}",
                )

        return ValidationReportResponse(
            run_id=report.run_id,
            model_name=run.model_name,
            format=report.format.value,
            report_content=report.report_content,
            summary=report.summary,
            recommendations=report.recommendations,
            generated_at=report.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get validation report: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve validation report: {str(e)}"
        )


# Background task functions
async def _execute_validation_background(runner, run_id: str):
    """
    Execute validation run in background.

    Args:
        runner: ValidationTestRunner instance
        run_id: Validation run ID
    """
    logger.info(f"Starting background validation execution: {run_id}")

    try:
        # Execute validation tests
        # Note: In production, would fetch real data here
        run, tests = runner.run_all_tests(
            funding_data=None,  # Would fetch from data_fetcher
            oi_data=None,  # Would fetch from data_fetcher
            directional_data=None,  # Would fetch from data_fetcher
        )

        # Generate reports
        from src.validation.reports.json_reporter import JSONReporter
        from src.validation.reports.text_reporter import TextReporter

        json_reporter = JSONReporter()
        text_reporter = TextReporter()

        json_report = json_reporter.generate_report(run, tests)
        text_report = text_reporter.generate_report(run, tests)

        # Persist results
        with ValidationStorage() as storage:
            storage.save_run(run)
            for test in tests:
                storage.save_test(test)
            storage.save_report(json_report)
            storage.save_report(text_report)

        # Trigger alerts if needed
        from src.validation.alerts.alert_manager import AlertManager

        alert_manager = AlertManager()
        if alert_manager.should_trigger_alert(run):
            alert_manager.process_run(run, tests)

        logger.info(
            f"Background validation completed: {run_id}, "
            f"grade={run.overall_grade.value if run.overall_grade else 'N/A'}"
        )

    except Exception as e:
        logger.error(f"Background validation failed: {run_id}, error: {e}", exc_info=True)

        # Update run status to failed
        try:
            with ValidationStorage() as storage:
                run = storage.get_run(run_id)
                if run:
                    run.status = ValidationStatus.FAILED
                    run.error_message = str(e)
                    run.completed_at = datetime.utcnow()
                    storage.save_run(run)
        except Exception as update_error:
            logger.error(f"Failed to update run status: {update_error}")
