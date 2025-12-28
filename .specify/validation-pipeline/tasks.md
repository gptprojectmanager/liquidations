# ULTIMATUM Tasks: Validation Pipeline

## Phase 1: Coinglass Benchmark [Day 1-2]

### T1.1 - Reverse-engineer Coinglass API
- [ ] Inspect Coinglass network requests (Chrome DevTools)
- [ ] Document API endpoints and parameters
- [ ] Test API response format
- [ ] Handle authentication/anti-bot if needed
- **Output**: `docs/coinglass_api.md`

### T1.2 - Create Coinglass fetcher
- [ ] Create `src/liquidationheatmap/validation/coinglass_client.py`
- [ ] Implement `fetch_heatmap(symbol, interval)`
- [ ] Add rate limiting and retry logic
- [ ] Cache responses to avoid repeated calls
- **Output**: Working Coinglass client

### T1.3 - Implement comparison metrics
- [ ] Price level Jaccard similarity
- [ ] Density correlation (Pearson)
- [ ] Top-N level overlap percentage
- **Output**: `src/liquidationheatmap/validation/metrics.py`

### T1.4 - Create comparison script
- [ ] Fetch both heatmaps
- [ ] Normalize to same price buckets
- [ ] Calculate all metrics
- [ ] Generate comparison report
- **Output**: `scripts/validate_vs_coinglass.py`

### T1.5 - Run initial comparison & document
- [ ] Run script on BTC 24h, 7d, 30d
- [ ] Document correlation scores
- [ ] Identify major discrepancies
- [ ] Decision: proceed or investigate
- **Output**: `reports/coinglass_comparison.md`

---

## Phase 2: Historical Backtest [Day 2-3]

### T2.1 - Extract liquidation events
- [ ] Query aggTrades for liquidation markers (if available)
- [ ] Alternative: use large price moves + volume spikes
- [ ] Create `liquidation_events` table in DuckDB
- **Output**: Historical liquidation dataset

### T2.2 - Build backtest framework
- [ ] Create `src/liquidationheatmap/validation/backtest.py`
- [ ] `get_heatmap_at_time(timestamp)` - reconstruct historical heatmap
- [ ] `check_prediction(liq_price, heatmap)` - was it predicted?
- [ ] Handle time alignment (heatmap before event)
- **Output**: Reusable backtest framework

### T2.3 - Define evaluation metrics
- [ ] True Positive: Predicted zone hit by liquidation
- [ ] False Positive: Predicted zone not hit
- [ ] False Negative: Liquidation outside predicted zones
- [ ] Calculate: Precision, Recall, F1
- **Output**: Metric calculation functions

### T2.4 - Run backtest on 2024 data
- [ ] Select test period (e.g., 2024-06-01 to 2024-12-31)
- [ ] Run backtest with different tolerance levels (0.5%, 1%, 2%)
- [ ] Record all results
- **Output**: Backtest results CSV

### T2.5 - Generate backtest report
- [ ] Summary statistics
- [ ] Best/worst performing periods
- [ ] Visualizations (predicted vs actual)
- [ ] Recommendations
- **Output**: `reports/backtest_2024.md`

---

## Phase 3: CI Integration [Day 3-4]

### T3.1 - Create validation test suite
- [ ] `tests/validation/test_coinglass_correlation.py`
- [ ] `tests/validation/test_backtest_accuracy.py`
- [ ] Use pytest fixtures for data loading
- [ ] Add `@pytest.mark.validation` marker
- **Output**: Validation test suite

### T3.2 - GitHub Actions workflow
- [ ] Create `.github/workflows/validation.yml`
- [ ] Run on model changes only (path filter)
- [ ] Cache test data for speed
- [ ] Post results to PR comments
- **Output**: CI workflow

### T3.3 - Regression alerting
- [ ] Define baseline metrics
- [ ] Alert if new code degrades accuracy > 5%
- [ ] Block merge if below minimum thresholds
- **Output**: Quality gates

---

## Phase 4: Real-time Monitor [Day 4-5] (Optional)

### T4.1 - Liquidation WebSocket listener
- [ ] Connect to `wss://fstream.binance.com/ws/!forceOrder@arr`
- [ ] Parse liquidation events
- [ ] Filter for BTC/ETH
- **Output**: `src/liquidationheatmap/validation/ws_monitor.py`

### T4.2 - Real-time validation logic
- [ ] Get current cached heatmap
- [ ] Check if liquidation price was predicted
- [ ] Log result to validation_events table
- **Output**: Live validation

### T4.3 - Metrics dashboard endpoint
- [ ] `GET /validation/metrics` - current accuracy stats
- [ ] Rolling 1h, 24h, 7d windows
- [ ] Simple JSON response (frontend optional)
- **Output**: API endpoint

### T4.4 - Alerting (optional)
- [ ] Webhook to Discord/Slack if accuracy drops
- [ ] Daily summary email
- **Output**: Alerting system

---

## Decision Gates

### Gate 1: After Phase 1
```
IF coinglass_correlation >= 0.7:
    PROCEED to Phase 2
ELIF coinglass_correlation >= 0.5:
    INVESTIGATE discrepancies (max 1 day)
    IF fixable: FIX and re-test
    ELSE: PROCEED with caution
ELSE:
    STOP - Model review needed
```

### Gate 2: After Phase 2
```
IF backtest_f1 >= 0.6:
    MODEL VALIDATED - Proceed to ETH expansion
ELIF backtest_f1 >= 0.4:
    ACCEPTABLE - Document limitations, proceed
ELSE:
    STOP - Model rework required
```

---

## Quick Start Commands

```bash
# Phase 1: Coinglass comparison
uv run python scripts/validate_vs_coinglass.py --symbol BTC --interval 1d

# Phase 2: Backtest
uv run python scripts/backtest_liquidations.py --start 2024-06-01 --end 2024-12-31

# Phase 3: Run validation tests
uv run pytest tests/validation/ -v --tb=short

# Phase 4: Start monitor
uv run python -m src.liquidationheatmap.validation.ws_monitor
```

---

## Estimated Timeline

| Phase | Days | Cumulative |
|-------|------|------------|
| Phase 1: Coinglass | 1.5 | 1.5 |
| Phase 2: Backtest | 1.5 | 3 |
| Phase 3: CI | 1 | 4 |
| Phase 4: Monitor | 1 | 5 |

**Total: 4-5 days to full validation pipeline**

---

## Success = Green Light for ETH

After validation passes:
1. Copy validation framework for ETH
2. Run same tests on ETH data
3. If passes → Ship multi-symbol support
4. If fails → ETH-specific tuning needed
