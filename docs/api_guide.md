# API Usage Guide

## Quick Start

### Calculate Margin

```bash
curl -X POST "http://localhost:8000/api/margin/calculate" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "notional": "50000"}'
```

**Response**:
```json
{
  "symbol": "BTCUSDT",
  "notional": "50000.00",
  "margin": "250.00",
  "tier": 1,
  "margin_rate": "0.5%",
  "maintenance_amount": "0.00"
}
```

### Calculate with Liquidation Price

```bash
curl -X POST "http://localhost:8000/api/margin/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "entry_price": "50000",
    "position_size": "1",
    "leverage": "10",
    "side": "long"
  }'
```

**Response**:
```json
{
  "symbol": "BTCUSDT",
  "notional": "50000.00",
  "margin": "250.00",
  "tier": 1,
  "margin_rate": "0.5%",
  "maintenance_amount": "0.00",
  "liquidation_price": "45250.00"
}
```

### Get Tier Information

```bash
curl "http://localhost:8000/api/margin/tiers/BTCUSDT"
```

### Batch Calculation

```bash
curl -X POST "http://localhost:8000/api/margin/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "calculations": [
      {"symbol": "BTCUSDT", "notional": "50000"},
      {"symbol": "BTCUSDT", "notional": "100000"},
      {"symbol": "BTCUSDT", "notional": "500000"}
    ]
  }'
```

## Exchange Filtering

### List Supported Exchanges

```bash
curl "http://localhost:8000/exchanges"
```

**Response**:
```json
{
  "binance": {"status": "active", "type": "REST", "features": ["historical", "realtime"]},
  "hyperliquid": {"status": "active", "type": "WebSocket", "features": ["realtime"]},
  "bybit": {"status": "stub", "type": "REST", "features": []}
}
```

### Get Exchange Health

```bash
curl "http://localhost:8000/exchanges/health"
```

**Response**:
```json
{
  "binance": {
    "is_connected": true,
    "last_heartbeat": "2024-12-29T10:00:00Z",
    "error_count": 0
  },
  "hyperliquid": {
    "is_connected": true,
    "last_heartbeat": "2024-12-29T10:00:01Z",
    "error_count": 0
  }
}
```

### Filter Heatmap by Exchange

```bash
# Single exchange
curl "http://localhost:8000/liquidations/heatmap-timeseries?symbol=BTCUSDT&exchanges=binance"

# Multiple exchanges
curl "http://localhost:8000/liquidations/heatmap-timeseries?symbol=BTCUSDT&exchanges=binance,hyperliquid"

# All exchanges (default)
curl "http://localhost:8000/liquidations/heatmap-timeseries?symbol=BTCUSDT"
```

**Response with exchange breakdown**:
```json
{
  "symbol": "BTCUSDT",
  "data": [
    {
      "time": "2024-12-29T10:00:00Z",
      "price_bucket": 43000,
      "density": 0.85,
      "exchange": "binance"
    },
    {
      "time": "2024-12-29T10:00:00Z",
      "price_bucket": 43000,
      "density": 0.15,
      "exchange": "hyperliquid"
    }
  ]
}
```

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/margin/calculate` | Calculate margin for position |
| POST | `/api/margin/batch` | Batch margin calculations |
| GET | `/api/margin/tiers/{symbol}` | Get tier information |
| GET | `/exchanges` | List supported exchanges |
| GET | `/exchanges/health` | Exchange connection health |
| GET | `/liquidations/heatmap-timeseries` | Heatmap with optional exchange filter |
| GET | `/health` | Health check |

### Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 404 | Symbol not found |
| 422 | Validation error |
| 500 | Internal server error |

## Python Client Example

```python
import requests
from decimal import Decimal

API_BASE = "http://localhost:8000/api"

def calculate_margin(symbol: str, notional: Decimal):
    response = requests.post(
        f"{API_BASE}/margin/calculate",
        json={"symbol": symbol, "notional": str(notional)}
    )
    return response.json()

# Example usage
result = calculate_margin("BTCUSDT", Decimal("50000"))
print(f"Margin: ${result['margin']} (Tier {result['tier']})")
```

## Interactive Documentation

Visit `http://localhost:8000/docs` for interactive Swagger UI documentation.
