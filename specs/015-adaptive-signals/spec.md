# Spec 015: Adaptive Signal Loop

## Overview
Real-time self-adapting liquidation signals with feedback from trading performance.

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
   - Redis connection
   - Publish top N zones as signals
   - Include confidence scores

2. **Feedback Consumer** (`src/liquidationheatmap/signals/feedback.py`)
   - Subscribe to P&L feedback
   - Update model weights
   - Store in DuckDB for analysis

3. **Adaptive Engine** (`src/liquidationheatmap/signals/adaptive.py`)
   - Rolling accuracy metrics
   - Weight adjustment algorithm
   - Regime detection (trending/ranging/volatile)

## Validation Results (from 014)
- Gate 1 (Coinglass): hit_rate = 77.8% ✅
- Gate 2 (Backtest): F1 = 80.93% ✅
- Methodology: Recall-focused ("did we cover important levels?")

## Dependencies
- Redis running on localhost:6379
- Nautilus TradingNode configured
- UTXOracle API running
