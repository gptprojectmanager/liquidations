# Quickstart: Time-Evolving Liquidation Heatmap

## Prerequisites

- Python 3.11+
- UV package manager
- DuckDB database with historical data

## Setup

```bash
# Clone and navigate
cd /media/sam/1TB/LiquidationHeatmap

# Checkout feature branch
git checkout 008-time-evolving-heatmap

# Install dependencies
uv sync
```

## Quick Test

### 1. Verify Data Exists

```bash
uv run python -c "
import duckdb
conn = duckdb.connect('data/processed/liquidations.duckdb', read_only=True)
print('Klines:', conn.execute('SELECT COUNT(*) FROM klines_5m_history').fetchone()[0])
print('OI:', conn.execute('SELECT COUNT(*) FROM open_interest_history').fetchone()[0])
conn.close()
"
```

Expected output:
```
Klines: 14112
OI: 417460
```

### 2. Run Tests

```bash
# Run unit tests for time-evolving model (core algorithm tests)
uv run pytest tests/unit/models/test_time_evolving_heatmap.py -v

# Run integration tests (database persistence, API)
uv run pytest tests/integration/test_time_evolving_algorithm.py tests/integration/test_heatmap_api.py -v

# Run contract tests (API contract validation)
uv run pytest tests/contract/test_heatmap_timeseries.py -v

# Run performance tests
uv run pytest tests/performance/test_algorithm_performance.py tests/performance/test_api_performance.py -v

# Run full test suite (all 878+ tests)
uv run pytest tests/ -v
```

Expected output for time-evolving model tests:
```
tests/unit/models/test_time_evolving_heatmap.py::TestShouldLiquidate::test_long_position_not_liquidated_when_price_above ... PASSED
tests/unit/models/test_time_evolving_heatmap.py::TestShouldLiquidate::test_long_position_liquidated_when_price_touches ... PASSED
tests/unit/models/test_time_evolving_heatmap.py::TestShouldLiquidate::test_short_position_liquidated_when_price_rises ... PASSED
... (all tests should pass)
```

### 3. Start API Server

```bash
uv run uvicorn src.liquidationheatmap.api.main:app --host 127.0.0.1 --port 8888
```

### 4. Test New Endpoint

```bash
# Get time-evolving heatmap (last 7 days, 15m intervals)
curl "http://localhost:8888/liquidations/heatmap-timeseries?symbol=BTCUSDT&interval=15m"

# Get with custom time range
curl "http://localhost:8888/liquidations/heatmap-timeseries?symbol=BTCUSDT&start_time=2025-11-15T00:00:00&end_time=2025-11-17T00:00:00"
```

### 5. View Visualization

Open in browser:
```
file:///media/sam/1TB/LiquidationHeatmap/frontend/coinglass_heatmap.html
```

Click "Load Heatmap" to see time-evolving visualization.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/liquidations/heatmap-timeseries` | GET | Time-evolving heatmap (NEW) |
| `/liquidations/levels` | GET | Static levels (DEPRECATED) |
| `/prices/klines` | GET | OHLC price data |
| `/health` | GET | Health check |
| `/cache/stats` | GET | Cache hit/miss statistics (NEW) |
| `/cache/clear` | DELETE | Clear heatmap cache (NEW) |

## Example Response

```json
{
  "data": [
    {
      "timestamp": "2025-11-15T00:00:00",
      "levels": [
        {"price": 88000, "long_density": 1234567, "short_density": 0},
        {"price": 89000, "long_density": 2345678, "short_density": 0},
        {"price": 95000, "long_density": 0, "short_density": 3456789}
      ],
      "positions_created": 15,
      "positions_consumed": 3
    }
  ],
  "meta": {
    "symbol": "BTCUSDT",
    "total_snapshots": 200,
    "total_long_volume": 50000000,
    "total_short_volume": 45000000
  }
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LH_DB_PATH` | `data/processed/liquidations.duckdb` | Database path |
| `LH_CACHE_TTL` | `300` | Cache TTL in seconds (5 minutes) |
| `LH_CACHE_MAX_SIZE` | `100` | Maximum cache entries |
| `LH_DEFAULT_INTERVAL` | `15m` | Default heatmap interval |

### Leverage Distribution

Default weights can be overridden via API parameter:

```bash
# Custom leverage weights
curl "http://localhost:8888/liquidations/heatmap-timeseries?symbol=BTCUSDT&leverage_weights=5:20,10:35,25:25,50:15,100:5"
```

## Troubleshooting

### Empty Heatmap Data

1. Check database has data for requested time range:
   ```sql
   SELECT MIN(open_time), MAX(open_time) FROM klines_5m_history;
   ```

2. Verify OI data exists:
   ```sql
   SELECT COUNT(*) FROM open_interest_history WHERE timestamp >= '2025-11-15';
   ```

### Performance Issues

1. Use pre-computed cache:
   ```bash
   uv run python scripts/precompute_heatmap.py --symbol BTCUSDT --days 30
   ```

2. Reduce time range or increase interval (1h instead of 15m)

### API Errors

Check logs:
```bash
tail -f /tmp/api_server.log
```

## Next Steps

1. Read [spec.md](./spec.md) for full feature specification
2. Review [data-model.md](./data-model.md) for entity details
3. Check [tasks.md](./tasks.md) for implementation roadmap
4. See [contracts/openapi.yaml](./contracts/openapi.yaml) for API schema
