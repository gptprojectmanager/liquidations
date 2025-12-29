# Tasks: Real-time WebSocket Streaming

**Input**: Design documents from `/specs/011-realtime-streaming/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: TDD approach required per constitution - tests included for each user story.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Includes exact file paths in descriptions

## User Stories (from spec.md)

| Story | Title | Priority |
|-------|-------|----------|
| US1 | Real-time Trader Dashboard | P1 (MVP) |
| US2 | Multi-Symbol Monitoring | P2 |
| US3 | Graceful Degradation | P3 |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and WebSocket module structure

- [ ] T001 Create WebSocket module structure: `src/liquidationheatmap/api/websocket.py`
- [ ] T002 Create background task module: `src/liquidationheatmap/api/websocket_background.py`
- [ ] T003 [P] Create test directories: `tests/test_ws/` and `tests/integration/`
- [ ] T004 [P] Add environment variables to `.env.template` (WS_UPDATE_INTERVAL, WS_MAX_CONNECTIONS, etc.)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core WebSocket infrastructure that MUST be complete before ANY user story

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Create BroadcastStats dataclass in `src/liquidationheatmap/api/websocket.py`
- [ ] T006 Create HeatmapSnapshot and LiquidationLevel dataclasses in `src/liquidationheatmap/api/websocket.py`
- [ ] T007 [P] Define SUPPORTED_SYMBOLS constant in `src/liquidationheatmap/api/websocket.py`
- [ ] T008 [P] Add symbol validation helper `validate_symbols()` in `src/liquidationheatmap/api/websocket.py`
- [ ] T009 [P] Add interval validation helper `validate_interval()` in `src/liquidationheatmap/api/websocket.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Real-time Trader Dashboard (Priority: P1) MVP

**Goal**: Day traders see heatmap updates in real-time without refreshing

**Acceptance Criteria**:
- WebSocket connection established on page load
- New snapshots appear within 1 second of generation
- Connection auto-reconnects if dropped
- Visual indicator shows connection status (green = live, red = disconnected)

**Independent Test**: Connect to `/ws/heatmap`, subscribe to BTCUSDT, verify snapshots arrive every 5s

### Tests for User Story 1

- [ ] T010 [P] [US1] Unit test: `test_connect_adds_client_to_subscriptions()` in `tests/test_ws/test_connection_manager.py`
- [ ] T011 [P] [US1] Unit test: `test_disconnect_removes_client()` in `tests/test_ws/test_connection_manager.py`
- [ ] T012 [P] [US1] Unit test: `test_broadcast_sends_to_all_subscribers()` in `tests/test_ws/test_connection_manager.py`
- [ ] T013 [P] [US1] Integration test: `test_websocket_accepts_connection()` in `tests/integration/test_ws_endpoint.py`
- [ ] T014 [P] [US1] Integration test: `test_subscribe_adds_to_manager()` in `tests/integration/test_ws_endpoint.py`

### Implementation for User Story 1

- [ ] T015 [US1] Implement ConnectionManager class with `__init__`, `_lock`, `active_connections` in `src/liquidationheatmap/api/websocket.py`
- [ ] T016 [US1] Implement `connect()` method in ConnectionManager in `src/liquidationheatmap/api/websocket.py`
- [ ] T017 [US1] Implement `disconnect()` method in ConnectionManager in `src/liquidationheatmap/api/websocket.py`
- [ ] T018 [US1] Implement `broadcast()` method (basic, without backpressure) in `src/liquidationheatmap/api/websocket.py`
- [ ] T019 [US1] Implement `get_stats()` method in ConnectionManager in `src/liquidationheatmap/api/websocket.py`
- [ ] T020 [US1] Add WebSocket endpoint `@app.websocket("/ws/heatmap")` in `src/liquidationheatmap/api/main.py`
- [ ] T021 [US1] Implement subscribe action handler in WebSocket endpoint in `src/liquidationheatmap/api/main.py`
- [ ] T022 [US1] Implement ping/pong action handler in WebSocket endpoint in `src/liquidationheatmap/api/main.py`
- [ ] T023 [US1] Implement `get_latest_heatmap_snapshot()` helper in `src/liquidationheatmap/api/websocket_background.py`
- [ ] T024 [US1] Implement `hash_snapshot()` for change detection in `src/liquidationheatmap/api/websocket_background.py`
- [ ] T025 [US1] Implement `heatmap_update_generator()` background task in `src/liquidationheatmap/api/websocket_background.py`
- [ ] T026 [US1] Add startup hook to create ConnectionManager and start background task in `src/liquidationheatmap/api/main.py`
- [ ] T027 [US1] Add shutdown hook to cancel background task and disconnect clients in `src/liquidationheatmap/api/main.py`
- [ ] T028 [P] [US1] Create JavaScript WebSocket client class in `frontend/js/websocket-client.js`
- [ ] T029 [P] [US1] Implement `connect()` method with auto-reconnect in `frontend/js/websocket-client.js`
- [ ] T030 [P] [US1] Implement `subscribe()` method in `frontend/js/websocket-client.js`
- [ ] T031 [US1] Implement connection status indicator in `frontend/coinglass_heatmap.html`
- [ ] T032 [US1] Integrate WebSocket client with heatmap chart update in `frontend/coinglass_heatmap.html`

**Checkpoint**: User Story 1 complete - single symbol real-time updates working

---

## Phase 4: User Story 2 - Multi-Symbol Monitoring (Priority: P2)

**Goal**: Portfolio managers subscribe to multiple symbols (BTC, ETH) simultaneously

**Acceptance Criteria**:
- Client can subscribe to multiple symbols (e.g., `["BTCUSDT", "ETHUSDT"]`)
- Each symbol sends independent updates
- Bandwidth proportional to number of subscribed symbols
- Unsubscribe from individual symbols without reconnecting

**Independent Test**: Subscribe to BTCUSDT and ETHUSDT, verify both receive independent updates

### Tests for User Story 2

- [ ] T033 [P] [US2] Unit test: `test_client_subscribes_to_multiple_symbols()` in `tests/test_ws/test_connection_manager.py`
- [ ] T034 [P] [US2] Unit test: `test_broadcast_only_to_symbol_subscribers()` in `tests/test_ws/test_connection_manager.py`
- [ ] T035 [P] [US2] Integration test: `test_unsubscribe_stops_messages()` in `tests/integration/test_ws_endpoint.py`
- [ ] T036 [P] [US2] Integration test: `test_multiple_symbols_same_client()` in `tests/integration/test_ws_endpoint.py`

### Implementation for User Story 2

- [ ] T037 [US2] Implement unsubscribe action handler in WebSocket endpoint in `src/liquidationheatmap/api/main.py`
- [ ] T038 [US2] Add per-client subscription tracking (set of symbols) in WebSocket endpoint in `src/liquidationheatmap/api/main.py`
- [ ] T039 [US2] Implement `unsubscribe()` method in JavaScript client in `frontend/js/websocket-client.js`
- [ ] T040 [US2] Update heatmap update generator to iterate all active symbols in `src/liquidationheatmap/api/websocket_background.py`
- [ ] T041 [US2] Add ETHUSDT support to SUPPORTED_SYMBOLS in `src/liquidationheatmap/api/websocket.py`

**Checkpoint**: User Story 2 complete - multi-symbol subscriptions working

---

## Phase 5: User Story 3 - Graceful Degradation (Priority: P3)

**Goal**: Mobile users on slow connections don't miss critical updates or crash

**Acceptance Criteria**:
- Client receives "slow consumer" warning if queue fills up
- Server drops oldest messages (not newest) when backpressure occurs
- Client UI shows warning: "Connection slow - may miss updates"
- Auto-fallback to polling if WebSocket fails 3 times

**Independent Test**: Simulate slow client (delay receives), verify warning sent and fast clients unaffected

### Tests for User Story 3

- [ ] T042 [P] [US3] Unit test: `test_slow_consumer_receives_warning()` in `tests/test_ws/test_connection_manager.py`
- [ ] T043 [P] [US3] Unit test: `test_fast_clients_not_blocked_by_slow_client()` in `tests/test_ws/test_connection_manager.py`
- [ ] T044 [P] [US3] Unit test: `test_disconnected_client_removed_on_broadcast()` in `tests/test_ws/test_connection_manager.py`
- [ ] T045 [P] [US3] Integration test: `test_slow_consumer_warning_sent()` in `tests/integration/test_ws_endpoint.py`

### Implementation for User Story 3

- [ ] T046 [US3] Add `asyncio.wait_for()` timeout to `broadcast()` method in `src/liquidationheatmap/api/websocket.py`
- [ ] T047 [US3] Implement `_warn_slow_consumer()` helper method in `src/liquidationheatmap/api/websocket.py`
- [ ] T048 [US3] Track slow_consumer_warnings in BroadcastStats in `src/liquidationheatmap/api/websocket.py`
- [ ] T049 [US3] Auto-remove disconnected clients in `broadcast()` method in `src/liquidationheatmap/api/websocket.py`
- [ ] T050 [US3] Add slow consumer detection to JavaScript client in `frontend/js/websocket-client.js`
- [ ] T051 [US3] Implement polling fallback after 3 WebSocket failures in `frontend/js/websocket-client.js`
- [ ] T052 [US3] Add "Connection slow" warning UI in `frontend/coinglass_heatmap.html`

**Checkpoint**: User Story 3 complete - graceful degradation working

---

## Phase 6: Production Readiness

**Purpose**: Monitoring, logging, and deployment preparation

### Monitoring & Stats

- [ ] T053 [P] Add `/ws/stats` REST endpoint in `src/liquidationheatmap/api/main.py`
- [ ] T054 [P] Add Prometheus metrics (ws_active_connections, ws_messages_sent_total) in `src/liquidationheatmap/api/websocket.py`
- [ ] T055 [P] Add structured logging for ws_connect, ws_disconnect, ws_broadcast events in `src/liquidationheatmap/api/websocket.py`

### Load Testing

- [ ] T056 [P] Create k6 load test script in `tests/load/ws_load_test.js`
- [ ] T057 Run k6 load test: 1000 concurrent connections, validate <1% failures

### Feature Flag

- [ ] T058 Add WS_ENABLED environment variable in `src/liquidationheatmap/api/main.py`
- [ ] T059 Return 503 if WebSocket disabled in `src/liquidationheatmap/api/main.py`

---

## Phase 7: Documentation & Polish

**Purpose**: API documentation and code cleanup

- [ ] T060 [P] Create WebSocket API documentation in `docs/websocket_api.md`
- [ ] T061 [P] Update ARCHITECTURE.md with WebSocket streaming section in `docs/ARCHITECTURE.md`
- [ ] T062 [P] Create troubleshooting guide in `docs/websocket_troubleshooting.md`
- [ ] T063 Run quickstart.md validation (manual test with examples)
- [ ] T064 Code cleanup: remove debug statements, add docstrings
- [ ] T065 Final test run: `uv run pytest tests/test_ws/ tests/integration/`

---

## Phase 8: Redis Pub/Sub Scaling (Future Enhancement)

**Purpose**: Enable horizontal scaling across multiple API servers via Redis pub/sub

**Prerequisites**: All user stories (Phase 3-5) complete

### Tests for Redis Integration

- [ ] T066 [P] Unit test: `test_redis_publishes_snapshot()` in `tests/test_ws/test_redis_pubsub.py`
- [ ] T067 [P] Unit test: `test_redis_subscriber_broadcasts_to_local_clients()` in `tests/test_ws/test_redis_pubsub.py`
- [ ] T068 [P] Unit test: `test_fallback_to_memory_if_redis_fails()` in `tests/test_ws/test_redis_pubsub.py`
- [ ] T069 [P] Integration test: `test_multi_server_message_delivery()` in `tests/integration/test_redis_scaling.py`

### Implementation for Redis Scaling

- [ ] T070 Create Redis pub/sub client class in `src/liquidationheatmap/api/redis_pubsub.py`
- [ ] T071 Implement `publish_snapshot()` method in `src/liquidationheatmap/api/redis_pubsub.py`
- [ ] T072 Implement `subscribe_to_symbols()` method in `src/liquidationheatmap/api/redis_pubsub.py`
- [ ] T073 Add Redis subscriber background task in `src/liquidationheatmap/api/redis_pubsub.py`
- [ ] T074 Integrate Redis publisher into `heatmap_update_generator()` in `src/liquidationheatmap/api/websocket_background.py`
- [ ] T075 Add REDIS_ENABLED, REDIS_URL environment variables to `.env.template`
- [ ] T076 Add graceful fallback to in-memory if Redis unavailable in `src/liquidationheatmap/api/redis_pubsub.py`
- [ ] T077 Create Nginx config for WebSocket load balancing in `deploy/nginx.conf`
- [ ] T078 Create docker-compose for multi-server setup in `deploy/docker-compose.multi.yml`
- [ ] T079 Run multi-server load test: 2000 concurrent connections across 2 servers

**Checkpoint**: Horizontal scaling complete - multiple servers can serve WebSocket clients

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup ────────► Phase 2: Foundational ────┬───► Phase 3: US1 (MVP)
                                                   │
                                                   ├───► Phase 4: US2
                                                   │
                                                   └───► Phase 5: US3
                                                            │
                                                            ▼
                                                   Phase 6: Production
                                                            │
                                                            ▼
                                                   Phase 7: Documentation
                                                            │
                                                            ▼
                                                   Phase 8: Redis Scaling (Optional)
```

### User Story Independence

| Story | Depends On | Can Start After |
|-------|------------|-----------------|
| US1 (P1) | Foundational only | Phase 2 complete |
| US2 (P2) | US1 (uses ConnectionManager) | T019 (get_stats) complete |
| US3 (P3) | US1 (extends broadcast) | T018 (broadcast) complete |

### Within Each User Story (TDD Order)

1. Tests MUST be written and FAIL before implementation
2. Models/dataclasses before services
3. Services before endpoints
4. Backend before frontend integration
5. Core implementation before polish

### Parallel Opportunities

**Phase 1** (all parallel):
```
T001 || T002 || T003 || T004
```

**Phase 2** (T005-T006 sequential, then parallel):
```
T005 → T006
T007 || T008 || T009
```

**US1 Tests** (all parallel):
```
T010 || T011 || T012 || T013 || T014
```

**US1 Implementation**:
```
T015 → T016 → T017 → T018 → T019  (ConnectionManager sequential)
T020 → T021 → T022                  (Endpoint sequential)
T023 → T024 → T025                  (Background task sequential)
T026 → T027                          (Lifecycle hooks sequential)
T028 || T029 || T030                (JS client parallel)
T031 → T032                          (Frontend integration sequential)
```

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Tasks** | 79 |
| **Phase 1 (Setup)** | 4 tasks |
| **Phase 2 (Foundational)** | 5 tasks |
| **US1 (MVP)** | 23 tasks (5 tests + 18 impl) |
| **US2** | 9 tasks (4 tests + 5 impl) |
| **US3** | 11 tasks (4 tests + 7 impl) |
| **Phase 6 (Production)** | 7 tasks |
| **Phase 7 (Documentation)** | 6 tasks |
| **Phase 8 (Redis Scaling)** | 14 tasks (4 tests + 10 impl) |
| **Parallel Opportunities** | 32 tasks marked [P] |

### MVP Scope (Recommended)

**For initial delivery, complete only**:
- Phase 1: Setup (T001-T004)
- Phase 2: Foundational (T005-T009)
- Phase 3: User Story 1 (T010-T032)

This delivers: Single-symbol real-time updates with auto-reconnect and status indicator.

**Estimated MVP Duration**: ~5 working days
