# Research: Time-Evolving Liquidation Heatmap

**Date**: 2025-12-22
**Feature**: 008-time-evolving-heatmap

## Research Questions

Based on Phase 0 unknowns from plan.md.

---

## Q1: OI Delta Interpretation - Negative Delta Handling

### Question
How should we handle negative OI delta (positions closed voluntarily or liquidated)?

### Research

**Options Analyzed**:

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Proportional removal** | Remove volume proportionally from all active price levels | Simple, mathematically consistent | May not reflect actual position distribution |
| **B: Nearest-price removal** | Remove from levels nearest current price first | More realistic (traders close profitable positions) | Complex implementation |
| **C: Ignore negative delta** | Don't remove anything, only add | Simplest | Overestimates liquidation density |

**Industry Practice**:
- Coinglass and similar tools focus on **potential** liquidations, not exact counts
- The heatmap is inherently an estimation based on incomplete data
- Most implementations use some form of proportional decay

**Decision**: **Option A - Proportional Removal**

**Rationale**:
1. Mathematically consistent with how positions are created
2. Maintains total volume conservation (important for validation)
3. Avoids over-complexity while still being more accurate than ignoring
4. Can be refined later if more position-level data becomes available

**Implementation**:
```python
def remove_proportionally(active_positions: Dict, volume_to_remove: float):
    """Remove volume proportionally from all active positions."""
    total_volume = sum(sum(p.volume for p in positions)
                       for positions in active_positions.values())
    if total_volume == 0:
        return

    removal_ratio = min(volume_to_remove / total_volume, 1.0)

    for price_level, positions in active_positions.items():
        for pos in positions:
            pos.volume *= (1 - removal_ratio)
        # Remove positions with negligible volume
        active_positions[price_level] = [p for p in positions if p.volume > 0.01]
```

---

## Q2: Price Crossing Edge Cases

### Question
How should we handle edge cases when price crosses liquidation levels?

### Research

**Scenarios Analyzed**:

| Scenario | Current Price | Liq Price | Candle | Should Liquidate? |
|----------|---------------|-----------|--------|-------------------|
| Exact match (low) | - | 95000 | L=95000 | ✅ Yes |
| Wick-only (long) | 96000 | 95000 | O=96000, L=94800, C=95500 | ✅ Yes |
| Gap down | 96000 | 95000 | Previous C=96000, Open=94500 | ✅ Yes |
| Near miss | - | 95000 | L=95001 | ❌ No |

**Exchange Behavior** (Binance):
- Liquidation triggers when **mark price** reaches liquidation price
- Not based on last traded price
- For historical data, we use candle low/high as proxy for mark price range

**Decision**: **Inclusive boundary check**

```python
def should_liquidate(pos: LiquidationLevel, candle: Candle) -> bool:
    """
    Check if candle price action would trigger liquidation.
    Uses inclusive boundaries (>= and <=) to capture exact matches.
    """
    if pos.side == "long":
        # Long liquidates when price drops TO OR BELOW liq_price
        return candle.low <= pos.liq_price
    else:
        # Short liquidates when price rises TO OR ABOVE liq_price
        return candle.high >= pos.liq_price
```

**Rationale**:
1. Inclusive boundaries capture exact price matches
2. Candle low/high inherently capture wicks
3. Gap scenarios handled automatically (if open crosses, low/high will too)
4. Matches intuitive trader expectations

---

## Q3: Leverage Distribution Estimates

### Question
What leverage distribution should we use for estimating position sizes?

### Research

**Industry Insights**:
- [Professional traders rarely use more than 5x leverage](https://wundertrading.com/journal/en/learn/article/binance-leverage)
- [100x leverage for professionals only; beginners should use 5x-20x](https://www.btcc.com/en-US/academy/research-analysis/understanding-leverage-and-margin-in-crypto-trading-best-cryptocurrency-leverage-trading-platforms-in-2024)
- [1% move liquidates 100x positions](https://academy.binance.com/en/articles/what-is-leverage-in-crypto-trading)

**Coinglass Tiers** (observed from their UI):
- They display 5 tiers: 10x, 25x, 50x, 75x, 100x
- No public disclosure of distribution weights

**Academic/Research Estimates**:
- No publicly available statistics on actual leverage distribution
- Exchange data is proprietary

**Current Implementation**:
```python
LeverageDistribution = [
    (5,   0.15),  # 15% at 5x (safer traders)
    (10,  0.30),  # 30% at 10x (conservative)
    (25,  0.25),  # 25% at 25x (moderate)
    (50,  0.20),  # 20% at 50x (aggressive)
    (100, 0.10)   # 10% at 100x (degens)
]
```

**Decision**: **Keep current estimates with documentation**

**Rationale**:
1. No public data available to improve estimates
2. Current distribution is reasonable based on industry guidance
3. Weights can be made configurable for future tuning
4. The heatmap shows **relative** density, so exact distribution less critical

**Future Enhancement**: Add API parameter to override weights:
```python
@app.get("/liquidations/heatmap-timeseries")
async def get_heatmap(
    leverage_weights: Optional[str] = Query(None, description="Custom weights: '5:15,10:30,25:25,50:20,100:10'")
):
```

---

## Q4: Performance Optimization Strategy

### Question
How should we optimize for large time ranges?

### Research

**Performance Bottlenecks**:

| Operation | Current | Target | Strategy |
|-----------|---------|--------|----------|
| DuckDB query (14K candles) | ~50ms | <100ms | ✅ OK |
| Python iteration (14K) | ~200ms | <300ms | Vectorize with numpy |
| Memory (14K × 1000 positions) | ~50MB | <100MB | Use generators |
| API response | ~500ms | <100ms | Pre-computation |

**Pre-computation Strategy**:

```
┌─────────────────────────────────────────────┐
│           PRE-COMPUTATION FLOW              │
├─────────────────────────────────────────────┤
│                                             │
│  1. BATCH JOB (nightly or on-demand):       │
│     - Calculate snapshots for date range    │
│     - Store in liquidation_snapshots table  │
│     - ~5 min for full history               │
│                                             │
│  2. INCREMENTAL UPDATE (per new candle):    │
│     - Load last snapshot                    │
│     - Apply single candle update            │
│     - Store new snapshot                    │
│     - ~10ms per candle                      │
│                                             │
│  3. API QUERY (cached):                     │
│     - SELECT FROM liquidation_snapshots     │
│     - ~20ms for 500 timestamps              │
│                                             │
└─────────────────────────────────────────────┘
```

**Decision**: **Hybrid approach - compute on demand, cache results**

**Rationale**:
1. MVP: Calculate on-the-fly (acceptable for <500 candles)
2. Phase 2: Add caching layer for frequently requested ranges
3. Phase 3: Pre-computation pipeline for full history
4. Progressive enhancement aligns with constitution

**Implementation Priority**:
1. Core algorithm (no caching) - MVP
2. In-memory caching with TTL - Quick win
3. DuckDB table caching - Production ready
4. Incremental updates - Real-time capable

---

## Summary of Decisions

| Question | Decision | Confidence |
|----------|----------|------------|
| Q1: Negative OI handling | Proportional removal | High |
| Q2: Price crossing | Inclusive boundaries (<=, >=) | High |
| Q3: Leverage distribution | Keep current + make configurable | Medium |
| Q4: Performance | Hybrid (compute + cache) | High |

---

## References

- [Binance Leverage & Margin Documentation](https://www.binance.com/en/futures/trading-rules/perpetual/leverage-margin)
- [Binance Academy: What Is Leverage](https://academy.binance.com/en/articles/what-is-leverage-in-crypto-trading)
- [Coinglass Liquidation Heatmap](https://www.coinglass.com/pro/futures/LiquidationHeatMap)
- [TradingView Liquidation Heatmap Indicator](https://www.tradingview.com/script/32PMF3sV-Crypto-Liquidation-Heatmap/)
