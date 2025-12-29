# Research: Adaptive Signal Loop

**Feature**: 015-adaptive-signals
**Date**: 2025-12-28
**Status**: COMPLETE

---

## Research Questions

### Q1: Redis Pub/Sub Pattern for Financial Signals

**Decision**: JSON serialization over Redis pub/sub, one channel per symbol

**Rationale**:
- JSON is human-readable for debugging
- Channel-per-symbol allows selective subscription
- Pub/sub decouples producer from consumers

**Implementation**:
```python
# Channel format
channel = f"liquidation:signals:{symbol}"  # e.g., "liquidation:signals:BTCUSDT"

# Message format
{
    "symbol": "BTCUSDT",
    "price": "95000.50",
    "side": "long",
    "confidence": 0.85,
    "timestamp": "2025-12-28T10:30:00Z"
}
```

**Alternatives Considered**:
- MessagePack: Faster but harder to debug
- Protobuf: Overkill for simple signals
- Redis Streams: More complex, not needed for simple pub/sub

---

### Q2: Weight Adjustment Algorithm

**Decision**: Exponential Moving Average (EMA) of hit rates

**Rationale**:
- Recent performance weighted higher
- Smooth adaptation (no sudden jumps)
- Easy to tune via alpha parameter

**Implementation**:
```python
# Weight update formula
alpha = 0.1  # Smoothing factor
new_weight = alpha * recent_hit_rate + (1 - alpha) * old_weight

# Rolling windows
windows = ["1h", "24h", "7d"]
weights = {
    "1h": 0.5,   # Most reactive
    "24h": 0.3,  # Medium-term
    "7d": 0.2    # Stable baseline
}
```

**Alternatives Considered**:
- Simple Moving Average: Less responsive to recent data
- Kalman Filter: Overkill for this use case
- Reinforcement Learning: Too complex, needs more data

---

### Q3: Regime Detection

**Decision**: ATR + SMA crossover for volatility/trend classification

**Rationale**:
- ATR captures volatility
- SMA crossover captures trend
- Combine for regime: trending, ranging, volatile

**Implementation**:
```python
# Regime classification
def classify_regime(atr_percentile, trend_slope):
    if atr_percentile > 0.8:
        return "volatile"
    elif abs(trend_slope) > 0.01:
        return "trending"
    else:
        return "ranging"
```

**Alternatives Considered**:
- Hidden Markov Model: Too complex
- Machine Learning: Needs labeled data
- Manual thresholds: Current approach, simple and transparent

---

### Q4: Rollback Strategy

**Decision**: Default weights stored, automatic revert if hit_rate < 0.50

**Rationale**:
- Constitution §6 requires graceful degradation
- 50% hit rate = random, should revert to defaults
- Automatic revert prevents manual intervention

**Implementation**:
```python
# Rollback logic
DEFAULT_WEIGHTS = {"long": 0.5, "short": 0.5}

if current_hit_rate < 0.50:
    weights = DEFAULT_WEIGHTS.copy()
    log.warning(f"Hit rate {current_hit_rate:.2%} below threshold, reverting to defaults")
```

---

## Validation Results (from 014)

| Gate | Metric | Result |
|------|--------|--------|
| Coinglass | hit_rate | 77.8% ✅ |
| Backtest | F1 Score | 80.93% ✅ |

**Methodology**: Recall-focused ("did we cover important levels?")

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| redis-py | >=5.0 | Redis client |
| DuckDB | existing | Feedback storage |
| FastAPI | existing | API endpoints |

---

**Research Status**: ✅ Complete - No blockers
