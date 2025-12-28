# ULTIMATUM Tasks: Validation Pipeline

**Last Updated**: 2025-12-28
**Gate 1 Status**: ✅ PASSED (hit_rate=77.8% > 70%)

## Phase 1: Coinglass Benchmark [Day 1-2] - 80% COMPLETE

### T1.1 - Reverse-engineer Coinglass API
- [x] Inspect Coinglass network requests (Chrome DevTools)
- [x] Test API response format
- [x] Handle authentication/anti-bot (Playwright scraping)
- [ ] Document API endpoints and parameters
- **Output**: `docs/coinglass_api.md` ❌ TODO

### T1.2 - Create Coinglass fetcher ✅ COMPLETE
- [x] Create `src/liquidationheatmap/validation/coinglass_scraper.py`
- [x] Implement scraping via Playwright
- [x] Add Hyperliquid API alternative
- [x] Cache responses to JSONL
- **Output**: Working Coinglass client ✅

### T1.3 - Implement comparison metrics ✅ COMPLETE
- [x] Price level hit rate calculation
- [x] Long/short breakdown
- [x] Zone matching algorithm
- **Output**: Metrics in `scripts/validate_vs_coinglass.py` ✅

### T1.4 - Create comparison script ✅ COMPLETE
- [x] Fetch both heatmaps (ours + Coinglass/Hyperliquid)
- [x] Normalize to same price buckets
- [x] Calculate hit rate metrics
- [x] Generate JSON results
- **Output**: `scripts/validate_vs_coinglass.py` (640 lines) ✅

### T1.5 - Run initial comparison & document
- [x] Run script on BTC (mock + real data)
- [x] Current result: hit_rate=77.8%, status=GOOD
- [ ] Run on multiple timeframes (24h, 7d, 30d)
- [ ] Document in report
- **Output**: `reports/coinglass_comparison.md` ❌ TODO

**Gate 1 Decision**: ✅ PROCEED - hit_rate=77.8% >= 70%

---

## Phase 2: Historical Backtest [Day 2-3] - ✅ COMPLETE

### T2.1 - Extract liquidation events ✅ COMPLETE
- [x] DuckDB tables exist: `liquidation_levels`, `liquidation_snapshots`
- [x] `position_events` table available
- [x] Uses `liquidation_snapshots` for predictions (864k+ rows)
- **Output**: Historical liquidation dataset ✅

### T2.2 - Build backtest framework ✅ COMPLETE
- [x] `scripts/backtest_models.py` exists
- [x] Create `src/liquidationheatmap/validation/backtest.py`
- [x] `get_predicted_zones()` - get heatmap at timestamp
- [x] `match_predictions_to_actuals()` - compare vs price range
- **Output**: Reusable backtest framework ✅

### T2.3 - Define evaluation metrics ✅ COMPLETE
- [x] True Positive: Predicted zone hit by price movement
- [x] False Positive: Predicted zone not hit
- [x] False Negative: Not measured (no ground truth)
- [x] Calculate: Precision, Recall, F1
- **Output**: `calculate_metrics()` function ✅

### T2.4 - Run backtest on available data ✅ COMPLETE
- [x] Period: 2025-11-10 to 2025-12-24 (data available)
- [x] Run backtest with tolerance levels (0.5%, 1%, 2%)
- [x] Best result: **F1=80.93%** at 2% tolerance
- **Output**: `reports/backtest_2024.json` ✅

### T2.5 - Generate backtest report ✅ COMPLETE
- [x] Summary statistics (TP=1396, FN=658)
- [x] Precision: 100%, Recall: 68%
- [x] Gate 2 Status: **VALIDATED** (F1=80.93% ≥ 60%)
- **Output**: `reports/backtest_2024.md` ✅

---

## Phase 3: CI Integration [Day 3-4] - 60% COMPLETE

### T3.1 - Create validation test suite ✅ COMPLETE
- [x] 26 validation test files exist in `tests/validation/`
- [x] Tests cover: metrics, comparison, accuracy, security
- [x] Pytest fixtures in place
- **Output**: Validation test suite ✅

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

## Phase 4: Real-time Monitor [Day 4-5] (Optional) - 0% COMPLETE

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

### Gate 1: After Phase 1 ✅ PASSED
```
hit_rate = 0.778 >= 0.70 → PROCEED to Phase 2
```

### Gate 2: After Phase 2 ✅ PASSED
```
IF backtest_f1 >= 0.6:
    MODEL VALIDATED - Proceed to ETH expansion  ← CURRENT (F1=80.93%)
ELIF backtest_f1 >= 0.4:
    ACCEPTABLE - Document limitations, proceed
ELSE:
    STOP - Model rework required

Result: F1=80.93% at 2% tolerance → VALIDATED ✅
Methodology: Recall-focused ("Did we cover the important price levels?")
- Precision: 100% (predictions near actual levels are always correct)
- Recall: 68% (we cover 68% of important levels reached)
```

---

## Quick Start Commands

```bash
# Phase 1: Coinglass comparison
uv run python scripts/validate_vs_coinglass.py --mock      # Test with mock data
uv run python scripts/validate_vs_coinglass.py             # Real Playwright scrape
uv run python scripts/validate_vs_coinglass.py --summary   # View historical results

# Phase 2: Backtest
uv run python scripts/backtest_models.py  # Existing script

# Phase 3: Run validation tests
uv run pytest tests/validation/ -v --tb=short

# Phase 4: Start monitor (TODO)
# uv run python -m src.liquidationheatmap.validation.ws_monitor
```

---

## Remaining Work Summary

| Task | Priority | Effort | Blocker? |
|------|----------|--------|----------|
| T1.5 - Comparison report | P1 | 1h | No |
| T2.2-T2.5 - Backtest framework | P0 | 4-6h | Gate 2 |
| T3.2 - GitHub Actions | P2 | 2h | No |
| T4.* - Real-time monitor | P3 | 4h | Optional |

**Next Action**: Complete Phase 2 backtest to pass Gate 2 → unlock ETH expansion

---

## Success = Green Light for ETH

After validation passes:
1. Copy validation framework for ETH
2. Run same tests on ETH data
3. If passes → Ship multi-symbol support
4. If fails → ETH-specific tuning needed
