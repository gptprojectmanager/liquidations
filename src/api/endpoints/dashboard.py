"""
Dashboard API endpoints for validation pipeline.

Provides REST API endpoints for dashboard metrics, pipeline triggering,
status checking, and validation history.
Per specs/014-validation-pipeline/contracts/dashboard_api.json
"""

import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, Query
from pydantic import BaseModel, Field, field_validator

from src.validation.logger import logger
from src.validation.pipeline import (
    DashboardMetrics,
    GateDecision,
    PipelineStatus,
    ValidationPipelineRun,
    get_dashboard_metrics,
    run_pipeline,
)

router = APIRouter(prefix="/api/validation", tags=["dashboard"])


# ============================================================================
# Request/Response Models
# ============================================================================


class DashboardResponse(BaseModel):
    """Dashboard metrics response."""

    status: str = Field(..., description="System health: healthy/warning/critical")
    last_validation: dict[str, Any] = Field(..., description="Latest validation details")
    backtest_coverage: dict[str, int] = Field(..., description="Backtest coverage stats")
    trend: list[dict[str, Any]] = Field(default_factory=list, description="Trend data")
    alerts: list[dict[str, Any]] = Field(default_factory=list, description="Active alerts")


class PipelineRunRequest(BaseModel):
    """Request to trigger a pipeline run."""

    symbol: str = Field(
        default="BTCUSDT",
        pattern=r"^[A-Z]{3,10}USDT$",
        description="Trading symbol (e.g., BTCUSDT)",
    )
    validation_types: list[str] = Field(
        default=["backtest"],
        description="Types: backtest, coinglass, realtime",
    )
    triggered_by: str = Field(
        default="api",
        min_length=1,
        max_length=200,
        description="User ID or system identifier",
    )
    backtest_config: dict[str, Any] | None = Field(
        default=None,
        description="Optional backtest config: start_date, end_date, tolerance_pct",
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate and sanitize symbol."""
        v = v.upper().strip()
        if not re.match(r"^[A-Z]{3,10}USDT$", v):
            raise ValueError("Symbol must match pattern: ^[A-Z]{3,10}USDT$")
        return v

    @field_validator("validation_types")
    @classmethod
    def validate_types(cls, v: list[str]) -> list[str]:
        """Validate validation types."""
        if not v:
            raise ValueError("validation_types cannot be empty")
        valid_types = {"backtest", "coinglass", "realtime", "full"}
        for t in v:
            if t not in valid_types:
                raise ValueError(f"Invalid validation type: {t}")
        return v


class PipelineRunResponse(BaseModel):
    """Response from pipeline trigger."""

    run_id: str = Field(..., description="Unique pipeline run ID")
    status: str = Field(..., description="Initial run status")
    message: str = Field(..., description="Status message")
    estimated_duration_seconds: int = Field(default=300, description="Estimated completion time")


class PipelineStatusResponse(BaseModel):
    """Response with pipeline run status."""

    run_id: str
    status: str
    started_at: str
    completed_at: str | None = None
    duration_seconds: int | None = None
    symbol: str
    gate_2_decision: str | None = None
    overall_grade: str | None = None
    overall_score: float | None = None
    results: dict[str, Any] | None = None
    error_message: str | None = None


class ValidationHistoryItem(BaseModel):
    """Single validation history entry."""

    run_id: str
    symbol: str
    started_at: str
    completed_at: str | None = None
    status: str
    gate_2_decision: str | None = None
    overall_grade: str | None = None
    overall_score: float | None = None


class ValidationHistoryResponse(BaseModel):
    """Paginated validation history."""

    runs: list[ValidationHistoryItem]
    total: int
    limit: int
    offset: int


# ============================================================================
# In-memory storage for active runs (demo - use DB in production)
# ============================================================================
# Thread-safe storage with size limit to prevent memory leaks
import threading
from collections import OrderedDict

_MAX_STORED_RUNS = 1000  # Limit stored runs to prevent memory exhaustion
_active_runs: OrderedDict[str, ValidationPipelineRun] = OrderedDict()
_runs_lock = threading.Lock()


def _store_run(run_id: str, run: ValidationPipelineRun) -> None:
    """Thread-safe store with size limit."""
    with _runs_lock:
        _active_runs[run_id] = run
        # Evict oldest entries if over limit
        while len(_active_runs) > _MAX_STORED_RUNS:
            _active_runs.popitem(last=False)


def _get_run(run_id: str) -> ValidationPipelineRun | None:
    """Thread-safe get."""
    with _runs_lock:
        return _active_runs.get(run_id)


def _get_runs_by_symbol(symbol: str) -> list[ValidationPipelineRun]:
    """Thread-safe get runs filtered by symbol."""
    with _runs_lock:
        return [r for r in _active_runs.values() if r.symbol == symbol]


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    symbol: str = Query(
        default="BTCUSDT",
        pattern=r"^[A-Z]{3,10}USDT$",
        description="Trading symbol",
    ),
    days: int = Query(
        default=30,
        ge=1,
        le=90,
        description="Days of trend history",
    ),
) -> DashboardResponse:
    """
    Get dashboard metrics for validation monitoring.

    Returns aggregated metrics including:
    - Current health status
    - Latest validation results
    - Historical trend data
    - Active alerts

    Example:
        GET /api/validation/dashboard?symbol=BTCUSDT&days=30
    """
    logger.info(f"Dashboard request: symbol={symbol}, days={days}")

    try:
        metrics: DashboardMetrics | None = get_dashboard_metrics(
            symbol=symbol,
            days=days,
        )

        if metrics is None:
            raise HTTPException(
                status_code=404,
                detail=f"No validation data found for {symbol}",
            )

        return DashboardResponse(**metrics.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve dashboard metrics: {str(e)}",
        )


@router.post("/pipeline/run", response_model=PipelineRunResponse, status_code=202)
async def trigger_pipeline(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks,
) -> PipelineRunResponse:
    """
    Trigger a validation pipeline run.

    Queues a pipeline run to execute in the background.
    Use the returned run_id to check status.

    Example:
        POST /api/validation/pipeline/run
        {
            "symbol": "BTCUSDT",
            "validation_types": ["backtest"],
            "triggered_by": "user@example.com"
        }
    """
    logger.info(
        f"Pipeline trigger: symbol={request.symbol}, "
        f"types={request.validation_types}, by={request.triggered_by}"
    )

    try:
        # Parse optional backtest config
        start_date = None
        end_date = None
        tolerance_pct = 2.0

        if request.backtest_config:
            try:
                if "start_date" in request.backtest_config:
                    start_date = datetime.fromisoformat(request.backtest_config["start_date"])
                if "end_date" in request.backtest_config:
                    end_date = datetime.fromisoformat(request.backtest_config["end_date"])
            except (ValueError, TypeError) as e:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid date format in backtest_config: {e}. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).",
                )
            tolerance_pct = request.backtest_config.get("tolerance_pct", 2.0)

        # Create initial run record
        from uuid import uuid4

        run_id = str(uuid4())
        from src.validation.pipeline import TriggerType

        run = ValidationPipelineRun(
            run_id=run_id,
            started_at=datetime.now(),
            trigger_type=TriggerType.API
            if request.triggered_by != "system"
            else TriggerType.SCHEDULED,
            triggered_by=request.triggered_by,
            symbol=request.symbol,
            status=PipelineStatus.PENDING,
        )

        # Store for status lookup (thread-safe with size limit)
        _store_run(run_id, run)

        # Queue background execution
        background_tasks.add_task(
            _execute_pipeline_background,
            run_id=run_id,
            symbol=request.symbol,
            validation_types=request.validation_types,
            triggered_by=request.triggered_by,
            start_date=start_date,
            end_date=end_date,
            tolerance_pct=tolerance_pct,
        )

        logger.info(f"Pipeline run queued: {run_id}")

        return PipelineRunResponse(
            run_id=run_id,
            status="pending",
            message=f"Pipeline run {run_id} queued for execution",
            estimated_duration_seconds=300,
        )

    except Exception as e:
        logger.error(f"Failed to trigger pipeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger pipeline: {str(e)}",
        )


@router.get("/pipeline/status/{run_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    run_id: str = Path(
        ...,
        min_length=36,
        max_length=36,
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        description="UUID of the pipeline run",
    ),
) -> PipelineStatusResponse:
    """
    Get status of a pipeline run.

    Example:
        GET /api/validation/pipeline/status/550e8400-e29b-41d4-a716-446655440000
    """
    logger.debug(f"Status request for run: {run_id}")

    # Check in-memory storage first (thread-safe)
    run = _get_run(run_id)

    if run is None:
        # TODO: Query from database if not in memory
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline run {run_id} not found",
        )

    return PipelineStatusResponse(
        run_id=run.run_id,
        status=run.status.value,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        duration_seconds=run.duration_seconds,
        symbol=run.symbol,
        gate_2_decision=run.gate_2_decision.value if run.gate_2_decision else None,
        overall_grade=run.overall_grade,
        overall_score=float(run.overall_score) if run.overall_score else None,
        results={
            "backtest": {"result_id": run.backtest_result_id} if run.backtest_result_id else None,
            "coinglass": {"result_id": run.coinglass_result_id}
            if run.coinglass_result_id
            else None,
        },
        error_message=run.error_message,
    )


@router.get("/history", response_model=ValidationHistoryResponse)
async def get_validation_history(
    symbol: str = Query(
        default="BTCUSDT",
        pattern=r"^[A-Z]{3,10}USDT$",
        description="Trading symbol",
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Result offset"),
) -> ValidationHistoryResponse:
    """
    Get paginated validation history.

    Example:
        GET /api/validation/history?symbol=BTCUSDT&limit=20&offset=0
    """
    logger.debug(f"History request: symbol={symbol}, limit={limit}, offset={offset}")

    # Get runs from in-memory storage (thread-safe, filtered by symbol)
    runs = _get_runs_by_symbol(symbol)

    # Sort by started_at descending
    runs.sort(key=lambda r: r.started_at, reverse=True)

    # Total count before pagination
    total = len(runs)

    # Apply pagination
    paginated = runs[offset : offset + limit]

    return ValidationHistoryResponse(
        runs=[
            ValidationHistoryItem(
                run_id=r.run_id,
                symbol=r.symbol,
                started_at=r.started_at.isoformat(),
                completed_at=r.completed_at.isoformat() if r.completed_at else None,
                status=r.status.value,
                gate_2_decision=r.gate_2_decision.value if r.gate_2_decision else None,
                overall_grade=r.overall_grade,
                overall_score=float(r.overall_score) if r.overall_score else None,
            )
            for r in paginated
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


# ============================================================================
# Background Task Functions
# ============================================================================


async def _execute_pipeline_background(
    run_id: str,
    symbol: str,
    validation_types: list[str],
    triggered_by: str,
    start_date: datetime | None,
    end_date: datetime | None,
    tolerance_pct: float,
) -> None:
    """
    Execute pipeline run in background.

    Updates the in-memory run record with results.
    Note: Run object is mutable, so updates are visible to readers.
    The lock protects dict access, not run object mutations.

    Uses asyncio.to_thread() to run the blocking pipeline in a thread pool,
    preventing event loop blocking.
    """
    import asyncio

    logger.info(f"Starting background pipeline: {run_id}")

    run = _get_run(run_id)
    if run is None:
        logger.error(f"Run not found in active runs: {run_id}")
        return

    try:
        # Update status to running
        run.status = PipelineStatus.RUNNING

        # Execute the blocking pipeline in a thread pool to avoid blocking event loop
        result = await asyncio.to_thread(
            run_pipeline,
            symbol=symbol,
            validation_types=validation_types,
            trigger_type="api",
            triggered_by=triggered_by,
            start_date=start_date,
            end_date=end_date,
            tolerance_pct=tolerance_pct,
            verbose=False,
        )

        # Update run with results
        run.status = result.status
        run.completed_at = result.completed_at
        run.duration_seconds = result.duration_seconds
        run.gate_2_decision = result.gate_2_decision
        run.gate_2_reason = result.gate_2_reason
        run.overall_grade = result.overall_grade
        run.overall_score = result.overall_score
        run.backtest_result_id = result.backtest_result_id
        run.coinglass_result_id = result.coinglass_result_id
        run.error_message = result.error_message

        logger.info(
            f"Pipeline completed: {run_id}, "
            f"gate={run.gate_2_decision.value if run.gate_2_decision else 'N/A'}, "
            f"grade={run.overall_grade or 'N/A'}"
        )

    except Exception as e:
        logger.error(f"Pipeline failed: {run_id}, error: {e}", exc_info=True)

        run.status = PipelineStatus.FAILED
        run.completed_at = datetime.now()
        run.error_message = str(e)
        run.gate_2_decision = GateDecision.FAIL
