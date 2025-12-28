# ETH/USDT Symbol Support Specification

**Feature**: Add ETH/USDT support to LiquidationHeatmap
**Priority**: P1 - HIGH (validation pre-requisite for multi-symbol expansion)
**Estimated Effort**: 2-3 days
**Code Reuse**: 100% (pure parameterization, ZERO new code)

---

## 1. Executive Summary

Enable ETH/USDT support by **parameterizing existing BTC pipeline** - no new algorithms, no new logic, just configuration changes and data ingestion.

**Key Principle**: If we need to write new code, we're doing it wrong. The entire pipeline was designed to be symbol-agnostic from day one.

---

## 2. Problem Statement

### Current State
- ✅ **BTC/USDT**: Fully operational with complete data pipeline
- ❌ **ETH/USDT**: Historical data available but not ingested
- ❌ **Other symbols**: SUPPORTED_SYMBOLS whitelist exists but only BTC tested
- ⚠️ **N8N**: Already captures Coinglass ETH screenshots but no validation pipeline

### Why ETH Now?
| Reason | Impact |
|--------|--------|
| **Validation requirement** | Coinglass comparison needs 2+ symbols for model confidence |
| **Second largest market** | ETH has ~40% the volume of BTC (material validation data) |
| **Production readiness** | Proves symbol-agnostic design works before full expansion |
| **Low risk** | 100% code reuse = minimal regression risk |

---

## 3. Existing Architecture (BTC Implementation)

### 3.1 Data Flow (Already Symbol-Agnostic)

```
Historical Data Sources
├── aggTrades: /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/*.csv
├── Open Interest: Binance API (real-time)
├── Klines: Binance API (real-time)
└── Funding Rate: Binance API (real-time)

↓ Ingestion Pipeline (symbol parameterized)
├── scripts/ingest_aggtrades.py --symbol ETHUSDT
├── scripts/ingest_oi.py --symbol ETHUSDT
├── scripts/ingest_klines_15m.py --symbol ETHUSDT
└── ingest_full_history_n8n.py --symbol ETHUSDT

↓ DuckDB Storage (symbol-indexed)
├── aggtrades_history (WHERE symbol = 'ETHUSDT')
├── open_interest_history (WHERE symbol = 'ETHUSDT')
└── klines_15m_history (WHERE symbol = 'ETHUSDT')

↓ API Endpoints (symbol query param)
└── GET /liquidations/heatmap-timeseries?symbol=ETHUSDT

↓ Frontend (symbol selector)
└── coinglass_heatmap.html?symbol=ETHUSDT
```

**OBSERVATION**: Every layer already accepts `symbol` parameter! No architectural changes needed.

### 3.2 Whitelist Validation

**File**: `src/liquidationheatmap/api/main.py` (lines 229-241)

```python
SUPPORTED_SYMBOLS = {
    "BTCUSDT",
    "ETHUSDT",    # ← Already whitelisted! Just needs data
    "BNBUSDT",
    "ADAUSDT",
    # ... (10 total symbols)
}
```

**Status**: ETH already in whitelist, no code change required.

---

## 4. Implementation Plan (100% Data Operations)

### Phase 1: Data Ingestion (CRITICAL)

#### T001: Verify ETH Historical Data Availability
**Objective**: Confirm data exists and identify date range

```bash
# Check aggTrades files
ls -lh /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/

# Expected output: ETHUSDT-aggTrades-YYYY-MM-DD.csv files
# Determine: start_date, end_date, total file count
```

**Success Criteria**: Minimum 30 days of continuous data for meaningful validation

---

#### T002: Ingest ETH aggTrades (Historical Trades)
**Script**: `scripts/ingest_aggtrades.py` (already symbol-agnostic)

```bash
# Dry-run first (validation only)
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

**Validation Query**:
```sql
SELECT
  COUNT(*) as total_trades,
  MIN(timestamp) as start_date,
  MAX(timestamp) as end_date,
  SUM(gross_value) as total_volume_usd
FROM aggtrades_history
WHERE symbol = 'ETHUSDT';
```

**Success Criteria**:
- Total trades > 1M (for 30-day period)
- No date gaps
- Total volume correlates with Binance public metrics

---

#### T003: Ingest ETH Open Interest (Real-Time)
**Script**: `scripts/ingest_oi.py`

```bash
# Start real-time OI collector for ETH
uv run python scripts/ingest_oi.py --symbol ETHUSDT
```

**Validation Query**:
```sql
SELECT
  COUNT(*) as snapshots,
  MIN(timestamp) as start,
  MAX(timestamp) as end,
  AVG(open_interest_value) as avg_oi_usd
FROM open_interest_history
WHERE symbol = 'ETHUSDT'
AND timestamp > NOW() - INTERVAL '24 hours';
```

**Success Criteria**:
- Snapshots updated every 30s (2,880 per day)
- OI values in reasonable range ($500M - $5B for ETH)

---

#### T004: Ingest ETH Klines (5m and 15m intervals)
**Script**: `scripts/ingest_klines_15m.py`

```bash
# Ingest klines for date range matching aggTrades
uv run python scripts/ingest_klines_15m.py \
  --symbol ETHUSDT \
  --start-date 2024-11-01 \
  --end-date 2024-11-30
```

**Validation Query**:
```sql
-- Check 15m klines
SELECT COUNT(*) as candles
FROM klines_15m_history
WHERE symbol = 'ETHUSDT';

-- Check 5m klines (if separate table)
SELECT COUNT(*) as candles
FROM klines_5m_history
WHERE symbol = 'ETHUSDT';
```

**Success Criteria**:
- 15m: ~2,880 candles per 30 days (4 per hour × 24 × 30)
- 5m: ~8,640 candles per 30 days (12 per hour × 24 × 30)

---

### Phase 2: API Validation (READ-ONLY Testing)

#### T005: Test `/liquidations/heatmap-timeseries` with ETH
**Endpoint**: `GET /liquidations/heatmap-timeseries?symbol=ETHUSDT`

**Test Cases**:

```bash
# Test 1: Default time window
curl "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&time_window=7d"

# Test 2: Custom date range
curl "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&start_time=2024-11-01T00:00:00&end_time=2024-11-30T23:59:59&interval=15m"

# Test 3: Extended timeframes
curl "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&time_window=30d&interval=4h"
```

**Validation Checklist**:
- [ ] Response returns 200 OK
- [ ] `meta.symbol` = "ETHUSDT"
- [ ] `meta.total_snapshots` > 0
- [ ] `data[].levels` contains price buckets near current ETH price ($2000-$4000 range)
- [ ] `total_long_volume` + `total_short_volume` > 0
- [ ] Response time < 500ms (cached) or < 2s (uncached)

---

#### T006: Test `/prices/klines` with ETH
**Endpoint**: `GET /prices/klines?symbol=ETHUSDT&interval=15m&limit=100`

**Test Cases**:

```bash
# Test 1: Recent klines
curl "http://localhost:8000/prices/klines?symbol=ETHUSDT&interval=15m&limit=100"

# Test 2: Historical range
curl "http://localhost:8000/prices/klines?symbol=ETHUSDT&interval=1h&start_time=2024-11-01T00:00:00&end_time=2024-11-30T23:59:59"
```

**Validation**:
- [ ] Returns OHLC data
- [ ] `timestamp` values sequential
- [ ] `close` prices in reasonable range ($2000-$4000)
- [ ] `volume` > 0

---

#### T007: Test `/data/date-range` with ETH
**Endpoint**: `GET /data/date-range?symbol=ETHUSDT`

```bash
curl "http://localhost:8000/data/date-range?symbol=ETHUSDT"
```

**Expected Response**:
```json
{
  "symbol": "ETHUSDT",
  "start_date": "2024-11-01T00:00:00",
  "end_date": "2024-11-30T23:59:59"
}
```

---

### Phase 3: Frontend Integration

#### T008: Add Symbol Selector to Frontend
**File**: `frontend/coinglass_heatmap.html`

**Implementation**: Update existing symbol dropdown (already supports ETHUSDT in whitelist)

**Test**:
1. Open `http://localhost:8000/frontend/coinglass_heatmap.html`
2. Select "ETHUSDT" from dropdown
3. Verify heatmap re-renders with ETH data
4. Verify price overlay shows ETH klines

---

### Phase 4: Validation Pipeline (Coinglass Comparison)

#### T009: Run Coinglass Validation for ETH
**Script**: `scripts/validate_vs_coinglass.py`

```bash
# Run validation with N8N-captured screenshots
uv run python scripts/validate_vs_coinglass.py \
  --symbol ETHUSDT \
  --screenshot-dir /path/to/n8n/screenshots/ETH

# Expected output:
# - hit_rate: 0.60-0.85 (60-85% of Coinglass liquidations match our zones)
# - price_level_overlap: 0.70+ (Jaccard similarity)
```

**Success Criteria**:
- [ ] hit_rate > 0.60 (same threshold as BTC)
- [ ] No crashes or data quality errors
- [ ] Results consistent across multiple time windows

---

#### T010: Compare BTC vs ETH Model Performance
**Objective**: Verify model is truly symbol-agnostic

**Metrics to Compare**:

| Metric | BTC | ETH | Delta |
|--------|-----|-----|-------|
| Hit Rate | 0.75 | ? | Should be ±5% |
| Price Level Overlap | 0.72 | ? | Should be ±5% |
| API Response Time | 350ms | ? | Should be ±10% |
| Computation Time | 1.2s | ? | Should be ±10% |

**Success Criteria**: No metric differs by >10% between symbols (proves parameterization works)

---

### Phase 5: Documentation & Deployment

#### T011: Update API Documentation
**File**: OpenAPI spec (auto-generated by FastAPI)

**Changes**:
- Update `/liquidations/heatmap-timeseries` example to include ETHUSDT
- Add note: "Supports BTCUSDT, ETHUSDT, and 8 other whitelisted symbols"

---

#### T012: Update README
**File**: `README.md`

**Additions**:
```markdown
## Supported Trading Pairs

- **BTC/USDT**: Fully validated (Coinglass correlation: 0.75)
- **ETH/USDT**: Fully validated (Coinglass correlation: TBD)
- **Others**: Whitelisted but not yet validated (BNB, ADA, DOGE, XRP, SOL, DOT, MATIC, LINK)
```

---

## 5. Testing Strategy

### 5.1 Data Integrity Tests

**Test**: `tests/integration/test_multi_symbol.py::test_eth_data_completeness`

```python
def test_eth_data_completeness():
    """Verify ETH data ingestion completed successfully."""
    db = DuckDBService(read_only=True)

    # Check aggTrades
    result = db.conn.execute("""
        SELECT COUNT(*) FROM aggtrades_history WHERE symbol = 'ETHUSDT'
    """).fetchone()
    assert result[0] > 1_000_000, "Insufficient aggTrades data"

    # Check Open Interest
    result = db.conn.execute("""
        SELECT COUNT(*) FROM open_interest_history WHERE symbol = 'ETHUSDT'
    """).fetchone()
    assert result[0] > 2_000, "Insufficient OI snapshots"

    # Check Klines
    result = db.conn.execute("""
        SELECT COUNT(*) FROM klines_15m_history WHERE symbol = 'ETHUSDT'
    """).fetchone()
    assert result[0] > 2_000, "Insufficient klines"
```

---

### 5.2 API Contract Tests

**Test**: `tests/contract/test_heatmap_timeseries.py::test_eth_endpoint`

```python
@pytest.mark.parametrize("symbol", ["BTCUSDT", "ETHUSDT"])
def test_heatmap_timeseries_multi_symbol(symbol):
    """Verify heatmap endpoint works for both BTC and ETH."""
    response = client.get(
        f"/liquidations/heatmap-timeseries",
        params={"symbol": symbol, "time_window": "7d"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["symbol"] == symbol
    assert len(data["data"]) > 0
```

---

### 5.3 Performance Tests

**Test**: `tests/performance/test_api_performance.py::test_eth_response_time`

```python
def test_eth_response_time():
    """Verify ETH queries are as fast as BTC (proves no symbol-specific bottlenecks)."""
    btc_time = timeit.timeit(
        lambda: client.get("/liquidations/heatmap-timeseries?symbol=BTCUSDT&time_window=7d"),
        number=10
    )

    eth_time = timeit.timeit(
        lambda: client.get("/liquidations/heatmap-timeseries?symbol=ETHUSDT&time_window=7d"),
        number=10
    )

    # ETH should be within 10% of BTC speed
    assert abs(eth_time - btc_time) / btc_time < 0.10
```

---

## 6. Success Criteria

### P0 - Must Have (Blocking PR Merge)
- [ ] **T001-T004**: All ETH data ingested successfully
- [ ] **T005-T007**: All API endpoints return valid data for ETHUSDT
- [ ] **T009**: Coinglass validation hit_rate > 0.60
- [ ] **All tests pass**: `uv run pytest -v`

### P1 - Should Have (Nice to Have)
- [ ] **T010**: BTC vs ETH performance delta < 10%
- [ ] **T011-T012**: Documentation updated
- [ ] **T008**: Frontend symbol selector functional

### P2 - Nice to Have (Future Work)
- [ ] Real-time ETH OI streaming running 24/7
- [ ] Automated daily validation runs (cron job)

---

## 7. Rollback Plan

**If ETH data shows unexpected behavior**:

1. **Disable ETH in whitelist** (1-line change):
   ```python
   SUPPORTED_SYMBOLS = {
       "BTCUSDT",
       # "ETHUSDT",  # Temporarily disabled
   }
   ```

2. **Truncate ETH data** (if needed):
   ```sql
   DELETE FROM aggtrades_history WHERE symbol = 'ETHUSDT';
   DELETE FROM open_interest_history WHERE symbol = 'ETHUSDT';
   DELETE FROM klines_15m_history WHERE symbol = 'ETHUSDT';
   ```

3. **BTC pipeline continues unaffected** (data isolated by symbol column)

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **ETH data quality issues** | Low | Medium | Validate date ranges before ingestion |
| **Performance degradation** | Very Low | Low | Same queries, just different WHERE clause |
| **API regression** | Very Low | Medium | Comprehensive test coverage |
| **Frontend bugs** | Low | Low | Symbol selector already parameterized |

**Overall Risk**: LOW (this is 100% parameterization, not new features)

---

## 9. Timeline Estimate

| Phase | Tasks | Estimated Time | Dependencies |
|-------|-------|---------------|--------------|
| **Phase 1** | Data Ingestion (T001-T004) | 4-6 hours | ETH data availability |
| **Phase 2** | API Testing (T005-T007) | 2 hours | Phase 1 complete |
| **Phase 3** | Frontend (T008) | 1 hour | Phase 2 complete |
| **Phase 4** | Validation (T009-T010) | 3-4 hours | N8N screenshots available |
| **Phase 5** | Docs (T011-T012) | 1 hour | All phases complete |
| **TOTAL** | - | **11-14 hours** (~2 days) | - |

---

## 10. References

### Existing BTC Implementation
- **API Endpoint**: `src/liquidationheatmap/api/main.py::get_heatmap_timeseries()`
- **Ingestion Scripts**: `scripts/ingest_aggtrades.py`, `scripts/ingest_oi.py`, `scripts/ingest_klines_15m.py`
- **Time-Evolving Model**: `src/liquidationheatmap/models/time_evolving_heatmap.py`
- **Validation Script**: `scripts/validate_vs_coinglass.py`

### Data Paths
- **ETH aggTrades**: `/media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/`
- **Database**: `data/processed/liquidations.duckdb` (235GB DuckDB file)

### Coinglass References
- **BTC Heatmap**: https://www.coinglass.com/pro/futures/LiquidationHeatMap?symbol=BTC
- **ETH Heatmap**: https://www.coinglass.com/pro/futures/LiquidationHeatMap?symbol=ETH
- **N8N Screenshots**: Stored by existing workflow (ready for validation)

---

## Appendix A: Data Volume Estimates

### ETH Historical Data (30-day estimate)
- **aggTrades**: ~2-3M rows (vs 5-7M for BTC)
- **Open Interest**: ~2,880 snapshots per day × 30 = ~86,400 rows
- **Klines (15m)**: ~2,880 candles per 30 days
- **Klines (5m)**: ~8,640 candles per 30 days

**Total DB Growth**: +500MB-1GB (negligible vs 235GB current size)

### API Response Sizes
- **Heatmap timeseries (7d, 15m)**: ~20-30KB JSON (same as BTC)
- **Klines (100 candles)**: ~5KB JSON

---

## Appendix B: Symbol-Agnostic Design Verification

**Grep Audit Results**:

```bash
# All scripts accept --symbol parameter
grep -r "argparse.*symbol" scripts/
# Result: ingest_aggtrades.py, ingest_oi.py, ingest_klines_15m.py, validate_vs_coinglass.py

# All API queries filter by symbol
grep -r "WHERE symbol =" src/liquidationheatmap/
# Result: db_service.py, api/main.py (all queries parameterized)

# Whitelist validation
grep "SUPPORTED_SYMBOLS" src/liquidationheatmap/api/main.py
# Result: Lines 229-241, ETHUSDT already present
```

**Conclusion**: Architecture is truly symbol-agnostic. No code changes required.
