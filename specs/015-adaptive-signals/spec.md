# Spec 015: Adaptive Signal Loop

## Overview
Real-time self-adapting liquidation signals with feedback from trading performance.

## Acceptance Criteria

### AC1: Signal Publisher
- [ ] Publishes top 5 liquidation zones to Redis channel `liquidation:signals:{symbol}`
- [ ] Each signal includes: price, side, confidence (0.0-1.0), timestamp
- [ ] Publish latency < 10ms
- [ ] Graceful handling if Redis unavailable (log warning, continue without publish)

### AC2: Feedback Consumer
- [ ] Subscribes to `liquidation:feedback:{symbol}` channel
- [ ] Stores all feedback in DuckDB `signal_feedback` table
- [ ] Processing latency < 50ms per message
- [ ] Handles malformed messages gracefully (log error, skip)

### AC3: Adaptive Engine
- [ ] Calculates rolling hit_rate for 1h, 24h, 7d windows
- [ ] Adjusts weights using EMA (alpha=0.1)
- [ ] Rollback to default weights if hit_rate < 0.50
- [ ] Stores weight history in DuckDB `adaptive_weights` table

### AC4: API Endpoints
- [ ] GET /signals/status returns connection state and 24h counts
- [ ] GET /signals/metrics returns hit_rate, signal count, avg_pnl
- [ ] Response time < 100ms p95

## Architecture

```
LiquidationHeatmap
       ↓ Redis pub/sub
  ┌────┴────┐
  ↓         ↓
Nautilus   UTXOracle
(trade)    (dashboard)
  ↓         ↓
  └────┬────┘
       ↓
  P&L Feedback → Adapt Weights
```

## Integration Points

### LiquidationHeatmap → Redis
- Channel: `liquidation:signals:{symbol}`
- Format: `{price, side, confidence, timestamp}`
- Frequency: On heatmap update (every 15min)

### Redis → Nautilus
- Path: `/media/sam/1TB/nautilus_dev/`
- Uses existing Redis cache config
- Signal → Strategy → Order

### Redis → UTXOracle
- Path: `/media/sam/1TB/UTXOracle/`
- WebSocket: `whale_websocket.py`
- Dashboard visualization

### Feedback Loop
- Nautilus P&L → Redis `liquidation:feedback:{symbol}`
- LiquidationHeatmap consumes → adjusts weights
- Rolling accuracy tracking (1h, 24h, 7d)

## Components to Build

1. **Signal Publisher** (`src/liquidationheatmap/signals/publisher.py`)
   - Redis connection with graceful fallback if unavailable
   - Publish top 5 zones as signals (configurable via `SIGNAL_TOP_N` env var)
   - Include confidence scores (0.0-1.0 from heatmap density)

2. **Feedback Consumer** (`src/liquidationheatmap/signals/feedback.py`)
   - Subscribe to P&L feedback from `liquidation:feedback:{symbol}`
   - Store feedback in DuckDB `signal_feedback` table (does NOT update weights directly)
   - Handle malformed messages gracefully

3. **Adaptive Engine** (`src/liquidationheatmap/signals/adaptive.py`)
   - Reads feedback from DuckDB, calculates rolling accuracy metrics
   - Weight adjustment using EMA algorithm (alpha=0.1)
   - Rollback to defaults if hit_rate < 0.50
   - **[P2 Future]** Regime detection (trending/ranging/volatile) - deferred

## Validation Results (from 014)
- Gate 1 (Coinglass): hit_rate = 77.8% ✅
- Gate 2 (Backtest): F1 = 80.93% ✅
- Methodology: Recall-focused ("did we cover important levels?")

## Dependencies

**Required (P0)**:
- Redis running on localhost:6379

**Optional (P2 - Future Integration)**:
- Nautilus TradingNode configured (for automated trading)
- UTXOracle API running (for dashboard visualization)
