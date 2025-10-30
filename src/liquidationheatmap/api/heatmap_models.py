"""Pydantic models for heatmap API endpoints."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class HeatmapRequest(BaseModel):
    """Request parameters for heatmap endpoint."""
    
    symbol: str = Field(..., description="Trading pair symbol", example="BTCUSDT")
    model: str = Field(..., description="Liquidation model", example="ensemble")
    timeframe: str = Field(
        "1d",
        description="Time bucket size",
        pattern="^(1h|4h|12h|1d|7d|30d)$"
    )
    start: Optional[datetime] = Field(None, description="Start time (optional)")
    end: Optional[datetime] = Field(None, description="End time (optional)")
    
    @validator('model')
    def validate_model(cls, v):
        """Validate model is supported."""
        valid_models = {'binance_standard', 'funding_adjusted', 'py_liquidation_map', 'ensemble'}
        if v not in valid_models:
            raise ValueError(f"Model must be one of {valid_models}")
        return v


class HeatmapDataPoint(BaseModel):
    """Single data point in heatmap grid."""
    
    time: datetime = Field(..., description="Time bucket timestamp")
    price_bucket: float = Field(..., description="Price bucket (e.g., 67000.0)")
    density: int = Field(..., description="Number of liquidations in bucket", ge=0)
    volume: float = Field(..., description="Total liquidation volume (USDT)", ge=0)


class HeatmapMetadata(BaseModel):
    """Metadata about the heatmap data quality and statistics."""
    
    total_volume: float = Field(..., description="Total liquidation volume across all buckets")
    highest_density_price: float = Field(..., description="Price level with most liquidations")
    num_buckets: int = Field(..., description="Total number of data buckets", ge=0)
    data_quality_score: float = Field(
        ...,
        description="Data completeness score (0-1)",
        ge=0.0,
        le=1.0
    )
    time_range_hours: float = Field(..., description="Time span of data in hours", ge=0)


class HeatmapResponse(BaseModel):
    """Response from heatmap API endpoint."""
    
    symbol: str = Field(..., description="Trading pair symbol")
    model: str = Field(..., description="Liquidation model used")
    timeframe: str = Field(..., description="Time bucket size")
    current_price: Optional[float] = Field(None, description="Current market price")
    data: List[HeatmapDataPoint] = Field(..., description="Heatmap data points")
    metadata: HeatmapMetadata = Field(..., description="Heatmap metadata")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Response generation timestamp"
    )
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "symbol": "BTCUSDT",
                "model": "ensemble",
                "timeframe": "1d",
                "current_price": 67000.0,
                "data": [
                    {
                        "time": "2024-10-29T00:00:00",
                        "price_bucket": 63600.0,
                        "density": 12,
                        "volume": 4500000.0
                    }
                ],
                "metadata": {
                    "total_volume": 4500000.0,
                    "highest_density_price": 63600.0,
                    "num_buckets": 1,
                    "data_quality_score": 0.95,
                    "time_range_hours": 24.0
                },
                "timestamp": "2024-10-29T12:00:00"
            }
        }
