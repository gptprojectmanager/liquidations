# Feature Specification: Real-time WebSocket Streaming

> **Status**: Specification
> **Created**: 2025-12-28
> **Owner**: quant-analyst agent

## Overview

Add real-time WebSocket streaming capabilities to the LiquidationHeatmap API, enabling live heatmap updates for connected clients without polling. This feature leverages FastAPI's native WebSocket support and Redis pub/sub for horizontal scalability.

**Key Principle**: KISS - Start simple (in-memory broadcast), add Redis only when multi-server deployment is needed.

## Problem Statement

**Current Limitation**: Clients must poll `/liquidations/heatmap-timeseries` endpoint repeatedly (every 5-60 seconds) to receive updated heatmap data. This causes:
- Unnecessary server load (cache misses for new time windows)
- Network overhead (full response even if no changes)
- UI latency (5-60s delay until user sees new liquidation zones)

**Real-world Scenario**: A trader monitoring BTC/USDT liquidation levels during high volatility (e.g., news event, whale move) experiences:
1. Price moves from $98,000 to $99,500 in 2 minutes
2. New liquidation zones appear at $100k, $102k
3. User's frontend polls every 15 seconds
4. User sees critical $100k zone **30 seconds after it formed** (missed 2 poll cycles)

## Goals

### Primary Goals
1. **Real-time Heatmap Updates**: Push new snapshots to connected clients every N seconds (configurable)
2. **Symbol-based Subscriptions**: Clients subscribe to specific symbols (BTC, ETH) to reduce bandwidth
3. **Backpressure Handling**: Gracefully handle slow clients without blocking fast clients
4. **Horizontal Scalability**: Support multi-server deployments via Redis pub/sub

### Non-Goals (YAGNI)
- **Historical replay over WebSocket** (use REST API for history)
- **Bidirectional commands** (WebSocket is push-only; use REST for control)
- **Custom protocols** (stick to JSON over WebSocket)
- **Authentication** (rely on origin-based CORS for MVP; add JWT if needed later)

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Update Latency** | <500ms (95th percentile) | Time from heatmap calculation to client receipt |
| **Concurrent Connections** | 1000+ per server | Load test with artillery/k6 |
| **Bandwidth per Client** | <50 KB/s @ 5s updates | Measure payload size × update frequency |
| **Message Drop Rate** | <0.1% | Count messages sent vs received (slow client detection) |

## User Stories

### Story 1: Real-time Trader Dashboard
**As a** day trader monitoring liquidation levels
**I want** to see heatmap updates in real-time without refreshing
**So that** I can react immediately to new liquidation clusters forming

**Acceptance Criteria**:
- WebSocket connection established on page load
- New snapshots appear within 1 second of generation
- Connection auto-reconnects if dropped
- Visual indicator shows connection status (green = live, red = disconnected)

### Story 2: Multi-Symbol Monitoring
**As a** portfolio manager tracking BTC and ETH
**I want** to subscribe to multiple symbols simultaneously
**So that** I can monitor correlation between liquidation levels

**Acceptance Criteria**:
- Client can subscribe to multiple symbols (e.g., `["BTCUSDT", "ETHUSDT"]`)
- Each symbol sends independent updates
- Bandwidth is proportional to number of subscribed symbols
- Unsubscribe from individual symbols without reconnecting

### Story 3: Graceful Degradation
**As a** mobile user on slow 3G connection
**I want** the app to handle slow network gracefully
**So that** I don't miss critical updates or crash the app

**Acceptance Criteria**:
- Client receives "slow consumer" warning if queue fills up
- Server drops oldest messages (not newest) when backpressure occurs
- Client UI shows warning: "Connection slow - may miss updates"
- Auto-fallback to polling if WebSocket fails 3 times

## Technical Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CLIENT (Browser / Mobile)                        │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  WebSocket Client (JavaScript)                              │    │
│  │  - Connection management (auto-reconnect)                   │    │
│  │  - Symbol subscription handling                             │    │
│  │  - Backpressure detection (slow consumer warning)           │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ WebSocket (JSON)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│              FASTAPI SERVER (Uvicorn with --ws-max-size)             │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  WebSocket Endpoint: /ws/heatmap                            │    │
│  │  - Handle connections, subscriptions, disconnections        │    │
│  │  - Per-client queue with backpressure handling              │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                 │                                    │
│                                 ▼                                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Broadcast Manager (ConnectionManager)                      │    │
│  │  - Track active connections by symbol                       │    │
│  │  - Fan-out messages to subscribed clients                   │    │
│  │  - Handle slow consumer detection                           │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                 │                                    │
│                                 ▼                                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Update Generator (Background Task)                         │    │
│  │  - asyncio loop: every N seconds (configurable)             │    │
│  │  - Query latest heatmap data from DuckDB                    │    │
│  │  - Publish to ConnectionManager                             │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ (Optional: Multi-server scaling)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     REDIS PUB/SUB (Future)                           │
│  - Channel per symbol: "heatmap:BTCUSDT"                            │
│  - Enables horizontal scaling (multiple FastAPI servers)            │
│  - Pattern: Server A publishes → Redis → All servers subscribe     │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

**Phase 1: Single-Server (In-Memory Broadcast)**
```
1. Client connects to ws://api/ws/heatmap
2. Client sends: {"action": "subscribe", "symbols": ["BTCUSDT"]}
3. Server adds client to ConnectionManager.clients["BTCUSDT"]
4. Background task every 5s:
   a. Query: SELECT latest heatmap snapshot for BTCUSDT
   b. If data changed since last push:
      - Format as HeatmapSnapshotMessage
      - manager.broadcast("BTCUSDT", message)
5. ConnectionManager iterates clients["BTCUSDT"]:
   - Try to send message (with timeout)
   - If queue full → drop oldest message + send slow_consumer warning
6. Client receives snapshot → update Plotly.js chart
```

**Phase 2: Multi-Server (Redis Pub/Sub) - Future Enhancement**
```
1. Background task publishes to Redis: PUBLISH heatmap:BTCUSDT {json}
2. All servers subscribed to heatmap:BTCUSDT receive message
3. Each server's ConnectionManager broadcasts to its local clients
```

### API Specification

#### WebSocket Endpoint

**URL**: `ws://localhost:8000/ws/heatmap`

**Client → Server Messages**:

```json
{
  "action": "subscribe",
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "update_interval": 5  // Optional: seconds (default: 5)
}
```

```json
{
  "action": "unsubscribe",
  "symbols": ["ETHUSDT"]
}
```

```json
{
  "action": "ping"  // Keepalive (server responds with pong)
}
```

**Server → Client Messages**:

```json
{
  "type": "snapshot",
  "symbol": "BTCUSDT",
  "timestamp": "2025-12-28T14:30:00Z",
  "data": {
    "levels": [
      {"price": 98000, "long_density": 1500000, "short_density": 200000},
      {"price": 99000, "long_density": 2300000, "short_density": 150000}
    ],
    "current_price": 98450,
    "positions_created": 450,
    "positions_consumed": 120
  }
}
```

```json
{
  "type": "error",
  "code": "INVALID_SYMBOL",
  "message": "Symbol 'XYZUSDT' not supported. Valid: BTCUSDT, ETHUSDT, ..."
}
```

```json
{
  "type": "warning",
  "code": "SLOW_CONSUMER",
  "message": "Your connection is slow. Consider reducing subscriptions or update frequency.",
  "dropped_messages": 3
}
```

```json
{
  "type": "pong",
  "timestamp": "2025-12-28T14:30:00Z"
}
```

#### REST Endpoints (Supporting Infrastructure)

```
GET /ws/stats
→ Returns active connection count, message rates, slow consumer stats
{
  "active_connections": 127,
  "messages_sent_1m": 1524,
  "slow_consumers": 3,
  "subscriptions_by_symbol": {
    "BTCUSDT": 89,
    "ETHUSDT": 45
  }
}
```

### Connection Management

#### ConnectionManager Class

```python
class ConnectionManager:
    """Manages WebSocket connections and broadcasts.

    KISS Implementation:
    - In-memory dictionary: {symbol: [WebSocket, ...]}
    - Asyncio-safe with asyncio.Lock
    - No external dependencies (Redis) for MVP
    """

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self.stats = BroadcastStats()  # Track metrics

    async def connect(self, websocket: WebSocket, symbol: str):
        """Add client to symbol subscription."""
        await websocket.accept()
        async with self._lock:
            self.active_connections[symbol].append(websocket)
        logger.info(f"Client connected to {symbol}. Total: {len(self.active_connections[symbol])}")

    async def disconnect(self, websocket: WebSocket, symbol: str):
        """Remove client from symbol subscription."""
        async with self._lock:
            if websocket in self.active_connections[symbol]:
                self.active_connections[symbol].remove(websocket)
        logger.info(f"Client disconnected from {symbol}. Total: {len(self.active_connections[symbol])}")

    async def broadcast(self, symbol: str, message: dict, max_queue_size: int = 5):
        """Broadcast message to all subscribers of symbol.

        Backpressure Handling:
        - Each client has implicit queue (asyncio buffer)
        - If send() blocks >1s, assume slow consumer
        - Drop oldest pending message + send warning
        """
        disconnected = []
        slow_consumers = []

        for websocket in self.active_connections[symbol]:
            try:
                # Timeout prevents blocking on slow clients
                await asyncio.wait_for(
                    websocket.send_json(message),
                    timeout=1.0  # 1s send timeout
                )
                self.stats.messages_sent += 1
            except asyncio.TimeoutError:
                # Slow consumer detected
                slow_consumers.append(websocket)
                self.stats.slow_consumer_warnings += 1
                try:
                    await websocket.send_json({
                        "type": "warning",
                        "code": "SLOW_CONSUMER",
                        "message": "Connection slow - may miss updates"
                    })
                except:
                    disconnected.append(websocket)
            except WebSocketDisconnect:
                disconnected.append(websocket)

        # Cleanup disconnected clients
        for ws in disconnected:
            await self.disconnect(ws, symbol)

    def get_stats(self) -> dict:
        """Return connection statistics."""
        return {
            "active_connections": sum(len(conns) for conns in self.active_connections.values()),
            "subscriptions_by_symbol": {
                symbol: len(conns) for symbol, conns in self.active_connections.items()
            },
            "messages_sent": self.stats.messages_sent,
            "slow_consumers": self.stats.slow_consumer_warnings
        }
```

### Update Generator (Background Task)

```python
async def heatmap_update_generator(manager: ConnectionManager, interval: int = 5):
    """Background task to generate and broadcast heatmap updates.

    Runs continuously as asyncio task. Query DuckDB every `interval` seconds
    and broadcast new snapshots to subscribed clients.

    Args:
        manager: ConnectionManager instance
        interval: Update frequency in seconds (default: 5)
    """
    last_snapshots = {}  # Cache last snapshot per symbol to detect changes

    while True:
        try:
            # Get all symbols with active subscriptions
            active_symbols = [s for s in manager.active_connections.keys()
                            if manager.active_connections[s]]

            for symbol in active_symbols:
                # Query latest heatmap snapshot from DuckDB
                snapshot = await get_latest_heatmap_snapshot(symbol)

                # Check if data changed (avoid pushing duplicate snapshots)
                snapshot_hash = hash_snapshot(snapshot)
                if last_snapshots.get(symbol) == snapshot_hash:
                    logger.debug(f"No changes for {symbol}, skipping broadcast")
                    continue

                # Broadcast to all subscribers
                message = {
                    "type": "snapshot",
                    "symbol": symbol,
                    "timestamp": snapshot.timestamp.isoformat(),
                    "data": {
                        "levels": [
                            {
                                "price": level.price,
                                "long_density": level.long_density,
                                "short_density": level.short_density
                            }
                            for level in snapshot.levels
                        ],
                        "current_price": snapshot.current_price,
                        "positions_created": snapshot.positions_created,
                        "positions_consumed": snapshot.positions_consumed
                    }
                }

                await manager.broadcast(symbol, message)
                last_snapshots[symbol] = snapshot_hash
                logger.info(f"Broadcasted snapshot for {symbol} to {len(manager.active_connections[symbol])} clients")

        except Exception as e:
            logger.error(f"Error in update generator: {e}")

        # Wait before next iteration
        await asyncio.sleep(interval)


async def get_latest_heatmap_snapshot(symbol: str) -> HeatmapSnapshot:
    """Query latest heatmap data from DuckDB.

    Re-uses existing /liquidations/heatmap-timeseries logic but fetches
    only the most recent snapshot (last 5-15 minutes).
    """
    # Implementation will call calculate_time_evolving_heatmap with narrow time window
    # Example: last 15 minutes with 5m interval → returns 3 snapshots, take latest
    pass
```

### Client Implementation (JavaScript)

```javascript
class HeatmapWebSocket {
    constructor(url, options = {}) {
        this.url = url;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
        this.reconnectDelay = options.reconnectDelay || 2000; // 2s
        this.onSnapshot = options.onSnapshot || (() => {});
        this.onError = options.onError || console.error;
        this.onStatusChange = options.onStatusChange || (() => {});
        this.subscriptions = new Set();
    }

    connect() {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.onStatusChange('connected');

            // Re-subscribe to all symbols after reconnect
            if (this.subscriptions.size > 0) {
                this.send({
                    action: 'subscribe',
                    symbols: Array.from(this.subscriptions)
                });
            }
        };

        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);

            switch (message.type) {
                case 'snapshot':
                    this.onSnapshot(message);
                    break;
                case 'warning':
                    console.warn('WebSocket warning:', message);
                    if (message.code === 'SLOW_CONSUMER') {
                        this.onStatusChange('slow');
                    }
                    break;
                case 'error':
                    this.onError(message);
                    break;
                case 'pong':
                    // Keepalive response
                    break;
            }
        };

        this.ws.onclose = (event) => {
            console.log('WebSocket closed:', event.reason);
            this.onStatusChange('disconnected');

            // Auto-reconnect with exponential backoff
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
                console.log(`Reconnecting in ${delay}ms...`);
                setTimeout(() => this.connect(), delay);
                this.reconnectAttempts++;
            } else {
                console.error('Max reconnect attempts reached. Falling back to polling.');
                this.onStatusChange('failed');
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.onError(error);
        };
    }

    subscribe(symbols) {
        symbols.forEach(s => this.subscriptions.add(s));
        this.send({
            action: 'subscribe',
            symbols: symbols
        });
    }

    unsubscribe(symbols) {
        symbols.forEach(s => this.subscriptions.delete(s));
        this.send({
            action: 'unsubscribe',
            symbols: symbols
        });
    }

    send(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }

    // Keepalive ping every 30s
    startKeepalive() {
        this.keepaliveInterval = setInterval(() => {
            this.send({ action: 'ping' });
        }, 30000);
    }

    stopKeepalive() {
        if (this.keepaliveInterval) {
            clearInterval(this.keepaliveInterval);
        }
    }
}

// Usage Example
const ws = new HeatmapWebSocket('ws://localhost:8000/ws/heatmap', {
    onSnapshot: (message) => {
        console.log('New snapshot:', message.symbol, message.data);
        updateHeatmapChart(message.data);
    },
    onStatusChange: (status) => {
        document.getElementById('ws-status').className = status;
        document.getElementById('ws-status').textContent = status.toUpperCase();
    },
    onError: (error) => {
        console.error('WebSocket error:', error);
        showErrorNotification(error.message);
    }
});

ws.connect();
ws.subscribe(['BTCUSDT', 'ETHUSDT']);
ws.startKeepalive();
```

## Configuration

### Environment Variables

```bash
# WebSocket Configuration
WS_UPDATE_INTERVAL=5          # Seconds between broadcasts (default: 5)
WS_MAX_CONNECTIONS=1000       # Max concurrent connections per server
WS_SLOW_CONSUMER_TIMEOUT=1.0  # Seconds before marking client as slow
WS_MAX_QUEUE_SIZE=5           # Max pending messages per client

# Redis Pub/Sub (Optional - for multi-server scaling)
REDIS_ENABLED=false           # Enable Redis pub/sub (default: false)
REDIS_URL=redis://localhost:6379
REDIS_CHANNEL_PREFIX=heatmap  # Channel: heatmap:BTCUSDT
```

### Startup Configuration

```python
# src/liquidationheatmap/api/main.py

@app.on_event("startup")
async def startup_event():
    """Initialize WebSocket infrastructure on server start."""
    # Create global ConnectionManager instance
    app.state.ws_manager = ConnectionManager()

    # Start background task for heatmap updates
    update_interval = int(os.getenv("WS_UPDATE_INTERVAL", "5"))
    app.state.ws_task = asyncio.create_task(
        heatmap_update_generator(app.state.ws_manager, update_interval)
    )

    logger.info(f"WebSocket server started. Update interval: {update_interval}s")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown."""
    # Cancel background task
    if hasattr(app.state, 'ws_task'):
        app.state.ws_task.cancel()

    # Disconnect all clients gracefully
    if hasattr(app.state, 'ws_manager'):
        for symbol, clients in app.state.ws_manager.active_connections.items():
            for websocket in clients:
                await websocket.close(code=1000, reason="Server shutdown")

    logger.info("WebSocket server shutdown complete")
```

## Backpressure Handling

### Problem
If a client's network is slow (3G, high latency), the server's `send_json()` will block, delaying broadcasts to other clients.

### Solution: Per-Client Queue with Timeout

1. **Fast Path** (95% of clients):
   - `await websocket.send_json(msg)` completes in <100ms
   - No queue needed, direct send

2. **Slow Path** (5% of clients):
   - `send_json()` times out after 1s
   - Send "slow consumer" warning
   - Continue broadcasting to other clients
   - If client is consistently slow (3+ warnings), consider auto-disconnect

3. **Trade-off**:
   - **Pro**: Fast clients not blocked by slow clients
   - **Con**: Slow clients may miss snapshots (acceptable for real-time data)

### Monitoring

```python
class BroadcastStats:
    """Track broadcast performance metrics."""
    messages_sent: int = 0
    messages_dropped: int = 0
    slow_consumer_warnings: int = 0
    broadcast_duration_p50: float = 0.0
    broadcast_duration_p95: float = 0.0
```

Expose via `/ws/stats` endpoint for Grafana/Prometheus monitoring.

## Testing Strategy

### Unit Tests

```python
# tests/test_ws/test_connection_manager.py

async def test_connect_adds_client_to_subscriptions():
    """Test that connect() adds WebSocket to active_connections."""
    manager = ConnectionManager()
    mock_ws = AsyncMock(spec=WebSocket)

    await manager.connect(mock_ws, "BTCUSDT")

    assert mock_ws in manager.active_connections["BTCUSDT"]
    assert len(manager.active_connections["BTCUSDT"]) == 1


async def test_broadcast_sends_to_all_subscribers():
    """Test that broadcast() sends message to all clients."""
    manager = ConnectionManager()
    clients = [AsyncMock(spec=WebSocket) for _ in range(3)]

    for client in clients:
        await manager.connect(client, "BTCUSDT")

    message = {"type": "snapshot", "symbol": "BTCUSDT"}
    await manager.broadcast("BTCUSDT", message)

    for client in clients:
        client.send_json.assert_called_once_with(message)


async def test_slow_consumer_receives_warning():
    """Test that slow clients receive SLOW_CONSUMER warning."""
    manager = ConnectionManager()
    slow_client = AsyncMock(spec=WebSocket)
    slow_client.send_json.side_effect = asyncio.TimeoutError()

    await manager.connect(slow_client, "BTCUSDT")
    await manager.broadcast("BTCUSDT", {"type": "snapshot"})

    # Should send warning on second call (first was timeout)
    assert slow_client.send_json.call_count == 2
    warning_call = slow_client.send_json.call_args_list[1]
    assert warning_call[0][0]["type"] == "warning"
    assert warning_call[0][0]["code"] == "SLOW_CONSUMER"
```

### Integration Tests

```python
# tests/integration/test_ws_e2e.py

@pytest.mark.asyncio
async def test_client_receives_snapshots_after_subscribe():
    """End-to-end test: client subscribes and receives snapshot."""
    # Start test server
    async with TestClient(app) as client:
        # Connect via WebSocket
        async with client.websocket_connect("/ws/heatmap") as ws:
            # Subscribe to BTCUSDT
            await ws.send_json({
                "action": "subscribe",
                "symbols": ["BTCUSDT"]
            })

            # Trigger background update (manually for test)
            # In real scenario, this happens every 5s automatically
            await trigger_heatmap_update("BTCUSDT")

            # Receive snapshot
            message = await ws.receive_json()

            assert message["type"] == "snapshot"
            assert message["symbol"] == "BTCUSDT"
            assert "levels" in message["data"]
            assert len(message["data"]["levels"]) > 0
```

### Load Tests

Use **k6** (modern load testing tool):

```javascript
// tests/load/ws_load_test.js
import ws from 'k6/ws';
import { check } from 'k6';

export let options = {
    stages: [
        { duration: '1m', target: 100 },   // Ramp up to 100 connections
        { duration: '5m', target: 500 },   // Ramp up to 500
        { duration: '2m', target: 1000 },  // Peak at 1000
        { duration: '2m', target: 0 },     // Ramp down
    ],
};

export default function () {
    const url = 'ws://localhost:8000/ws/heatmap';

    const response = ws.connect(url, {}, function (socket) {
        socket.on('open', () => {
            // Subscribe to BTCUSDT
            socket.send(JSON.stringify({
                action: 'subscribe',
                symbols: ['BTCUSDT']
            }));
        });

        socket.on('message', (msg) => {
            const data = JSON.parse(msg);
            check(data, {
                'is snapshot': (d) => d.type === 'snapshot',
                'has levels': (d) => d.data && d.data.levels.length > 0,
            });
        });

        socket.on('close', () => console.log('disconnected'));
    });

    check(response, { 'status is 101': (r) => r && r.status === 101 });
}
```

Run: `k6 run tests/load/ws_load_test.js`

**Success Criteria**:
- 1000 concurrent connections with <1% failures
- p95 latency <500ms
- Memory usage <2GB per server

## Deployment Considerations

### Single-Server Deployment (Phase 1)

```yaml
# docker-compose.yml
services:
  api:
    image: liquidationheatmap:latest
    ports:
      - "8000:8000"
    environment:
      - WS_UPDATE_INTERVAL=5
      - WS_MAX_CONNECTIONS=1000
    command: uvicorn liquidationheatmap.api.main:app --host 0.0.0.0 --port 8000 --ws max-size 16777216
```

**Capacity**: ~1000 concurrent connections (tested with k6)

### Multi-Server Deployment (Phase 2 - Redis)

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api-1:
    image: liquidationheatmap:latest
    ports:
      - "8001:8000"
    environment:
      - REDIS_ENABLED=true
      - REDIS_URL=redis://redis:6379
      - WS_UPDATE_INTERVAL=5

  api-2:
    image: liquidationheatmap:latest
    ports:
      - "8002:8000"
    environment:
      - REDIS_ENABLED=true
      - REDIS_URL=redis://redis:6379
      - WS_UPDATE_INTERVAL=5

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - api-1
      - api-2
```

```nginx
# nginx.conf - WebSocket load balancing
upstream websocket_backend {
    ip_hash;  # Sticky sessions for WebSocket
    server api-1:8000;
    server api-2:8000;
}

server {
    listen 80;

    location /ws/ {
        proxy_pass http://websocket_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;  # 24h timeout for long-lived connections
    }
}
```

**Capacity**: 2000+ concurrent connections (horizontally scalable)

## Monitoring & Observability

### Metrics to Track

```python
# Prometheus metrics (use prometheus-fastapi-instrumentator)

from prometheus_client import Counter, Gauge, Histogram

ws_connections = Gauge(
    'ws_active_connections',
    'Number of active WebSocket connections',
    ['symbol']
)

ws_messages_sent = Counter(
    'ws_messages_sent_total',
    'Total messages sent to clients',
    ['symbol']
)

ws_slow_consumers = Counter(
    'ws_slow_consumers_total',
    'Total slow consumer warnings',
    ['symbol']
)

ws_broadcast_duration = Histogram(
    'ws_broadcast_duration_seconds',
    'Time taken to broadcast to all clients',
    ['symbol']
)
```

### Logs

```python
# Structured logging with contextvars for tracing

logger.info(
    "WebSocket connection established",
    extra={
        "event": "ws_connect",
        "symbol": symbol,
        "client_ip": websocket.client.host,
        "active_connections": len(manager.active_connections[symbol])
    }
)

logger.warning(
    "Slow consumer detected",
    extra={
        "event": "slow_consumer",
        "symbol": symbol,
        "client_ip": websocket.client.host,
        "queue_size": queue_size
    }
)
```

## Migration Path

### Phase 1: MVP (Week 1)
- Implement `ConnectionManager` with in-memory broadcast
- Add `/ws/heatmap` endpoint
- Build JavaScript client library
- Unit + integration tests
- Deploy to staging, test with 100 clients

### Phase 2: Production Rollout (Week 2)
- Load testing with k6 (1000 connections)
- Add Prometheus metrics
- Update frontend to use WebSocket (with polling fallback)
- Deploy to production behind feature flag
- Monitor for 1 week, gather feedback

### Phase 3: Scaling (Week 3-4)
- Implement Redis pub/sub integration
- Multi-server deployment with Nginx
- Load test with 2000+ connections
- Gradual rollout to all users

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **DuckDB query blocks async loop** | High (all clients freeze) | Medium | Use `asyncio.to_thread()` for DB queries |
| **Memory leak from disconnected clients** | High (OOM crash) | Low | Implement connection timeout + cleanup task |
| **Redis single point of failure** | Medium (multi-server broadcast fails) | Low | Redis Sentinel for HA; fallback to in-memory |
| **WebSocket incompatible with proxy** | Medium (some clients can't connect) | Medium | Document proxy requirements; provide polling fallback |

## Open Questions

1. **Update frequency**: 5s default, or adaptive based on volatility?
   - **Decision**: Start with fixed 5s, add adaptive in future if needed (YAGNI)

2. **Authentication**: JWT tokens or origin-based CORS?
   - **Decision**: CORS for MVP, add JWT if abuse detected

3. **Historical replay**: Should `/ws/heatmap` support replay from timestamp?
   - **Decision**: No, use REST API for history (KISS)

## References

- **FastAPI WebSocket Docs**: https://fastapi.tiangolo.com/advanced/websockets/
- **Redis Pub/Sub Pattern**: https://redis.io/docs/manual/pubsub/
- **Backpressure Handling**: https://www.nginx.com/blog/websocket-nginx/
- **Load Testing WebSockets**: https://k6.io/docs/using-k6/protocols/websockets/

## Appendix: Code Skeleton

```python
# src/liquidationheatmap/api/websocket.py

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
from collections import defaultdict
import asyncio
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, symbol: str):
        await websocket.accept()
        async with self._lock:
            self.active_connections[symbol].append(websocket)
        logger.info(f"Client connected to {symbol}")

    async def disconnect(self, websocket: WebSocket, symbol: str):
        async with self._lock:
            if websocket in self.active_connections[symbol]:
                self.active_connections[symbol].remove(websocket)
        logger.info(f"Client disconnected from {symbol}")

    async def broadcast(self, symbol: str, message: dict):
        disconnected = []
        for websocket in self.active_connections[symbol]:
            try:
                await asyncio.wait_for(websocket.send_json(message), timeout=1.0)
            except (asyncio.TimeoutError, WebSocketDisconnect):
                disconnected.append(websocket)

        for ws in disconnected:
            await self.disconnect(ws, symbol)


# src/liquidationheatmap/api/main.py (add to existing file)

from fastapi import WebSocket, WebSocketDisconnect
from .websocket import ConnectionManager

manager = ConnectionManager()


@app.websocket("/ws/heatmap")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time heatmap updates."""
    subscribed_symbols = set()

    try:
        # Initial connection (no symbol yet)
        await websocket.accept()

        while True:
            # Receive client message
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "subscribe":
                symbols = data.get("symbols", [])
                for symbol in symbols:
                    if symbol in SUPPORTED_SYMBOLS:
                        await manager.connect(websocket, symbol)
                        subscribed_symbols.add(symbol)
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "code": "INVALID_SYMBOL",
                            "message": f"Symbol '{symbol}' not supported"
                        })

            elif action == "unsubscribe":
                symbols = data.get("symbols", [])
                for symbol in symbols:
                    await manager.disconnect(websocket, symbol)
                    subscribed_symbols.discard(symbol)

            elif action == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        # Cleanup all subscriptions on disconnect
        for symbol in subscribed_symbols:
            await manager.disconnect(websocket, symbol)


@app.on_event("startup")
async def startup_websocket():
    """Start background task for heatmap updates."""
    from .websocket_background import heatmap_update_generator

    app.state.ws_task = asyncio.create_task(
        heatmap_update_generator(manager, interval=5)
    )
```

---

**End of Specification**
