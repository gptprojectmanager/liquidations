# Quickstart: Real-time WebSocket Streaming

**Feature**: spec-011 (Real-time WebSocket Streaming)
**Prerequisite**: FastAPI server running on `localhost:8000`

---

## 1. Server Setup

### Start the API Server

```bash
# From project root
uv run uvicorn src.liquidationheatmap.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --ws max-size 16777216
```

### Environment Variables (Optional)

```bash
# .env or export directly
export WS_UPDATE_INTERVAL=5         # Broadcast every 5 seconds
export WS_MAX_CONNECTIONS=1000      # Max concurrent clients
export WS_SLOW_CONSUMER_TIMEOUT=1.0 # 1s timeout for slow clients
```

---

## 2. JavaScript Client

### Basic Usage

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/heatmap');

ws.onopen = () => {
    console.log('Connected!');
    // Subscribe to BTCUSDT updates
    ws.send(JSON.stringify({
        action: 'subscribe',
        symbols: ['BTCUSDT']
    }));
};

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);

    switch (msg.type) {
        case 'snapshot':
            console.log(`New snapshot for ${msg.symbol}:`, msg.data);
            updateChart(msg.data.levels);
            break;
        case 'warning':
            console.warn('Warning:', msg.message);
            break;
        case 'error':
            console.error('Error:', msg.message);
            break;
        case 'pong':
            console.log('Keepalive OK');
            break;
    }
};

ws.onclose = () => {
    console.log('Disconnected');
    // Implement reconnection logic here
};
```

### Using the Client Library

```html
<!-- Include the client library -->
<script src="js/websocket-client.js"></script>

<script>
const client = new HeatmapWebSocket('ws://localhost:8000/ws/heatmap', {
    onSnapshot: (msg) => {
        console.log('Snapshot:', msg.symbol, msg.data.levels.length, 'levels');
        updateHeatmapChart(msg.data);
    },
    onStatusChange: (status) => {
        document.getElementById('status').textContent = status;
        document.getElementById('status').className = `status-${status}`;
    },
    onError: (error) => {
        console.error('WebSocket error:', error);
        showNotification('Connection error', 'error');
    }
});

// Connect and subscribe
client.connect();
client.subscribe(['BTCUSDT', 'ETHUSDT']);
client.startKeepalive();

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    client.disconnect();
});
</script>
```

---

## 3. Python Client (Testing)

### Using websockets Library

```python
import asyncio
import json
import websockets

async def subscribe_to_heatmap():
    uri = "ws://localhost:8000/ws/heatmap"

    async with websockets.connect(uri) as ws:
        # Subscribe to BTCUSDT
        await ws.send(json.dumps({
            "action": "subscribe",
            "symbols": ["BTCUSDT"]
        }))

        # Receive updates
        while True:
            message = await ws.recv()
            data = json.loads(message)

            if data["type"] == "snapshot":
                print(f"Snapshot for {data['symbol']}:")
                print(f"  Price: {data['data']['current_price']}")
                print(f"  Levels: {len(data['data']['levels'])}")

asyncio.run(subscribe_to_heatmap())
```

### Using httpx for Testing

```python
import httpx

# Check WebSocket stats
response = httpx.get("http://localhost:8000/ws/stats")
print(response.json())
# {
#   "active_connections": 5,
#   "messages_sent_1m": 120,
#   "slow_consumers": 0,
#   "subscriptions_by_symbol": {"BTCUSDT": 3, "ETHUSDT": 2}
# }
```

---

## 4. Command-Line Testing

### Using websocat

```bash
# Install websocat
cargo install websocat  # or via package manager

# Connect and subscribe
echo '{"action":"subscribe","symbols":["BTCUSDT"]}' | \
    websocat ws://localhost:8000/ws/heatmap

# Interactive mode
websocat ws://localhost:8000/ws/heatmap
> {"action":"subscribe","symbols":["BTCUSDT"]}
< {"type":"snapshot","symbol":"BTCUSDT",...}
> {"action":"ping"}
< {"type":"pong","timestamp":"2025-12-29T10:00:00Z"}
```

### Using wscat (Node.js)

```bash
# Install wscat
npm install -g wscat

# Connect
wscat -c ws://localhost:8000/ws/heatmap

# In the connected session:
> {"action":"subscribe","symbols":["BTCUSDT"]}
> {"action":"ping"}
```

---

## 5. Message Examples

### Subscribe to Multiple Symbols

```json
{"action": "subscribe", "symbols": ["BTCUSDT", "ETHUSDT"]}
```

### Unsubscribe from Symbol

```json
{"action": "unsubscribe", "symbols": ["ETHUSDT"]}
```

### Receive Snapshot

```json
{
  "type": "snapshot",
  "symbol": "BTCUSDT",
  "timestamp": "2025-12-29T10:00:00Z",
  "data": {
    "levels": [
      {"price": 98000, "long_density": 1500000, "short_density": 200000},
      {"price": 99000, "long_density": 2300000, "short_density": 150000},
      {"price": 100000, "long_density": 5000000, "short_density": 800000}
    ],
    "current_price": 98450,
    "positions_created": 450,
    "positions_consumed": 120
  }
}
```

### Handle Errors

```json
{
  "type": "error",
  "code": "INVALID_SYMBOL",
  "message": "Symbol 'XYZUSDT' not supported. Valid: BTCUSDT, ETHUSDT"
}
```

---

## 6. Frontend Integration

### Update Plotly Heatmap

```javascript
function updateHeatmapChart(data) {
    const trace = {
        x: data.levels.map(l => l.price),
        y: data.levels.map(l => l.long_density + l.short_density),
        type: 'bar',
        marker: {
            color: data.levels.map(l =>
                l.long_density > l.short_density ? 'green' : 'red'
            )
        }
    };

    Plotly.react('heatmap-chart', [trace], {
        title: `Liquidation Heatmap - ${data.current_price}`,
        xaxis: { title: 'Price' },
        yaxis: { title: 'Density (USD)' }
    });
}
```

### Connection Status Indicator

```html
<style>
  .status-connected { color: green; }
  .status-slow { color: orange; }
  .status-disconnected { color: red; }
  .status-failed { color: darkred; }
</style>

<div id="ws-status" class="status-disconnected">DISCONNECTED</div>
```

---

## 7. Troubleshooting

### Connection Refused

```bash
# Check server is running
curl http://localhost:8000/health

# Check WebSocket endpoint
curl -v -N \
    -H "Connection: Upgrade" \
    -H "Upgrade: websocket" \
    -H "Sec-WebSocket-Version: 13" \
    -H "Sec-WebSocket-Key: test" \
    http://localhost:8000/ws/heatmap
```

### Slow Consumer Warnings

If you receive `SLOW_CONSUMER` warnings:
1. Reduce number of subscribed symbols
2. Check network latency
3. Ensure client processing is fast (don't block in `onmessage`)

### No Snapshots Received

1. Verify subscription was accepted (no error response)
2. Check if heatmap data exists for the symbol
3. Look at server logs for broadcast activity:
   ```bash
   uvicorn ... --log-level debug
   ```

---

## 8. Next Steps

- **Load Testing**: Run k6 tests to validate performance
  ```bash
  k6 run tests/load/ws_load_test.js
  ```

- **Monitor Stats**: Check `/ws/stats` endpoint for connection metrics

- **Multi-Server**: Enable Redis for horizontal scaling
  ```bash
  export REDIS_ENABLED=true
  export REDIS_URL=redis://localhost:6379
  ```
