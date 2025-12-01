"""
Margin calculation API endpoints.

REST API for margin tier calculations and liquidation prices.
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.models.requests import BatchCalculateRequest, CalculateMarginRequest
from src.api.models.responses import (
    BatchCalculateResponse,
    CalculateMarginResponse,
    TierDetailsResponse,
    TierInfo,
    TiersResponse,
)
from src.services.display_formatter import DisplayFormatter
from src.services.margin_calculator import MarginCalculator
from src.services.tier_loader import TierLoader

router = APIRouter(prefix="/margin", tags=["margin"])

# Global cache for tier configurations
_tier_cache = {}


def get_calculator(symbol: str) -> MarginCalculator:
    """Get margin calculator for symbol."""
    if symbol not in _tier_cache:
        try:
            if symbol == "BTCUSDT":
                config = TierLoader.load_binance_default()
            else:
                raise ValueError(f"Symbol {symbol} not found")
            _tier_cache[symbol] = MarginCalculator(config)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found: {str(e)}")
    return _tier_cache[symbol]


def get_formatter(symbol: str) -> DisplayFormatter:
    """Get display formatter for symbol."""
    calculator = get_calculator(symbol)
    return DisplayFormatter(calculator.config)


@router.post("/calculate", response_model=CalculateMarginResponse)
async def calculate_margin(request: CalculateMarginRequest):
    """
    Calculate margin requirement for a position.

    Args:
        request: Margin calculation request

    Returns:
        Margin calculation result with tier information

    Raises:
        HTTPException: If symbol not found or invalid parameters
    """
    try:
        calculator = get_calculator(request.symbol)
        notional = request.get_notional()

        # Validate positive notional
        if notional <= 0:
            raise HTTPException(status_code=400, detail="Invalid notional: value must be positive")

        # Get tier and calculate margin
        tier = calculator.get_tier_for_position(notional)
        margin = calculator.calculate_margin(notional)

        # Calculate liquidation price if parameters provided
        liquidation_price = None
        if request.entry_price and request.position_size and request.leverage and request.side:
            liq = calculator.calculate_liquidation_price(
                Decimal(request.entry_price),
                Decimal(request.position_size),
                Decimal(request.leverage),
                request.side,
            )
            liquidation_price = f"{liq:.2f}"

        # Build response
        response = CalculateMarginResponse(
            symbol=request.symbol,
            notional=f"{notional:.2f}",
            margin=f"{margin:.2f}",
            tier=tier.tier_number,
            margin_rate=f"{tier.margin_rate * 100:.1f}%",
            maintenance_amount=f"{tier.maintenance_amount:.2f}",
            liquidation_price=liquidation_price,
        )

        # Add tier details if requested
        if request.include_tier_details:
            max_lev = int(Decimal("1") / tier.margin_rate)
            response.tier_details = TierDetailsResponse(
                tier_number=tier.tier_number,
                min_notional=f"{tier.min_notional:.2f}",
                max_notional=f"{tier.max_notional:.2f}",
                margin_rate=f"{tier.margin_rate * 100:.1f}%",
                maintenance_amount=f"{tier.maintenance_amount:.2f}",
                max_leverage=f"{max_lev}x",
            )

        # Add display format if requested
        if request.include_display:
            formatter = get_formatter(request.symbol)
            response.display = formatter.format_tier_info(notional)

        return response

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/batch", response_model=BatchCalculateResponse)
async def calculate_batch(request: BatchCalculateRequest):
    """
    Calculate margins for multiple positions in batch.

    Args:
        request: Batch calculation request

    Returns:
        Batch calculation results
    """
    results = []
    success_count = 0

    for calc_request in request.calculations:
        try:
            result = await calculate_margin(calc_request)
            results.append(result)
            success_count += 1
        except HTTPException:
            # Include error in results
            error_result = CalculateMarginResponse(
                symbol=calc_request.symbol,
                notional="0",
                margin="0",
                tier=0,
                margin_rate="0%",
                maintenance_amount="0",
            )
            results.append(error_result)

    return BatchCalculateResponse(
        results=results, total_count=len(request.calculations), success_count=success_count
    )


@router.get("/tiers/{symbol}", response_model=TiersResponse)
async def get_tiers(
    symbol: str,
    format: Optional[str] = Query("simple", description="Response format"),
    current_notional: Optional[str] = Query(None, description="Current position for comparison"),
):
    """
    Get margin tier information for a symbol.

    Args:
        symbol: Trading pair symbol
        format: Response format ('simple' or 'comparison')
        current_notional: Current position size for highlighting

    Returns:
        Tier information
    """
    calculator = get_calculator(symbol)

    # Build tier list
    tier_list = []
    for tier in calculator.config.tiers:
        max_lev = int(Decimal("1") / tier.margin_rate)
        tier_info = TierInfo(
            tier_number=tier.tier_number,
            min_notional=f"{tier.min_notional:.2f}",
            max_notional=f"{tier.max_notional:.2f}",
            margin_rate=f"{tier.margin_rate * 100:.1f}%",
            maintenance_amount=f"{tier.maintenance_amount:.2f}",
            max_leverage=f"{max_lev}x",
        )
        tier_list.append(tier_info)

    # Build response
    response = TiersResponse(symbol=symbol, tiers=tier_list)

    # Add comparison table if requested
    if format == "comparison":
        formatter = get_formatter(symbol)
        notional = Decimal(current_notional) if current_notional else None
        response.comparison_table = formatter.generate_tier_comparison_table(symbol, notional)

    return response


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}
