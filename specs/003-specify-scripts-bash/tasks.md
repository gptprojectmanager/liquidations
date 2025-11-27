# Tasks: Liquidation Model Validation Suite

**Feature**: Validation framework with proxy metrics for continuous model quality assurance
**Prerequisites**: spec.md (available), plan.md (not available - using project conventions)

**Organization**: Tasks grouped by user story for independent implementation and testing

## Format: `- [ ] [ID] [P?] [Story?] Description with file path`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (Automated Weekly), US2 (Manual Trigger), US3 (Historical Trends)

## Path Conventions
- Backend: `src/` at repository root
- Tests: `tests/` at repository root
- Configuration: `config/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and validation framework structure

- [X] T001 Create validation module structure in src/validation/
- [X] T002 Initialize Python dependencies for statistical analysis (scipy, numpy, pandas)
- [X] T003 [P] Configure validation constants in src/validation/constants.py
- [X] T004 [P] Setup DuckDB schema for validation results storage

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core validation infrastructure required by ALL user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Create ValidationRun base model in src/models/validation_run.py
- [X] T006 Create ValidationTest base model in src/models/validation_test.py
- [X] T007 Create ValidationReport model in src/models/validation_report.py
- [X] T008 Implement data fetcher for 30-day historical data in src/validation/data_fetcher.py
- [X] T009 [P] Create validation error handling in src/validation/exceptions.py
- [X] T010 [P] Setup validation logging configuration in src/validation/logger.py
- [X] T011 Implement report storage interface in src/validation/storage.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Automated Weekly Validation (Priority: P1) 🎯 MVP

**Goal**: Automated validation runs weekly at 2 AM UTC with graded reports

**Independent Test**: Trigger scheduled run and verify report generation within 5 minutes

### Core Validation Tests

- [X] T012 [P] [US1] Implement funding rate correlation test in src/validation/tests/funding_correlation.py
- [X] T013 [P] [US1] Implement OI conservation test in src/validation/tests/oi_conservation.py
- [X] T014 [P] [US1] Implement directional positioning test in src/validation/tests/directional_test.py
- [X] T015 [US1] Create test aggregator in src/validation/test_runner.py (depends on T012-T014)

### Grading System

- [ ] T016 [US1] Implement grading calculator (A/B/C/F) in src/validation/grading.py
- [ ] T017 [US1] Create weighted score aggregation in src/validation/scoring.py
- [ ] T018 [US1] Add grade thresholds configuration in config/validation_thresholds.yaml

### Scheduling & Automation

- [X] T019 [US1] Implement APScheduler integration in src/validation/scheduler.py
- [X] T020 [US1] Create weekly trigger at 2 AM UTC in src/validation/cron_jobs.py
- [X] T021 [US1] Add automatic retry logic with backoff in src/validation/retry_handler.py

### Report Generation

- [ ] T022 [US1] Implement JSON report generator in src/validation/reports/json_reporter.py
- [ ] T023 [P] [US1] Implement human-readable report in src/validation/reports/text_reporter.py
- [ ] T024 [US1] Create report persistence in src/validation/reports/report_storage.py

### Alert System

- [ ] T025 [US1] Implement alert trigger for C/F grades in src/validation/alerts/alert_manager.py
- [ ] T026 [P] [US1] Create email notification handler in src/validation/alerts/email_handler.py
- [ ] T027 [P] [US1] Add alert configuration in config/alert_settings.yaml

**Checkpoint**: Automated weekly validation fully functional with alerts

---

## Phase 4: User Story 2 - Manual Validation Trigger (Priority: P2)

**Goal**: On-demand validation runs for development and testing

**Independent Test**: Manually trigger validation and verify results without affecting scheduled runs

### API Endpoints

- [ ] T028 [US2] Create validation trigger endpoint POST /api/validation/run in src/api/validation_endpoints.py
- [ ] T029 [US2] Add validation status endpoint GET /api/validation/status/{run_id} in src/api/validation_endpoints.py
- [ ] T030 [US2] Implement result retrieval endpoint GET /api/validation/report/{run_id} in src/api/validation_endpoints.py

### Queue Management

- [ ] T031 [US2] Implement validation queue with FIFO processing in src/validation/queue_manager.py
- [ ] T032 [US2] Add queue size limit (max 10) and overflow handling in src/validation/queue_config.py
- [ ] T033 [US2] Create concurrent run prevention in src/validation/concurrency_lock.py

### Multi-Model Support

- [ ] T034 [P] [US2] Add model selection parameter in validation runner in src/validation/model_selector.py
- [ ] T035 [US2] Implement separate report generation per model in src/validation/reports/multi_model_reporter.py
- [ ] T036 [P] [US2] Create model comparison utilities in src/validation/comparison.py

**Checkpoint**: Manual validation triggers work independently without disrupting scheduled runs

---

## Phase 5: User Story 3 - Historical Trend Analysis (Priority: P3)

**Goal**: View validation trends over 90+ days for pattern analysis

**Independent Test**: Load dashboard with 90 days of data and verify trend visualization

### Data Retention

- [ ] T037 [US3] Implement 90-day data retention policy in src/validation/retention_policy.py
- [ ] T038 [P] [US3] Create historical data pruning job in src/validation/data_pruner.py
- [ ] T039 [US3] Add time-series storage optimization in src/validation/timeseries_storage.py

### Trend Calculation

- [ ] T040 [US3] Implement trend calculator for each metric in src/validation/trends/trend_calculator.py
- [ ] T041 [P] [US3] Create moving average calculations in src/validation/trends/moving_averages.py
- [ ] T042 [P] [US3] Add degradation detection algorithm in src/validation/trends/degradation_detector.py

### Dashboard API

- [ ] T043 [US3] Create trend data endpoint GET /api/validation/trends in src/api/trend_endpoints.py
- [ ] T044 [US3] Add comparison endpoint GET /api/validation/compare in src/api/comparison_endpoints.py
- [ ] T045 [US3] Implement dashboard data aggregation in src/api/dashboard_aggregator.py

### Visualization Support

- [ ] T046 [P] [US3] Create chart data formatter in src/validation/visualization/chart_formatter.py
- [ ] T047 [P] [US3] Add performance metrics calculator in src/validation/visualization/metrics.py
- [ ] T048 [US3] Implement cache layer for dashboard queries in src/validation/visualization/cache.py

**Checkpoint**: Historical trends viewable with 90-day history and comparison capabilities

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements affecting multiple user stories

- [ ] T049 [P] Add comprehensive logging across all validation modules
- [ ] T050 Implement performance optimizations for <5 minute execution
- [ ] T051 [P] Add input validation and sanitization
- [ ] T052 Create API documentation in docs/api/validation.md
- [ ] T053 [P] Add monitoring metrics for validation runs
- [ ] T054 Security hardening for API endpoints
- [ ] T055 Create user documentation in docs/user_guide/validation_suite.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - Core MVP functionality
- **User Story 2 (Phase 4)**: Depends on Foundational - Can run parallel with US1
- **User Story 3 (Phase 5)**: Depends on Foundational - Can run parallel with US1/US2
- **Polish (Phase 6)**: Depends on all desired user stories

### User Story Dependencies

- **US1**: Independent after Foundational phase
- **US2**: Independent after Foundational phase (may reuse US1 components)
- **US3**: Independent after Foundational phase (needs US1 data but not blocking)

### Within Each User Story

1. Core logic implementation first
2. Integration components next
3. API/UI last
4. Story complete before moving to next

### Parallel Opportunities

**Phase 3 (US1) Parallel Tasks:**
```bash
# Launch all validation tests together:
T012: "Implement funding rate correlation test"
T013: "Implement OI conservation test"
T014: "Implement directional positioning test"

# Launch report generators together:
T022: "Implement JSON report generator"
T023: "Implement human-readable report"
```

**Cross-Story Parallelization:**
```bash
# After Foundational phase, launch all stories:
Developer A: US1 (T012-T027) - Automated validation
Developer B: US2 (T028-T036) - Manual triggers
Developer C: US3 (T037-T048) - Historical trends
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T011)
3. Complete Phase 3: User Story 1 (T012-T027)
4. **VALIDATE**: Test automated weekly validation
5. Deploy MVP with core validation functionality

### Incremental Delivery

1. **Week 1**: Setup + Foundational → Infrastructure ready
2. **Week 2**: US1 Core Tests (T012-T015) → Basic validation working
3. **Week 3**: US1 Automation (T016-T027) → Automated weekly runs (MVP!)
4. **Week 4**: US2 (T028-T036) → Manual triggers added
5. **Week 5**: US3 (T037-T048) → Historical analysis added
6. **Week 6**: Polish (T049-T055) → Production ready

### Risk Mitigation

- Start with US1 (highest priority) for early validation
- Each story independently testable reduces integration risk
- Parallel execution options if schedule tight
- Polish phase can be deferred if needed

---

## Summary Statistics

- **Total Tasks**: 55
- **Setup Tasks**: 4
- **Foundational Tasks**: 7
- **User Story 1 Tasks**: 16 (MVP)
- **User Story 2 Tasks**: 9
- **User Story 3 Tasks**: 12
- **Polish Tasks**: 7
- **Parallel Opportunities**: 23 tasks marked [P]
- **MVP Scope**: 27 tasks (Phases 1-3)

## Success Metrics

- Validation suite runs in <5 minutes ✓
- Weekly automation at 2 AM UTC ✓
- A/B/C/F grading system ✓
- 90-day data retention ✓
- Manual triggers without disruption ✓
- All user stories independently testable ✓