"""
API endpoints for funding rate bias adjustment.
Feature: LIQHEAT-005
Tasks: T026-T028
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from src.services.funding.adjustment_config import load_config
from src.services.funding.complete_calculator import CompleteBiasCalculator

logger = logging.getLogger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/api/bias",
    tags=["Funding Bias"],
    responses={404: {"description": "Not found"}},
)

# Global calculator instance (initialized on first request)
_calculator: Optional[CompleteBiasCalculator] = None


def get_calculator() -> CompleteBiasCalculator:
    """Get or create global calculator instance."""
    global _calculator
    if _calculator is None:
        config = load_config()
        _calculator = CompleteBiasCalculator(config)
        logger.info("Initialized global bias calculator")
    return _calculator


# Response Models
class FundingRateResponse(BaseModel):
    """Response model for funding rate endpoint."""

    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    rate: str = Field(..., description="Current funding rate as decimal string")
    rate_percentage: str = Field(..., description="Rate as percentage string")
    funding_time: datetime = Field(..., description="Funding timestamp")
    source: str = Field(default="binance", description="Data source")
    is_positive: bool = Field(..., description="True if rate is positive")
    is_negative: bool = Field(..., description="True if rate is negative")
    is_neutral: bool = Field(..., description="True if rate is zero")

    model_config = {"ser_json_timedelta": "iso8601"}


class BiasAdjustmentResponse(BaseModel):
    """Response model for bias adjustment endpoint."""

    symbol: str = Field(..., description="Trading symbol")
    long_ratio: str = Field(..., description="Adjusted long position ratio")
    short_ratio: str = Field(..., description="Adjusted short position ratio")
    total_oi: str = Field(..., description="Total open interest")
    long_oi: str = Field(..., description="Long open interest")
    short_oi: str = Field(..., description="Short open interest")
    confidence_score: str = Field(..., description="Confidence score (0-1)")
    funding_rate: Optional[str] = Field(None, description="Funding rate used")
    funding_time: Optional[datetime] = Field(None, description="Funding timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    model_config = {"ser_json_timedelta": "iso8601"}


# T026: GET /api/bias/funding/{symbol}
@router.get(
    "/funding/{symbol}",
    response_model=FundingRateResponse,
    summary="Get current funding rate",
    description="Fetch the current funding rate for a trading symbol from Binance.",
)
async def get_funding_rate(
    symbol: str = Path(
        ...,
        description="Trading symbol (e.g., BTCUSDT)",
        regex="^[A-Z]+USDT$",
    ),
) -> FundingRateResponse:
    """Get current funding rate for a symbol.

    Args:
        symbol: Trading symbol (must end with USDT)

    Returns:
        Current funding rate information

    Raises:
        HTTPException: If unable to fetch funding rate
    """
    try:
        calculator = get_calculator()

        # Get funding rate directly from fetcher
        funding = await calculator._fetcher.get_funding_rate(symbol)

        return FundingRateResponse(
            symbol=funding.symbol,
            rate=str(funding.rate),
            rate_percentage=str(funding.rate_percentage),
            funding_time=funding.funding_time,
            source=funding.source,
            is_positive=funding.is_positive,
            is_negative=funding.is_negative,
            is_neutral=funding.is_neutral,
        )

    except Exception as e:
        logger.error(f"Failed to fetch funding rate for {symbol}: {e}")
        raise HTTPException(status_code=503, detail=f"Unable to fetch funding rate: {str(e)}")


# T027: GET /api/bias/adjustment/{symbol}
@router.get(
    "/adjustment/{symbol}",
    response_model=BiasAdjustmentResponse,
    summary="Get bias adjustment",
    description="Calculate bias-adjusted long/short ratios based on funding rate.",
)
async def get_bias_adjustment(
    symbol: str = Path(
        ...,
        description="Trading symbol (e.g., BTCUSDT)",
        regex="^[A-Z]+USDT$",
    ),
    total_oi: Decimal = Query(
        Decimal("1000000"),
        description="Total open interest in USDT",
        ge=0,
    ),
) -> BiasAdjustmentResponse:
    """Calculate bias adjustment for a symbol.

    Args:
        symbol: Trading symbol (must end with USDT)
        total_oi: Total open interest to distribute

    Returns:
        Bias-adjusted long/short ratios and volumes

    Raises:
        HTTPException: If calculation fails
    """
    try:
        calculator = get_calculator()

        # Calculate bias adjustment
        adjustment = await calculator.calculate_bias_adjustment(symbol, total_oi)

        # Build response
        response = BiasAdjustmentResponse(
            symbol=adjustment.symbol or symbol,
            long_ratio=str(adjustment.long_ratio),
            short_ratio=str(adjustment.short_ratio),
            total_oi=str(adjustment.total_oi),
            long_oi=str(adjustment.long_oi),
            short_oi=str(adjustment.short_oi),
            confidence_score=str(adjustment.confidence_score or adjustment.confidence),
            metadata=adjustment.metadata,
        )

        # Add funding rate info from metadata if available
        if adjustment.metadata:
            response.funding_rate = adjustment.metadata.get("funding_rate")
            if "funding_time" in adjustment.metadata:
                try:
                    response.funding_time = datetime.fromisoformat(
                        adjustment.metadata["funding_time"]
                    )
                except (ValueError, TypeError):
                    # Invalid timestamp format - skip
                    pass

        return response

    except Exception as e:
        logger.error(f"Failed to calculate bias adjustment for {symbol}: {e}")
        raise HTTPException(
            status_code=503, detail=f"Unable to calculate bias adjustment: {str(e)}"
        )


# T028: Health check endpoint
@router.get(
    "/health",
    summary="Health check",
    description="Check if bias adjustment service is healthy.",
)
async def health_check() -> Dict[str, Any]:
    """Health check endpoint.

    Returns:
        Service health status
    """
    try:
        calculator = get_calculator()
        config = calculator.config

        return {
            "status": "healthy",
            "enabled": config.enabled,
            "symbol": config.symbol,
            "sensitivity": config.sensitivity,
            "max_adjustment": config.max_adjustment,
            "cache_ttl": config.cache_ttl_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Additional endpoint for getting configuration
@router.get(
    "/config",
    response_model=Dict[str, Any],
    summary="Get configuration",
    description="Get current bias adjustment configuration.",
)
async def get_configuration() -> Dict[str, Any]:
    """Get current bias adjustment configuration.

    Returns:
        Current configuration settings
    """
    try:
        calculator = get_calculator()
        config = calculator.config

        return {
            "enabled": config.enabled,
            "symbol": config.symbol,
            "sensitivity": config.sensitivity,
            "max_adjustment": config.max_adjustment,
            "outlier_cap": config.outlier_cap,
            "cache_ttl_seconds": config.cache_ttl_seconds,
            "extreme_alert_threshold": config.extreme_alert_threshold,
            "smoothing_enabled": config.smoothing_enabled,
            "smoothing_periods": config.smoothing_periods,
            "smoothing_weights": config.smoothing_weights,
        }

    except Exception as e:
        logger.error(f"Failed to get configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Unable to retrieve configuration: {str(e)}")
