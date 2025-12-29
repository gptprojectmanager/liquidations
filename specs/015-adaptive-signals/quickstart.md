# Quickstart: Adaptive Signal Loop

**Feature**: 015-adaptive-signals
**Date**: 2025-12-28

---

## Prerequisites

- [ ] Redis server installed (`sudo apt install redis-server`)
- [ ] Redis running on localhost:6379
- [ ] LiquidationHeatmap API running

---

## Step 1: Start Redis

```bash
# Start Redis (if not running)
redis-server --daemonize yes

# Verify Redis is running
redis-cli ping  # Should return PONG

# Check Redis version
redis-cli INFO server | grep redis_version
```

---

## Step 2: Test Redis Pub/Sub (Manual)

```bash
# Terminal 1: Subscribe to signals
redis-cli SUBSCRIBE liquidation:signals:BTCUSDT

# Terminal 2: Publish test signal
redis-cli PUBLISH liquidation:signals:BTCUSDT '{"symbol":"BTCUSDT","price":"95000","side":"long","confidence":0.85,"timestamp":"2025-12-28T10:30:00Z"}'
```

**Expected**: Terminal 1 receives the JSON message.

---

## Step 3: Run Signal Publisher

```bash
cd /media/sam/1TB/LiquidationHeatmap

# Test with single publish
uv run python -c "
from src.liquidationheatmap.signals.publisher import SignalPublisher
pub = SignalPublisher()
pub.publish_signal('BTCUSDT', 95000.0, 'long', 0.85)
print('Signal published!')
"

# Run as background service
uv run python -m src.liquidationheatmap.signals.publisher --symbol BTCUSDT &
```

---

## Step 4: Run Feedback Consumer

```bash
cd /media/sam/1TB/LiquidationHeatmap

# Run feedback consumer
uv run python -m src.liquidationheatmap.signals.feedback --symbol BTCUSDT &

# Simulate feedback from Nautilus
redis-cli PUBLISH liquidation:feedback:BTCUSDT '{"symbol":"BTCUSDT","signal_id":"abc123","entry_price":"95000","exit_price":"95500","pnl":"500","timestamp":"2025-12-28T11:00:00Z","source":"nautilus"}'
```

---

## Step 5: Check API Status

```bash
# Start API (if not running)
uv run uvicorn src.liquidationheatmap.api.main:app --reload &

# Check signal status
curl -s http://localhost:8000/signals/status | jq

# Check metrics
curl -s "http://localhost:8000/signals/metrics?symbol=BTCUSDT&window=24h" | jq
```

---

## Step 6: Run Tests

```bash
cd /media/sam/1TB/LiquidationHeatmap

# Unit tests (mocked Redis)
uv run pytest tests/unit/test_adaptive_signals.py -v

# Integration tests (requires real Redis)
uv run pytest tests/integration/test_redis_pubsub.py -v

# All tests
uv run pytest -v
```

---

## Troubleshooting

### Redis Connection Failed

```bash
# Check if Redis is running
redis-cli ping

# Start Redis if not running
redis-server --daemonize yes

# Check Redis logs
tail -f /var/log/redis/redis-server.log
```

### No Signals Received

```bash
# Check channel subscription
redis-cli PUBSUB CHANNELS "liquidation:*"

# Monitor all Redis activity
redis-cli MONITOR
```

### Feedback Not Processing

```bash
# Check DuckDB for feedback records
uv run python -c "
import duckdb
conn = duckdb.connect('data/processed/liquidations.duckdb', read_only=True)
print(conn.execute('SELECT * FROM signal_feedback ORDER BY timestamp DESC LIMIT 5').fetchall())
"
```

---

## Architecture Verification

```bash
# Verify integration points exist
ls /media/sam/1TB/nautilus_dev/  # Nautilus path
ls /media/sam/1TB/UTXOracle/     # UTXOracle path

# Check Redis channels
redis-cli PUBSUB CHANNELS "liquidation:*"
```

---

## Rollback

```bash
# Disable signals (set env var)
export SIGNALS_ENABLED=false

# Or kill background processes
pkill -f "signals.publisher"
pkill -f "signals.feedback"

# Clear adaptive weights (if needed)
uv run python -c "
import duckdb
conn = duckdb.connect('data/processed/liquidations.duckdb')
conn.execute('DELETE FROM adaptive_weights')
conn.close()
print('Weights reset to defaults')
"
```

---

**Quickstart Status**: ✅ Complete
