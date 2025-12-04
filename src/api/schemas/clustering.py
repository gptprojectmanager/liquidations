"""Pydantic schemas for clustering API requests/responses.

Response models reuse src.clustering.models for consistency.
"""

from typing import Optional

from pydantic import BaseModel, Field

from src.clustering.models import ClusteringResult

# Response model = ClusteringResult (already defined)
ClusteringResponse = ClusteringResult


class ClusteringQueryParams(BaseModel):
    """Query parameters for clustering endpoint."""

    symbol: str = Field(
        ...,
        min_length=1,
        description="Trading pair symbol (e.g., BTCUSDT)",
        examples=["BTCUSDT"],
    )
    timeframe_minutes: int = Field(
        ..., ge=1, description="Data timeframe in minutes", examples=[30]
    )
    epsilon: Optional[float] = Field(
        default=0.1,
        ge=0.01,
        le=1.0,
        description="DBSCAN epsilon parameter (neighborhood radius)",
    )
    min_samples: Optional[int] = Field(
        default=3, ge=2, le=10, description="Minimum samples to form a cluster"
    )
    auto_tune: Optional[bool] = Field(
        default=True, description="Auto-calculate epsilon using k-distance graph"
    )
    distance_metric: Optional[str] = Field(
        default="euclidean", description="Distance metric (euclidean or manhattan)"
    )
