# ULTIMATUM: Validation Pipeline Specification

**Feature**: Liquidation Heatmap Validation & Benchmarking Pipeline
**Priority**: P0 - CRITICAL (blocks all expansion)
**Estimated Effort**: 3-5 days
**ROI**: Prevents scaling broken model (10x cost savings)

---

## 1. Problem Statement

### Current State
- Heatmap generates liquidation levels based on OI + leverage distribution
- **ZERO validation** that outputs match reality
- Expanding to ETH/exchanges without validation = scaling potential garbage

### Risk Without Validation
| Scenario | Probability | Impact |
|----------|-------------|--------|
| Model is 90%+ accurate | 30% | Ship confidently |
| Model is 60-90% accurate | 50% | Fix bugs, then ship |
| Model is <60% accurate | 20% | Complete rework needed |

**Expected value of validation**: Catch problems BEFORE 10x effort on expansion

---

## 2. Success Criteria

### P0 - Must Have
- [ ] **Coinglass Benchmark**: Correlation > 0.7 with Coinglass heatmap
- [ ] **Backtest Accuracy**: Precision > 60% on historical liquidation events
- [ ] **Automated CI**: Validation runs on every model change

### P1 - Should Have
- [ ] **Real-time Monitoring**: Dashboard showing prediction vs actual
- [ ] **Alerting**: Notify when hit rate drops below threshold

### P2 - Nice to Have
- [ ] **Multi-exchange Comparison**: Validate against Bybit/OKX data
- [ ] **Public Leaderboard**: Show accuracy metrics publicly

---

## 3. Technical Design

### 3.1 Data Sources

```
REFERENCE DATA (Ground Truth)
├── Coinglass API (heatmap snapshots)
├── Binance Liquidation Stream (wss://fstream.binance.com)
└── Historical Liquidations (from aggTrades with special flag)

OUR DATA (To Validate)
├── /liquidations/heatmap-timeseries endpoint
└── Pre-computed heatmap_cache table
```

### 3.2 Validation Tests

#### TEST 1: Coinglass Correlation
```python
# Fetch Coinglass heatmap for BTC
coinglass_levels = fetch_coinglass_heatmap("BTC", "1d")

# Fetch our heatmap
our_levels = fetch_our_heatmap("BTCUSDT", "1d")

# Compare
correlation = calculate_price_level_correlation(coinglass_levels, our_levels)
assert correlation > 0.7, f"Correlation {correlation} below threshold"
```

**Metrics**:
- Price level overlap (Jaccard similarity)
- Density distribution correlation (Pearson/Spearman)
- Top-10 level match rate

#### TEST 2: Historical Backtest
```python
# Get historical liquidations from Binance
liquidations = fetch_historical_liquidations("BTCUSDT", "2024-01-01", "2024-12-31")

# For each liquidation event:
for liq in liquidations:
    # Get our heatmap BEFORE the liquidation
    heatmap = get_heatmap_at_time(liq.timestamp - timedelta(hours=1))

    # Check if liquidation price was in our predicted zones
    hit = is_price_in_liquidation_zone(liq.price, heatmap, tolerance=0.5%)

# Calculate metrics
precision = hits / total_predictions
recall = hits / total_liquidations
f1 = 2 * (precision * recall) / (precision + recall)
```

**Metrics**:
- Precision: % of our predictions that were correct
- Recall: % of actual liquidations we predicted
- F1 Score: Harmonic mean

#### TEST 3: Real-time Monitoring
```python
# WebSocket listener for live liquidations
async def monitor_liquidations():
    async with websocket.connect(BINANCE_LIQUIDATION_STREAM) as ws:
        while True:
            liq = await ws.recv()

            # Check against current heatmap
            current_heatmap = get_cached_heatmap()
            predicted = was_level_predicted(liq.price, current_heatmap)

            # Log to metrics DB
            log_validation_event(liq, predicted)

            # Alert if hit rate drops
            if rolling_hit_rate(window=100) < 0.5:
                send_alert("Hit rate below 50%!")
```

---

## 4. Implementation Plan

### Phase 1: Coinglass Benchmark (Day 1-2)
| Task | Description | Effort |
|------|-------------|--------|
| 1.1 | Reverse-engineer Coinglass API | 2h |
| 1.2 | Create comparison script | 2h |
| 1.3 | Define correlation metrics | 1h |
| 1.4 | Run initial comparison | 1h |
| 1.5 | Document findings | 1h |

**Deliverable**: `scripts/validate_vs_coinglass.py`

### Phase 2: Historical Backtest (Day 2-3)
| Task | Description | Effort |
|------|-------------|--------|
| 2.1 | Extract liquidation events from aggTrades | 3h |
| 2.2 | Build backtest framework | 3h |
| 2.3 | Run backtest on 2024 data | 2h |
| 2.4 | Calculate precision/recall | 1h |
| 2.5 | Generate report | 1h |

**Deliverable**: `scripts/backtest_liquidations.py`, `reports/backtest_2024.md`

### Phase 3: CI Integration (Day 3-4)
| Task | Description | Effort |
|------|-------------|--------|
| 3.1 | Create pytest validation suite | 2h |
| 3.2 | Add GitHub Actions workflow | 1h |
| 3.3 | Set up regression alerts | 1h |

**Deliverable**: `tests/validation/test_model_accuracy.py`

### Phase 4: Real-time Dashboard (Day 4-5)
| Task | Description | Effort |
|------|-------------|--------|
| 4.1 | WebSocket liquidation listener | 2h |
| 4.2 | Metrics logging to DuckDB | 2h |
| 4.3 | Simple dashboard endpoint | 2h |
| 4.4 | Alerting (optional) | 2h |

**Deliverable**: `src/liquidationheatmap/validation/monitor.py`

---

## 5. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Coinglass API changes | Cache responses, implement retry logic |
| No historical liquidation data | Use price touches on high-density zones as proxy |
| Model fundamentally flawed | Early detection = early pivot, not sunk cost |

---

## 6. Decision Points

### After Phase 1 (Coinglass Comparison)
- **If correlation > 0.7**: Proceed to Phase 2
- **If correlation 0.5-0.7**: Investigate discrepancies, tune model
- **If correlation < 0.5**: STOP. Fundamental model review needed.

### After Phase 2 (Backtest)
- **If F1 > 0.6**: Model is production-ready, proceed to ETH
- **If F1 0.4-0.6**: Acceptable, but flag for improvement
- **If F1 < 0.4**: Model needs rework before expansion

---

## 7. Success Metrics Summary

| Metric | Threshold | Current | Target |
|--------|-----------|---------|--------|
| Coinglass Correlation | > 0.7 | ? | 0.8+ |
| Backtest Precision | > 60% | ? | 70%+ |
| Backtest Recall | > 50% | ? | 60%+ |
| Real-time Hit Rate | > 50% | ? | 65%+ |

---

## 8. Next Steps After Validation

**If Validation PASSES:**
1. ETH expansion (2-3 days)
2. Multi-symbol support refactor
3. Exchange aggregation (lower priority)

**If Validation FAILS:**
1. Root cause analysis
2. Model algorithm review
3. Possible pivot to different approach

---

## Appendix: Coinglass API Notes

```
# Observed endpoints (may change)
GET https://www.coinglass.com/api/futures/liquidation/chart
Params: symbol=BTC, interval=1d

# Response structure (estimated)
{
  "data": {
    "prices": [...],
    "longLiquidations": [...],
    "shortLiquidations": [...]
  }
}
```

**Note**: Coinglass may have anti-scraping. Use respectful rate limiting.
