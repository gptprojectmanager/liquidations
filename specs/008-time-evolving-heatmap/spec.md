# Liquidation Heatmap V2 - Time-Evolving Model

## Executive Summary

The current liquidation heatmap implementation has a fundamental flaw: **liquidation levels are static and don't evolve over time**. When price crosses a liquidation level, those positions should be "consumed" (liquidated), but currently they persist indefinitely.

This specification defines a complete redesign to implement a **time-evolving liquidation model** that accurately reflects market dynamics.

---

## 1. Problem Analysis

### 1.1 Core Issue: Static Liquidation Levels

**Current Behavior (INCORRECT)**:
```
Time →    T1     T2     T3     T4     T5
$95K     ████   ████   ████   ████   ████   ← Liquidations persist forever
Price         ────────X                      ← Price crosses $95K at T3
                      ↑
                      Liquidations should be CONSUMED here!
```

**Expected Behavior (CORRECT)**:
```
Time →    T1     T2     T3     T4     T5
$95K     ████   ████   ░░░░   ░░░░   ░░░░   ← Liquidations consumed at T3
                      ↑
                      Price triggers liquidations, density disappears
```

### 1.2 Additional Issues Identified

| Issue | Severity | Description |
|-------|----------|-------------|
| **I1: Position Lifecycle** | CRITICAL | No concept of position creation/consumption over time |
| **I2: OI Decrease Ignored** | HIGH | Negative `oi_delta` (positions closed) is ignored |
| **I3: Time-Flat Heatmap** | HIGH | Frontend shows same density across all timestamps |
| **I4: No Liquidation Events** | MEDIUM | Don't track actual triggered liquidations |
| **I5: Leverage Hardcoded** | LOW | Leverage distribution is estimated, not data-driven |
| **I6: Price Crossing Logic** | CRITICAL | No mechanism to detect when price triggers levels |

### 1.3 Data Quality Assessment

| Data Source | Records | Coverage | Quality |
|-------------|---------|----------|---------|
| klines_5m_history | 14,112 | Sep-Nov 2025 | ✅ Good |
| open_interest_history | 417,460 | Dec 2021-Nov 2025 | ✅ Good |
| oi_delta | Available | 98% match rate | ✅ Good |
| liquidation_events | N/A | Not available | ⚠️ Missing |

---

## 2. Proposed Solution: Time-Evolving Model

### 2.1 Core Concept

Instead of calculating a single static snapshot of liquidation levels, we calculate a **time series** of liquidation states:

```
For each timestamp T:
  liquidation_state[T] = liquidation_state[T-1]
                         + new_positions[T]       # From positive OI delta
                         - consumed_positions[T]  # Price crossed level
                         - closed_positions[T]    # From negative OI delta
```

### 2.2 Algorithm Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    TIME-EVOLVING MODEL                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. INITIALIZATION                                           │
│     └─ Start with empty position map                         │
│                                                              │
│  2. FOR EACH CANDLE (chronologically):                       │
│     │                                                        │
│     ├─ 2a. CHECK CONSUMPTION                                 │
│     │   └─ If candle.high >= liq_level (short) → consume     │
│     │   └─ If candle.low <= liq_level (long) → consume       │
│     │                                                        │
│     ├─ 2b. ADD NEW POSITIONS                                 │
│     │   └─ If oi_delta > 0:                                  │
│     │       ├─ Bullish candle → Add LONG at entry_price      │
│     │       └─ Bearish candle → Add SHORT at entry_price     │
│     │                                                        │
│     └─ 2c. REMOVE CLOSED POSITIONS                           │
│         └─ If oi_delta < 0: Remove proportionally            │
│                                                              │
│  3. OUTPUT: time_series[T] = {price_level → density}         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Data Structures

```python
@dataclass
class LiquidationLevel:
    entry_price: float          # Price where position was opened
    liq_price: float            # Calculated liquidation price
    volume: float               # Position size (in USDT)
    side: Literal["long", "short"]
    leverage: int               # Leverage tier
    created_at: datetime        # When position was opened
    consumed_at: datetime | None  # When liquidated (None if still open)

@dataclass
class HeatmapCell:
    timestamp: datetime
    price_bucket: float
    long_density: float         # Volume of long liquidations at this level
    short_density: float        # Volume of short liquidations at this level
    total_density: float        # Combined density
```

### 2.4 Consumption Logic

**Long Position Liquidation**:
```
IF candle.low <= long_position.liq_price:
    → Position is liquidated
    → Remove from active positions
    → Add to consumed_liquidations for this timestamp
```

**Short Position Liquidation**:
```
IF candle.high >= short_position.liq_price:
    → Position is liquidated
    → Remove from active positions
    → Add to consumed_liquidations for this timestamp
```

---

## 3. Implementation Plan

### Phase 1: Core Algorithm (Priority: CRITICAL)

#### Task 1.1: Create Time-Evolving Calculator
- **File**: `src/liquidationheatmap/models/time_evolving_heatmap.py`
- **Function**: `calculate_time_evolving_heatmap(symbol, start_time, end_time, interval)`
- **Returns**: `List[HeatmapSnapshot]` with density at each timestamp

#### Task 1.2: Position Lifecycle Management
- Track position creation from positive OI delta
- Track position consumption when price crosses
- Track voluntary closes from negative OI delta

#### Task 1.3: Price Crossing Detection
- For each candle, check if high/low crossed any active liquidation levels
- Mark consumed positions with `consumed_at` timestamp

### Phase 2: Database Schema (Priority: HIGH)

#### Task 2.1: New Table - `liquidation_snapshots`
```sql
CREATE TABLE liquidation_snapshots (
    id BIGINT PRIMARY KEY,
    timestamp TIMESTAMP,
    symbol VARCHAR,
    price_bucket DECIMAL(18,2),
    side VARCHAR,           -- 'long' or 'short'
    active_volume DECIMAL(20,8),    -- Still open positions
    consumed_volume DECIMAL(20,8),  -- Liquidated this period
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Task 2.2: New Table - `position_events`
```sql
CREATE TABLE position_events (
    id BIGINT PRIMARY KEY,
    timestamp TIMESTAMP,
    symbol VARCHAR,
    event_type VARCHAR,     -- 'open', 'close', 'liquidate'
    entry_price DECIMAL(18,2),
    liq_price DECIMAL(18,2),
    volume DECIMAL(20,8),
    side VARCHAR,
    leverage INT
);
```

### Phase 3: API Updates (Priority: HIGH)

#### Task 3.1: New Endpoint - `/liquidations/heatmap-timeseries`
```
GET /liquidations/heatmap-timeseries
Parameters:
  - symbol: str (e.g., "BTCUSDT")
  - start_time: datetime
  - end_time: datetime
  - interval: str ("5m", "15m", "1h")

Response:
{
  "data": [
    {
      "timestamp": "2025-11-16T00:00:00",
      "levels": [
        {"price": 95000, "long_density": 1234567, "short_density": 0},
        {"price": 96000, "long_density": 0, "short_density": 2345678},
        ...
      ]
    },
    ...
  ],
  "meta": {
    "total_timestamps": 200,
    "price_range": [88000, 100000],
    "total_long_volume": ...,
    "total_short_volume": ...
  }
}
```

### Phase 4: Frontend Updates (Priority: HIGH)

#### Task 4.1: Update Heatmap Rendering
- Fetch time-series data instead of static levels
- Each column in heatmap corresponds to one timestamp
- Density varies per-cell based on that timestamp's state

#### Task 4.2: Add Visual Indicators for Liquidation Events
- Flash/highlight when price triggers major liquidation zone
- Show "consumed" areas differently (faded or removed)

### Phase 5: Performance Optimization (Priority: MEDIUM)

#### Task 5.1: Pre-computation Pipeline
- Calculate snapshots during data ingestion
- Store in `liquidation_snapshots` table
- API reads from cache, not real-time calculation

#### Task 5.2: Incremental Updates
- Only recalculate from last known state
- Efficient for real-time updates

---

## 4. Detailed Algorithm Pseudocode

```python
def calculate_time_evolving_heatmap(
    symbol: str,
    start_time: datetime,
    end_time: datetime,
    interval: str = "5m"
) -> List[HeatmapSnapshot]:

    # 1. Load data
    candles = load_candles(symbol, start_time, end_time, interval)
    oi_data = load_oi_with_delta(symbol, start_time, end_time)

    # 2. Initialize position tracker
    active_positions: Dict[float, List[LiquidationLevel]] = defaultdict(list)
    snapshots: List[HeatmapSnapshot] = []

    # 3. Process chronologically
    for candle in sorted(candles, key=lambda c: c.open_time):
        timestamp = candle.open_time
        oi = get_oi_for_timestamp(oi_data, timestamp)

        # 3a. CONSUME: Check if price triggered any liquidations
        consumed = []
        for price_level, positions in active_positions.items():
            for pos in positions:
                if should_liquidate(pos, candle):
                    pos.consumed_at = timestamp
                    consumed.append(pos)

        for pos in consumed:
            active_positions[pos.liq_price].remove(pos)

        # 3b. ADD: New positions from positive OI delta
        if oi and oi.delta > 0:
            side = infer_side(candle)
            if side:
                new_positions = create_positions(
                    entry_price=candle.close,
                    volume=oi.delta,
                    side=side,
                    timestamp=timestamp
                )
                for pos in new_positions:
                    active_positions[pos.liq_price].append(pos)

        # 3c. REMOVE: Closed positions from negative OI delta
        if oi and oi.delta < 0:
            remove_proportionally(active_positions, abs(oi.delta))

        # 3d. Snapshot current state
        snapshot = create_snapshot(timestamp, active_positions)
        snapshots.append(snapshot)

    return snapshots


def should_liquidate(pos: LiquidationLevel, candle: Candle) -> bool:
    """Check if candle price action would trigger this liquidation."""
    if pos.side == "long":
        # Long liquidates when price drops to liq_price
        return candle.low <= pos.liq_price
    else:
        # Short liquidates when price rises to liq_price
        return candle.high >= pos.liq_price


def infer_side(candle: Candle) -> Optional[str]:
    """Infer position side from candle direction."""
    if candle.close > candle.open:
        return "long"   # Bullish → longs opened
    elif candle.close < candle.open:
        return "short"  # Bearish → shorts opened
    return None  # Neutral
```

---

## 5. Testing Strategy

### 5.1 Unit Tests
- `test_position_creation`: Verify positions created correctly from OI delta
- `test_liquidation_trigger_long`: Long position liquidated when price drops
- `test_liquidation_trigger_short`: Short position liquidated when price rises
- `test_snapshot_density`: Density correctly aggregated per timestamp

### 5.2 Integration Tests
- `test_full_heatmap_calculation`: End-to-end with real data subset
- `test_api_endpoint_response`: Correct JSON structure returned
- `test_frontend_rendering`: Visual verification with playwright

### 5.3 Validation Tests
- Compare output against known liquidation events (if available)
- Verify total volume conservation (positions not created/destroyed incorrectly)

---

## 6. Success Criteria

| Metric | Target |
|--------|--------|
| Liquidation levels consumed after price cross | 100% |
| API response time (<1000 candles) | <500ms |
| Frontend render time | <1s |
| Test coverage | >80% |
| Visual accuracy vs Coinglass | Qualitative match |

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Performance degradation | Medium | High | Pre-compute snapshots |
| Incorrect consumption logic | Low | Critical | Extensive testing |
| Data gaps in OI | Low | Medium | Interpolation fallback |
| Complex frontend changes | Medium | Medium | Incremental rollout |

---

## 8. Timeline Estimate

| Phase | Tasks | Dependencies |
|-------|-------|--------------|
| Phase 1 | Core Algorithm | None |
| Phase 2 | Database Schema | Phase 1 |
| Phase 3 | API Updates | Phase 1, 2 |
| Phase 4 | Frontend Updates | Phase 3 |
| Phase 5 | Optimization | Phase 3, 4 |

---

## 9. References

- [Coinglass Liquidation Heatmap](https://www.coinglass.com/pro/futures/LiquidationHeatMap)
- [How to Use Liquidation Heatmaps](https://www.coinglass.com/learn/how-to-use-liqmap-to-assist-trading-en)
- [TradingView Liquidation Heatmap Indicator](https://www.tradingview.com/script/32PMF3sV-Crypto-Liquidation-Heatmap/)
- [Bitcoin Liquidation Heatmaps Explained](https://blofin.com/academy/blofin-courses/bitcoin-liquidation-heatmaps-explained-a-complete-guide-for-traders)
