"""Clustering API endpoints for liquidation zones.

Provides REST API for DBSCAN clustering of liquidation levels.
"""

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from src.clustering.models import ClusterParameters
from src.clustering.service import ClusteringService

router = APIRouter(prefix="/liquidations", tags=["clustering"])

# Service instance
_clustering_service = ClusteringService()


def _get_mock_liquidations(symbol: str, timeframe_minutes: int):
    """Get mock liquidation data for testing.

    TODO: Replace with actual database query in production.

    Args:
        symbol: Trading pair symbol
        timeframe_minutes: Timeframe in minutes

    Returns:
        List of liquidation dicts with price and volume
    """
    # Mock data for testing - dense cluster around 95000
    return [
        {"price": 94900.0, "volume": 1000000.0},
        {"price": 94950.0, "volume": 1200000.0},
        {"price": 95000.0, "volume": 1500000.0},
        {"price": 95050.0, "volume": 1100000.0},
        {"price": 95100.0, "volume": 900000.0},
        {"price": 96500.0, "volume": 800000.0},
        {"price": 96550.0, "volume": 750000.0},
        {"price": 96600.0, "volume": 850000.0},
    ]


@router.get("/clusters")
async def get_liquidation_clusters(
    symbol: str = Query(..., min_length=1, description="Trading pair symbol (e.g., BTCUSDT)"),
    timeframe_minutes: int = Query(..., ge=1, description="Data timeframe in minutes"),
    epsilon: Optional[float] = Query(
        default=0.1, ge=0.01, le=1.0, description="DBSCAN epsilon parameter"
    ),
    min_samples: Optional[int] = Query(default=3, ge=2, le=10, description="Minimum samples"),
    auto_tune: Optional[bool] = Query(
        default=True, description="Auto-calculate epsilon using k-distance"
    ),
    distance_metric: Optional[Literal["euclidean", "manhattan"]] = Query(
        default="euclidean", description="Distance metric"
    ),
):
    """Cluster liquidation levels into zones using DBSCAN.

    This endpoint groups nearby liquidation levels into distinct zones,
    making it easier to identify major liquidation areas.

    Args:
        symbol: Trading pair symbol (e.g., BTCUSDT)
        timeframe_minutes: Data timeframe in minutes
        epsilon: DBSCAN neighborhood radius [0.01, 1.0]
        min_samples: Minimum points to form a cluster [2, 10]
        auto_tune: Auto-calculate epsilon (overrides epsilon param)
        distance_metric: Distance metric (euclidean or manhattan)

    Returns:
        ClusteringResult with clusters, noise points, and metadata

    Raises:
        HTTPException: 422 if validation fails
    """
    try:
        # Get liquidation data (mock for now)
        liquidations = _get_mock_liquidations(symbol, timeframe_minutes)

        # Create parameters
        params = ClusterParameters(
            epsilon=epsilon,
            min_samples=min_samples,
            auto_tune=auto_tune,
            distance_metric=distance_metric,
        )

        # Run clustering
        result = _clustering_service.cluster_liquidations(
            liquidations=liquidations,
            symbol=symbol,
            timeframe_minutes=timeframe_minutes,
            params=params,
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")
