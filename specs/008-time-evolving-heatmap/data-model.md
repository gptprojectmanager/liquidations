# Data Model: Time-Evolving Liquidation Heatmap

**Date**: 2025-12-22
**Feature**: 008-time-evolving-heatmap

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA MODEL                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     1:N     ┌───────────────────┐                 │
│  │   Candle     │────────────→│ LiquidationLevel  │                 │
│  │  (klines)    │             │   (calculated)    │                 │
│  └──────────────┘             └───────────────────┘                 │
│         │                              │                             │
│         │ 1:1                          │ N:1                         │
│         ▼                              ▼                             │
│  ┌──────────────┐             ┌───────────────────┐                 │
│  │  OISnapshot  │             │ HeatmapSnapshot   │                 │
│  │  (oi_delta)  │             │   (aggregated)    │                 │
│  └──────────────┘             └───────────────────┘                 │
│                                        │                             │
│                                        │ N:1                         │
│                                        ▼                             │
│                               ┌───────────────────┐                 │
│                               │   HeatmapCell     │                 │
│                               │ (price × time)    │                 │
│                               └───────────────────┘                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Entities

### 1. Candle (Source Data)

**Table**: `klines_5m_history` / `klines_15m_history`

| Field | Type | Description |
|-------|------|-------------|
| open_time | TIMESTAMP | Candle start time (PK) |
| symbol | VARCHAR(20) | Trading pair (e.g., BTCUSDT) |
| open | DECIMAL(18,8) | Opening price |
| high | DECIMAL(18,8) | Highest price in period |
| low | DECIMAL(18,8) | Lowest price in period |
| close | DECIMAL(18,8) | Closing price |
| volume | DECIMAL(18,8) | Base asset volume |
| quote_volume | DECIMAL(20,8) | Quote asset volume |

**Validation Rules**:
- `open_time` must be unique per symbol
- `high >= max(open, close)`
- `low <= min(open, close)`
- `volume > 0`

---

### 2. OISnapshot (Source Data)

**Table**: `open_interest_history`

| Field | Type | Description |
|-------|------|-------------|
| id | BIGINT | Primary key |
| timestamp | TIMESTAMP | Snapshot time |
| symbol | VARCHAR(20) | Trading pair |
| open_interest_value | DECIMAL(20,8) | Total OI in quote currency |
| open_interest_contracts | DECIMAL(18,8) | Total OI in contracts |
| oi_delta | DECIMAL(20,8) | Change from previous snapshot |

**Validation Rules**:
- `oi_delta` calculated as `current_oi - previous_oi`
- Can be positive (new positions) or negative (closed positions)

---

### 3. LiquidationLevel (Calculated)

**In-Memory Model** (Python):

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional
from decimal import Decimal

@dataclass
class LiquidationLevel:
    """Represents a single liquidation level created from a position."""

    entry_price: Decimal          # Price where position was opened
    liq_price: Decimal            # Calculated liquidation price
    volume: Decimal               # Position size in quote currency (USDT)
    side: Literal["long", "short"]
    leverage: int                 # Leverage tier (5, 10, 25, 50, 100)
    created_at: datetime          # When position was opened
    consumed_at: Optional[datetime] = None  # When liquidated (None if active)

    def is_active(self) -> bool:
        """Check if position is still open."""
        return self.consumed_at is None

    def __post_init__(self):
        """Validate fields after initialization."""
        if self.leverage not in (5, 10, 25, 50, 100):
            raise ValueError(f"Invalid leverage: {self.leverage}")
        if self.side not in ("long", "short"):
            raise ValueError(f"Invalid side: {self.side}")
        if self.volume <= 0:
            raise ValueError(f"Volume must be positive: {self.volume}")
```

**Liquidation Price Calculation**:
```python
def calculate_liq_price(entry_price: Decimal, leverage: int, side: str, mmr: Decimal = Decimal("0.004")) -> Decimal:
    """
    Calculate liquidation price using Binance formula.

    Long:  liq_price = entry_price * (1 - 1/leverage + mmr/leverage)
    Short: liq_price = entry_price * (1 + 1/leverage - mmr/leverage)

    Args:
        entry_price: Position entry price
        leverage: Leverage multiplier (e.g., 10 for 10x)
        side: "long" or "short"
        mmr: Maintenance margin rate (default 0.4%)

    Returns:
        Liquidation price
    """
    lev = Decimal(leverage)
    if side == "long":
        return entry_price * (1 - 1/lev + mmr/lev)
    else:  # short
        return entry_price * (1 + 1/lev - mmr/lev)
```

---

### 4. HeatmapSnapshot (Aggregated)

**In-Memory Model** (Python):

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
from decimal import Decimal

@dataclass
class HeatmapCell:
    """Single cell in the heatmap matrix."""

    price_bucket: Decimal         # Price level (rounded to bin size)
    long_density: Decimal = Decimal("0")   # Volume of active long liquidations
    short_density: Decimal = Decimal("0")  # Volume of active short liquidations

    @property
    def total_density(self) -> Decimal:
        return self.long_density + self.short_density


@dataclass
class HeatmapSnapshot:
    """Complete heatmap state at a single timestamp."""

    timestamp: datetime
    symbol: str
    cells: Dict[Decimal, HeatmapCell] = field(default_factory=dict)

    # Metadata
    total_long_volume: Decimal = Decimal("0")
    total_short_volume: Decimal = Decimal("0")
    positions_created: int = 0
    positions_consumed: int = 0

    def get_cell(self, price_bucket: Decimal) -> HeatmapCell:
        """Get or create cell for price bucket."""
        if price_bucket not in self.cells:
            self.cells[price_bucket] = HeatmapCell(price_bucket=price_bucket)
        return self.cells[price_bucket]

    def to_dict(self) -> dict:
        """Convert to API response format."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "levels": [
                {
                    "price": float(cell.price_bucket),
                    "long_density": float(cell.long_density),
                    "short_density": float(cell.short_density),
                }
                for cell in sorted(self.cells.values(), key=lambda c: c.price_bucket)
            ],
            "meta": {
                "total_long_volume": float(self.total_long_volume),
                "total_short_volume": float(self.total_short_volume),
                "positions_created": self.positions_created,
                "positions_consumed": self.positions_consumed,
            }
        }
```

---

### 5. LiquidationSnapshotDB (Persisted Cache)

**Table**: `liquidation_snapshots` (NEW)

| Field | Type | Description |
|-------|------|-------------|
| id | BIGINT | Primary key (auto-increment) |
| timestamp | TIMESTAMP | Snapshot time |
| symbol | VARCHAR(20) | Trading pair |
| price_bucket | DECIMAL(18,2) | Price level |
| side | VARCHAR(10) | "long" or "short" |
| active_volume | DECIMAL(20,8) | Volume of active liquidations |
| consumed_volume | DECIMAL(20,8) | Volume consumed this period |
| created_at | TIMESTAMP | Record creation time |

**Indexes**:
```sql
CREATE INDEX idx_liq_snap_ts_sym ON liquidation_snapshots(timestamp, symbol);
CREATE INDEX idx_liq_snap_price ON liquidation_snapshots(price_bucket);
CREATE UNIQUE INDEX idx_liq_snap_unique ON liquidation_snapshots(timestamp, symbol, price_bucket, side);
```

---

## State Transitions

### Position Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                    POSITION STATE MACHINE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                     ┌──────────────┐                                │
│                     │   CREATED    │                                │
│                     │ (oi_delta>0) │                                │
│                     └──────┬───────┘                                │
│                            │                                        │
│            ┌───────────────┼───────────────┐                        │
│            │               │               │                        │
│            ▼               ▼               ▼                        │
│     ┌──────────┐   ┌──────────┐   ┌──────────────┐                 │
│     │  ACTIVE  │   │ CONSUMED │   │   CLOSED     │                 │
│     │          │──→│ (price   │   │ (oi_delta<0) │                 │
│     │          │   │ crossed) │   │              │                 │
│     └────┬─────┘   └──────────┘   └──────────────┘                 │
│          │                                                          │
│          └─────────────────────────────────────────────────────────│
│            Transitions:                                             │
│            - oi_delta > 0 → CREATE new positions                    │
│            - price crosses liq_price → CONSUME (liquidate)          │
│            - oi_delta < 0 → CLOSE (voluntary exit)                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Consumption Logic

```python
def process_candle(
    candle: Candle,
    oi: OISnapshot,
    active_positions: Dict[Decimal, List[LiquidationLevel]]
) -> Tuple[List[LiquidationLevel], List[LiquidationLevel]]:
    """
    Process a single candle and update position states.

    Returns:
        (consumed_positions, new_positions)
    """
    consumed = []
    new_positions = []

    # 1. CHECK CONSUMPTION: Did price trigger any liquidations?
    for liq_price, positions in list(active_positions.items()):
        for pos in positions:
            if should_liquidate(pos, candle):
                pos.consumed_at = candle.open_time
                consumed.append(pos)

        # Remove consumed positions
        active_positions[liq_price] = [p for p in positions if p.is_active()]

    # 2. ADD NEW POSITIONS: From positive OI delta
    if oi and oi.oi_delta > 0:
        side = infer_side(candle)
        if side:
            new_positions = create_positions(
                entry_price=candle.close,
                volume=oi.oi_delta,
                side=side,
                timestamp=candle.open_time
            )
            for pos in new_positions:
                if pos.liq_price not in active_positions:
                    active_positions[pos.liq_price] = []
                active_positions[pos.liq_price].append(pos)

    # 3. REMOVE CLOSED POSITIONS: From negative OI delta
    if oi and oi.oi_delta < 0:
        remove_proportionally(active_positions, abs(oi.oi_delta))

    return consumed, new_positions
```

---

## Validation Rules Summary

| Entity | Rule | Type |
|--------|------|------|
| LiquidationLevel | leverage ∈ {5, 10, 25, 50, 100} | MUST |
| LiquidationLevel | side ∈ {"long", "short"} | MUST |
| LiquidationLevel | volume > 0 | MUST |
| LiquidationLevel | liq_price calculated correctly | MUST |
| HeatmapSnapshot | timestamp unique per symbol | MUST |
| HeatmapSnapshot | cells non-empty for active levels | SHOULD |
| Consumption | candle.low <= liq_price triggers long | MUST |
| Consumption | candle.high >= liq_price triggers short | MUST |
