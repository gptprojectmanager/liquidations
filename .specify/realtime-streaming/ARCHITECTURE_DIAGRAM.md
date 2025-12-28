# Real-time WebSocket Streaming - Architecture Diagram

## High-Level Data Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                          BROWSER CLIENT                               │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  HeatmapWebSocket Class (JavaScript)                       │     │
│  │  - Auto-reconnect (exponential backoff)                    │     │
│  │  - Symbol subscriptions: ["BTCUSDT", "ETHUSDT"]            │     │
│  │  - Connection status: connected | slow | disconnected      │     │
│  │  - Keepalive ping every 30s                                │     │
│  └────────────────────────────────────────────────────────────┘     │
│                            │                                         │
│                            │ WebSocket (wss://)                      │
│                            │ JSON Messages                           │
└────────────────────────────┼─────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    FASTAPI SERVER (Uvicorn)                          │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  /ws/heatmap WebSocket Endpoint                            │     │
│  │  - Handle subscribe/unsubscribe/ping actions               │     │
│  │  - Validate symbols against whitelist                      │     │
│  │  - Route messages to ConnectionManager                     │     │
│  └──────────────────────┬─────────────────────────────────────┘     │
│                         │                                            │
│                         ▼                                            │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  ConnectionManager (In-Memory)                             │     │
│  │  ┌──────────────────────────────────────────────┐          │     │
│  │  │  active_connections: dict                     │          │     │
│  │  │  {                                            │          │     │
│  │  │    "BTCUSDT": [WebSocket1, WebSocket2, ...], │          │     │
│  │  │    "ETHUSDT": [WebSocket3, WebSocket4, ...]  │          │     │
│  │  │  }                                            │          │     │
│  │  └──────────────────────────────────────────────┘          │     │
│  │                                                             │     │
│  │  Methods:                                                   │     │
│  │  - connect(ws, symbol) → Add to subscriptions              │     │
│  │  - disconnect(ws, symbol) → Remove from subscriptions      │     │
│  │  - broadcast(symbol, msg) → Send to all subscribers        │     │
│  │  - get_stats() → Connection metrics                        │     │
│  └──────────────────────┬─────────────────────────────────────┘     │
│                         │                                            │
│                         │ Receives broadcasts from                  │
│                         │                                            │
│                         ▼                                            │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Background Task: heatmap_update_generator()               │     │
│  │  - Runs async loop every 5 seconds (configurable)          │     │
│  │  - For each active symbol:                                 │     │
│  │    1. Query latest heatmap snapshot                        │     │
│  │    2. Check if data changed (hash comparison)              │     │
│  │    3. If changed → manager.broadcast(symbol, snapshot)     │     │
│  │  - Handles exceptions without crashing                     │     │
│  └──────────────────────┬─────────────────────────────────────┘     │
│                         │                                            │
│                         │ Queries                                   │
│                         │                                            │
└─────────────────────────┼────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       DUCKDB DATABASE                                 │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  klines_5m_history                                         │     │
│  │  - OHLCV data (5-minute candles)                           │     │
│  │  - Used for: Price movement tracking                       │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  open_interest_history                                     │     │
│  │  - Open Interest deltas                                    │     │
│  │  - Used for: Position creation/consumption                 │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                       │
│  Query: SELECT last 15 minutes of data → calculate_time_evolving_   │
│         heatmap() → return latest snapshot only                     │
└───────────────────────────────────────────────────────────────────────┘
```

## Message Flow Examples

### 1. Client Subscribes to Symbol

```
Client → Server:
{
  "action": "subscribe",
  "symbols": ["BTCUSDT"],
  "update_interval": 5
}

Server → ConnectionManager:
manager.connect(websocket, "BTCUSDT")

Response: None (silent success)
```

### 2. Background Task Broadcasts Snapshot

```
Background Task (every 5s):
1. Query DuckDB for latest BTCUSDT snapshot
2. Compare hash with last_snapshots["BTCUSDT"]
3. If changed:
   
   manager.broadcast("BTCUSDT", {
     "type": "snapshot",
     "symbol": "BTCUSDT",
     "timestamp": "2025-12-28T14:30:00Z",
     "data": {
       "levels": [
         {"price": 98000, "long_density": 1500000, "short_density": 200000}
       ],
       "current_price": 98450,
       "positions_created": 450,
       "positions_consumed": 120
     }
   })

ConnectionManager:
- For each WebSocket in active_connections["BTCUSDT"]:
  - await websocket.send_json(message) with 1s timeout
  - If timeout → send SLOW_CONSUMER warning
```

### 3. Slow Consumer Detection

```
Fast Client:
  send_json(msg) → completes in 50ms ✓

Slow Client:
  send_json(msg) → times out after 1000ms ✗
  
  Server → Slow Client:
  {
    "type": "warning",
    "code": "SLOW_CONSUMER",
    "message": "Connection slow - may miss updates"
  }
  
  Stats:
  slow_consumer_warnings += 1
```

## Phase 2: Multi-Server Architecture (Future)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NGINX LOAD BALANCER                           │
│  - IP hash for sticky WebSocket sessions                            │
│  - Upstream: server1:8000, server2:8000                             │
└─────────────┬───────────────────────────┬───────────────────────────┘
              │                           │
              ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐
    │  FastAPI        │         │  FastAPI        │
    │  Server 1       │         │  Server 2       │
    │  - Local clients│         │  - Local clients│
    └────────┬────────┘         └────────┬────────┘
             │                           │
             │   Subscribe to channels   │
             │                           │
             └─────────┬─────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │  REDIS PUB/SUB │
              │  Channels:     │
              │  - heatmap:BTC │
              │  - heatmap:ETH │
              └────────┬───────┘
                       │
                       ▼
          Background Task Publishes:
          PUBLISH heatmap:BTCUSDT {json}
          
          All Servers Receive:
          Subscribe to heatmap:* pattern
          → Broadcast to local clients
```

## Backpressure Handling Detail

```
ConnectionManager.broadcast(symbol, message):

  for websocket in active_connections[symbol]:
    ┌───────────────────────────────────────────┐
    │  Try: asyncio.wait_for(                   │
    │    websocket.send_json(message),          │
    │    timeout=1.0  ← 1 second deadline       │
    │  )                                        │
    └───────────────────────────────────────────┘
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
    ┌─────────┐         ┌──────────────┐
    │ Success │         │  Timeout     │
    │ <1000ms │         │  ≥1000ms     │
    └─────────┘         └──────┬───────┘
         │                     │
         │                     ▼
         │              Send SLOW_CONSUMER warning
         │              slow_consumer_warnings++
         │              Continue to next client
         │              (don't block other clients)
         │
         ▼
    Continue broadcasting
```

## Data Change Detection

```
Background Task Loop:

  last_snapshots = {}  # Cache: {symbol: hash}

  while True:
    for symbol in active_symbols:
      
      snapshot = get_latest_heatmap_snapshot(symbol)
      
      # Hash snapshot to detect changes
      snapshot_hash = hash(
        (snapshot.timestamp, 
         tuple(sorted(snapshot.levels)),
         snapshot.positions_created,
         snapshot.positions_consumed)
      )
      
      if last_snapshots.get(symbol) == snapshot_hash:
        logger.debug(f"No changes for {symbol}, skip")
        continue  ← Don't broadcast duplicates
      
      # Data changed → broadcast
      manager.broadcast(symbol, message)
      last_snapshots[symbol] = snapshot_hash
    
    await asyncio.sleep(5)  # Update interval
```

## Monitoring Integration

```
┌─────────────────────────────────────────────────────────────────┐
│  Prometheus Metrics                                             │
│                                                                  │
│  ws_active_connections{symbol="BTCUSDT"} = 127                  │
│  ws_messages_sent_total{symbol="BTCUSDT"} = 45231               │
│  ws_slow_consumers_total{symbol="BTCUSDT"} = 3                  │
│  ws_broadcast_duration_seconds{symbol="BTCUSDT",                │
│    quantile="0.95"} = 0.042                                     │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
                      Grafana Dashboard
                      - Active connections graph
                      - Message rate graph
                      - Slow consumer alerts
                      - Broadcast latency histogram
```

## Configuration Flow

```
Environment Variables:
  WS_ENABLED=true
  WS_UPDATE_INTERVAL=5
  WS_MAX_CONNECTIONS=1000
  WS_SLOW_CONSUMER_TIMEOUT=1.0
  REDIS_ENABLED=false  ← Phase 3
        │
        ▼
  app.on_event("startup"):
    if WS_ENABLED:
      manager = ConnectionManager()
      app.state.ws_manager = manager
      
      task = asyncio.create_task(
        heatmap_update_generator(
          manager, 
          interval=WS_UPDATE_INTERVAL
        )
      )
      app.state.ws_task = task
```

## Error Recovery

```
Client Disconnect:
  WebSocketDisconnect exception
  → manager.disconnect(websocket, symbol)
  → Remove from active_connections
  → Client auto-reconnects (exponential backoff)

Server Restart:
  app.on_event("shutdown")
  → Cancel background task
  → Close all WebSocket connections
  → Clients detect disconnect
  → Auto-reconnect after backoff

DuckDB Query Failure:
  try:
    snapshot = get_latest_heatmap_snapshot(symbol)
  except Exception as e:
    logger.error(f"Failed to query snapshot: {e}")
    continue  ← Skip this iteration, try again in 5s
```

---

**Key Takeaways**:
1. **KISS**: In-memory broadcast for Phase 1 (no Redis)
2. **Backpressure**: 1s timeout prevents slow clients blocking fast clients
3. **Efficiency**: Hash-based change detection avoids duplicate broadcasts
4. **Reliability**: Auto-reconnect + error recovery ensures uptime
5. **Scalability**: Redis pub/sub (Phase 3) enables multi-server deployment
