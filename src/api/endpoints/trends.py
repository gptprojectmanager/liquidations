"""
Trend analysis API endpoints.

Provides historical trend data and comparison endpoints.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.validation.logger import logger
from src.validation.storage import ValidationStorage
from src.validation.timeseries_storage import get_timeseries_storage
from src.validation.trends.degradation_detector import get_degradation_detector
from src.validation.trends.moving_averages import get_moving_averages
from src.validation.trends.trend_calculator import get_trend_calculator

router = APIRouter(prefix="/api/validation", tags=["trends"])


# Response Models
class TrendDataResponse(BaseModel):
    """Response with trend data."""

    model_name: str
    start_date: str
    end_date: str
    resolution: str
    time_series: list
    trend_analysis: dict
    moving_averages: dict
    degradation: dict


class ComparisonResponse(BaseModel):
    """Response with model comparison data."""

    models: list
    time_period: dict
    comparison_metrics: dict
    rankings: list
    best_model: dict


# API Endpoints
@router.get("/trends", response_model=TrendDataResponse)
async def get_trends(
    model_name: str = Query(
        "liquidation_model_v1",
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_\-\.]+$",
        description="Model to analyze",
    ),
    days: int = Query(90, ge=7, le=365, description="Days of historical data"),
    resolution: str = Query(
        "daily",
        pattern=r"^(daily|weekly|monthly)$",
        description="Time resolution: daily, weekly, or monthly",
    ),
    include_ma: bool = Query(True, description="Include moving averages"),
    include_degradation: bool = Query(True, description="Include degradation detection"),
) -> TrendDataResponse:
    """
    Get historical trend data for validation runs.

    Args:
        model_name: Model to analyze
        days: Number of days of historical data (7-365)
        resolution: Time resolution (daily, weekly, monthly)
        include_ma: Include moving average calculations
        include_degradation: Include degradation detection

    Returns:
        TrendDataResponse with time-series and analysis

    Example:
        GET /api/validation/trends?model_name=liquidation_model_v1&days=90&resolution=daily
    """
    logger.info(f"Trend request: model={model_name}, days={days}, resolution={resolution}")

    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Retrieve runs from storage
        with ValidationStorage() as storage:
            runs = storage.get_runs_in_date_range(
                model_name=model_name,
                start_date=start_date,
                end_date=end_date,
            )

        if not runs:
            raise HTTPException(
                status_code=404,
                detail=f"No validation runs found for {model_name} in last {days} days",
            )

        logger.info(f"Retrieved {len(runs)} runs for trend analysis")

        # Generate time-series data
        ts_storage = get_timeseries_storage()
        time_series = ts_storage.get_time_series(
            runs=runs,
            start_date=start_date,
            end_date=end_date,
            resolution=resolution,
        )

        # Calculate trends
        trend_calculator = get_trend_calculator()
        trends = trend_calculator.calculate_multi_metric_trends(runs)

        # Calculate moving averages (if requested)
        moving_averages = {}
        if include_ma:
            ma_calculator = get_moving_averages()
            moving_averages = ma_calculator.calculate_all_averages(
                data_points=[
                    (run.started_at, float(run.overall_score)) for run in runs if run.overall_score
                ],
                window_size=7,
                alpha=0.3,
            )

            # Convert to serializable format
            moving_averages = {
                "sma": [(ts.isoformat(), val) for ts, val in moving_averages.get("sma", [])],
                "ema": [(ts.isoformat(), val) for ts, val in moving_averages.get("ema", [])],
                "wma": [(ts.isoformat(), val) for ts, val in moving_averages.get("wma", [])],
                "window_size": moving_averages.get("window_size", 7),
                "alpha": moving_averages.get("alpha", 0.3),
            }

        # Detect degradation (if requested)
        degradation = {}
        if include_degradation:
            degradation_detector = get_degradation_detector()
            degradation = degradation_detector.detect_multi_metric_degradation(runs)

        return TrendDataResponse(
            model_name=model_name,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            resolution=resolution,
            time_series=time_series,
            trend_analysis=trends,
            moving_averages=moving_averages,
            degradation=degradation,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trends: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve trends: {str(e)}")


@router.get("/compare", response_model=ComparisonResponse)
async def compare_models(
    model_names: str = Query(
        ...,
        min_length=1,
        max_length=500,
        pattern=r"^[a-zA-Z0-9_\-\., ]+$",
        description="Comma-separated model names (e.g., model1,model2,model3)",
    ),
    days: int = Query(30, ge=7, le=365, description="Days of historical data"),
) -> ComparisonResponse:
    """
    Compare multiple models over time period.

    Args:
        model_names: Comma-separated list of model names to compare
        days: Number of days for comparison

    Returns:
        ComparisonResponse with comparison metrics

    Example:
        GET /api/validation/compare?model_names=model_v1,model_v2&days=30
    """
    # Parse model names
    models = [name.strip() for name in model_names.split(",")]

    logger.info(f"Comparison request: models={models}, days={days}")

    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Retrieve runs for each model
        all_runs = {}
        all_tests = {}

        with ValidationStorage() as storage:
            for model_name in models:
                runs = storage.get_runs_in_date_range(
                    model_name=model_name,
                    start_date=start_date,
                    end_date=end_date,
                )

                if runs:
                    all_runs[model_name] = runs[0]  # Most recent run

                    # Get tests for this run
                    tests = storage.get_tests_for_run(runs[0].run_id)
                    all_tests[model_name] = tests

        if not all_runs:
            raise HTTPException(
                status_code=404,
                detail=f"No validation runs found for models in last {days} days",
            )

        logger.info(f"Retrieved runs for {len(all_runs)} models")

        # Compare models
        from src.validation.comparison import get_model_comparison

        comparison = get_model_comparison()

        scores = comparison.compare_scores(all_runs)
        grades = comparison.compare_grades(all_runs)
        rankings = comparison.rank_models(all_runs)
        stats = comparison.get_statistics(all_runs)
        best_model, reason = comparison.recommend_best_model(all_runs, all_tests)

        return ComparisonResponse(
            models=models,
            time_period={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
            },
            comparison_metrics={
                "scores": scores,
                "grades": grades,
                "statistics": stats,
            },
            rankings=[
                {"model": name, "score": score, "grade": grade} for name, score, grade in rankings
            ],
            best_model={"model_name": best_model, "reason": reason} if best_model else {},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compare models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compare models: {str(e)}")


@router.get("/dashboard")
async def get_dashboard_data(
    model_name: str = Query(
        "liquidation_model_v1",
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_\-\.]+$",
        description="Model name",
    ),
    days: int = Query(90, ge=7, le=365, description="Days of data"),
) -> dict:
    """
    Get aggregated dashboard data.

    Combines trends, statistics, and recent runs for dashboard display.

    Args:
        model_name: Model to display
        days: Days of historical data

    Returns:
        Dict with dashboard data

    Example:
        GET /api/validation/dashboard?model_name=liquidation_model_v1&days=90
    """
    logger.info(f"Dashboard request: model={model_name}, days={days}")

    try:
        # Get trend data
        trends_response = await get_trends(
            model_name=model_name,
            days=days,
            resolution="daily",
            include_ma=True,
            include_degradation=True,
        )

        # Get recent runs
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        with ValidationStorage() as storage:
            recent_runs = storage.get_runs_in_date_range(
                model_name=model_name,
                start_date=start_date,
                end_date=end_date,
            )

            # Get latest run details
            latest_run = recent_runs[0] if recent_runs else None
            latest_tests = []

            if latest_run:
                latest_tests = storage.get_tests_for_run(latest_run.run_id)

        # Build dashboard response
        dashboard = {
            "model_name": model_name,
            "time_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
            },
            "latest_run": {
                "run_id": latest_run.run_id if latest_run else None,
                "grade": latest_run.overall_grade.value
                if latest_run and latest_run.overall_grade
                else None,
                "score": float(latest_run.overall_score)
                if latest_run and latest_run.overall_score
                else None,
                "completed_at": latest_run.completed_at.isoformat()
                if latest_run and latest_run.completed_at
                else None,
                "test_count": len(latest_tests),
                "tests_passed": sum(1 for t in latest_tests if t.passed),
            }
            if latest_run
            else None,
            "trends": trends_response.dict(),
            "statistics": {
                "total_runs": len(recent_runs),
                "runs_with_grade_a": sum(
                    1 for r in recent_runs if r.overall_grade and r.overall_grade.value == "A"
                ),
                "runs_with_grade_f": sum(
                    1 for r in recent_runs if r.overall_grade and r.overall_grade.value == "F"
                ),
            },
        }

        logger.info(f"Dashboard data generated for {model_name}")

        return dashboard

    except Exception as e:
        logger.error(f"Failed to get dashboard data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve dashboard data: {str(e)}")
