# Tasks: Adaptive Signal Loop

**Input**: Design documents from `/specs/015-adaptive-signals/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete), quickstart.md (complete)

**Feature Type**: New Module (signals/) + API endpoints + Redis integration

**Organization**: Tasks grouped by user story (component). TDD enabled per Constitution.

## Format: `[ID] [P?] [Story?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[US#]**: User Story mapping
- Include exact file paths in descriptions

## User Stories (from spec)

| Story | Component | Priority | Description |
|-------|-----------|----------|-------------|
| **US1** | Signal Publisher | P0 | Publish liquidation signals to Redis |
| **US2** | Feedback Consumer | P1 | Consume P&L feedback from Nautilus |
| **US3** | Adaptive Engine | P1 | Adjust weights based on feedback |
| **US4** | API Integration | P1 | Signal status and metrics endpoints |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and Redis dependencies

- [X] T001 Add redis-py dependency to pyproject.toml
- [X] T002 Create signals module directory structure at src/liquidationheatmap/signals/
- [X] T003 [P] Create src/liquidationheatmap/signals/__init__.py with module exports
- [X] T004 [P] Add Redis connection config to src/liquidationheatmap/signals/config.py

**Checkpoint**: Module structure ready, Redis dependency available

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

- [X] T005 Create Pydantic models (LiquidationSignal + TradeFeedback) in src/liquidationheatmap/signals/models.py
- [X] T006 [P] Create Redis connection manager in src/liquidationheatmap/signals/redis_client.py
- [X] T007 [P] Create DuckDB table for signal_feedback in scripts/migrations/add_signal_feedback_table.sql
- [X] T008 [P] Add SIGNAL_TOP_N config (default=5) to src/liquidationheatmap/signals/config.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Signal Publisher (Priority: P0) 🎯 MVP

**Goal**: Publish top 5 liquidation zones to Redis on heatmap update (configurable via SIGNAL_TOP_N)

**Independent Test**: `redis-cli SUBSCRIBE liquidation:signals:BTCUSDT` receives signals

### Tests for User Story 1 (TDD - Constitution requires)

- [X] T009 [P] [US1] Create unit test for SignalPublisher in tests/unit/test_signal_publisher.py
- [X] T010 [P] [US1] Create integration test for Redis publish in tests/integration/test_redis_pubsub.py

### Implementation for User Story 1

- [X] T011 [US1] Implement SignalPublisher class in src/liquidationheatmap/signals/publisher.py
- [X] T012 [US1] Add publish_signal() method to SignalPublisher in src/liquidationheatmap/signals/publisher.py
- [X] T013 [US1] Add extract_top_signals() helper to convert heatmap to signals in src/liquidationheatmap/signals/publisher.py
- [X] T014 [US1] Add CLI entry point for publisher in src/liquidationheatmap/signals/publisher.py
- [X] T015 [US1] Add publish_signals_from_snapshot() integration helper in src/liquidationheatmap/signals/publisher.py

**Checkpoint**: Signal Publisher functional - signals flow to Redis

---

## Phase 4: User Story 2 - Feedback Consumer (Priority: P1)

**Goal**: Consume P&L feedback from Nautilus and store in DuckDB

**Independent Test**: Publish to `liquidation:feedback:BTCUSDT`, verify DuckDB row created

### Tests for User Story 2 (TDD)

- [X] T016 [P] [US2] Create unit test for FeedbackConsumer in tests/unit/test_feedback_consumer.py
- [X] T017 [P] [US2] Create integration test for feedback storage in tests/integration/test_feedback_storage.py

### Implementation for User Story 2

- [X] T018 [US2] Implement FeedbackConsumer class in src/liquidationheatmap/signals/feedback.py
- [X] T019 [US2] Add subscribe_feedback() method in src/liquidationheatmap/signals/feedback.py
- [X] T020 [US2] Add store_feedback() method for DuckDB persistence in src/liquidationheatmap/signals/feedback.py
- [X] T021 [US2] Add CLI entry point for consumer in src/liquidationheatmap/signals/feedback.py

**Checkpoint**: Feedback Consumer functional - P&L data stored in DuckDB

---

## Phase 5: User Story 3 - Adaptive Engine (Priority: P1)

**Goal**: Adjust model weights based on rolling accuracy metrics

**Independent Test**: Feed synthetic P&L data, verify weights change

### Tests for User Story 3 (TDD)

- [X] T022 [P] [US3] Create unit test for AdaptiveEngine in tests/unit/test_adaptive_engine.py
- [X] T023 [P] [US3] Create test for weight adjustment algorithm in tests/unit/test_adaptive_engine.py

### Implementation for User Story 3

- [X] T024 [US3] Implement AdaptiveEngine class in src/liquidationheatmap/signals/adaptive.py
- [X] T025 [US3] Add calculate_rolling_metrics() for 1h/24h/7d windows in src/liquidationheatmap/signals/adaptive.py
- [X] T026 [US3] Add adjust_weights() using EMA algorithm in src/liquidationheatmap/signals/adaptive.py
- [X] T027 [US3] Add rollback_to_defaults() for hit_rate < 0.50 in src/liquidationheatmap/signals/adaptive.py
- [X] T028 [US3] Add DuckDB table for adaptive_weights in scripts/migrations/add_adaptive_weights_table.sql

**Checkpoint**: Adaptive Engine functional - weights adjust based on feedback

---

## Phase 6: User Story 4 - API Integration (Priority: P1)

**Goal**: Expose signal status and metrics via FastAPI endpoints

**Independent Test**: `curl http://localhost:8000/signals/status` returns JSON

### Tests for User Story 4 (TDD)

- [X] T029 [P] [US4] Create contract test for /signals/status in tests/contract/test_signal_endpoints.py
- [X] T030 [P] [US4] Create contract test for /signals/metrics in tests/contract/test_signal_endpoints.py

### Implementation for User Story 4

- [X] T031 [US4] Add SignalRouter in src/liquidationheatmap/api/routers/signals.py
- [X] T032 [US4] Implement GET /signals/status endpoint in src/liquidationheatmap/api/routers/signals.py
- [X] T033 [US4] Implement GET /signals/metrics endpoint in src/liquidationheatmap/api/routers/signals.py
- [X] T034 [US4] Register SignalRouter in src/liquidationheatmap/api/main.py

**Checkpoint**: API Integration complete - monitoring endpoints available

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, final validation

- [X] T035 SKIPPED - Per CLAUDE.md: only add docs when requested
- [X] T036 [P] Add signal configuration to .env.example
- [X] T037 [P] Create SIGNALS_ENABLED feature flag in src/liquidationheatmap/signals/config.py
- [X] T038 Run full test suite via `uv run pytest -v` (451 passed, 23 skipped)
- [X] T039 Run quickstart.md validation commands (unit tests verified)

**Checkpoint**: Feature complete - ready for merge

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup
  └─→ Phase 2: Foundational (models + Redis client)
        └─→ Phase 3: US1 - Signal Publisher (MVP)
              ├─→ Phase 4: US2 - Feedback Consumer (can parallel after MVP)
              └─→ Phase 5: US3 - Adaptive Engine (depends on US2)
                    └─→ Phase 6: US4 - API Integration
                          └─→ Phase 7: Polish
```

### User Story Dependencies

- **US1 (Signal Publisher)**: No dependencies - can start after Foundational
- **US2 (Feedback Consumer)**: Can start after Foundational (parallel with US1)
- **US3 (Adaptive Engine)**: Depends on US2 (needs feedback data)
- **US4 (API Integration)**: Can start after US1 (needs publisher for status)

### Parallel Opportunities

**Phase 1** (Setup):
```bash
# T003 and T004 can run in parallel
Task: "Create signals/__init__.py"
Task: "Add Redis config"
```

**Phase 2** (Foundational):
```bash
# T006, T007, T008 can run in parallel (after T005)
Task: "Create Redis connection manager"
Task: "Create DuckDB migration"
Task: "Add SIGNAL_TOP_N config"
```

**Phase 3** (US1 Tests):
```bash
# T009 and T010 can run in parallel
Task: "Create unit test for SignalPublisher"
Task: "Create integration test for Redis publish"
```

**Phase 4/5** (US2 + US3 after US1):
```bash
# US2 and US3 tests can run in parallel
Task: "Create unit test for FeedbackConsumer"
Task: "Create unit test for AdaptiveEngine"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (30 min)
2. Complete Phase 2: Foundational (1h)
3. Complete Phase 3: US1 - Signal Publisher (2h)
4. **STOP and VALIDATE**: Signals flow to Redis
5. Deploy/demo MVP

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Signal Publisher) → Test with Redis CLI → **MVP!**
3. Add US2 (Feedback Consumer) → Test with synthetic feedback
4. Add US3 (Adaptive Engine) → Test weight adjustment
5. Add US4 (API Integration) → Test endpoints
6. Polish + Documentation → **Complete!**

---

## Success Criteria Summary

| Story | Critical Test | Threshold |
|-------|--------------|-----------|
| **US1** | Redis message received | Signal in <10ms |
| **US2** | DuckDB row created | Feedback stored |
| **US3** | Weights change | EMA adjustment works |
| **US4** | API returns 200 | Status/metrics valid |

---

## Notes

- **TDD Required**: Constitution mandates tests before implementation
- **Redis Required**: Must be running for integration tests
- **Rollback**: `SIGNALS_ENABLED=false` disables entire feature
- **Total Tasks**: 39 (T001-T039)
- **Parallel Opportunities**: 16 tasks marked [P]
- **MVP Scope**: Phase 1-3 (Setup + Foundational + US1)
