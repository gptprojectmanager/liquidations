# ETH/USDT Symbol Support - Implementation Tasks

**Feature**: Add ETH/USDT support via 100% code reuse
**Priority**: P1 - HIGH
**Estimated Effort**: 11-14 hours (2 days)

---

## Task Dependency Graph

```
T001 (Data Discovery)
  ↓
T002 (aggTrades Ingestion) ─┬─→ T005 (API Test: Heatmap)
                            │
T003 (OI Ingestion) ────────┼─→ T006 (API Test: Klines)
                            │
T004 (Klines Ingestion) ────┴─→ T007 (API Test: Date Range)
                                  ↓
                                T008 (Frontend Integration)
                                  ↓
                                T009 (Coinglass Validation)
                                  ↓
                                T010 (BTC vs ETH Comparison)
                                  ↓
                                T011 (Update Docs)
                                  ↓
                                T012 (Update README)
```

---

## Phase 1: Data Ingestion (CRITICAL PATH)

### T001: Verify ETH Historical Data Availability
**Priority**: P0 - CRITICAL
**Estimated Time**: 30 minutes
**Dependencies**: None

**Objective**: Confirm ETH data exists and identify ingestion scope

**Steps**:
1. Check data directory structure:
   ```bash
   ls -lh /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/
   ```

2. Count available files:
   ```bash
   find /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/ \
     -name "ETHUSDT-aggTrades-*.csv" | wc -l
   ```

3. Identify date range:
   ```bash
   ls /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/ \
     | head -1  # First file (start date)
   ls /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/ \
     | tail -1  # Last file (end date)
   ```

4. Sample file to verify format:
   ```bash
   head -5 /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/ETHUSDT-aggTrades-2024-11-01.csv
   ```

**Success Criteria**:
- [ ] Directory exists
- [ ] At least 30 CSV files found (30 days minimum)
- [ ] Date range identified (start_date, end_date)
- [ ] CSV format matches BTC structure (agg_trade_id, price, quantity, timestamp, is_buyer_maker)

**Deliverable**: Document start_date and end_date for T002

---

### T002: Ingest ETH aggTrades (Historical Trades)
**Priority**: P0 - CRITICAL
**Estimated Time**: 4-5 hours (mostly wait time for streaming ingestion)
**Dependencies**: T001

**Objective**: Load ETH trade history into DuckDB

**Implementation**:

1. **Dry-run validation** (fast, no data written):
   ```bash
   cd /media/sam/1TB/LiquidationHeatmap
   uv run python scripts/ingest_aggtrades.py \
     --symbol ETHUSDT \
     --start-date 2024-11-01 \
     --end-date 2024-11-30 \
     --data-dir /media/sam/3TB-WDC/binance-history-data-downloader/data \
     --db data/processed/liquidations.duckdb \
     --dry-run
   ```

   **Expected Output**: File count, estimated row count, no errors

2. **Production ingestion** (streaming, OOM-safe):
   ```bash
   uv run python scripts/ingest_aggtrades.py \
     --symbol ETHUSDT \
     --start-date 2024-11-01 \
     --end-date 2024-11-30 \
     --data-dir /media/sam/3TB-WDC/binance-history-data-downloader/data \
     --db data/processed/liquidations.duckdb \
     --throttle-ms 200
   ```

   **Expected Duration**: ~2-4 hours for 30 days (depends on I/O speed)

3. **Validation query**:
   ```bash
   uv run python -c "
   import duckdb
   conn = duckdb.connect('data/processed/liquidations.duckdb', read_only=True)
   result = conn.execute('''
     SELECT
       COUNT(*) as total_trades,
       MIN(timestamp) as start_date,
       MAX(timestamp) as end_date,
       SUM(gross_value) as total_volume_usd,
       COUNT(DISTINCT DATE(timestamp)) as days_covered
     FROM aggtrades_history
     WHERE symbol = 'ETHUSDT'
   ''').fetchone()
   print(f'Trades: {result[0]:,}')
   print(f'Date range: {result[1]} to {result[2]}')
   print(f'Volume: ${result[3]:,.2f}')
   print(f'Days: {result[4]}')
   conn.close()
   "
   ```

**Success Criteria**:
- [ ] Total trades > 1M (for 30-day period)
- [ ] Date range matches input (no gaps)
- [ ] Total volume > $1B (sanity check for ETH)
- [ ] Days covered = 30 (continuous data)
- [ ] No duplicate agg_trade_id (PRIMARY KEY constraint enforced)

**Rollback**: If ingestion fails, truncate and retry:
```sql
DELETE FROM aggtrades_history WHERE symbol = 'ETHUSDT';
```

---

### T003: Ingest ETH Open Interest (Real-Time)
**Priority**: P0 - CRITICAL
**Estimated Time**: 1 hour (setup) + 24h monitoring
**Dependencies**: T001

**Objective**: Start collecting real-time ETH Open Interest snapshots

**Implementation**:

1. **Start OI collector** (runs continuously):
   ```bash
   cd /media/sam/1TB/LiquidationHeatmap
   uv run python scripts/ingest_oi.py --symbol ETHUSDT
   ```

   **Process Management**: Run in tmux/screen for persistence:
   ```bash
   tmux new -s eth-oi
   uv run python scripts/ingest_oi.py --symbol ETHUSDT
   # Detach: Ctrl+B, D
   ```

2. **Verify after 1 hour**:
   ```bash
   uv run python -c "
   import duckdb
   from datetime import datetime, timedelta
   conn = duckdb.connect('data/processed/liquidations.duckdb', read_only=True)
   result = conn.execute('''
     SELECT
       COUNT(*) as snapshots,
       MIN(timestamp) as start,
       MAX(timestamp) as end,
       AVG(open_interest_value) as avg_oi_usd,
       AVG(open_interest_value) / AVG(open_interest_contracts) as avg_price
     FROM open_interest_history
     WHERE symbol = 'ETHUSDT'
     AND timestamp > ?
   ''', [datetime.now() - timedelta(hours=1)]).fetchone()
   print(f'Snapshots (1h): {result[0]}')
   print(f'Time range: {result[1]} to {result[2]}')
   print(f'Avg OI: ${result[3]:,.2f}')
   print(f'Avg ETH price: ${result[4]:,.2f}')
   conn.close()
   "
   ```

**Success Criteria**:
- [ ] Snapshots collected every ~30s (120 per hour)
- [ ] OI values in range: $500M - $5B (reasonable for ETH)
- [ ] Avg price matches spot price (~$3000-$4000 as of Dec 2024)
- [ ] No errors in logs

**Monitoring**:
```bash
# Check OI collector logs
tail -f /path/to/logs/ingest_oi.log

# Re-attach to tmux session
tmux attach -t eth-oi
```

---

### T004: Ingest ETH Klines (5m and 15m intervals)
**Priority**: P0 - CRITICAL
**Estimated Time**: 2 hours
**Dependencies**: T001

**Objective**: Load ETH price candles for heatmap overlays

**Implementation**:

1. **Ingest 15m klines** (primary interval):
   ```bash
   cd /media/sam/1TB/LiquidationHeatmap
   uv run python scripts/ingest_klines_15m.py \
     --symbol ETHUSDT \
     --start-date 2024-11-01 \
     --end-date 2024-11-30
   ```

   **Expected Duration**: ~30-60 minutes

2. **Ingest 5m klines** (for 30m aggregation):
   ```bash
   # Check if separate script exists
   if [ -f scripts/ingest_klines_5m.py ]; then
     uv run python scripts/ingest_klines_5m.py \
       --symbol ETHUSDT \
       --start-date 2024-11-01 \
       --end-date 2024-11-30
   else
     echo "5m ingestion may be handled by 15m script"
   fi
   ```

3. **Validation query**:
   ```bash
   uv run python -c "
   import duckdb
   conn = duckdb.connect('data/processed/liquidations.duckdb', read_only=True)

   # Check 15m klines
   result_15m = conn.execute('''
     SELECT
       COUNT(*) as candles,
       MIN(open_time) as start,
       MAX(open_time) as end,
       AVG(CAST(close AS DOUBLE)) as avg_price
     FROM klines_15m_history
     WHERE symbol = 'ETHUSDT'
   ''').fetchone()
   print(f'15m Klines: {result_15m[0]:,}')
   print(f'Time range: {result_15m[1]} to {result_15m[2]}')
   print(f'Avg close price: ${result_15m[3]:,.2f}')

   # Check 5m klines (if separate table)
   try:
     result_5m = conn.execute('''
       SELECT COUNT(*) FROM klines_5m_history WHERE symbol = 'ETHUSDT'
     ''').fetchone()
     print(f'5m Klines: {result_5m[0]:,}')
   except:
     print('5m klines not in separate table (may be aggregated from 15m)')

   conn.close()
   "
   ```

**Success Criteria**:
- [ ] 15m klines: ~2,880 candles for 30 days (4 per hour × 24 × 30)
- [ ] 5m klines: ~8,640 candles for 30 days (12 per hour × 24 × 30) OR confirmed aggregated from 15m
- [ ] No gaps in time series
- [ ] Avg price correlates with known ETH price range

---

## Phase 2: API Validation (READ-ONLY Testing)

### T005: Test `/liquidations/heatmap-timeseries` with ETH
**Priority**: P0 - CRITICAL
**Estimated Time**: 1 hour
**Dependencies**: T002, T003, T004

**Objective**: Verify core heatmap endpoint works for ETHUSDT

**Test Cases**:

1. **Test 1: Default time window (7d)**
   ```bash
   curl -s "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&time_window=7d" \
     | jq '.meta'
   ```

   **Expected**:
   ```json
   {
     "symbol": "ETHUSDT",
     "total_snapshots": 672,  // ~7d * 96 (15m snapshots)
     "interval": "1h",
     "total_long_volume": >0,
     "total_short_volume": >0
   }
   ```

2. **Test 2: Custom date range**
   ```bash
   curl -s "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&start_time=2024-11-01T00:00:00&end_time=2024-11-30T23:59:59&interval=15m" \
     | jq '{symbol: .meta.symbol, snapshots: .meta.total_snapshots, price_range: .meta.price_range}'
   ```

   **Expected**:
   - `snapshots`: ~2,880 (30d × 96)
   - `price_range.min`: ~$2500-$3000
   - `price_range.max`: ~$3500-$4500

3. **Test 3: Extended timeframe (30d)**
   ```bash
   curl -s "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&time_window=30d" \
     | jq '.data[0].levels[0:3]'
   ```

   **Expected**: Array of `HeatmapLevel` objects with:
   - `price`: Float values near ETH price range
   - `long_density`: >= 0
   - `short_density`: >= 0

4. **Performance test**:
   ```bash
   time curl -s "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&time_window=7d" > /dev/null
   ```

   **Expected**: < 2s (uncached), < 500ms (cached)

**Success Criteria**:
- [ ] All 3 test cases return 200 OK
- [ ] Response structure matches OpenAPI schema
- [ ] Price buckets in reasonable ETH range ($2000-$4000)
- [ ] No crashes or 500 errors
- [ ] Response time acceptable

---

### T006: Test `/prices/klines` with ETH
**Priority**: P0 - CRITICAL
**Estimated Time**: 30 minutes
**Dependencies**: T004

**Objective**: Verify klines endpoint returns ETH price data

**Test Cases**:

1. **Test 1: Recent 100 candles (15m)**
   ```bash
   curl -s "http://localhost:8000/prices/klines?symbol=ETHUSDT&interval=15m&limit=100" \
     | jq '{symbol, interval, count, first_close: .data[0].close, last_close: .data[-1].close}'
   ```

   **Expected**:
   - `count`: 100
   - `first_close` and `last_close`: In ETH price range

2. **Test 2: Historical range query**
   ```bash
   curl -s "http://localhost:8000/prices/klines?symbol=ETHUSDT&interval=1h&start_time=2024-11-01T00:00:00&end_time=2024-11-30T23:59:59" \
     | jq '{count: .count, symbol, interval}'
   ```

   **Expected**:
   - `count`: ~720 (30d × 24h)

3. **Test 3: Aggregated intervals**
   ```bash
   # Test 4h aggregation (from 15m base)
   curl -s "http://localhost:8000/prices/klines?symbol=ETHUSDT&interval=4h&limit=50" \
     | jq '.data[0]'
   ```

   **Expected**: Valid OHLC data with `volume > 0`

**Success Criteria**:
- [ ] All intervals return data: 5m, 15m, 30m, 1h, 4h
- [ ] Timestamps are sequential
- [ ] OHLC data valid (high >= low, close between high/low)
- [ ] Volume > 0 for all candles

---

### T007: Test `/data/date-range` with ETH
**Priority**: P1 - HIGH
**Estimated Time**: 15 minutes
**Dependencies**: T003

**Objective**: Verify date range endpoint reports ETH data availability

**Test**:
```bash
curl -s "http://localhost:8000/data/date-range?symbol=ETHUSDT" | jq
```

**Expected Response**:
```json
{
  "symbol": "ETHUSDT",
  "start_date": "2024-11-01T00:00:00",
  "end_date": "2024-11-30T23:59:59"
}
```

**Success Criteria**:
- [ ] Returns 200 OK
- [ ] Date range matches ingested data
- [ ] No 404 errors

---

## Phase 3: Frontend Integration

### T008: Add Symbol Selector to Frontend
**Priority**: P1 - HIGH
**Estimated Time**: 1 hour
**Dependencies**: T005, T006

**Objective**: Enable ETH selection in Coinglass heatmap dashboard

**Implementation**:

**File**: `frontend/coinglass_heatmap.html`

**Changes**:
1. Verify symbol dropdown exists (should already be there from SUPPORTED_SYMBOLS whitelist)
2. If not, add dropdown HTML:
   ```html
   <select id="symbolSelect">
     <option value="BTCUSDT">BTC/USDT</option>
     <option value="ETHUSDT">ETH/USDT</option>
   </select>
   ```

3. Add event listener to re-fetch data on symbol change:
   ```javascript
   document.getElementById('symbolSelect').addEventListener('change', (e) => {
     const newSymbol = e.target.value;
     fetchHeatmapData(newSymbol, currentTimeWindow);
   });
   ```

**Manual Testing**:
1. Open `http://localhost:8000/frontend/coinglass_heatmap.html`
2. Select "ETHUSDT" from dropdown
3. Verify:
   - [ ] Heatmap re-renders
   - [ ] Price levels update to ETH range ($2000-$4000)
   - [ ] Klines overlay shows ETH candlesticks
   - [ ] No console errors

**Success Criteria**:
- [ ] Symbol selector functional
- [ ] ETH heatmap visually distinct from BTC
- [ ] No JavaScript errors
- [ ] Switching between BTC/ETH works seamlessly

---

## Phase 4: Validation Pipeline

### T009: Run Coinglass Validation for ETH
**Priority**: P0 - CRITICAL
**Estimated Time**: 2 hours
**Dependencies**: T005, N8N screenshot availability

**Objective**: Validate ETH predictions against Coinglass ground truth

**Prerequisites**:
- N8N workflow has captured ETH screenshots (confirm with user)
- Screenshots stored in known directory

**Implementation**:

1. **Locate screenshots**:
   ```bash
   # Confirm screenshot location with user
   ls -lh /path/to/n8n/screenshots/ETH/  # Adjust path
   ```

2. **Run validation script**:
   ```bash
   cd /media/sam/1TB/LiquidationHeatmap
   uv run python scripts/validate_vs_coinglass.py \
     --symbol ETHUSDT \
     --screenshot-dir /path/to/n8n/screenshots/ETH
   ```

   **Expected Duration**: ~10-20 minutes per screenshot

3. **Analyze results**:
   ```bash
   # View validation results
   cat data/validation/price_level_comparison.jsonl | grep ETHUSDT | jq
   ```

4. **Generate summary report**:
   ```bash
   uv run python scripts/validate_vs_coinglass.py --summary
   ```

**Success Criteria**:
- [ ] hit_rate > 0.60 (60%+ of Coinglass liquidations match our zones)
- [ ] price_level_overlap > 0.70 (Jaccard similarity)
- [ ] No data quality errors
- [ ] Results saved to `data/validation/price_level_comparison.jsonl`

**Acceptance**:
- If hit_rate < 0.60: Investigate (may be data quality issue, not model failure)
- If hit_rate >= 0.60: Pass (consistent with BTC performance)

---

### T010: Compare BTC vs ETH Model Performance
**Priority**: P1 - HIGH
**Estimated Time**: 1 hour
**Dependencies**: T009

**Objective**: Prove model is truly symbol-agnostic

**Metrics to Extract**:

```bash
# BTC baseline
btc_hit_rate=$(cat data/validation/price_level_comparison.jsonl | grep BTCUSDT | jq -r '.hit_rate' | awk '{sum+=$1; count++} END {print sum/count}')

# ETH comparison
eth_hit_rate=$(cat data/validation/price_level_comparison.jsonl | grep ETHUSDT | jq -r '.hit_rate' | awk '{sum+=$1; count++} END {print sum/count}')

echo "BTC Hit Rate: $btc_hit_rate"
echo "ETH Hit Rate: $eth_hit_rate"
echo "Delta: $(echo "$eth_hit_rate - $btc_hit_rate" | bc)"
```

**Comparison Table**:

| Metric | BTC | ETH | Delta | Pass? |
|--------|-----|-----|-------|-------|
| Hit Rate | 0.75 | ? | ? | ±10% |
| Price Level Overlap | 0.72 | ? | ? | ±10% |
| API Response Time | 350ms | ? | ? | ±10% |
| Computation Time | 1.2s | ? | ? | ±10% |

**Success Criteria**:
- [ ] No metric differs by >10% between BTC and ETH
- [ ] ETH performance within expected range (0.60-0.85 hit rate)
- [ ] Proves parameterization works (no symbol-specific tuning needed)

---

## Phase 5: Documentation

### T011: Update API Documentation
**Priority**: P1 - HIGH
**Estimated Time**: 30 minutes
**Dependencies**: T010

**Objective**: Document ETHUSDT support in OpenAPI spec

**File**: Auto-generated by FastAPI, but update examples in `src/liquidationheatmap/api/main.py`

**Changes**:

1. Update endpoint docstrings:
   ```python
   @app.get("/liquidations/heatmap-timeseries")
   async def get_heatmap_timeseries(
       symbol: str = Query(
           ...,
           description="Trading pair symbol (e.g., BTCUSDT, ETHUSDT)",
           examples=["BTCUSDT", "ETHUSDT"],  # ← Add ETHUSDT
       ),
       ...
   ):
   ```

2. Add note in API description:
   ```python
   app = FastAPI(
       title="Liquidation Heatmap API",
       description="""
       Calculate and visualize cryptocurrency liquidation levels.

       **Supported Symbols**: BTCUSDT (validated), ETHUSDT (validated),
       and 8 others (whitelisted but not yet validated).
       """,
       version="0.2.0",  # Bump version
   )
   ```

**Verification**:
```bash
# Start API server
uv run uvicorn src.liquidationheatmap.api.main:app --reload

# Check OpenAPI docs
curl http://localhost:8000/docs
```

**Success Criteria**:
- [ ] ETHUSDT appears in examples
- [ ] API docs show supported symbols
- [ ] No breaking changes to existing endpoints

---

### T012: Update README
**Priority**: P1 - HIGH
**Estimated Time**: 30 minutes
**Dependencies**: T009, T010

**Objective**: Document ETH support in public README

**File**: `README.md`

**Additions**:

1. **Supported Trading Pairs section**:
   ```markdown
   ## Supported Trading Pairs

   | Symbol | Status | Coinglass Validation | Data Coverage |
   |--------|--------|---------------------|---------------|
   | **BTC/USDT** | ✅ Production | Hit rate: 0.75 | 2024-09-01 to present |
   | **ETH/USDT** | ✅ Production | Hit rate: 0.XX | 2024-11-01 to present |
   | BNB/USDT | ⚠️ Whitelisted | Not validated | - |
   | ADA/USDT | ⚠️ Whitelisted | Not validated | - |
   | ... | ... | ... | ... |

   **Legend**:
   - ✅ Production: Fully validated with >60% hit rate against Coinglass
   - ⚠️ Whitelisted: API accepts symbol but no validation yet
   ```

2. **Update Quickstart**:
   ```markdown
   ## Quickstart

   ```bash
   # Fetch BTC liquidation heatmap
   curl "http://localhost:8000/liquidations/heatmap-timeseries?symbol=BTCUSDT&time_window=7d"

   # Fetch ETH liquidation heatmap
   curl "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&time_window=7d"
   ```
   ```

3. **Add ETH ingestion to Setup section**:
   ```markdown
   ### Data Ingestion

   **BTC/USDT** (primary):
   ```bash
   uv run python scripts/ingest_aggtrades.py --symbol BTCUSDT ...
   ```

   **ETH/USDT**:
   ```bash
   uv run python scripts/ingest_aggtrades.py --symbol ETHUSDT ...
   ```
   ```

**Success Criteria**:
- [ ] README updated with ETH info
- [ ] Examples include both BTC and ETH
- [ ] Validation results documented

---

## Testing Checklist

### Pre-Merge Requirements

**Unit Tests** (existing tests should pass):
```bash
uv run pytest tests/unit/ -v
```

**Integration Tests** (add ETH-specific tests):
```bash
uv run pytest tests/integration/test_multi_symbol.py -v
```

**Contract Tests** (verify API contracts):
```bash
uv run pytest tests/contract/test_heatmap_timeseries.py -v
```

**Performance Tests** (regression check):
```bash
uv run pytest tests/performance/test_api_performance.py -v
```

**All Tests**:
```bash
uv run pytest -v --tb=short
```

---

## Rollback Procedure

**If ETH support needs to be disabled**:

1. **Disable in whitelist** (1-line change):
   ```python
   # src/liquidationheatmap/api/main.py
   SUPPORTED_SYMBOLS = {
       "BTCUSDT",
       # "ETHUSDT",  # Temporarily disabled - rollback
       ...
   }
   ```

2. **Stop OI collector**:
   ```bash
   tmux kill-session -t eth-oi
   ```

3. **Optionally truncate data** (if rollback permanent):
   ```bash
   uv run python -c "
   import duckdb
   conn = duckdb.connect('data/processed/liquidations.duckdb')
   conn.execute(\"DELETE FROM aggtrades_history WHERE symbol = 'ETHUSDT'\")
   conn.execute(\"DELETE FROM open_interest_history WHERE symbol = 'ETHUSDT'\")
   conn.execute(\"DELETE FROM klines_15m_history WHERE symbol = 'ETHUSDT'\")
   conn.execute(\"DELETE FROM klines_5m_history WHERE symbol = 'ETHUSDT'\")
   conn.close()
   "
   ```

4. **Restart API**:
   ```bash
   # API will now reject ETHUSDT requests with 400 error
   sudo systemctl restart liquidation-heatmap  # Or equivalent
   ```

**BTC pipeline continues unaffected** (data isolated by symbol column).

---

## Definition of Done

**Feature is complete when**:
- [ ] All P0 tasks (T001-T007, T009) completed
- [ ] All tests pass (`uv run pytest -v`)
- [ ] ETH heatmap visually validated in frontend
- [ ] Coinglass validation hit_rate > 0.60
- [ ] Documentation updated (README, API docs)
- [ ] PR merged to main branch

**Deployment ready when**:
- [ ] Real-time OI collector running for ETH (24h+ uptime)
- [ ] API serving ETH requests in production
- [ ] Monitoring confirms no performance degradation
