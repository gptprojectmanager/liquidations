# ETH/USDT Support - Quickstart Guide

**Goal**: Add ETH/USDT support in 2 days via 100% code reuse
**Approach**: Pure parameterization - no new algorithms, just data ingestion

---

## TL;DR - What You Need to Do

```bash
# 1. Find ETH data
ls /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/

# 2. Ingest ETH trades (4h wait time)
uv run python scripts/ingest_aggtrades.py \
  --symbol ETHUSDT \
  --start-date 2024-11-01 \
  --end-date 2024-11-30 \
  --data-dir /media/sam/3TB-WDC/binance-history-data-downloader/data \
  --db data/processed/liquidations.duckdb

# 3. Start real-time OI collector (background)
tmux new -s eth-oi
uv run python scripts/ingest_oi.py --symbol ETHUSDT

# 4. Ingest klines (1h)
uv run python scripts/ingest_klines_15m.py --symbol ETHUSDT --start-date 2024-11-01 --end-date 2024-11-30

# 5. Test API
curl "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&time_window=7d" | jq '.meta'

# 6. Validate against Coinglass
uv run python scripts/validate_vs_coinglass.py --symbol ETHUSDT

# 7. Done! (if hit_rate > 0.60)
```

---

## Why This Works

**The entire codebase is symbol-agnostic**:

1. **Ingestion scripts**: All accept `--symbol` parameter
   - `scripts/ingest_aggtrades.py`
   - `scripts/ingest_oi.py`
   - `scripts/ingest_klines_15m.py`

2. **Database schema**: `symbol` column in all tables
   - `aggtrades_history(symbol, timestamp, price, ...)`
   - `open_interest_history(symbol, timestamp, open_interest_value, ...)`
   - `klines_15m_history(symbol, open_time, open, high, low, close, ...)`

3. **API queries**: Filter by `WHERE symbol = ?`
   - `calculate_time_evolving_heatmap(symbol, ...)`
   - `get_heatmap_timeseries(symbol, ...)`

4. **Whitelist**: ETH already approved
   ```python
   SUPPORTED_SYMBOLS = {"BTCUSDT", "ETHUSDT", ...}  # Line 230 in main.py
   ```

**Result**: No code changes needed, just ingest ETH data and test.

---

## Step-by-Step Execution

### Step 1: Verify Data Availability (5 min)

```bash
# Check directory exists
ls -lh /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/

# Count files
find /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/ -name "*.csv" | wc -l

# Identify date range
ls /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/ | head -1
ls /media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/ | tail -1
```

**Expected**: 30+ CSV files, date range Nov 2024 (adjust as needed)

---

### Step 2: Ingest aggTrades (4-5h streaming ingestion)

```bash
cd /media/sam/1TB/LiquidationHeatmap

# Dry-run first (fast validation)
uv run python scripts/ingest_aggtrades.py \
  --symbol ETHUSDT \
  --start-date 2024-11-01 \
  --end-date 2024-11-30 \
  --data-dir /media/sam/3TB-WDC/binance-history-data-downloader/data \
  --db data/processed/liquidations.duckdb \
  --dry-run

# Production ingestion (streaming, OOM-safe)
uv run python scripts/ingest_aggtrades.py \
  --symbol ETHUSDT \
  --start-date 2024-11-01 \
  --end-date 2024-11-30 \
  --data-dir /media/sam/3TB-WDC/binance-history-data-downloader/data \
  --db data/processed/liquidations.duckdb \
  --throttle-ms 200
```

**Monitor progress**: Script outputs "Inserted X rows" every batch

**Verify after completion**:
```bash
uv run python -c "
import duckdb
conn = duckdb.connect('data/processed/liquidations.duckdb', read_only=True)
result = conn.execute('''
  SELECT COUNT(*) as trades, MIN(timestamp) as start, MAX(timestamp) as end
  FROM aggtrades_history WHERE symbol = 'ETHUSDT'
''').fetchone()
print(f'ETH Trades: {result[0]:,}, Range: {result[1]} to {result[2]}')
conn.close()
"
```

---

### Step 3: Start Real-Time OI Collector (1h setup + 24h monitoring)

```bash
# Run in tmux for persistence
tmux new -s eth-oi
cd /media/sam/1TB/LiquidationHeatmap
uv run python scripts/ingest_oi.py --symbol ETHUSDT

# Detach: Ctrl+B, D
# Re-attach later: tmux attach -t eth-oi
```

**Verify after 1 hour**:
```bash
uv run python -c "
import duckdb
from datetime import datetime, timedelta
conn = duckdb.connect('data/processed/liquidations.duckdb', read_only=True)
result = conn.execute('''
  SELECT COUNT(*) as snapshots, AVG(open_interest_value) as avg_oi
  FROM open_interest_history
  WHERE symbol = 'ETHUSDT'
  AND timestamp > ?
''', [datetime.now() - timedelta(hours=1)]).fetchone()
print(f'OI Snapshots (1h): {result[0]}, Avg: ${result[1]:,.2f}')
conn.close()
"
```

**Expected**: ~120 snapshots per hour, OI in $500M-$5B range

---

### Step 4: Ingest Klines (1-2h)

```bash
cd /media/sam/1TB/LiquidationHeatmap

# Ingest 15m klines (matches aggTrades date range)
uv run python scripts/ingest_klines_15m.py \
  --symbol ETHUSDT \
  --start-date 2024-11-01 \
  --end-date 2024-11-30
```

**Verify**:
```bash
uv run python -c "
import duckdb
conn = duckdb.connect('data/processed/liquidations.duckdb', read_only=True)
result = conn.execute('''
  SELECT COUNT(*) as candles, AVG(CAST(close AS DOUBLE)) as avg_price
  FROM klines_15m_history WHERE symbol = 'ETHUSDT'
''').fetchone()
print(f'ETH 15m Klines: {result[0]:,}, Avg Price: ${result[1]:,.2f}')
conn.close()
"
```

**Expected**: ~2,880 candles for 30 days, avg price ~$3000-$4000

---

### Step 5: Test API Endpoints (30 min)

**Start API server** (if not running):
```bash
cd /media/sam/1TB/LiquidationHeatmap
uv run uvicorn src.liquidationheatmap.api.main:app --reload
```

**Test heatmap endpoint**:
```bash
# Test 1: 7-day window
curl -s "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&time_window=7d" | jq '.meta'

# Test 2: Custom date range
curl -s "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&start_time=2024-11-01T00:00:00&end_time=2024-11-30T23:59:59&interval=15m" | jq '.meta.total_snapshots'

# Test 3: 30-day window
curl -s "http://localhost:8000/liquidations/heatmap-timeseries?symbol=ETHUSDT&time_window=30d" | jq '.data[0].levels[0:3]'
```

**Test klines endpoint**:
```bash
curl -s "http://localhost:8000/prices/klines?symbol=ETHUSDT&interval=15m&limit=100" | jq '{symbol, count, first_close: .data[0].close}'
```

**Test date range endpoint**:
```bash
curl -s "http://localhost:8000/data/date-range?symbol=ETHUSDT" | jq
```

**Success**: All endpoints return 200 OK with valid JSON

---

### Step 6: Frontend Testing (15 min)

```bash
# Open browser
xdg-open http://localhost:8000/frontend/coinglass_heatmap.html
```

**Manual Tests**:
1. Select "ETHUSDT" from symbol dropdown
2. Verify heatmap re-renders
3. Check price levels are in ETH range ($2000-$4000)
4. Verify klines overlay shows ETH candlesticks
5. Switch back to BTC, then to ETH again (test toggling)

---

### Step 7: Coinglass Validation (2h)

**Prerequisites**: N8N has captured ETH screenshots

```bash
# Run validation
uv run python scripts/validate_vs_coinglass.py \
  --symbol ETHUSDT \
  --screenshot-dir /path/to/n8n/screenshots/ETH

# View results
cat data/validation/price_level_comparison.jsonl | grep ETHUSDT | jq

# Generate summary
uv run python scripts/validate_vs_coinglass.py --summary
```

**Success Criteria**:
- `hit_rate > 0.60` (60%+ of Coinglass liquidations match our zones)
- `price_level_overlap > 0.70` (Jaccard similarity)

**If hit_rate < 0.60**: Investigate data quality, NOT model failure (model is same for BTC/ETH)

---

### Step 8: Run Full Test Suite (30 min)

```bash
cd /media/sam/1TB/LiquidationHeatmap

# Unit tests
uv run pytest tests/unit/ -v

# Integration tests (multi-symbol)
uv run pytest tests/integration/test_multi_symbol.py -v

# Contract tests (API)
uv run pytest tests/contract/test_heatmap_timeseries.py -v

# Performance tests
uv run pytest tests/performance/test_api_performance.py -v

# All tests
uv run pytest -v --tb=short
```

**Success**: All tests pass (no regressions)

---

### Step 9: Update Documentation (30 min)

**Update README.md**:
```markdown
## Supported Trading Pairs

| Symbol | Status | Validation | Coverage |
|--------|--------|-----------|----------|
| BTC/USDT | ✅ | Hit rate: 0.75 | Sep 2024 - present |
| ETH/USDT | ✅ | Hit rate: 0.XX | Nov 2024 - present |
```

**Update API docs** (examples in `src/liquidationheatmap/api/main.py`):
```python
examples=["BTCUSDT", "ETHUSDT"]
```

---

## Troubleshooting

### Issue: aggTrades ingestion fails with OOM
**Solution**: Reduce throttle or process in smaller date ranges
```bash
# Split into weekly batches
uv run python scripts/ingest_aggtrades.py --symbol ETHUSDT --start-date 2024-11-01 --end-date 2024-11-07 ...
uv run python scripts/ingest_aggtrades.py --symbol ETHUSDT --start-date 2024-11-08 --end-date 2024-11-14 ...
```

### Issue: OI collector crashes
**Solution**: Check Binance API limits, restart with backoff
```bash
# Check logs
tail -f /path/to/logs/ingest_oi.log

# Restart
tmux attach -t eth-oi
# Ctrl+C, then restart script
```

### Issue: API returns empty data for ETH
**Solution**: Verify data exists in DuckDB
```bash
uv run python -c "
import duckdb
conn = duckdb.connect('data/processed/liquidations.duckdb', read_only=True)
print(conn.execute('SELECT COUNT(*) FROM aggtrades_history WHERE symbol = \"ETHUSDT\"').fetchone())
print(conn.execute('SELECT COUNT(*) FROM open_interest_history WHERE symbol = \"ETHUSDT\"').fetchone())
print(conn.execute('SELECT COUNT(*) FROM klines_15m_history WHERE symbol = \"ETHUSDT\"').fetchone())
conn.close()
"
```

### Issue: Validation hit_rate < 0.60
**Diagnosis**:
1. Check if Coinglass screenshots are for correct time period
2. Verify ETH data quality (no gaps)
3. Compare with BTC hit_rate (should be similar)

**If BTC also drops**: Model issue (unlikely, already validated)
**If only ETH drops**: Data quality issue (re-ingest or adjust date range)

---

## Rollback Plan

**Disable ETH temporarily**:
```python
# src/liquidationheatmap/api/main.py
SUPPORTED_SYMBOLS = {
    "BTCUSDT",
    # "ETHUSDT",  # Disabled - rollback
}
```

**Stop OI collector**:
```bash
tmux kill-session -t eth-oi
```

**Truncate data** (if permanent rollback):
```bash
uv run python -c "
import duckdb
conn = duckdb.connect('data/processed/liquidations.duckdb')
conn.execute('DELETE FROM aggtrades_history WHERE symbol = \"ETHUSDT\"')
conn.execute('DELETE FROM open_interest_history WHERE symbol = \"ETHUSDT\"')
conn.execute('DELETE FROM klines_15m_history WHERE symbol = \"ETHUSDT\"')
conn.close()
"
```

**BTC continues unaffected** (symbol-isolated data).

---

## Success Checklist

- [ ] ETH data ingested (trades, OI, klines)
- [ ] API endpoints return valid ETH data
- [ ] Frontend shows ETH heatmap
- [ ] Coinglass validation hit_rate > 0.60
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Real-time OI collector running 24h+

**When all checked**: Merge PR, deploy to production.

---

## Next Steps (After ETH)

Once ETH is validated, expanding to other symbols is trivial:

```bash
# BNB/USDT
uv run python scripts/ingest_aggtrades.py --symbol BNBUSDT ...
uv run python scripts/ingest_oi.py --symbol BNBUSDT
uv run python scripts/validate_vs_coinglass.py --symbol BNBUSDT

# ADA/USDT
uv run python scripts/ingest_aggtrades.py --symbol ADAUSDT ...
uv run python scripts/ingest_oi.py --symbol ADAUSDT
uv run python scripts/validate_vs_coinglass.py --symbol ADAUSDT
```

**Validation requirement**: hit_rate > 0.60 for production approval.

**Roadmap**: 10 symbols validated by Q1 2025.
