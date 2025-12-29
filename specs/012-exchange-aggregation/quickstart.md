# Quickstart: Exchange Aggregation

**Feature**: 012-exchange-aggregation
**Date**: 2025-12-29

## Prerequisites

- Python 3.11+
- UV package manager
- Existing LiquidationHeatmap setup

## Installation

```bash
# Install new dependencies
uv add websockets aiohttp

# Verify
uv run python -c "import websockets; import aiohttp; print('OK')"
```

## Basic Usage

### 1. Initialize Aggregator

```python
from src.exchanges.aggregator import ExchangeAggregator

# Create aggregator with specific exchanges
agg = ExchangeAggregator(exchanges=["binance", "hyperliquid"])

# Or use all supported exchanges
agg = ExchangeAggregator()  # Defaults to all
```

### 2. Connect and Stream

```python
import asyncio

async def main():
    agg = ExchangeAggregator(exchanges=["binance", "hyperliquid"])

    # Connect to all exchanges
    await agg.connect_all()

    # Stream aggregated liquidations
    async for liq in agg.stream_aggregated("BTCUSDT"):
        print(f"[{liq.exchange}] {liq.side} liq at ${liq.price:.2f}")
        print(f"  Size: {liq.quantity} BTC (${liq.value_usd:,.0f})")

    # Cleanup
    await agg.disconnect_all()

asyncio.run(main())
```

### 3. Health Monitoring

```python
async def check_health():
    agg = ExchangeAggregator()
    await agg.connect_all()

    # Get health for all exchanges
    health = await agg.health_check_all()

    for exchange, status in health.items():
        emoji = "" if status.is_connected else ""
        print(f"{emoji} {exchange}: {status.message_count} msgs, {status.error_count} errors")

    # Get list of active exchanges
    active = agg.get_active_exchanges()
    print(f"Active: {', '.join(active)}")
```

## API Usage

### Get Aggregated Heatmap

```bash
# All exchanges (default)
curl "http://localhost:8000/liquidations/heatmap?symbol=BTCUSDT&timeframe=24h"

# Specific exchanges
curl "http://localhost:8000/liquidations/heatmap?exchanges=binance,hyperliquid"

# Single exchange
curl "http://localhost:8000/liquidations/heatmap?exchanges=binance"
```

### Check Exchange Health

```bash
curl "http://localhost:8000/exchanges/health"
```

### List Supported Exchanges

```bash
curl "http://localhost:8000/exchanges"
```

## Integration Scenarios

### Scenario 1: Real-time Dashboard

```python
# Frontend WebSocket consumer
async def dashboard_consumer():
    agg = ExchangeAggregator()
    await agg.connect_all()

    async for liq in agg.stream_aggregated("BTCUSDT"):
        # Send to WebSocket clients
        await broadcast_to_clients({
            "type": "liquidation",
            "exchange": liq.exchange,
            "price": liq.price,
            "side": liq.side,
            "value_usd": liq.value_usd
        })
```

### Scenario 2: Historical Analysis

```python
import duckdb

def query_by_exchange(exchange: str, hours: int = 24):
    conn = duckdb.connect("data/processed/liquidations.duckdb")

    result = conn.execute("""
        SELECT
            exchange,
            side,
            COUNT(*) as count,
            SUM(value_usd) as total_value
        FROM liquidations
        WHERE exchange = ?
          AND timestamp >= NOW() - INTERVAL ? HOUR
        GROUP BY exchange, side
    """, [exchange, hours]).fetchall()

    return result
```

### Scenario 3: Failover Handling

```python
async def resilient_stream():
    agg = ExchangeAggregator(exchanges=["binance", "hyperliquid"])

    while True:
        try:
            await agg.connect_all()

            async for liq in agg.stream_aggregated("BTCUSDT"):
                process_liquidation(liq)

        except Exception as e:
            logger.error(f"Stream error: {e}")
            await agg.disconnect_all()
            await asyncio.sleep(5)  # Wait before reconnect
```

## Testing

### Unit Tests

```bash
# Run adapter tests
uv run pytest tests/test_exchanges/ -v

# Run with coverage
uv run pytest tests/test_exchanges/ --cov=src/exchanges --cov-report=term
```

### Integration Tests

```bash
# Run integration tests (requires network)
uv run pytest tests/integration/test_aggregator.py -v --timeout=60
```

### Manual Testing

```python
# Quick smoke test
from src.exchanges.binance import BinanceAdapter

async def smoke_test():
    adapter = BinanceAdapter()
    await adapter.connect()

    health = await adapter.health_check()
    print(f"Binance connected: {health.is_connected}")

    await adapter.disconnect()

import asyncio
asyncio.run(smoke_test())
```

## Troubleshooting

### Binance 403 Error (WebSocket)

**Symptom**: WebSocket connection rejected with 403
**Cause**: Rate limit or IP restriction
**Solution**: Use REST polling (default behavior)

### Hyperliquid No Data

**Symptom**: No liquidations received
**Cause**: Low liquidation frequency for BTC
**Solution**: Wait longer (liquidations may be 1-2/hour) or test with altcoins

### Connection Timeout

**Symptom**: `asyncio.TimeoutError` after 30s
**Cause**: No liquidations in timeframe
**Solution**: This is normal during quiet markets; aggregator continues waiting

## Configuration

### Environment Variables

```bash
# Optional: Override polling interval (seconds)
export BINANCE_POLL_INTERVAL=5

# Optional: WebSocket timeout (seconds)
export WS_TIMEOUT=30

# Optional: Max retry attempts
export MAX_RETRIES=3
```

### Adapter Configuration

```python
# Custom polling interval
adapter = BinanceAdapter(poll_interval=10)  # 10 seconds

# Custom WebSocket URL (for testing)
adapter = HyperliquidAdapter(ws_url="wss://test.hyperliquid.xyz/ws")
```

## Performance Tips

1. **Use specific exchanges**: Only connect to exchanges you need
2. **Batch processing**: Process liquidations in batches for DB inserts
3. **Cache health checks**: Health endpoint caches for 10s
4. **Index queries**: Ensure `(exchange, timestamp)` index exists

---

**Next Steps**:
1. Run migration: `uv run python scripts/migrate_add_exchange_column.py`
2. Start API: `uv run uvicorn src.liquidationheatmap.api.main:app --reload`
3. Open dashboard: `http://localhost:8000/docs`
