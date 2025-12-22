"""Time-evolving liquidation heatmap algorithm.

Implements a model where liquidation levels are dynamically created from OI increases
and consumed when price crosses them. This fixes the fundamental flaw where static
liquidation bands persist incorrectly after being triggered.

Key concepts:
- Positions are CREATED when OI increases (positive delta)
- Positions are CONSUMED when price crosses their liquidation level
- Positions are CLOSED when OI decreases (negative delta) - removed proportionally

Research decisions (see research.md):
- Q1: Proportional removal for negative OI delta
- Q2: Inclusive boundary check for price crossing (<=, >=)
- Q3: Configurable leverage distribution with sensible defaults
"""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Protocol

from src.liquidationheatmap.models.position import (
    HeatmapSnapshot,
    LiquidationLevel,
    calculate_liq_price,
)

# Default leverage distribution (see research.md Q3)
DEFAULT_LEVERAGE_WEIGHTS: list[tuple[int, Decimal]] = [
    (5, Decimal("0.15")),  # 15% at 5x (safer traders)
    (10, Decimal("0.30")),  # 30% at 10x (conservative)
    (25, Decimal("0.25")),  # 25% at 25x (moderate)
    (50, Decimal("0.20")),  # 20% at 50x (aggressive)
    (100, Decimal("0.10")),  # 10% at 100x (high risk)
]


class CandleLike(Protocol):
    """Protocol for candle-like objects."""

    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


def should_liquidate(pos: LiquidationLevel, candle: CandleLike) -> bool:
    """Check if candle price action would trigger this liquidation.

    Uses inclusive boundaries to capture exact price matches.
    See research.md Q2 for edge case analysis.

    Args:
        pos: The liquidation level to check
        candle: The candle with OHLC data

    Returns:
        True if the position would be liquidated
    """
    if pos.side == "long":
        # Long liquidates when price drops TO OR BELOW liq_price
        return candle.low <= pos.liq_price
    else:
        # Short liquidates when price rises TO OR ABOVE liq_price
        return candle.high >= pos.liq_price


def infer_side(candle: CandleLike) -> Literal["long", "short"]:
    """Infer position side from candle direction.

    Bullish candle (close > open) → longs opened
    Bearish candle (close < open) → shorts opened
    Neutral candle (close == open) → default to long

    Args:
        candle: The candle with OHLC data

    Returns:
        "long" or "short"
    """
    if candle.close > candle.open:
        return "long"
    elif candle.close < candle.open:
        return "short"
    else:
        # Doji - default to long
        return "long"


def create_positions(
    entry_price: Decimal,
    volume: Decimal,
    side: Literal["long", "short"],
    timestamp: datetime,
    leverage_weights: list[tuple[int, Decimal]] | None = None,
) -> list[LiquidationLevel]:
    """Create positions distributed across leverage tiers.

    Distributes the given volume across different leverage tiers based on
    the configured weights. Each tier gets a proportional share of volume.

    Args:
        entry_price: Price where positions are opened
        volume: Total position size in quote currency (USDT)
        side: Position direction ("long" or "short")
        timestamp: When positions are opened
        leverage_weights: Optional custom weights (default: DEFAULT_LEVERAGE_WEIGHTS)

    Returns:
        List of LiquidationLevel objects, one per leverage tier
    """
    if leverage_weights is None:
        leverage_weights = DEFAULT_LEVERAGE_WEIGHTS

    positions = []
    for leverage, weight in leverage_weights:
        tier_volume = volume * weight
        if tier_volume <= 0:
            continue

        liq_price = calculate_liq_price(
            entry_price=entry_price,
            leverage=leverage,
            side=side,
        )

        positions.append(
            LiquidationLevel(
                entry_price=entry_price,
                liq_price=liq_price,
                volume=tier_volume,
                side=side,
                leverage=leverage,
                created_at=timestamp,
            )
        )

    return positions


def remove_proportionally(
    active_positions: dict[Decimal, list[LiquidationLevel]],
    volume_to_remove: Decimal,
) -> None:
    """Remove volume proportionally from all active positions.

    When OI decreases (positions are closed voluntarily), we don't know which
    specific positions were closed. This function removes volume proportionally
    from all active positions based on their relative sizes.

    See research.md Q1 for decision rationale.

    Args:
        active_positions: Dict mapping liq_price to list of positions
        volume_to_remove: Amount of volume to remove (absolute value)

    Note:
        Modifies active_positions in place. Positions with volume < 0.01 are removed.
    """
    # Calculate total volume across all positions
    total_volume = sum(sum(p.volume for p in positions) for positions in active_positions.values())

    if total_volume == 0:
        return

    # Calculate removal ratio (capped at 100%)
    removal_ratio = min(volume_to_remove / total_volume, Decimal("1.0"))

    # Apply proportional reduction to all positions
    for price_level in list(active_positions.keys()):
        positions = active_positions[price_level]
        for pos in positions:
            pos.volume = pos.volume * (Decimal("1.0") - removal_ratio)

        # Remove positions with negligible volume
        active_positions[price_level] = [p for p in positions if p.volume >= Decimal("0.01")]


def process_candle(
    candle: CandleLike,
    oi_delta: Decimal,
    active_positions: dict[Decimal, list[LiquidationLevel]],
    leverage_weights: list[tuple[int, Decimal]] | None = None,
) -> tuple[list[LiquidationLevel], list[LiquidationLevel]]:
    """Process a single candle and update position states.

    Implements the core time-evolving algorithm:
    1. CHECK CONSUMPTION: Did price trigger any liquidations?
    2. ADD NEW POSITIONS: From positive OI delta
    3. REMOVE CLOSED POSITIONS: From negative OI delta

    Args:
        candle: The candle with OHLC data
        oi_delta: Change in open interest (positive = new positions, negative = closed)
        active_positions: Dict mapping liq_price to list of positions (modified in place)
        leverage_weights: Optional custom leverage distribution

    Returns:
        Tuple of (consumed_positions, created_positions)
    """
    consumed: list[LiquidationLevel] = []
    created: list[LiquidationLevel] = []

    # 1. CHECK CONSUMPTION: Did price trigger any liquidations?
    for liq_price in list(active_positions.keys()):
        positions = active_positions[liq_price]
        for pos in positions:
            if pos.is_active() and should_liquidate(pos, candle):
                pos.consumed_at = candle.open_time
                consumed.append(pos)

        # Keep only active (not consumed) positions
        active_positions[liq_price] = [p for p in positions if p.is_active()]

    # 2. ADD NEW POSITIONS: From positive OI delta
    if oi_delta > 0:
        side = infer_side(candle)
        new_positions = create_positions(
            entry_price=candle.close,
            volume=oi_delta,
            side=side,
            timestamp=candle.open_time,
            leverage_weights=leverage_weights,
        )
        for pos in new_positions:
            if pos.liq_price not in active_positions:
                active_positions[pos.liq_price] = []
            active_positions[pos.liq_price].append(pos)
            created.append(pos)

    # 3. REMOVE CLOSED POSITIONS: From negative OI delta
    if oi_delta < 0:
        remove_proportionally(active_positions, abs(oi_delta))

    return consumed, created


def _aggregate_to_snapshot(
    timestamp: datetime,
    symbol: str,
    active_positions: dict[Decimal, list[LiquidationLevel]],
    positions_created: int,
    positions_consumed: int,
    price_bucket_size: Decimal = Decimal("100"),
) -> HeatmapSnapshot:
    """Aggregate active positions into a heatmap snapshot.

    Groups positions into price buckets and calculates density for visualization.

    Args:
        timestamp: Snapshot timestamp
        symbol: Trading pair symbol
        active_positions: Dict mapping liq_price to list of positions
        positions_created: Count of positions created this period
        positions_consumed: Count of positions consumed this period
        price_bucket_size: Size of price buckets for aggregation

    Returns:
        HeatmapSnapshot with aggregated cell data
    """
    snapshot = HeatmapSnapshot(
        timestamp=timestamp,
        symbol=symbol,
        positions_created=positions_created,
        positions_consumed=positions_consumed,
    )

    total_long = Decimal("0")
    total_short = Decimal("0")

    for liq_price, positions in active_positions.items():
        # Round to price bucket
        bucket = (liq_price // price_bucket_size) * price_bucket_size

        cell = snapshot.get_cell(bucket)

        for pos in positions:
            if pos.side == "long":
                cell.long_density += pos.volume
                total_long += pos.volume
            else:
                cell.short_density += pos.volume
                total_short += pos.volume

    snapshot.total_long_volume = total_long
    snapshot.total_short_volume = total_short

    return snapshot


def calculate_time_evolving_heatmap(
    candles: list[Any],
    oi_deltas: list[Decimal],
    symbol: str,
    leverage_weights: list[tuple[int, Decimal]] | None = None,
    price_bucket_size: Decimal = Decimal("100"),
) -> list[HeatmapSnapshot]:
    """Calculate time-evolving liquidation heatmap.

    Main entry point for the algorithm. Processes candles chronologically,
    tracking position lifecycle (creation → consumption → closure) with
    proper price-crossing detection logic.

    Args:
        candles: List of candle-like objects with OHLC data
        oi_deltas: List of OI delta values, one per candle
        symbol: Trading pair symbol (e.g., "BTCUSDT")
        leverage_weights: Optional custom leverage distribution
        price_bucket_size: Size of price buckets for visualization

    Returns:
        List of HeatmapSnapshot objects, one per candle

    Raises:
        ValueError: If candles and oi_deltas have different lengths
    """
    if len(candles) != len(oi_deltas):
        raise ValueError(
            f"candles ({len(candles)}) and oi_deltas ({len(oi_deltas)}) must have same length"
        )

    if not candles:
        return []

    # Sort candles chronologically
    sorted_pairs = sorted(zip(candles, oi_deltas), key=lambda x: x[0].open_time)

    active_positions: dict[Decimal, list[LiquidationLevel]] = defaultdict(list)
    snapshots: list[HeatmapSnapshot] = []

    for candle, oi_delta in sorted_pairs:
        consumed, created = process_candle(
            candle=candle,
            oi_delta=oi_delta,
            active_positions=active_positions,
            leverage_weights=leverage_weights,
        )

        snapshot = _aggregate_to_snapshot(
            timestamp=candle.open_time,
            symbol=symbol,
            active_positions=active_positions,
            positions_created=len(created),
            positions_consumed=len(consumed),
            price_bucket_size=price_bucket_size,
        )

        snapshots.append(snapshot)

    return snapshots
