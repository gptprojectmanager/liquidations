# Implementation Tasks: Real-time WebSocket Streaming

> **Generated from**: spec.md
> **Status**: Ready for implementation
> **Estimated Duration**: 2-3 weeks (3 phases)

## Task Organization

Tasks are organized into 3 phases following the migration path in spec.md:
- **Phase 1**: MVP (Single-server, in-memory broadcast) - Week 1
- **Phase 2**: Production Rollout - Week 2
- **Phase 3**: Scaling (Redis pub/sub) - Week 3-4

Each task follows TDD workflow (RED → GREEN → REFACTOR).

---

## Phase 1: MVP Implementation (Week 1)

### T001: Create ConnectionManager class with in-memory broadcast

**Status**: Pending
**Priority**: P0 (Blocking)
**Estimated Time**: 2 hours
**Assignee**: quant-analyst

**Description**:
Implement `ConnectionManager` class to manage WebSocket connections and broadcast messages to subscribers.

**Acceptance Criteria**:
- [ ] `ConnectionManager` class created in `src/liquidationheatmap/api/websocket.py`
- [ ] Methods implemented:
  - `connect(websocket, symbol)` - Add client to subscription
  - `disconnect(websocket, symbol)` - Remove client
  - `broadcast(symbol, message)` - Send to all subscribers
  - `get_stats()` - Return connection statistics
- [ ] Thread-safe with `asyncio.Lock`
- [ ] In-memory storage: `dict[str, list[WebSocket]]`
- [ ] No external dependencies (Redis) for MVP

**TDD Steps**:
1. RED: Write test `test_connect_adds_client_to_subscriptions()`
2. GREEN: Implement `connect()` method
3. RED: Write test `test_broadcast_sends_to_all_subscribers()`
4. GREEN: Implement `broadcast()` method
5. REFACTOR: Extract stats tracking to `BroadcastStats` dataclass

**Files**:
- Create: `src/liquidationheatmap/api/websocket.py`
- Create: `tests/test_ws/test_connection_manager.py`

**Dependencies**: None

---

### T002: Add WebSocket endpoint `/ws/heatmap`

**Status**: Pending
**Priority**: P0 (Blocking)
**Estimated Time**: 3 hours
**Assignee**: quant-analyst

**Description**:
Create WebSocket endpoint in FastAPI to handle client connections, subscriptions, and message routing.

**Acceptance Criteria**:
- [ ] Endpoint added: `@app.websocket("/ws/heatmap")`
- [ ] Handles client messages:
  - `{"action": "subscribe", "symbols": [...]}`
  - `{"action": "unsubscribe", "symbols": [...]}`
  - `{"action": "ping"}` → responds with `{"type": "pong"}`
- [ ] Validates symbols against `SUPPORTED_SYMBOLS` whitelist
- [ ] Sends error message for invalid symbols
- [ ] Cleanup subscriptions on disconnect
- [ ] Integration with `ConnectionManager` from T001

**TDD Steps**:
1. RED: Write test `test_websocket_accepts_connection()`
2. GREEN: Implement basic endpoint with `websocket.accept()`
3. RED: Write test `test_subscribe_adds_to_manager()`
4. GREEN: Implement subscribe action
5. RED: Write test `test_invalid_symbol_returns_error()`
6. GREEN: Add symbol validation
7. REFACTOR: Extract message handlers to separate functions

**Files**:
- Edit: `src/liquidationheatmap/api/main.py`
- Create: `tests/integration/test_ws_endpoint.py`

**Dependencies**: T001

---

### T003: Implement backpressure handling for slow consumers

**Status**: Pending
**Priority**: P0 (Critical)
**Estimated Time**: 2 hours
**Assignee**: quant-analyst

**Description**:
Add timeout-based slow consumer detection to prevent fast clients from being blocked by slow clients.

**Acceptance Criteria**:
- [ ] `broadcast()` uses `asyncio.wait_for(send_json(), timeout=1.0)`
- [ ] On timeout, send `{"type": "warning", "code": "SLOW_CONSUMER"}`
- [ ] Track slow consumer count in `BroadcastStats`
- [ ] Disconnected clients automatically removed from subscriptions
- [ ] No blocking of fast clients when slow client times out

**TDD Steps**:
1. RED: Write test `test_slow_consumer_receives_warning()`
2. GREEN: Add timeout to `websocket.send_json()`
3. RED: Write test `test_fast_clients_not_blocked_by_slow_client()`
4. GREEN: Use `asyncio.wait_for()` with timeout
5. REFACTOR: Extract slow consumer logic to `_handle_slow_consumer()`

**Files**:
- Edit: `src/liquidationheatmap/api/websocket.py`
- Edit: `tests/test_ws/test_connection_manager.py`

**Dependencies**: T001

---

### T004: Create background task for heatmap updates

**Status**: Pending
**Priority**: P0 (Blocking)
**Estimated Time**: 4 hours
**Assignee**: quant-analyst

**Description**:
Implement async background task that generates heatmap snapshots and broadcasts to subscribers.

**Acceptance Criteria**:
- [ ] Function `heatmap_update_generator(manager, interval)` in new file
- [ ] Runs in infinite loop with `asyncio.sleep(interval)`
- [ ] Queries latest heatmap snapshot using existing logic
- [ ] Detects data changes (hash-based comparison)
- [ ] Broadcasts only if data changed (avoid duplicate snapshots)
- [ ] Handles exceptions without crashing
- [ ] Configurable update interval (default: 5s)

**TDD Steps**:
1. RED: Write test `test_update_generator_queries_active_symbols()`
2. GREEN: Implement symbol iteration loop
3. RED: Write test `test_skips_broadcast_if_no_changes()`
4. GREEN: Add hash-based change detection
5. RED: Write test `test_broadcasts_on_data_change()`
6. GREEN: Integrate with `manager.broadcast()`
7. REFACTOR: Extract `get_latest_heatmap_snapshot()` helper

**Files**:
- Create: `src/liquidationheatmap/api/websocket_background.py`
- Create: `tests/test_ws/test_update_generator.py`

**Dependencies**: T001

---

### T005: Implement `get_latest_heatmap_snapshot()` helper

**Status**: Pending
**Priority**: P0 (Blocking)
**Estimated Time**: 3 hours
**Assignee**: quant-analyst

**Description**:
Create helper function to query latest heatmap snapshot from DuckDB, re-using existing calculation logic.

**Acceptance Criteria**:
- [ ] Function signature: `async def get_latest_heatmap_snapshot(symbol: str) -> HeatmapSnapshot`
- [ ] Queries last 15 minutes of data with 5m interval
- [ ] Returns only the most recent snapshot
- [ ] Re-uses `calculate_time_evolving_heatmap()` from existing code
- [ ] Uses `asyncio.to_thread()` to avoid blocking event loop
- [ ] Handles empty data gracefully (returns None or empty snapshot)

**TDD Steps**:
1. RED: Write test `test_get_latest_snapshot_returns_most_recent()`
2. GREEN: Query DuckDB for last 15 minutes
3. RED: Write test `test_uses_asyncio_to_thread_for_db_query()`
4. GREEN: Wrap DB query in `asyncio.to_thread()`
5. RED: Write test `test_empty_data_returns_none()`
6. GREEN: Add empty data handling
7. REFACTOR: Extract time window calculation to constant

**Files**:
- Edit: `src/liquidationheatmap/api/websocket_background.py`
- Create: `tests/test_ws/test_snapshot_helper.py`

**Dependencies**: T004

---

### T006: Add startup/shutdown hooks for WebSocket task

**Status**: Pending
**Priority**: P0 (Blocking)
**Estimated Time**: 1 hour
**Assignee**: quant-analyst

**Description**:
Register background task on FastAPI startup and cleanup on shutdown.

**Acceptance Criteria**:
- [ ] `@app.on_event("startup")` creates `ConnectionManager` instance
- [ ] Stores manager in `app.state.ws_manager`
- [ ] Starts background task: `asyncio.create_task(heatmap_update_generator(...))`
- [ ] Stores task in `app.state.ws_task`
- [ ] `@app.on_event("shutdown")` cancels background task
- [ ] Disconnects all clients gracefully on shutdown
- [ ] Logs startup/shutdown events

**TDD Steps**:
1. RED: Write test `test_startup_creates_connection_manager()`
2. GREEN: Implement `startup_event()` function
3. RED: Write test `test_shutdown_cancels_background_task()`
4. GREEN: Implement `shutdown_event()` function
5. REFACTOR: Extract cleanup logic to separate function

**Files**:
- Edit: `src/liquidationheatmap/api/main.py`
- Create: `tests/integration/test_ws_lifecycle.py`

**Dependencies**: T001, T004

---

### T007: Create JavaScript WebSocket client library

**Status**: Pending
**Priority**: P1 (High)
**Estimated Time**: 4 hours
**Assignee**: visualization-renderer

**Description**:
Build reusable JavaScript class for WebSocket connection management with auto-reconnect.

**Acceptance Criteria**:
- [ ] Class `HeatmapWebSocket` in `frontend/js/websocket-client.js`
- [ ] Methods:
  - `connect()` - Establish WebSocket connection
  - `subscribe(symbols)` - Subscribe to symbol updates
  - `unsubscribe(symbols)` - Unsubscribe from symbols
  - `disconnect()` - Close connection
- [ ] Auto-reconnect with exponential backoff (max 5 attempts)
- [ ] Callbacks: `onSnapshot`, `onError`, `onStatusChange`
- [ ] Keepalive ping every 30s
- [ ] Handle all message types: snapshot, warning, error, pong

**TDD Steps**:
1. Write test: `test_connect_opens_websocket()`
2. Implement: `connect()` method
3. Write test: `test_auto_reconnect_on_disconnect()`
4. Implement: Auto-reconnect logic
5. Write test: `test_subscribe_sends_correct_message()`
6. Implement: `subscribe()` method
7. REFACTOR: Extract message handling to `_handleMessage()`

**Files**:
- Create: `frontend/js/websocket-client.js`
- Create: `frontend/tests/websocket-client.test.js` (optional)

**Dependencies**: T002

---

### T008: Add environment variable configuration

**Status**: Pending
**Priority**: P1 (High)
**Estimated Time**: 1 hour
**Assignee**: quant-analyst

**Description**:
Add WebSocket configuration via environment variables with sensible defaults.

**Acceptance Criteria**:
- [ ] Environment variables documented in `.env.template`:
  - `WS_UPDATE_INTERVAL=5` (seconds)
  - `WS_MAX_CONNECTIONS=1000`
  - `WS_SLOW_CONSUMER_TIMEOUT=1.0` (seconds)
  - `WS_MAX_QUEUE_SIZE=5`
- [ ] Variables read in `main.py` with `os.getenv()`
- [ ] Type conversion (int/float) with validation
- [ ] Defaults applied if not set
- [ ] Configuration logged on startup

**Files**:
- Edit: `.env.template`
- Edit: `src/liquidationheatmap/api/main.py`
- Edit: `src/liquidationheatmap/api/websocket.py`

**Dependencies**: None

---

### T009: Write unit tests for ConnectionManager

**Status**: Pending
**Priority**: P0 (Critical)
**Estimated Time**: 3 hours
**Assignee**: quant-analyst

**Description**:
Comprehensive unit tests for `ConnectionManager` class covering all edge cases.

**Acceptance Criteria**:
- [ ] Test: `test_connect_adds_client_to_subscriptions()`
- [ ] Test: `test_disconnect_removes_client_from_subscriptions()`
- [ ] Test: `test_broadcast_sends_to_all_subscribers()`
- [ ] Test: `test_broadcast_handles_disconnected_client()`
- [ ] Test: `test_slow_consumer_receives_warning()`
- [ ] Test: `test_get_stats_returns_correct_counts()`
- [ ] Test: `test_concurrent_connect_is_thread_safe()` (asyncio.Lock)
- [ ] All tests pass with 100% coverage

**Files**:
- Create: `tests/test_ws/test_connection_manager.py`

**Dependencies**: T001

---

### T010: Write integration tests for WebSocket endpoint

**Status**: Pending
**Priority**: P0 (Critical)
**Estimated Time**: 4 hours
**Assignee**: quant-analyst

**Description**:
End-to-end integration tests using FastAPI TestClient.

**Acceptance Criteria**:
- [ ] Test: `test_client_receives_snapshots_after_subscribe()`
- [ ] Test: `test_unsubscribe_stops_messages()`
- [ ] Test: `test_invalid_symbol_returns_error()`
- [ ] Test: `test_ping_returns_pong()`
- [ ] Test: `test_disconnect_removes_from_manager()`
- [ ] Test: `test_multiple_clients_same_symbol()`
- [ ] Test: `test_multiple_symbols_same_client()`
- [ ] All tests use `pytest-asyncio` and `TestClient`

**Files**:
- Create: `tests/integration/test_ws_endpoint.py`

**Dependencies**: T002, T004, T006

---

## Phase 2: Production Rollout (Week 2)

### T011: Add `/ws/stats` endpoint for monitoring

**Status**: Pending
**Priority**: P1 (High)
**Estimated Time**: 2 hours
**Assignee**: quant-analyst

**Description**:
Create REST endpoint to expose WebSocket connection statistics.

**Acceptance Criteria**:
- [ ] Endpoint: `GET /ws/stats`
- [ ] Returns JSON:
  ```json
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
- [ ] Uses `manager.get_stats()`
- [ ] No authentication required (internal monitoring endpoint)

**Files**:
- Edit: `src/liquidationheatmap/api/main.py`
- Create: `tests/test_api/test_ws_stats.py`

**Dependencies**: T001

---

### T012: Add Prometheus metrics for WebSocket

**Status**: Pending
**Priority**: P1 (High)
**Estimated Time**: 3 hours
**Assignee**: quant-analyst

**Description**:
Instrument WebSocket code with Prometheus metrics for Grafana monitoring.

**Acceptance Criteria**:
- [ ] Metrics added:
  - `ws_active_connections` (Gauge) - by symbol
  - `ws_messages_sent_total` (Counter) - by symbol
  - `ws_slow_consumers_total` (Counter) - by symbol
  - `ws_broadcast_duration_seconds` (Histogram) - by symbol
- [ ] Metrics exposed via `/metrics` endpoint (existing)
- [ ] Metrics updated in `ConnectionManager.broadcast()`
- [ ] Use `prometheus-client` library (already in dependencies)

**Files**:
- Edit: `src/liquidationheatmap/api/websocket.py`
- Edit: `pyproject.toml` (verify prometheus-client dependency)

**Dependencies**: T001

---

### T013: Add structured logging for WebSocket events

**Status**: Pending
**Priority**: P2 (Medium)
**Estimated Time**: 2 hours
**Assignee**: quant-analyst

**Description**:
Add comprehensive logging for debugging and monitoring.

**Acceptance Criteria**:
- [ ] Log events:
  - `ws_connect` - Client connects (with IP, symbol)
  - `ws_disconnect` - Client disconnects
  - `ws_subscribe` - Symbol subscription
  - `ws_unsubscribe` - Symbol unsubscription
  - `ws_broadcast` - Broadcast to N clients
  - `slow_consumer` - Slow consumer warning
  - `ws_error` - Any WebSocket error
- [ ] Use structured logging with `extra={}` context
- [ ] Log level: INFO for normal events, WARNING for slow consumers, ERROR for failures
- [ ] Include context: symbol, client_ip, active_connections

**Files**:
- Edit: `src/liquidationheatmap/api/websocket.py`
- Edit: `src/liquidationheatmap/api/main.py`

**Dependencies**: T001, T002

---

### T014: Create k6 load test script

**Status**: Pending
**Priority**: P1 (High)
**Estimated Time**: 3 hours
**Assignee**: quant-analyst

**Description**:
Write k6 load test to validate WebSocket performance under load.

**Acceptance Criteria**:
- [ ] Script: `tests/load/ws_load_test.js`
- [ ] Test stages:
  - Ramp up to 100 connections (1 minute)
  - Ramp up to 500 connections (5 minutes)
  - Peak at 1000 connections (2 minutes)
  - Ramp down (2 minutes)
- [ ] Checks:
  - Connection status is 101 (WebSocket upgrade)
  - Snapshot messages received
  - Message format valid
- [ ] Success criteria:
  - <1% connection failures
  - p95 latency <500ms
  - Memory usage <2GB

**Files**:
- Create: `tests/load/ws_load_test.js`
- Create: `docs/load_testing.md` (instructions)

**Dependencies**: T010

---

### T015: Update frontend to use WebSocket client

**Status**: Pending
**Priority**: P1 (High)
**Estimated Time**: 4 hours
**Assignee**: visualization-renderer

**Description**:
Integrate WebSocket client into existing `coinglass_heatmap.html` with polling fallback.

**Acceptance Criteria**:
- [ ] Import `websocket-client.js` in HTML
- [ ] Initialize WebSocket on page load
- [ ] Subscribe to selected symbol (from dropdown)
- [ ] Update heatmap chart on snapshot received
- [ ] Show connection status indicator (green/yellow/red)
- [ ] Fallback to polling if WebSocket fails 3 times
- [ ] Unsubscribe on symbol change
- [ ] Disconnect on page unload

**TDD Steps**:
1. Add connection status indicator to HTML
2. Initialize WebSocket client with callbacks
3. Test: Verify chart updates on snapshot
4. Implement: Chart update logic
5. Test: Verify fallback to polling after 3 failures
6. Implement: Fallback logic
7. REFACTOR: Extract chart update to `updateHeatmapFromSnapshot()`

**Files**:
- Edit: `frontend/coinglass_heatmap.html`
- Edit: `frontend/js/websocket-client.js` (if needed)

**Dependencies**: T007

---

### T016: Add feature flag for WebSocket

**Status**: Pending
**Priority**: P2 (Medium)
**Estimated Time**: 1 hour
**Assignee**: quant-analyst

**Description**:
Allow enabling/disabling WebSocket via environment variable for gradual rollout.

**Acceptance Criteria**:
- [ ] Environment variable: `WS_ENABLED=true` (default: true)
- [ ] If disabled, `/ws/heatmap` returns 503 Service Unavailable
- [ ] Background task not started if disabled
- [ ] Log warning on startup if disabled
- [ ] Frontend detects 503 and falls back to polling

**Files**:
- Edit: `src/liquidationheatmap/api/main.py`
- Edit: `.env.template`

**Dependencies**: T006

---

### T017: Deploy to staging environment

**Status**: Pending
**Priority**: P1 (High)
**Estimated Time**: 3 hours
**Assignee**: DevOps / quant-analyst

**Description**:
Deploy WebSocket-enabled API to staging for testing with real clients.

**Acceptance Criteria**:
- [ ] Staging environment updated with latest code
- [ ] Environment variables configured
- [ ] Uvicorn started with `--ws max-size 16777216`
- [ ] Test with 10 concurrent clients (manual)
- [ ] Verify metrics in Prometheus/Grafana
- [ ] Monitor logs for errors (1 hour)
- [ ] Document deployment steps in `docs/deployment.md`

**Files**:
- Create: `docs/deployment.md`
- Edit: `docker-compose.yml` (if using Docker)

**Dependencies**: T001-T015

---

### T018: Run k6 load test on staging

**Status**: Pending
**Priority**: P1 (High)
**Estimated Time**: 2 hours
**Assignee**: quant-analyst

**Description**:
Execute k6 load test against staging environment to validate performance.

**Acceptance Criteria**:
- [ ] Run: `k6 run tests/load/ws_load_test.js --vus 1000 --duration 10m`
- [ ] Results:
  - Connection success rate >99%
  - p95 latency <500ms
  - p99 latency <1000ms
  - Memory usage <2GB
  - CPU usage <80%
- [ ] Document results in `docs/load_testing_results.md`
- [ ] Identify and fix bottlenecks if any

**Files**:
- Create: `docs/load_testing_results.md`

**Dependencies**: T014, T017

---

### T019: Production deployment (gradual rollout)

**Status**: Pending
**Priority**: P1 (High)
**Estimated Time**: 4 hours
**Assignee**: DevOps / quant-analyst

**Description**:
Deploy to production with feature flag enabled for 10% of users initially.

**Acceptance Criteria**:
- [ ] Deploy code to production servers
- [ ] Set `WS_ENABLED=true` for canary server (10% traffic)
- [ ] Monitor for 24 hours:
  - Connection stability
  - Error rates
  - Slow consumer warnings
  - Memory/CPU usage
- [ ] Gradually increase to 50%, then 100%
- [ ] Rollback plan: Set `WS_ENABLED=false` if issues detected

**Files**:
- Edit: Production environment configuration

**Dependencies**: T018

---

## Phase 3: Scaling with Redis (Week 3-4)

### T020: Add Redis pub/sub integration

**Status**: Pending
**Priority**: P2 (Future)
**Estimated Time**: 6 hours
**Assignee**: quant-analyst

**Description**:
Implement Redis pub/sub to enable multi-server deployments.

**Acceptance Criteria**:
- [ ] Environment variable: `REDIS_ENABLED=false` (default: false)
- [ ] If enabled:
  - Connect to Redis: `REDIS_URL=redis://localhost:6379`
  - Subscribe to channels: `heatmap:BTCUSDT`, `heatmap:ETHUSDT`
  - Publish snapshots to Redis instead of direct broadcast
- [ ] Each server subscribes to Redis and broadcasts to local clients
- [ ] Graceful fallback to in-memory if Redis unavailable
- [ ] Connection pooling with `aioredis` library

**TDD Steps**:
1. RED: Write test `test_redis_publishes_snapshot()`
2. GREEN: Implement Redis publish in `heatmap_update_generator()`
3. RED: Write test `test_redis_subscriber_broadcasts_to_local_clients()`
4. GREEN: Add Redis subscriber task
5. RED: Write test `test_fallback_to_memory_if_redis_fails()`
6. GREEN: Implement fallback logic
7. REFACTOR: Extract Redis client to separate class

**Files**:
- Create: `src/liquidationheatmap/api/redis_pubsub.py`
- Edit: `src/liquidationheatmap/api/websocket_background.py`
- Create: `tests/test_ws/test_redis_pubsub.py`

**Dependencies**: T001, T004

---

### T021: Multi-server deployment with Nginx

**Status**: Pending
**Priority**: P2 (Future)
**Estimated Time**: 4 hours
**Assignee**: DevOps / quant-analyst

**Description**:
Configure Nginx for WebSocket load balancing across multiple API servers.

**Acceptance Criteria**:
- [ ] Nginx config: `nginx.conf` with WebSocket support
- [ ] Load balancing: `ip_hash` for sticky sessions
- [ ] Upstream servers: `api-1:8000`, `api-2:8000`
- [ ] WebSocket-specific headers:
  - `Upgrade: websocket`
  - `Connection: upgrade`
  - `proxy_read_timeout: 86400` (24h)
- [ ] Docker Compose setup with 2 API servers + Redis + Nginx
- [ ] Test: Client reconnects to same server (sticky sessions)

**Files**:
- Create: `nginx.conf`
- Edit: `docker-compose.yml`
- Create: `docs/multi_server_deployment.md`

**Dependencies**: T020

---

### T022: Load test multi-server setup

**Status**: Pending
**Priority**: P2 (Future)
**Estimated Time**: 3 hours
**Assignee**: quant-analyst

**Description**:
Validate multi-server deployment handles 2000+ concurrent connections.

**Acceptance Criteria**:
- [ ] Run k6 test against Nginx load balancer
- [ ] 2000 concurrent connections (1000 per server)
- [ ] Verify messages received from both servers
- [ ] Check Redis pub/sub working correctly
- [ ] Monitor metrics: connection distribution, latency, errors
- [ ] Document results

**Files**:
- Edit: `docs/load_testing_results.md`

**Dependencies**: T021

---

## Documentation Tasks

### T023: Write WebSocket API documentation

**Status**: Pending
**Priority**: P1 (High)
**Estimated Time**: 3 hours
**Assignee**: quant-analyst

**Description**:
Comprehensive documentation for WebSocket API usage.

**Acceptance Criteria**:
- [ ] Document created: `docs/websocket_api.md`
- [ ] Sections:
  - Connection URL
  - Message formats (client → server, server → client)
  - Example JavaScript code
  - Error codes and handling
  - Backpressure behavior
  - Deployment requirements
- [ ] Link from main `README.md`

**Files**:
- Create: `docs/websocket_api.md`
- Edit: `README.md`

**Dependencies**: T002, T007

---

### T024: Update ARCHITECTURE.md with WebSocket design

**Status**: Pending
**Priority**: P1 (High)
**Estimated Time**: 2 hours
**Assignee**: quant-analyst

**Description**:
Add WebSocket streaming section to architecture documentation.

**Acceptance Criteria**:
- [ ] New section: "Real-time Streaming (WebSocket)"
- [ ] Diagram: Client → WebSocket → ConnectionManager → Background Task
- [ ] Explain in-memory vs Redis pub/sub architectures
- [ ] Document configuration options
- [ ] Link to `docs/websocket_api.md`

**Files**:
- Edit: `docs/ARCHITECTURE.md`

**Dependencies**: T001, T004

---

### T025: Create troubleshooting guide

**Status**: Pending
**Priority**: P2 (Medium)
**Estimated Time**: 2 hours
**Assignee**: quant-analyst

**Description**:
Document common WebSocket issues and solutions.

**Acceptance Criteria**:
- [ ] Document: `docs/websocket_troubleshooting.md`
- [ ] Common issues:
  - "WebSocket connection failed" → Check proxy settings
  - "Slow consumer warning" → Reduce subscriptions
  - "Connection keeps disconnecting" → Check network stability
  - "No snapshots received" → Verify symbol is valid
- [ ] Include debugging commands (curl, wscat)
- [ ] Link from main docs

**Files**:
- Create: `docs/websocket_troubleshooting.md`

**Dependencies**: None

---

## Task Summary

**Total Tasks**: 25
**Estimated Duration**:
- Phase 1 (MVP): 28 hours → ~5 working days
- Phase 2 (Production): 30 hours → ~5 working days
- Phase 3 (Scaling): 13 hours → ~2 working days
- Documentation: 7 hours → ~1 working day

**Total**: ~13 working days (2.5 weeks with testing buffer)

## Dependencies Graph

```
Phase 1 (MVP):
T001 (ConnectionManager) → T002 (WS Endpoint) → T003 (Backpressure)
                        ↓
T004 (Background Task) → T005 (Snapshot Helper)
                        ↓
T006 (Startup/Shutdown) → T010 (Integration Tests)
                        ↓
T007 (JS Client) → T015 (Frontend Integration)
T008 (Config)
T009 (Unit Tests) → T010

Phase 2 (Production):
T011 (Stats Endpoint)
T012 (Prometheus)
T013 (Logging)
T014 (k6 Script) → T018 (Load Test Staging)
T015 (Frontend)
T016 (Feature Flag)
T017 (Staging Deploy) → T018 → T019 (Production)

Phase 3 (Scaling):
T020 (Redis Pub/Sub) → T021 (Nginx Multi-Server) → T022 (Load Test Multi-Server)

Documentation:
T023 (API Docs)
T024 (Architecture)
T025 (Troubleshooting)
```

## Priority Levels

- **P0 (Blocking)**: Must complete before moving to next phase
- **P1 (High)**: Important for production readiness
- **P2 (Medium)**: Nice to have, can defer if time-constrained

## Risk Mitigation

| Task | Risk | Mitigation |
|------|------|------------|
| T004 | DuckDB blocks event loop | Use `asyncio.to_thread()` (T005) |
| T003 | Memory leak from slow clients | Timeout + auto-disconnect |
| T018 | Load test fails at 1000 clients | Optimize broadcast, add Redis (T020) |
| T020 | Redis single point of failure | Fallback to in-memory, add Redis Sentinel later |

---

**Next Steps**:
1. Start with T001 (ConnectionManager) - foundation for everything
2. Follow TDD workflow: RED → GREEN → REFACTOR
3. Run `uv run pytest` after each GREEN step
4. Commit after each task completion
5. Deploy to staging after Phase 1 complete (T017)

**Questions?** See `docs/websocket_troubleshooting.md` or ask in team chat.
