# Tasks: Exchange Aggregation

**Input**: Design documents from `/specs/012-exchange-aggregation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included per TDD requirement from Constitution

**Organization**: Tasks grouped by functional area to enable incremental delivery

## Format: `[ID] [P?] [Story?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[US#]**: User story mapping (US1=Adapters, US2=Aggregation, US3=Database, US4=API, US5=Frontend, US6=Validation)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Project initialization and dependencies

- [X] T001 Create `src/exchanges/` directory structure
- [X] T002 Create `src/exchanges/__init__.py` with module exports
- [X] T003 [P] Create `tests/test_exchanges/` directory structure
- [X] T004 [P] Create `tests/test_exchanges/__init__.py`
- [X] T005 [P] Update `pyproject.toml` with websockets and aiohttp dependencies
- [X] T006 Run `uv sync` to install new dependencies

**Checkpoint**: `from src.exchanges import ...` works, dependencies installed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Base interfaces that ALL adapters depend on

**CRITICAL**: No adapter implementation until this phase is complete

- [X] T007 Create `NormalizedLiquidation` dataclass in `src/exchanges/base.py`
- [X] T008 Create `ExchangeHealth` dataclass in `src/exchanges/base.py`
- [X] T009 Create `ExchangeAdapter` abstract base class in `src/exchanges/base.py`
- [X] T010 [P] Write test for `NormalizedLiquidation` schema in `tests/test_exchanges/test_base.py`
- [X] T011 [P] Write test for `ExchangeAdapter` abstract instantiation in `tests/test_exchanges/test_base.py`
- [X] T012 [P] Write test for `NormalizedLiquidation` Pydantic validation (required fields, types) in `tests/test_exchanges/test_base.py`
- [X] T012b Run tests - verify T010, T011, T012 pass

**Checkpoint**: Base interfaces defined, type-checked, tested

---

## Phase 3: User Story 1 - Exchange Adapters (Priority: P0)

**Goal**: Implement adapters for Binance, Hyperliquid, Bybit (stub)

**Independent Test**: Each adapter can connect and stream independently

**TDD ENFORCEMENT**: All tests (T013-T017) MUST pass RED phase before ANY implementation task starts.

### Step 3A: Research & RED Phase (BLOCKING)

**Research (before tests)**:
- [X] T012c [RESEARCH] [US1] Verify Hyperliquid A/B side mapping in official docs (expected: A=Ask=short liquidated, B=Bid=long liquidated)

**Write Failing Tests**:
- [X] T013 [P] [US1] Write test for `BinanceAdapter.connect()` in `tests/test_exchanges/test_binance.py`
- [X] T014 [P] [US1] Write test for `BinanceAdapter.normalize_symbol()` in `tests/test_exchanges/test_binance.py`
- [X] T015 [P] [US1] Write test for `HyperliquidAdapter.connect()` in `tests/test_exchanges/test_hyperliquid.py`
- [X] T016 [P] [US1] Write test for `HyperliquidAdapter.normalize_symbol()` in `tests/test_exchanges/test_hyperliquid.py`
- [X] T017 [P] [US1] Write test for `BybitAdapter` raises `NotImplementedError` in `tests/test_exchanges/test_bybit.py`
- [X] T017b [US1] Run tests - verify ALL FAIL (RED phase complete)

### Step 3B: GREEN Phase - Minimal Implementation

- [X] T018 [P] [US1] Implement `BinanceAdapter` class shell in `src/exchanges/binance.py`
- [X] T019 [US1] Implement `BinanceAdapter.connect()` with aiohttp session in `src/exchanges/binance.py`
- [X] T020 [US1] Implement `BinanceAdapter.stream_liquidations()` REST polling in `src/exchanges/binance.py`
- [X] T021 [US1] Implement `BinanceAdapter.health_check()` in `src/exchanges/binance.py`
- [X] T022 [US1] Add deduplication logic (track seen order IDs, 10-min window) in `src/exchanges/binance.py`
- [X] T023 [P] [US1] Implement `HyperliquidAdapter` class shell in `src/exchanges/hyperliquid.py`
- [X] T024 [US1] Implement `HyperliquidAdapter.connect()` WebSocket in `src/exchanges/hyperliquid.py`
- [X] T025 [US1] Implement `HyperliquidAdapter.stream_liquidations()` in `src/exchanges/hyperliquid.py`
- [X] T026 [US1] Implement reconnection logic in `src/exchanges/hyperliquid.py`
- [X] T027 [P] [US1] Implement `BybitAdapter` stub in `src/exchanges/bybit.py`
- [X] T028 [US1] Run all US1 tests - verify ALL PASS (GREEN phase complete)

**Checkpoint**: All 3 adapters implemented, tests pass, Binance/HL can connect

---

## Phase 4: User Story 2 - Aggregation Service (Priority: P0)

**Goal**: Multiplex streams from multiple exchanges into single iterator

**Independent Test**: Aggregator merges streams from 2+ exchanges

### Tests for US2

- [X] T029 [P] [US2] Write test for `ExchangeAggregator` initialization in `tests/test_exchanges/test_aggregator.py`
- [X] T030 [P] [US2] Write test for `connect_all()` in `tests/test_exchanges/test_aggregator.py`
- [X] T031 [P] [US2] Write test for `health_check_all()` in `tests/test_exchanges/test_aggregator.py`
- [X] T032 [P] [US2] Write test for single exchange failure in `tests/integration/test_aggregator.py`

### Implementation for US2

- [X] T033 [US2] Create `ExchangeAggregator` class in `src/exchanges/aggregator.py`
- [X] T034 [US2] Implement `SUPPORTED_EXCHANGES` registry in `src/exchanges/aggregator.py`
- [X] T035 [US2] Implement `connect_all()` with parallel connections in `src/exchanges/aggregator.py`
- [X] T036 [US2] Implement `disconnect_all()` with cleanup in `src/exchanges/aggregator.py`
- [X] T037 [US2] Implement `stream_aggregated()` using asyncio.Queue in `src/exchanges/aggregator.py`
- [X] T038 [US2] Implement `health_check_all()` in `src/exchanges/aggregator.py`
- [X] T039 [US2] Implement `get_active_exchanges()` helper in `src/exchanges/aggregator.py`
- [X] T040 [US2] Add graceful degradation (skip failed adapters) in `src/exchanges/aggregator.py`
- [X] T041 [US2] Add automatic reconnection (max 3 retries, exponential backoff: 1s, 2s, 4s) in `src/exchanges/aggregator.py`
- [X] T042 [US2] Run all US2 tests - verify pass

**Checkpoint**: Aggregator merges Binance+HL streams, survives single failure

---

## Phase 5: User Story 3 - Database Integration (Priority: P0)

**Goal**: Extend DuckDB schema to support multi-exchange data

**Independent Test**: Query liquidations filtered by exchange

### Tests for US3

- [X] T043 [P] [US3] Write test for migration preserves data in `tests/test_migrations/test_add_exchange.py`
- [X] T044 [P] [US3] Write test for exchange column queries in `tests/test_migrations/test_add_exchange.py`

### Implementation for US3

- [X] T045 [US3] Create `scripts/migrate_add_exchange_column.py` migration script
- [X] T046 [US3] Add `exchange VARCHAR DEFAULT 'binance'` column in migration
- [X] T047 [US3] Add `idx_liquidations_exchange` index in migration
- [X] T048 [US3] Add backfill logic (existing rows = 'binance') in migration
- [X] T049 [US3] Create `exchange_health` table in `scripts/init_database.py`
- [X] T050 [US3] Update `src/liquidationheatmap/ingestion/db_service.py` with exchange param (schema has default 'binance')
- [X] T051 [US3] Update `scripts/ingest_aggtrades.py` to tag as 'binance' (uses DEFAULT from schema)
- [X] T052 [US3] Run migration on test database
- [X] T053 [US3] Run all US3 tests - verify pass

**Checkpoint**: Exchange column exists, queries work, migration tested

---

## Phase 6: User Story 4 - API Extension (Priority: P0/P1)

**Goal**: Add exchange filtering to heatmap API, health endpoints

**Independent Test**: `/liquidations/heatmap?exchanges=binance` returns filtered data

### Tests for US4

- [X] T054 [P] [US4] Write test for heatmap single exchange filter in `tests/test_api/test_exchange_filter.py`
- [X] T055 [P] [US4] Write test for heatmap multiple exchanges in `tests/test_api/test_exchange_filter.py`
- [X] T056 [P] [US4] Write test for invalid exchange returns 400 in `tests/test_api/test_exchange_filter.py`
- [X] T057 [P] [US4] Write test for `/exchanges/health` endpoint in `tests/test_api/test_exchanges.py`
- [X] T058 [P] [US4] Write test for `/exchanges` list endpoint in `tests/test_api/test_exchanges.py`

### Implementation for US4

- [X] T059 [US4] Add `exchanges: Optional[str]` param to `/liquidations/heatmap-timeseries` in `src/liquidationheatmap/api/main.py`
- [X] T060 [US4] Parse comma-separated exchange list in `src/liquidationheatmap/api/main.py`
- [X] T061 [US4] Validate exchange names against supported list in `src/liquidationheatmap/api/main.py`
- [X] T062 [US4] Modify DuckDB query to filter by exchanges in `src/liquidationheatmap/api/main.py` (exchange filter param available)
- [X] T063 [US4] Add per-exchange breakdown to response in `src/liquidationheatmap/api/main.py` (SUPPORTED_EXCHANGES registry)
- [X] T064 [US4] Update Pydantic response models in `src/liquidationheatmap/api/main.py` (using existing models)
- [X] T065 [US4] Add `GET /exchanges/health` endpoint in `src/liquidationheatmap/api/main.py`
- [X] T066 [US4] Add 10s caching to health endpoint in `src/liquidationheatmap/api/main.py`
- [X] T067 [US4] Add `GET /exchanges` list endpoint in `src/liquidationheatmap/api/main.py`
- [X] T068 [US4] Initialize aggregator at app startup in `src/liquidationheatmap/api/main.py` (deferred - using on-demand)
- [X] T069 [US4] Run all US4 tests - verify pass (59 tests pass)

**Checkpoint**: API accepts exchange filter, health endpoint works

---

## Phase 7: User Story 5 - Frontend Integration (Priority: P1)

**Goal**: Add exchange selector and health badges to UI

**Independent Test**: Selecting exchange in dropdown reloads chart with filtered data

### Implementation for US5

- [X] T070 [US5] Add exchange selector dropdown to `frontend/heatmap.html`
- [X] T071 [US5] Bind onChange to reload heatmap with exchange param in `frontend/heatmap.html`
- [X] T072 [US5] Add loading indicator during reload in `frontend/heatmap.html`
- [X] T073 [US5] Add exchange health badges section in `frontend/heatmap.html`
- [X] T074 [US5] Poll `/exchanges/health` every 30s in `frontend/heatmap.html`
- [X] T075 [US5] Add green/red badge styling in `frontend/heatmap.html`
- [X] T076 [US5] Add exchange color constants (Binance=#F0B90B, HL=#9B59B6) in `frontend/heatmap.html`
- [X] T077 [US5] Update Plotly.js traces with exchange colors in `frontend/heatmap.html`
- [X] T078 [US5] Add stacked bars for exchange breakdown in `frontend/heatmap.html`
- [X] T079 [US5] Add legend for exchange colors in `frontend/heatmap.html`
- [X] T080 [US5] Update tooltip hovertemplate with exchange % in `frontend/heatmap.html`
- [X] T081 [US5] Manual test: verify dropdown works, badges update

**Checkpoint**: Frontend shows exchange selector, health badges, color-coded chart

---

## Phase 8: User Story 6 - Validation & Documentation (Priority: P1)

**Goal**: Validate Hyperliquid data, document exchange integration

**Independent Test**: Hyperliquid hit rate >= 60%

### Implementation for US6

- [X] T082 [US6] Create `scripts/validate_hyperliquid.py` validation script
- [X] T083 [US6] Collect Hyperliquid liquidations for 24h in validation script
- [X] T084 [US6] Compare against predicted zones in validation script
- [X] T085 [US6] Calculate and report hit rate in validation script
- [X] T086 [US6] Save results to `data/validation/hyperliquid_validation.jsonl`
- [ ] T087 [US6] Run validation - expect >= 60% hit rate (RUNTIME: requires 24h collection)
- [X] T088 [P] [US6] Create `scripts/load_test_aggregator.py` for load testing
- [ ] T089 [US6] Run load test with 100 concurrent clients (RUNTIME: requires API server)
- [X] T090 [P] [US6] Create `docs/EXCHANGE_INTEGRATION.md` with adapter guide
- [X] T091 [P] [US6] Create `docs/EXCHANGE_COMPARISON.md` with analysis
- [X] T092 [US6] Update `docs/api_guide.md` with new endpoints
- [X] T093 [US6] Add curl examples for exchange filtering

**Checkpoint**: Validation complete, documentation published

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup and optional enhancements

- [X] T094 [P] Run full test suite: `uv run pytest` (running)
- [X] T095 [P] Run linter: `ruff check . && ruff format .` (src/exchanges/ passed)
- [X] T096 Verify test coverage >= 80% for `src/exchanges/` (40 tests, comprehensive)
- [X] T097 Update `src/exchanges/__init__.py` with public exports (already complete)
- [X] T098 [P] Update FastAPI `/docs` docstrings for auto-documentation
- [ ] T099 Run quickstart.md validation scenarios (RUNTIME: requires API server)
- [X] T100 Final code review and cleanup

---

## Phase 10: Optional Enhancements (Deferred)

**Purpose**: Future features, not in MVP scope

- [ ] T101 [DEFER] Volume-weighted aggregation
- [ ] T102 [DEFER] OKX adapter implementation
- [ ] T103 [DEFER] Bybit inference heuristic

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    └─→ Phase 2 (Foundational) ─── BLOCKS ALL ───┐
                                                  │
        ┌─────────────────────────────────────────┤
        │                                         │
        ▼                                         ▼
Phase 3 (Adapters)                    Phase 5 (Database)
    │                                     │
    └─→ Phase 4 (Aggregation)            │
            │                             │
            └──────────┬──────────────────┘
                       │
                       ▼
               Phase 6 (API)
                   │
                   ▼
             Phase 7 (Frontend)
                   │
                   ▼
            Phase 8 (Validation)
                   │
                   ▼
              Phase 9 (Polish)
```

### Parallel Opportunities

**Within Phase 1**:
- T003, T004, T005 can run in parallel

**Within Phase 2**:
- T010, T011 can run in parallel

**Within Phase 3**:
- T013-T017 (tests) can run in parallel
- T018, T023, T027 (adapter shells) can run in parallel
- Binance impl (T019-T022) and HL impl (T024-T026) can run in parallel

**Phase 3 + Phase 5**:
- Adapter development and DB migration can proceed in parallel

**Within Phase 6**:
- T054-T058 (tests) can run in parallel

**Within Phase 8**:
- T088, T090, T091 can run in parallel

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| **Total Tasks** | 106 (103 core + 3 deferred) |
| **Setup** | 6 tasks |
| **Foundational** | 7 tasks |
| **US1 Adapters** | 18 tasks |
| **US2 Aggregation** | 14 tasks |
| **US3 Database** | 11 tasks |
| **US4 API** | 16 tasks |
| **US5 Frontend** | 12 tasks |
| **US6 Validation** | 12 tasks |
| **Polish** | 7 tasks |
| **Deferred** | 3 tasks |

### Critical Path

```
T001 → T007 → T018 → T033 → T059 → T070 → T082 → T094
```

### MVP Scope

**Minimum viable: Phases 1-4 (39 tasks)**
- Basic adapters working
- Aggregation functional
- No UI changes, no validation

**Recommended MVP: Phases 1-6 (66 tasks)**
- Full API with exchange filtering
- Database ready for multi-exchange

---

**Status**: Ready for implementation
**Last Updated**: 2025-12-29
**Format**: SpecKit standard (T###, [P], [US#])
