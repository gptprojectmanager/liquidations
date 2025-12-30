# Tasks: 014-validation-pipeline

**Input**: Design documents from `/specs/014-validation-pipeline/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Status Summary**:
- **Gate 1 (Coinglass)**: ✅ PASSED (hit_rate=77.8% > 70%)
- **Gate 2 (Backtest)**: ✅ PASSED (F1=80.93% ≥ 60%)
- **Phase 5 (CI)**: ✅ COMPLETE - Pipeline orchestrator, CLI, GitHub Actions workflow
- **Phase 6 (Dashboard)**: ✅ COMPLETE - API endpoints, frontend dashboard with Plotly.js
- **Remaining**: Polish (T056-T059)

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1=Coinglass, US2=Backtest, US3=CI, US4=Dashboard)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure - **ALREADY COMPLETE**

- [x] T001 Project structure exists per implementation plan
- [x] T002 Python 3.11 project with FastAPI, DuckDB, pytest dependencies
- [x] T003 [P] Linting and formatting configured (ruff)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure - **ALREADY COMPLETE**

- [x] T004 DuckDB database initialized with `liquidation_snapshots` table
- [x] T005 [P] Existing backtest module in `src/liquidationheatmap/validation/backtest.py`
- [x] T006 [P] Zone comparator in `src/liquidationheatmap/validation/zone_comparator.py`
- [x] T007 [P] OCR extractor in `src/liquidationheatmap/validation/ocr_extractor.py`
- [x] T008 Validation storage framework in `src/validation/storage.py`

**Checkpoint**: Foundation ready ✅

---

## Phase 3: User Story 1 - Coinglass Benchmark (Priority: P0) ✅ COMPLETE

**Goal**: Compare our liquidation predictions against Coinglass industry standard

**Independent Test**: Run `uv run python scripts/validate_vs_coinglass.py --mock` → hit_rate ≥ 70%

### Implementation for User Story 1 - ✅ ALL COMPLETE

- [x] T009 [US1] Create Coinglass scraper in `src/liquidationheatmap/validation/coinglass_scraper.py`
- [x] T010 [US1] Implement Playwright-based scraping with retry logic
- [x] T011 [US1] Add Hyperliquid API alternative fetcher
- [x] T012 [US1] Implement price level comparison in `scripts/validate_vs_coinglass.py`
- [x] T013 [US1] Add hit_rate, zone_overlap, long/short breakdown metrics
- [x] T014 [US1] Create validation CLI with `--mock` and `--summary` options
- [x] T015 [US1] Run Gate 1 validation → **PASSED** (hit_rate=77.8%)

**Checkpoint**: User Story 1 COMPLETE ✅ → Gate 1 PASSED

---

## Phase 4: User Story 2 - Historical Backtest (Priority: P0) ✅ COMPLETE

**Goal**: Validate model accuracy against historical price movements

**Independent Test**: Run `uv run python scripts/run_backtest.py --symbol BTCUSDT` → F1 ≥ 60%

### Implementation for User Story 2 - ✅ ALL COMPLETE

- [x] T016 [US2] Create backtest framework in `src/liquidationheatmap/validation/backtest.py`
- [x] T017 [US2] Implement `BacktestConfig` and `BacktestResult` dataclasses
- [x] T018 [US2] Implement `get_predicted_zones()` to query liquidation_snapshots
- [x] T019 [US2] Implement `get_actual_liquidations()` for price extremes
- [x] T020 [US2] Implement `match_predictions_to_actuals()` with tolerance matching
- [x] T021 [US2] Add `calculate_metrics()` for Precision, Recall, F1
- [x] T022 [US2] Create `run_backtest()` orchestrator function
- [x] T023 [US2] Add `generate_backtest_report()` markdown output
- [x] T024 [US2] Create CLI in `scripts/run_backtest.py`
- [x] T025 [US2] Run Gate 2 validation → **PASSED** (F1=80.93%, Precision=100%, Recall=68%)

**Checkpoint**: User Story 2 COMPLETE ✅ → Gate 2 PASSED

---

## Phase 5: User Story 3 - CI Integration (Priority: P1) 🎯 MVP

**Goal**: Automate validation on model changes with GitHub Actions

**Independent Test**: `gh workflow run validation.yml` completes successfully

### Implementation for User Story 3

- [x] T026 [P] [US3] Validation tests exist in `tests/validation/` (26 files)
- [x] T027 [P] [US3] Create data models in `src/validation/pipeline/models.py` per data-model.md
- [x] T028 [US3] Create pipeline orchestrator in `src/validation/pipeline/orchestrator.py`
- [x] T029 [US3] Add `run_pipeline()` to coordinate backtest + optional Coinglass
- [x] T030 [US3] Implement Gate 2 evaluation logic in orchestrator
- [x] T031 [US3] Create metrics aggregator in `src/validation/pipeline/metrics_aggregator.py`
- [x] T032 [US3] Add `compute_overall_grade()` (A/B/C/F based on F1)
- [x] T033 [US3] Create CI runner entrypoint in `src/validation/pipeline/ci_runner.py`
- [x] T034 [US3] Create unified CLI in `scripts/run_validation_pipeline.py`
- [x] T035 [US3] Create GitHub Actions workflow in `.github/workflows/validation.yml`
- [x] T036 [US3] Configure weekly schedule (cron: Monday 6am UTC)
- [x] T037 [US3] Add model change trigger (`src/liquidationheatmap/models/**`)
- [x] T038 [US3] Configure self-hosted runner requirement
- [x] T039 [US3] Add workflow artifact upload for reports

**Checkpoint**: CI pipeline runs on schedule and model changes

---

## Phase 6: User Story 4 - Real-time Dashboard (Priority: P2)

**Goal**: Display validation metrics in a monitoring dashboard

**Independent Test**: Open `http://localhost:8000/api/validation/dashboard` → shows metrics

### Implementation for User Story 4

- [x] T040 [P] [US4] Create DuckDB schema migration for `validation_pipeline_runs` table
- [x] T041 [P] [US4] Create DuckDB schema migration for `validation_backtest_results` table
- [x] T042 [P] [US4] Create DuckDB schema migration for `validation_metrics_history` table
- [x] T043 [US4] Extend `src/validation/storage.py` with new table operations (via metrics_aggregator)
- [x] T044 [US4] Create `DashboardMetrics` dataclass in `src/validation/pipeline/models.py`
- [x] T045 [US4] Add `get_dashboard_metrics()` to metrics_aggregator
- [x] T046 [US4] Create API endpoint in `src/api/endpoints/dashboard.py`
- [x] T047 [US4] Implement `GET /api/validation/dashboard` per OpenAPI contract
- [x] T048 [US4] Implement `POST /api/validation/pipeline/run` per OpenAPI contract
- [x] T049 [US4] Implement `GET /api/validation/pipeline/status/{run_id}` per OpenAPI contract
- [x] T050 [US4] Implement `GET /api/validation/history` per OpenAPI contract
- [x] T051 [US4] Register dashboard router in FastAPI app
- [x] T052 [US4] Create frontend dashboard in `frontend/validation_dashboard.html`
- [x] T053 [US4] Add Plotly.js trend chart visualization
- [x] T054 [US4] Add status indicator (healthy/warning/critical)
- [x] T055 [US4] Add alert display section

**Checkpoint**: Dashboard shows live validation metrics with trend chart

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T056 [P] Update `specs/014-validation-pipeline/quickstart.md` with final commands
- [ ] T057 Code cleanup - remove debug prints, unused imports
- [ ] T058 Performance validation - ensure <5min pipeline, <100ms API
- [ ] T059 Run full quickstart.md validation end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: ✅ Complete
- **Foundational (Phase 2)**: ✅ Complete
- **US1 Coinglass (Phase 3)**: ✅ Complete (Gate 1 PASSED)
- **US2 Backtest (Phase 4)**: ✅ Complete (Gate 2 PASSED)
- **US3 CI (Phase 5)**: Ready to start - depends on Phase 2, 4
- **US4 Dashboard (Phase 6)**: Ready to start - depends on Phase 2, 4
- **Polish (Phase 7)**: Depends on Phase 5, 6

### User Story Dependencies

| Story | Dependencies | Can Parallel? |
|-------|--------------|---------------|
| US1 (Coinglass) | Foundational | ✅ (Complete) |
| US2 (Backtest) | Foundational | ✅ (Complete) |
| US3 (CI) | US2 (backtest module) | ✅ Start now |
| US4 (Dashboard) | US2 (backtest module) | ✅ Start now |

### Within User Story 3 (CI)

1. T027 Models → T028-T033 Orchestrator → T034 CLI → T035-T39 GitHub Actions

### Within User Story 4 (Dashboard)

1. T040-T42 Schema → T043 Storage → T044-T45 Metrics → T046-T51 API → T52-T55 Frontend

### Parallel Opportunities

```bash
# Phase 5 + Phase 6 can run in parallel (different concerns):
# Developer A: US3 CI Integration (T027-T039)
# Developer B: US4 Dashboard (T040-T055)
```

---

## Parallel Example: User Story 3 (CI)

```bash
# Launch model creation in parallel with test review:
Task: "Create data models in src/validation/pipeline/models.py"
Task: "Review existing tests in tests/validation/"

# Then sequentially:
Task: "Create pipeline orchestrator in src/validation/pipeline/orchestrator.py"
Task: "Create CI runner entrypoint in src/validation/pipeline/ci_runner.py"
Task: "Create GitHub Actions workflow in .github/workflows/validation.yml"
```

---

## Implementation Strategy

### Current Status (Post-Phase 5)

1. ✅ Phase 1-4 Complete (Setup + Foundation + US1 + US2)
2. ✅ Gate 1 PASSED (Coinglass hit_rate=77.8%)
3. ✅ Gate 2 PASSED (Backtest F1=80.93%)
4. ✅ Phase 5 COMPLETE (CI Integration) - Orchestrator, CLI, GitHub Actions
5. 🎯 **Next**: Phase 6 (Dashboard) - 14 tasks remaining
6. **Finally**: Phase 7 (Polish) - 4 tasks remaining

### MVP Recommendation

For **minimal viable pipeline**:
1. Complete T027-T034 (Orchestrator + CLI) - enables unified validation
2. Defer T035-T039 (GitHub Actions) until repo goes public
3. Defer T040-T055 (Dashboard) until real-time needed

### Task Counts

| Phase | Total | Complete | Remaining |
|-------|-------|----------|-----------|
| Setup | 3 | 3 | 0 |
| Foundational | 5 | 5 | 0 |
| US1 Coinglass | 7 | 7 | 0 |
| US2 Backtest | 10 | 10 | 0 |
| US3 CI | 14 | 14 | 0 |
| US4 Dashboard | 16 | 16 | 0 |
| Polish | 4 | 0 | 4 |
| **TOTAL** | **59** | **55** | **4** |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Gates already passed - remaining work is infrastructure (CI, Dashboard)
- Commit after each task or logical group
- Test validation: `uv run pytest tests/validation/ -v`
