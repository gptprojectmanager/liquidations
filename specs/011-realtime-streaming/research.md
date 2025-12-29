# Research: Real-time WebSocket Streaming

**Date**: 2025-12-29
**Feature**: spec-011 (Real-time WebSocket Streaming)
**Status**: Complete

---

## 1. Dependency Analysis

### 1.1 FastAPI WebSocket Support

**Decision**: Use FastAPI's native WebSocket support (built-in)

**Rationale**:
- FastAPI has first-class WebSocket support via Starlette
- Already using FastAPI in project - zero new dependencies
- Async-native, integrates with existing event loop
- `websocket.accept()`, `send_json()`, `receive_json()` match our needs

**Alternatives Rejected**:
- `socket.io` (Python): Adds polling fallback complexity, heavier dependency
- `channels` (Django): Wrong framework, not async-native for our use case
- Raw `websockets` library: Would need to build routing ourselves

**Example Code**:
```python
from fastapi import WebSocket

@app.websocket("/ws/heatmap")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_json()
        await websocket.send_json({"type": "pong"})
```

### 1.2 Asyncio Background Tasks

**Decision**: Use `asyncio.create_task()` for background update generator

**Rationale**:
- Native Python async - no new dependencies
- Integrates with FastAPI startup/shutdown events
- Cancellable via `task.cancel()`
- Handles exceptions without crashing server

**Pattern**:
```python
@app.on_event("startup")
async def startup():
    app.state.ws_task = asyncio.create_task(
        heatmap_update_generator(manager, interval=5)
    )

@app.on_event("shutdown")
async def shutdown():
    app.state.ws_task.cancel()
```

### 1.3 Redis Pub/Sub (Phase 3)

**Decision**: Use `redis-py` with async support (already in pyproject.toml)

**Rationale**:
- `redis>=5.0.0` already in project dependencies
- Async pubsub via `aioredis` compatibility layer
- Simple channel-based messaging: `PUBLISH heatmap:BTCUSDT {json}`
- Horizontal scaling without code changes to broadcast logic

**Alternatives Rejected**:
- Apache Kafka: Overkill for real-time push, adds operational complexity
- RabbitMQ: Message queue semantics don't fit broadcast pattern
- Custom TCP: Reinventing the wheel

---

## 2. Existing Infrastructure Reuse

### 2.1 Heatmap Calculation Logic

**Finding**: `calculate_time_evolving_heatmap()` exists and produces snapshot data

**Decision**: Reuse existing calculation, wrap in `asyncio.to_thread()` for non-blocking

**Rationale**:
- Proven correct calculation logic
- DuckDB queries are CPU-bound, blocking async loop
- `asyncio.to_thread()` moves to thread pool, keeps event loop responsive

**Integration Pattern**:
```python
async def get_latest_heatmap_snapshot(symbol: str) -> HeatmapSnapshot:
    # Run blocking DuckDB query in thread pool
    return await asyncio.to_thread(
        calculate_time_evolving_heatmap,
        symbol=symbol,
        start_time=now - timedelta(minutes=15),
        interval_minutes=5
    )
```

### 2.2 Existing WebSocket Dependencies

**Finding**: `websockets>=12.0` already in pyproject.toml

**Decision**: No new WebSocket dependencies needed

**Verification**:
```toml
# pyproject.toml
dependencies = [
    ...
    "websockets>=12.0",
    ...
]
```

### 2.3 Frontend Infrastructure

**Finding**: `frontend/coinglass_heatmap.html` exists with Plotly.js charts

**Decision**: Add JavaScript WebSocket client, integrate with existing chart update logic

**Rationale**:
- Existing `updateHeatmapChart()` function can be called from WebSocket handler
- Connection status indicator fits existing UI pattern
- Polling fallback uses existing REST endpoint

---

## 3. Best Practices Research

### 3.1 WebSocket Connection Management

**Pattern: Per-Symbol Subscription Dictionary**

```python
class ConnectionManager:
    def __init__(self):
        # Thread-safe: {symbol: [websocket, ...]}
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()
```

**Rationale**:
- O(1) lookup for symbol broadcasts
- Easy cleanup on disconnect
- Lock prevents race conditions in async context

### 3.2 Backpressure Handling

**Pattern: Timeout-Based Slow Consumer Detection**

```python
async def broadcast(self, symbol: str, message: dict):
    for ws in self.active_connections[symbol]:
        try:
            await asyncio.wait_for(ws.send_json(message), timeout=1.0)
        except asyncio.TimeoutError:
            await self._warn_slow_consumer(ws)
```

**Rationale**:
- Fast clients (95%) complete in <100ms
- Slow clients timeout after 1s, receive warning
- No blocking of fast clients waiting for slow ones
- Graceful degradation over hard disconnection

### 3.3 Change Detection

**Pattern: Hash-Based Comparison**

```python
def hash_snapshot(snapshot: HeatmapSnapshot) -> str:
    """Create stable hash for change detection."""
    content = json.dumps(snapshot.to_dict(), sort_keys=True)
    return hashlib.md5(content.encode()).hexdigest()
```

**Rationale**:
- Avoid broadcasting duplicate data
- Reduces bandwidth and client processing
- MD5 sufficient for change detection (not security)

---

## 4. Technology Decisions Summary

| Component | Technology | Justification |
|-----------|------------|---------------|
| WebSocket Server | FastAPI (native) | Already using, async-native |
| Background Tasks | asyncio.create_task() | stdlib, no dependencies |
| Thread Pool | asyncio.to_thread() | Non-blocking DB queries |
| JS Client | Vanilla JavaScript | No build step, matches frontend pattern |
| Multi-Server | Redis pub/sub | Already in deps, proven pattern |
| Load Testing | k6 | Modern, WebSocket support, scriptable |

---

## 5. Open Questions Resolved

### Q1: Should we use Socket.IO for transport flexibility?

**Decision**: No - use raw WebSocket

**Rationale**:
- Socket.IO adds 200KB+ client library
- We don't need polling fallback (WebSocket is widely supported)
- Simpler debugging (standard WebSocket protocol)
- Frontend already uses fetch for REST, WebSocket is natural addition

### Q2: How to handle DuckDB blocking in async context?

**Decision**: `asyncio.to_thread()` for database queries

**Rationale**:
- DuckDB queries are CPU-bound (10-50ms typical)
- Blocking event loop = all WebSocket clients freeze
- Thread pool isolates blocking work
- No additional dependencies (Python 3.9+ stdlib)

### Q3: Message format - binary or JSON?

**Decision**: JSON

**Rationale**:
- Human-readable for debugging
- Direct integration with JavaScript `JSON.parse()`
- Compression can be added at WebSocket layer if needed
- Consistent with REST API format

### Q4: Reconnection strategy?

**Decision**: Exponential backoff with max 5 attempts, then polling fallback

**Rationale**:
- 2s, 4s, 8s, 16s, 32s delays prevent server overload on mass reconnect
- 5 attempts balances responsiveness with server protection
- Polling fallback ensures data availability on persistent failures
- Client-side logic, server doesn't need to track reconnections

---

## 6. Implementation Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| DuckDB blocks async loop | High | High | `asyncio.to_thread()` (T005) |
| Memory leak from zombie connections | Medium | High | Timeout + auto-cleanup (T003) |
| Slow consumer blocks broadcast | Medium | Medium | 1s timeout, continue to others (T003) |
| Redis SPOF in multi-server | Low | Medium | Fallback to in-memory, Redis Sentinel later |
| Frontend WebSocket not supported | Very Low | Low | All modern browsers support, polling fallback |

---

## 7. Performance Projections

### Single Server (MVP)

| Metric | Target | Based On |
|--------|--------|----------|
| Concurrent connections | 1000 | Uvicorn default worker capacity |
| Memory per connection | ~50KB | WebSocket buffer + state |
| Total memory for 1000 | ~50MB | Well under 2GB limit |
| Broadcast latency (1000 clients) | <100ms | Sequential send with timeout |
| Update frequency | 5s | Matches heatmap cache TTL |

### Multi-Server with Redis (Phase 3)

| Metric | Target | Based On |
|--------|--------|----------|
| Total connections | 2000+ | 1000 per server × N servers |
| Redis message latency | <10ms | Local network, small payloads |
| End-to-end latency | <500ms | Query + broadcast + network |

---

## 8. References

- [FastAPI WebSocket Documentation](https://fastapi.tiangolo.com/advanced/websockets/)
- [asyncio.to_thread() PEP 590](https://peps.python.org/pep-0590/)
- [Redis Pub/Sub Documentation](https://redis.io/docs/manual/pubsub/)
- [k6 WebSocket Testing Guide](https://k6.io/docs/using-k6/protocols/websockets/)
- [WebSocket Protocol RFC 6455](https://tools.ietf.org/html/rfc6455)

---

**Status**: All NEEDS CLARIFICATION items resolved. Ready for Phase 1 design.
