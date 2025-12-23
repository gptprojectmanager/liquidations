# Tasks: Time-Evolving Liquidation Heatmap

**Input**: Design documents from `/specs/008-time-evolving-heatmap/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/openapi.yaml ✅, quickstart.md ✅

**Tests**: Tests are included following TDD workflow (Red-Green-Refactor) per project constitution.

**Organization**: Tasks are grouped by implementation phase from spec.md to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1=Core Algorithm, US2=Database, US3=API, US4=Frontend, US5=Performance)
- Include exact file paths in descriptions

## Path Conventions
- **Backend**: `src/liquidationheatmap/` at repository root
- **Frontend**: `frontend/`
- **Tests**: `tests/` with `unit/`, `integration/` subdirectories

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and feature branch setup

- [x] T001 Verify feature branch `008-time-evolving-heatmap` is active and clean
- [x] T002 Verify existing dependencies in pyproject.toml (no new deps needed per plan.md)
- [x] T003 [P] Create directory structure for new models in src/liquidationheatmap/models/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational Phase

- [x] T004 [P] Unit test for LiquidationLevel dataclass in tests/unit/models/test_position.py
- [x] T005 [P] Unit test for HeatmapCell and HeatmapSnapshot dataclasses in tests/unit/models/test_position.py
- [x] T006 [P] Unit test for calculate_liq_price() function in tests/unit/models/test_position.py

### Implementation for Foundational Phase

- [x] T007 Create LiquidationLevel dataclass in src/liquidationheatmap/models/position.py (from data-model.md)
- [x] T008 Create HeatmapCell dataclass in src/liquidationheatmap/models/position.py (from data-model.md)
- [x] T009 Create HeatmapSnapshot dataclass in src/liquidationheatmap/models/position.py (from data-model.md)
- [x] T010 Implement calculate_liq_price() function with Binance formula in src/liquidationheatmap/models/position.py

**Checkpoint**: Foundation ready - core data models validated with tests

---

## Phase 3: User Story 1 - Core Algorithm (Priority: P1 CRITICAL) 🎯 MVP

**Goal**: Implement time-evolving heatmap calculation that consumes liquidation levels when price crosses them

**Independent Test**: Run `uv run pytest tests/unit/models/test_time_evolving_heatmap.py -v` - algorithm produces correct snapshots with consumed levels

### Tests for User Story 1

**NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T011 [P] [US1] Unit test for should_liquidate() function in tests/unit/models/test_time_evolving_heatmap.py
- [x] T012 [P] [US1] Unit test for infer_side() function in tests/unit/models/test_time_evolving_heatmap.py
- [x] T013 [P] [US1] Unit test for create_positions() function in tests/unit/models/test_time_evolving_heatmap.py
- [x] T014 [P] [US1] Unit test for remove_proportionally() function in tests/unit/models/test_time_evolving_heatmap.py
- [x] T015 [US1] Unit test for process_candle() function in tests/unit/models/test_time_evolving_heatmap.py
- [x] T016 [US1] Unit test for calculate_time_evolving_heatmap() main function in tests/unit/models/test_time_evolving_heatmap.py
- [ ] T017 [US1] Integration test with real DuckDB data subset in tests/integration/test_time_evolving_algorithm.py

### Implementation for User Story 1

- [x] T018 [US1] Implement should_liquidate(pos, candle) in src/liquidationheatmap/models/time_evolving_heatmap.py
- [x] T019 [US1] Implement infer_side(candle) in src/liquidationheatmap/models/time_evolving_heatmap.py
- [x] T020 [US1] Implement create_positions(entry_price, volume, side, timestamp) with leverage distribution in src/liquidationheatmap/models/time_evolving_heatmap.py
- [x] T021 [US1] Implement remove_proportionally(active_positions, volume_to_remove) per research.md Q1 decision in src/liquidationheatmap/models/time_evolving_heatmap.py
- [x] T022 [US1] Implement process_candle(candle, oi, active_positions) in src/liquidationheatmap/models/time_evolving_heatmap.py
- [x] T023 [US1] Implement calculate_time_evolving_heatmap(symbol, start_time, end_time, interval) in src/liquidationheatmap/models/time_evolving_heatmap.py
- [x] T024 [US1] Add configurable leverage weights (default + API override) per research.md Q3 in src/liquidationheatmap/models/time_evolving_heatmap.py
- [x] T025 [US1] Add validation and error handling with descriptive messages in src/liquidationheatmap/models/time_evolving_heatmap.py

**Checkpoint**: Core algorithm functional - can calculate time-evolving snapshots with consumption logic

---

## Phase 4: User Story 2 - Database Schema (Priority: P2 HIGH)

**Goal**: Add DuckDB tables for caching pre-computed snapshots

**Independent Test**: Run SQL queries against new tables in DuckDB - data persists and retrieves correctly

### Tests for User Story 2

- [ ] T026 [P] [US2] Unit test for liquidation_snapshots table schema in tests/unit/ingestion/test_snapshot_schema.py
- [ ] T027 [P] [US2] Unit test for position_events table schema in tests/unit/ingestion/test_snapshot_schema.py
- [ ] T028 [US2] Integration test for snapshot persistence and retrieval in tests/integration/test_snapshot_persistence.py

### Implementation for User Story 2

- [ ] T029 [US2] Create SQL schema for liquidation_snapshots table per spec.md Phase 2 in src/liquidationheatmap/ingestion/schema.sql
- [ ] T030 [US2] Create SQL schema for position_events table per spec.md Phase 2 in src/liquidationheatmap/ingestion/schema.sql
- [ ] T031 [US2] Add table creation to db_service.py initialize method in src/liquidationheatmap/ingestion/db_service.py
- [ ] T032 [US2] Implement save_snapshot(snapshot) method in src/liquidationheatmap/ingestion/db_service.py
- [ ] T033 [US2] Implement load_snapshots(symbol, start_time, end_time) method in src/liquidationheatmap/ingestion/db_service.py
- [ ] T034 [US2] Add indexes for query performance per data-model.md in src/liquidationheatmap/ingestion/schema.sql

**Checkpoint**: Database layer functional - snapshots persist to DuckDB

---

## Phase 5: User Story 3 - API Updates (Priority: P3 HIGH)

**Goal**: New `/liquidations/heatmap-timeseries` endpoint per openapi.yaml contract

**Independent Test**: `curl "http://localhost:8888/liquidations/heatmap-timeseries?symbol=BTCUSDT&interval=15m"` returns valid JSON matching contract schema

### Tests for User Story 3

- [x] T035 [P] [US3] Contract test for /liquidations/heatmap-timeseries endpoint in tests/contract/test_heatmap_timeseries.py
- [x] T036 [P] [US3] Contract test for query parameter validation (symbol, interval, time range) in tests/contract/test_heatmap_timeseries.py
- [ ] T037 [US3] Integration test for full API response matching openapi.yaml schema in tests/integration/test_heatmap_api.py

### Implementation for User Story 3

- [x] T038 [US3] Create Pydantic request model HeatmapTimeseriesRequest in src/liquidationheatmap/api/main.py (inline, not separate schemas.py)
- [x] T039 [US3] Create Pydantic response model HeatmapTimeseriesResponse per openapi.yaml in src/liquidationheatmap/api/main.py
- [x] T040 [US3] Create Pydantic models HeatmapSnapshot and HeatmapLevel per openapi.yaml in src/liquidationheatmap/api/main.py
- [x] T041 [US3] Implement GET /liquidations/heatmap-timeseries endpoint in src/liquidationheatmap/api/main.py
- [x] T042 [US3] Add leverage_weights query parameter parsing in src/liquidationheatmap/api/main.py
- [x] T043 [US3] Add deprecation warning to /liquidations/levels endpoint in src/liquidationheatmap/api/main.py
- [x] T044 [US3] Add error handling for 400/500 responses per openapi.yaml in src/liquidationheatmap/api/main.py

**Checkpoint**: API endpoint functional - returns valid time-series heatmap data

---

## Phase 6: User Story 4 - Frontend Updates (Priority: P4 HIGH)

**Goal**: Update heatmap visualization to render time-varying data with consumed levels

**Independent Test**: Open frontend/coinglass_heatmap.html in browser - heatmap columns vary by timestamp, consumed areas fade

### Tests for User Story 4

- [x] T045 [US4] Visual validation test with Playwright screenshot comparison in tests/integration/test_frontend_visual.py

### Implementation for User Story 4

- [x] T046 [US4] Update fetchHeatmapData() to call new /heatmap-timeseries endpoint in frontend/coinglass_heatmap.html
- [x] T047 [US4] Update Plotly.js data transformation for time-series format in frontend/coinglass_heatmap.html
- [x] T048 [US4] Implement per-column density rendering (each column = one timestamp) in frontend/coinglass_heatmap.html
- [x] T049 [US4] Add visual indicator for consumed/liquidated zones (faded styling) in frontend/coinglass_heatmap.html
- [x] T050 [US4] Add timestamp axis labels to heatmap in frontend/coinglass_heatmap.html
- [x] T051 [US4] Update color scale to handle dynamic density ranges per timestamp in frontend/coinglass_heatmap.html
- [x] T052 [US4] Add loading state and error handling for API calls in frontend/coinglass_heatmap.html

**Checkpoint**: Frontend renders time-evolving heatmap with consumption visualization ✅ COMPLETE

---

## Phase 7: User Story 5 - Performance Optimization (Priority: P5 MEDIUM)

**Goal**: Pre-computation pipeline and caching for <100ms API response time

**Independent Test**: Run `time curl "http://localhost:8888/liquidations/heatmap-timeseries?symbol=BTCUSDT"` - response <100ms for cached data

### Tests for User Story 5

- [ ] T053 [P] [US5] Performance test asserting <500ms for 1000 candle calculation in tests/performance/test_algorithm_performance.py
- [ ] T054 [P] [US5] Performance test asserting <100ms API response for cached data in tests/performance/test_api_performance.py

### Implementation for User Story 5

- [ ] T055 [US5] Create pre-computation script in scripts/precompute_heatmap.py
- [ ] T056 [US5] Add CLI arguments for symbol, date range, and interval in scripts/precompute_heatmap.py
- [ ] T057 [US5] Implement batch snapshot generation and DuckDB persistence in scripts/precompute_heatmap.py
- [ ] T058 [US5] Add in-memory cache layer with TTL to API endpoint in src/liquidationheatmap/api/main.py
- [ ] T059 [US5] Implement cache-first query strategy (check cache → check DB → compute) in src/liquidationheatmap/api/main.py
- [ ] T060 [US5] Add cache metrics logging for hit/miss ratio in src/liquidationheatmap/api/main.py

**Checkpoint**: Performance targets met - API responds in <100ms for typical queries

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T061 [P] Update quickstart.md with actual test commands and expected output
- [ ] T062 [P] Add docstrings to all public functions in src/liquidationheatmap/models/
- [ ] T063 Run full test suite and fix any regressions: `uv run pytest tests/ -v`
- [ ] T064 Run linter and formatter: `ruff check . && ruff format .`
- [ ] T065 Validate quickstart.md steps work end-to-end
- [ ] T066 Remove any debug/print statements from production code

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - BLOCKS US3, US4, US5 (provides core algorithm)
- **User Story 2 (Phase 4)**: Depends on Foundational - Can run parallel to US1
- **User Story 3 (Phase 5)**: Depends on US1 + US2 (needs algorithm + persistence)
- **User Story 4 (Phase 6)**: Depends on US3 (needs API endpoint)
- **User Story 5 (Phase 7)**: Depends on US1 + US2 + US3 (performance layer on top)
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies (DAG)

```
Setup → Foundational → US1 (Core Algorithm) → US3 (API) → US4 (Frontend)
                    ↘                      ↗           ↘
                      US2 (Database) ─────┘             US5 (Performance)
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD Red phase)
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to dependent stories

### Parallel Opportunities

**Phase 2 (Foundational)** - All tests can run in parallel:
- T004, T005, T006 can be written simultaneously

**Phase 3 (US1 Core Algorithm)** - Tests in parallel:
- T011, T012, T013, T014 can be written simultaneously

**Phase 4 (US2 Database)** - Tests in parallel:
- T026, T027 can be written simultaneously

**Phase 5 (US3 API)** - Tests in parallel:
- T035, T036 can be written simultaneously

**Cross-phase parallelism**:
- US1 and US2 can proceed in parallel after Foundational
- T061, T062 can run in parallel during Polish phase

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all TDD RED phase tests for User Story 1 together:
Task: "T011 [P] [US1] Unit test for should_liquidate() function"
Task: "T012 [P] [US1] Unit test for infer_side() function"
Task: "T013 [P] [US1] Unit test for create_positions() function"
Task: "T014 [P] [US1] Unit test for remove_proportionally() function"
```

---

## Implementation Strategy

### MVP First (User Story 1 + 3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Core Algorithm)
4. Complete Phase 5: User Story 3 (API) - skip US2 for MVP
5. **STOP and VALIDATE**: Test API endpoint returns evolving heatmap
6. Deploy/demo if ready - database caching is optional for MVP

### Full Feature Delivery

1. Complete Setup + Foundational → Foundation ready
2. Complete US1 (Core Algorithm) → Test independently → Core working
3. Complete US2 (Database) → Test independently → Persistence ready
4. Complete US3 (API) → Test independently → API ready for frontend
5. Complete US4 (Frontend) → Test independently → Full visualization
6. Complete US5 (Performance) → Test independently → Production ready
7. Polish phase → Clean and document

### Suggested MVP Scope

For immediate value, implement only:
- **Phase 1-3**: Setup + Foundational + US1 (Core Algorithm)
- **Phase 5**: US3 (API) - compute on-demand, no caching

This delivers a working time-evolving heatmap API in the fewest tasks (~25 tasks vs 66 total).

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD Red phase)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Performance budgets from spec.md: <500ms calc, <100ms API (cached), <1s frontend render

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Tasks** | 66 |
| **Foundational Tasks** | 7 (T004-T010) |
| **US1 (Core Algorithm) Tasks** | 15 (T011-T025) |
| **US2 (Database) Tasks** | 9 (T026-T034) |
| **US3 (API) Tasks** | 10 (T035-T044) |
| **US4 (Frontend) Tasks** | 8 (T045-T052) |
| **US5 (Performance) Tasks** | 8 (T053-T060) |
| **Polish Tasks** | 6 (T061-T066) |
| **Parallel Opportunities** | 22 tasks marked [P] |
| **MVP Scope** | ~25 tasks (Phases 1-3, 5) |
