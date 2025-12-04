"""
Configuration model for bias adjustment settings.
Feature: LIQHEAT-005
Task: T013 - Implement AdjustmentConfig model
"""

from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class AdjustmentConfigModel(BaseModel):
    """
    Configuration for funding rate bias adjustment.

    This model represents the runtime configuration loaded from
    bias_settings.yaml and validated for correctness.
    """

    enabled: bool = Field(default=True, description="Master switch for bias adjustment feature")

    symbol: str = Field(
        default="BTCUSDT", description="Trading symbol to track", pattern=r"^[A-Z]{3,10}USDT$"
    )

    sensitivity: float = Field(
        default=50.0, description="Sensitivity factor for tanh transformation", ge=10.0, le=100.0
    )

    max_adjustment: float = Field(
        default=0.20, description="Maximum deviation from 50/50 distribution", ge=0.10, le=0.30
    )

    outlier_cap: float = Field(
        default=0.10, description="Cap for extreme funding rates", ge=0.05, le=0.20
    )

    cache_ttl_seconds: int = Field(
        default=300, description="Cache time-to-live in seconds", ge=60, le=3600
    )

    extreme_alert_threshold: float = Field(
        default=0.05, description="Threshold for extreme sentiment alerts", ge=0.01, le=0.10
    )

    # Smoothing configuration
    smoothing_enabled: bool = Field(default=False, description="Enable moving average smoothing")

    smoothing_periods: int = Field(
        default=3, description="Number of periods for moving average", ge=1, le=10
    )

    smoothing_weights: Optional[List[float]] = Field(
        default=None, description="Weights for weighted moving average"
    )

    @field_validator("sensitivity")
    @classmethod
    def validate_sensitivity(cls, v: float) -> float:
        """Ensure sensitivity is within operational range."""
        if not 10.0 <= v <= 100.0:
            raise ValueError(f"sensitivity {v} out of range [10.0, 100.0]")
        return v

    @field_validator("max_adjustment")
    @classmethod
    def validate_max_adjustment(cls, v: float) -> float:
        """Ensure max_adjustment is within safe range."""
        if not 0.10 <= v <= 0.30:
            raise ValueError(f"max_adjustment {v} out of range [0.10, 0.30]")
        return v

    @field_validator("smoothing_weights")
    @classmethod
    def validate_smoothing_weights(cls, v: Optional[List[float]], info) -> Optional[List[float]]:
        """Validate that smoothing weights sum to 1.0."""
        if v is not None:
            values = info.data
            if values.get("smoothing_enabled", False):
                if abs(sum(v) - 1.0) > 0.001:
                    raise ValueError(f"Smoothing weights must sum to 1.0, got {sum(v)}")
                if len(v) != values.get("smoothing_periods", 3):
                    raise ValueError("Number of weights must match periods")
        return v

    def to_calculator_params(self) -> dict:
        """
        Convert config to parameters for BiasCalculator initialization.

        Returns:
            Dict with scale_factor, max_adjustment, outlier_cap
        """
        return {
            "scale_factor": self.sensitivity,
            "max_adjustment": self.max_adjustment,
            "outlier_cap": self.outlier_cap,
        }

    def is_extreme_funding(self, funding_rate: Decimal) -> bool:
        """
        Check if funding rate exceeds extreme threshold.

        Args:
            funding_rate: The funding rate to check

        Returns:
            True if rate exceeds threshold
        """
        return abs(float(funding_rate)) > self.extreme_alert_threshold

    model_config = {
        "json_schema_extra": {
            "example": {
                "enabled": True,
                "symbol": "BTCUSDT",
                "sensitivity": 50.0,
                "max_adjustment": 0.20,
                "outlier_cap": 0.10,
                "cache_ttl_seconds": 300,
                "extreme_alert_threshold": 0.05,
            }
        }
    }
