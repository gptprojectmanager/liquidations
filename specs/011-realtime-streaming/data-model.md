# Data Model: Real-time WebSocket Streaming

**Date**: 2025-12-29
**Feature**: spec-011 (Real-time WebSocket Streaming)
**Source**: [spec.md](./spec.md)

---

## 1. Core Entities

### 1.1 HeatmapSnapshot

The data structure broadcast to subscribed clients.

```python
@dataclass
class HeatmapSnapshot:
    """A point-in-time heatmap snapshot for WebSocket broadcast.

    Attributes:
        symbol: Trading pair (e.g., "BTCUSDT")
        timestamp: When snapshot was generated (UTC)
        current_price: Latest market price
        levels: List of liquidation levels with densities
        positions_created: New positions since last snapshot
        positions_consumed: Liquidated positions since last snapshot
    """
    symbol: str
    timestamp: datetime
    current_price: Decimal
    levels: list[LiquidationLevel]
    positions_created: int = 0
    positions_consumed: int = 0

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "current_price": str(self.current_price),
            "levels": [level.to_dict() for level in self.levels],
            "positions_created": self.positions_created,
            "positions_consumed": self.positions_consumed,
        }
```

### 1.2 LiquidationLevel

Individual price level within a snapshot.

```python
@dataclass
class LiquidationLevel:
    """A single liquidation level in the heatmap.

    Attributes:
        price: Price level (e.g., 98000.0)
        long_density: Long liquidation volume in USD
        short_density: Short liquidation volume in USD
    """
    price: Decimal
    long_density: Decimal
    short_density: Decimal

    def to_dict(self) -> dict:
        return {
            "price": float(self.price),
            "long_density": float(self.long_density),
            "short_density": float(self.short_density),
        }
```

### 1.3 BroadcastStats

Connection and performance statistics.

```python
@dataclass
class BroadcastStats:
    """Statistics for monitoring WebSocket performance.

    Attributes:
        messages_sent: Total messages broadcast
        messages_dropped: Messages dropped due to backpressure
        slow_consumer_warnings: Number of slow consumer warnings sent
        broadcast_duration_p50: Median broadcast duration (seconds)
        broadcast_duration_p95: 95th percentile broadcast duration
    """
    messages_sent: int = 0
    messages_dropped: int = 0
    slow_consumer_warnings: int = 0
    broadcast_duration_p50: float = 0.0
    broadcast_duration_p95: float = 0.0
```

---

## 2. WebSocket Message Schemas

### 2.1 Client → Server Messages

#### Subscribe Request
```json
{
  "action": "subscribe",
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "update_interval": 5
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| action | string | Yes | Must be "subscribe" |
| symbols | string[] | Yes | List of trading pairs to subscribe to |
| update_interval | int | No | Seconds between updates (default: 5) |

#### Unsubscribe Request
```json
{
  "action": "unsubscribe",
  "symbols": ["ETHUSDT"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| action | string | Yes | Must be "unsubscribe" |
| symbols | string[] | Yes | List of trading pairs to unsubscribe from |

#### Ping (Keepalive)
```json
{
  "action": "ping"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| action | string | Yes | Must be "ping" |

### 2.2 Server → Client Messages

#### Snapshot Message
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

| Field | Type | Description |
|-------|------|-------------|
| type | string | Always "snapshot" |
| symbol | string | Trading pair |
| timestamp | string | ISO 8601 timestamp (UTC) |
| data.levels | array | Liquidation levels |
| data.levels[].price | number | Price level |
| data.levels[].long_density | number | Long volume (USD) |
| data.levels[].short_density | number | Short volume (USD) |
| data.current_price | number | Latest market price |
| data.positions_created | int | New positions count |
| data.positions_consumed | int | Liquidated positions count |

#### Error Message
```json
{
  "type": "error",
  "code": "INVALID_SYMBOL",
  "message": "Symbol 'XYZUSDT' not supported. Valid: BTCUSDT, ETHUSDT, ..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| type | string | Always "error" |
| code | string | Error code (see Error Codes below) |
| message | string | Human-readable error description |

#### Warning Message
```json
{
  "type": "warning",
  "code": "SLOW_CONSUMER",
  "message": "Your connection is slow. Consider reducing subscriptions.",
  "dropped_messages": 3
}
```

| Field | Type | Description |
|-------|------|-------------|
| type | string | Always "warning" |
| code | string | Warning code |
| message | string | Human-readable warning |
| dropped_messages | int | Optional: Number of dropped messages |

#### Pong Response
```json
{
  "type": "pong",
  "timestamp": "2025-12-28T14:30:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| type | string | Always "pong" |
| timestamp | string | Server timestamp (UTC) |

---

## 3. Error Codes

| Code | HTTP Equiv | Description |
|------|------------|-------------|
| INVALID_SYMBOL | 400 | Symbol not in supported list |
| INVALID_ACTION | 400 | Unknown action type |
| INVALID_MESSAGE | 400 | Malformed JSON or missing fields |
| RATE_LIMITED | 429 | Too many subscriptions or messages |
| SERVER_ERROR | 500 | Internal server error |

---

## 4. Warning Codes

| Code | Description | Client Action |
|------|-------------|---------------|
| SLOW_CONSUMER | Client receiving data slower than server sending | Reduce subscriptions or improve network |
| CONNECTION_UNSTABLE | Frequent disconnections detected | Check network stability |

---

## 5. Connection State

### ConnectionManager State

```python
class ConnectionManager:
    """Internal state for WebSocket connection management."""

    # Symbol -> List of WebSocket connections
    active_connections: dict[str, list[WebSocket]] = defaultdict(list)

    # Thread safety lock
    _lock: asyncio.Lock

    # Performance statistics
    stats: BroadcastStats
```

### Client Subscription State (JavaScript)

```javascript
class HeatmapWebSocket {
    // WebSocket instance
    ws: WebSocket | null

    // Active symbol subscriptions
    subscriptions: Set<string>

    // Reconnection tracking
    reconnectAttempts: number
    maxReconnectAttempts: number  // Default: 5
    reconnectDelay: number        // Default: 2000ms

    // Connection status
    status: 'connecting' | 'connected' | 'slow' | 'disconnected' | 'failed'

    // Keepalive timer
    keepaliveInterval: number | null
}
```

---

## 6. Validation Rules

### Symbol Validation

```python
SUPPORTED_SYMBOLS = {"BTCUSDT", "ETHUSDT"}  # Extend as needed

def validate_symbols(symbols: list[str]) -> tuple[list[str], list[str]]:
    """Validate symbol list.

    Returns:
        (valid_symbols, invalid_symbols)
    """
    valid = [s for s in symbols if s in SUPPORTED_SYMBOLS]
    invalid = [s for s in symbols if s not in SUPPORTED_SYMBOLS]
    return valid, invalid
```

### Update Interval Validation

```python
MIN_UPDATE_INTERVAL = 1   # seconds
MAX_UPDATE_INTERVAL = 60  # seconds
DEFAULT_UPDATE_INTERVAL = 5

def validate_interval(interval: int | None) -> int:
    """Validate and normalize update interval."""
    if interval is None:
        return DEFAULT_UPDATE_INTERVAL
    return max(MIN_UPDATE_INTERVAL, min(interval, MAX_UPDATE_INTERVAL))
```

---

## 7. State Transitions

### Connection Lifecycle

```
[Initial]
    │
    ▼ connect()
[Connecting] ──────────────────────────────────┐
    │                                          │
    │ onopen                                   │ onerror/onclose
    ▼                                          ▼
[Connected] ◄───────────────────────── [Reconnecting]
    │                                          │
    │ send(subscribe)                          │ attempts < max
    ▼                                          │
[Subscribed] ◄─────────────────────────────────┘
    │
    │ slow consumer warning
    ▼
[Slow] ──────────────────────────────────────┐
    │                                        │
    │ recovers                               │ 3+ consecutive failures
    ▼                                        ▼
[Connected/Subscribed]                    [Failed]
                                             │
                                             ▼
                                         [Polling Fallback]
```

### Message Processing Flow

```
Client Message Received
    │
    ▼
Parse JSON ──── Invalid ──► Send error: INVALID_MESSAGE
    │
    ▼
Check action ─── Unknown ──► Send error: INVALID_ACTION
    │
    ├── subscribe ──► Validate symbols ──► Add to connections
    │                      │
    │                      └── Invalid ──► Send error: INVALID_SYMBOL
    │
    ├── unsubscribe ──► Remove from connections
    │
    └── ping ──► Send pong
```

---

## 8. Environment Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| WS_UPDATE_INTERVAL | int | 5 | Seconds between broadcasts |
| WS_MAX_CONNECTIONS | int | 1000 | Max concurrent connections |
| WS_SLOW_CONSUMER_TIMEOUT | float | 1.0 | Seconds before slow consumer warning |
| WS_MAX_QUEUE_SIZE | int | 5 | Max pending messages per client |
| WS_ENABLED | bool | true | Feature flag for WebSocket |
| REDIS_ENABLED | bool | false | Enable Redis pub/sub (Phase 3) |
| REDIS_URL | string | redis://localhost:6379 | Redis connection URL |
| REDIS_CHANNEL_PREFIX | string | heatmap | Channel prefix (e.g., heatmap:BTCUSDT) |

---

## 9. Database Schema

No new database tables required. WebSocket state is ephemeral (in-memory).

Redis pub/sub (Phase 3) uses channel-based messaging:
- Channel format: `{REDIS_CHANNEL_PREFIX}:{symbol}` (e.g., `heatmap:BTCUSDT`)
- Message format: JSON-serialized HeatmapSnapshot

---

## 10. Relationships

```
┌─────────────────────┐
│  ConnectionManager  │
│  (Singleton)        │
├─────────────────────┤
│  active_connections │──────┐
│  stats              │      │
│  _lock              │      │
└─────────────────────┘      │
                             │ 1:N per symbol
                             ▼
┌─────────────────────┐    ┌─────────────────────┐
│  HeatmapSnapshot    │    │  WebSocket          │
├─────────────────────┤    │  Connection         │
│  symbol             │    ├─────────────────────┤
│  timestamp          │    │  client_ip          │
│  current_price      │    │  subscribed_symbols │
│  levels[]           │    └─────────────────────┘
│  positions_created  │              │
│  positions_consumed │              │ receives
└─────────────────────┘              ▼
         │                  ┌─────────────────────┐
         │                  │  WebSocket Message  │
         │ broadcast        │  (snapshot)         │
         └─────────────────►├─────────────────────┤
                            │  type               │
                            │  symbol             │
                            │  timestamp          │
                            │  data               │
                            └─────────────────────┘
```
