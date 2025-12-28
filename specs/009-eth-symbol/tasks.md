# Tasks: ETH/USDT Symbol Support

**Input**: Design documents from `/specs/009-eth-symbol/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete), quickstart.md (complete)

**Feature Type**: Data Operations (100% code reuse - ZERO new code)

**Organization**: Tasks grouped by operational phase. No user stories in traditional sense - this is pure parameterization of existing symbol-agnostic pipeline.

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (no dependencies on other running tasks)
- Include exact commands/paths in descriptions

## Path Conventions
- **Scripts**: `scripts/` at repository root
- **Database**: `data/processed/liquidations.duckdb`
- **Data Source**: `/media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/`

---

## Phase 1: Data Discovery

**Purpose**: Verify ETH data availability before ingestion

- [X] T001 Verify ETH aggTrades data exists at /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/

**Validation Commands**:
```bash
ls -lh /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/
find /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/ -name "*.csv" | wc -l
```

**Success Criteria**:
- Directory exists
- At least 30 CSV files (30 days minimum)
- Date range identified for T002-T004

**Checkpoint**: Data discovery complete - ingestion can proceed

---

## Phase 2: Data Ingestion (CRITICAL PATH)

**Purpose**: Ingest ETH data into DuckDB using existing symbol-agnostic scripts

**Note**: T002, T003, T004 can run in parallel - they write to different tables

- [X] T002 [P] Ingest ETH aggTrades via scripts/ingest_aggtrades.py --symbol ETHUSDT
- [X] T003 [P] Start ETH Open Interest collector via scripts/ingest_oi.py --symbol ETHUSDT
- [X] T004 [P] Ingest ETH klines via scripts/ingest_klines_15m.py --symbol ETHUSDT

### T002 Commands (aggTrades - ~4-5 hours):
```bash
# Dry-run first
uv run python scripts/ingest_aggtrades.py \
  --symbol ETHUSDT \
  --start-date 2024-11-01 \
  --end-date 2024-11-30 \
  --data-dir /media/sam/3TB-WDC/binance-history-data-downloader/data \
  --db data/processed/liquidations.duckdb \
  --dry-run

# Production ingestion
uv run python scripts/ingest_aggtrades.py \
  --symbol ETHUSDT \
  --start-date 2024-11-01 \
  --end-date 2024-11-30 \
  --data-dir /media/sam/3TB-WDC/binance-history-data-downloader/data \
  --db data/processed/liquidations.duckdb \
  --throttle-ms 200
```

### T003 Commands (Open Interest - continuous):
```bash
# Run in tmux for persistence
tmux new -s eth-oi
uv run python scripts/ingest_oi.py --symbol ETHUSDT
# Detach: Ctrl+B, D
```

### T004 Commands (Klines - ~1-2 hours):
```bash
uv run python scripts/ingest_klines_15m.py \
  --symbol ETHUSDT \
  --start-date 2024-11-01 \
  --end-date 2024-11-30
```

**Note on 5m Klines**: The 15m script is the primary ingestion method. 5m klines (if needed) are either:
- Aggregated from 15m data at query time by the API
- Ingested separately if `scripts/ingest_klines_5m.py` exists (check with `ls scripts/ingest_klines_5m.py`)

**Success Criteria**:
- T002: >1M trades ingested, no date gaps
- T003: OI snapshots collecting every ~30s
- T004: ~2,880 klines (15m) for 30 days

**Checkpoint**: ETH data available in DuckDB - API testing can proceed

---

## Phase 3: API Validation (READ-ONLY)

**Purpose**: Verify existing endpoints work with ETHUSDT parameter

**Note**: T005, T006, T007 can run in parallel - they are read-only tests

- [X] T005 [P] Test /liquidations/heatmap-timeseries?symbol=ETHUSDT endpoint
- [X] T006 [P] Test /prices/klines?symbol=ETHUSDT endpoint
- [X] T007 [P] Test /data/date-range?symbol=ETHUSDT endpoint

### T005 Commands (Heatmap API):
```bash
# Test 1: 7-day window
curl -s "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&time_window=7d" | jq '.meta'

# Test 2: Custom date range
curl -s "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&start_time=2024-11-01T00:00:00&end_time=2024-11-30T23:59:59&interval=15m" | jq '.meta.total_snapshots'

# Test 3: Performance check
time curl -s "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&time_window=7d" > /dev/null
```

### T006 Commands (Klines API):
```bash
curl -s "http://localhost:8000/prices/klines?symbol=ETHUSDT&interval=15m&limit=100" | jq '{symbol, count, first_close: .data[0].close}'
```

### T007 Commands (Date Range API):
```bash
curl -s "http://localhost:8000/data/date-range?symbol=ETHUSDT" | jq
```

**Success Criteria**:
- All endpoints return 200 OK
- Response structure matches OpenAPI schema
- Price buckets in ETH range ($2000-$4000)
- Response time <2s uncached, <500ms cached

**Checkpoint**: API validation complete - frontend testing can proceed

---

## Phase 4: Frontend Validation

**Purpose**: Verify frontend symbol selector works with ETH

- [X] T008 Test frontend symbol selector at http://localhost:8000/frontend/coinglass_heatmap.html

**Manual Test Steps**:
1. Open `http://localhost:8000/frontend/coinglass_heatmap.html`
2. Select "ETHUSDT" from dropdown
3. Verify heatmap re-renders with ETH data
4. Verify price levels in ETH range ($2000-$4000)
5. Verify klines overlay shows ETH candlesticks
6. Switch back to BTC, then to ETH (test toggling)

**Success Criteria**:
- Symbol selector shows ETHUSDT option
- Heatmap renders correctly for ETH
- No JavaScript console errors
- Switching between BTC/ETH works seamlessly

**Checkpoint**: Frontend validation complete - Coinglass validation can proceed

---

## Phase 5: Coinglass Validation

**Purpose**: Validate ETH predictions against Coinglass ground truth

**Prerequisites**: N8N has captured ETH screenshots

- [X] T009 Run Coinglass validation via scripts/validate_vs_coinglass.py --symbol ETHUSDT
- [X] T010 Compare BTC vs ETH model performance metrics

### T009 Commands:
```bash
# ETH screenshots are in the same directory as BTC, filtered by filename pattern
# Screenshot path: /media/sam/1TB/N8N_dev/screenshots/
# ETH files match: coinglass_eth_*.png

# Run validation (use --screenshots for the validate_screenshots.py script)
uv run python scripts/validate_screenshots.py \
  --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
  --symbol ETHUSDT \
  --output data/validation/eth_validation_results.jsonl

# View results
cat data/validation/eth_validation_results.jsonl | jq

# Generate summary report
uv run python scripts/validate_screenshots.py \
  --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
  --symbol ETHUSDT \
  --summary
```

### T010 Analysis:
```bash
# Extract BTC baseline
btc_hit_rate=$(cat data/validation/price_level_comparison.jsonl | grep BTCUSDT | jq -r '.hit_rate' | awk '{sum+=$1; count++} END {print sum/count}')

# Extract ETH comparison
eth_hit_rate=$(cat data/validation/price_level_comparison.jsonl | grep ETHUSDT | jq -r '.hit_rate' | awk '{sum+=$1; count++} END {print sum/count}')

echo "BTC Hit Rate: $btc_hit_rate"
echo "ETH Hit Rate: $eth_hit_rate"
```

**Success Criteria**:
- T009: hit_rate > 0.60 (60%+ match threshold)
- T010: ETH metrics within ±10% of BTC (proves symbol-agnostic design)

**Checkpoint**: Model validation complete - documentation can proceed

---

## Phase 6: Testing & Documentation

**Purpose**: Run test suite and update documentation

### Testing

- [X] T013 Run pytest suite to verify no regressions via `uv run pytest -v`

### T013 Commands:
```bash
# Run full test suite
uv run pytest -v --tb=short

# Run multi-symbol specific tests (if they exist)
uv run pytest tests/integration/test_multi_symbol.py -v 2>/dev/null || echo "Multi-symbol tests not yet created"

# Run contract tests
uv run pytest tests/contract/ -v

# Expected: All tests pass, no regressions from ETH data addition
```

**Success Criteria**:
- All existing tests pass
- No regressions in BTC functionality
- Multi-symbol tests pass (if created)

### Documentation

- [X] T014 [P] Update API examples in src/liquidationheatmap/api/main.py to include ETHUSDT
- [X] T015 [P] Update README.md with ETH validation results

### T014 Changes:
Update endpoint docstrings to include ETHUSDT in examples:
```python
examples=["BTCUSDT", "ETHUSDT"]
```

### T015 Changes:
Add to README.md:
```markdown
## Supported Trading Pairs

| Symbol | Status | Coinglass Validation | Data Coverage |
|--------|--------|---------------------|---------------|
| **BTC/USDT** | Production | Hit rate: 0.75 | 2024-09-01 to present |
| **ETH/USDT** | Production | Hit rate: 0.XX | 2024-11-01 to present |
```

**Success Criteria**:
- API docs show ETHUSDT examples
- README documents ETH support with validation metrics

**Checkpoint**: Feature complete - ready for merge

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Data Discovery
  └─→ Phase 2: Data Ingestion (T002, T003, T004 in parallel)
        └─→ Phase 3: API Validation (T005, T006, T007 in parallel)
              └─→ Phase 4: Frontend Validation
                    └─→ Phase 5: Coinglass Validation (requires N8N screenshots)
                          └─→ Phase 6: Testing & Documentation
                                ├─→ T013 (pytest - sequential)
                                └─→ T014, T015 (docs - parallel after T013)
```

### Parallel Opportunities

**Phase 2** (Data Ingestion):
```bash
# Launch all ingestion tasks in parallel:
Task: "Ingest ETH aggTrades via scripts/ingest_aggtrades.py --symbol ETHUSDT"
Task: "Start ETH Open Interest collector via scripts/ingest_oi.py --symbol ETHUSDT"
Task: "Ingest ETH klines via scripts/ingest_klines_15m.py --symbol ETHUSDT"
```

**Phase 3** (API Validation):
```bash
# Launch all API tests in parallel:
Task: "Test /liquidations/heatmap-timeseries?symbol=ETHUSDT endpoint"
Task: "Test /prices/klines?symbol=ETHUSDT endpoint"
Task: "Test /data/date-range?symbol=ETHUSDT endpoint"
```

**Phase 6** (Testing & Documentation):
```bash
# T013 must complete first (sequential)
Task: "Run pytest suite to verify no regressions"

# After T013 passes, launch doc updates in parallel:
Task: "Update API examples in src/liquidationheatmap/api/main.py"
Task: "Update README.md with ETH validation results"
```

---

## Implementation Strategy

### MVP Approach

1. Complete Phase 1: Data Discovery (30 min)
2. Complete Phase 2: Data Ingestion (~5 hours, mostly wait time)
3. Complete Phase 3: API Validation (1 hour)
4. **STOP and VALIDATE**: ETH API is functional
5. Proceed to Phases 4-6 for full validation

### Rollback Plan

If issues arise, disable ETH in whitelist (1-line change):
```python
# src/liquidationheatmap/api/main.py line 230
SUPPORTED_SYMBOLS = {
    "BTCUSDT",
    # "ETHUSDT",  # Temporarily disabled
}
```

BTC pipeline continues unaffected (symbol-isolated data).

---

## Success Criteria Summary

| Phase | Critical Metric | Threshold |
|-------|-----------------|-----------|
| **Data Ingestion** | aggTrades count | >1M trades |
| **Data Ingestion** | OI snapshots | Collecting every ~30s |
| **Data Ingestion** | Klines count | ~2,880 for 30 days |
| **API Validation** | Endpoint responses | All 200 OK |
| **API Validation** | Response time | <2s uncached |
| **Coinglass Validation** | Hit rate | >0.60 |
| **Performance Comparison** | BTC vs ETH delta | <10% |

---

## Notes

- **Zero new code**: This feature reuses existing symbol-agnostic pipeline
- **Data isolation**: ETH data stored in same tables with `symbol='ETHUSDT'` filter
- **Rollback**: Instant via whitelist disable - no data migration needed
- **Validation dependency**: T009 requires N8N ETH screenshots at `/media/sam/1TB/N8N_dev/screenshots/`
- **Screenshot pattern**: ETH files match `coinglass_eth_*.png`
- **Total tasks**: 15 (T001-T015)
- **Time budget**: ~11-14 hours total (~2 days with wait time)
