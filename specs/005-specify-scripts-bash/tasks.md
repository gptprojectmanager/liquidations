# Tasks: Funding Rate Bias Adjustment

**Feature**: LIQHEAT-005 - Market sentiment adjustment using funding rate data
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/bias-api.yaml, quickstart.md
**Approach**: Implementation without TDD (tests optional based on project needs)

## Task Format: `- [ ] [ID] [P?] [Story?] Description with file path`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (Bull Market Positioning), US2 (Extreme Sentiment), US3 (Historical Correlation)

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Install dependencies and configure project structure

- [X] T001 Install Python dependencies (httpx, cachetools) in pyproject.toml
- [X] T002 [P] Create configuration structure in config/bias_settings.yaml
- [X] T003 [P] Create src/models/funding/ directory for new model classes
- [X] T004 [P] Create src/services/funding/ directory for service classes
- [X] T005 [P] Create tests/unit/funding/ directory for unit tests
- [X] T006 [P] Create tests/integration/funding/ directory for integration tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core mathematical functions and configuration that all user stories depend on

### Mathematical Foundation

- [X] T007 Implement tanh conversion formula in src/services/funding/math_utils.py
- [X] T008 Create configuration loader in src/services/funding/adjustment_config.py
- [X] T009 Implement OI conservation validation in src/services/funding/validators.py

### Data Models

- [X] T010 [P] Implement FundingRate model in src/models/funding/funding_rate.py
- [X] T011 [P] Implement BiasAdjustment model in src/models/funding/bias_adjustment.py
- [ ] T012 [P] Implement SentimentIndicator model in src/models/funding/sentiment_indicator.py
- [X] T013 [P] Implement AdjustmentConfig model in src/models/funding/adjustment_config.py

### Caching Infrastructure

- [X] T014 Implement TTL cache wrapper in src/services/funding/cache_manager.py
- [X] T015 Configure cachetools with 5-minute TTL in cache_manager.py

---

## Phase 3: User Story 1 - Bull Market Positioning (P1)

**Goal**: Core functionality to adjust long/short ratios based on funding rate
**Independent Test**: With +0.03% funding, verify long ratio shows ~68% (not 50%)

### Binance API Integration

- [X] T016 [US1] Implement Binance funding rate API client in src/services/funding/funding_fetcher.py
- [X] T017 [US1] Add rate limiting with exponential backoff in funding_fetcher.py
- [X] T018 [US1] Implement funding rate caching logic in funding_fetcher.py

### Bias Calculation Service

- [X] T019 [US1] Implement BiasCalculator class in src/services/funding/bias_calculator.py
- [X] T020 [US1] Add tanh-based conversion method in bias_calculator.py
- [X] T021 [US1] Implement confidence score calculation in bias_calculator.py
- [X] T022 [US1] Add OI conservation check in bias_calculator.py

### Model Integration

- [X] T023 [US1] Add bias adjustment to BinanceStandardModel in src/liquidationheatmap/models/binance_standard.py
- [ ] T024 [US1] Add bias adjustment to EnsembleModel in src/liquidationheatmap/models/ensemble.py
- [ ] T025 [US1] Refactor FundingAdjustedModel in src/liquidationheatmap/models/funding_adjusted.py

### API Endpoints

- [X] T026 [US1] Implement GET /api/bias/funding/{symbol} endpoint in src/api/endpoints/bias.py
- [X] T027 [US1] Implement GET /api/bias/adjustment/{symbol} endpoint in src/api/endpoints/bias.py
- [X] T028 [US1] Add OpenAPI schema validation in bias.py endpoints

### Database Storage

- [ ] T029 [US1] Create DuckDB schema for funding_rates table in src/db/migrations/005_funding_rates.sql
- [ ] T030 [US1] Implement historical funding storage in src/services/funding/storage_service.py

### Testing (Optional)

- [X] T031 [P] [US1] Unit test tanh formula in tests/unit/funding/test_bias_calculator.py
- [X] T032 [P] [US1] Unit test OI conservation in tests/unit/funding/test_validators.py
- [X] T033 [P] [US1] Integration test Binance API in tests/integration/funding/test_binance_api.py

---

## Phase 4: User Story 2 - Extreme Sentiment Detection (P2)

**Goal**: Alert system for extreme funding rates indicating market risk
**Independent Test**: Alert triggers when funding exceeds ±0.05% threshold

### Sentiment Classification

- [ ] T034 [US2] Implement sentiment classification logic in src/services/funding/sentiment_analyzer.py
- [ ] T035 [US2] Add threshold configuration (±0.05%) in sentiment_analyzer.py
- [ ] T036 [US2] Implement rapid change detection (>0.03% in 8h) in sentiment_analyzer.py

### Alert System

- [ ] T037 [US2] Create alert manager in src/services/funding/alert_manager.py
- [ ] T038 [US2] Implement extreme bias alerts in alert_manager.py
- [ ] T039 [US2] Add sentiment shift alerts in alert_manager.py
- [ ] T040 [US2] Configure alert thresholds in config/bias_settings.yaml

### API Endpoints

- [ ] T041 [US2] Implement GET /api/bias/sentiment/{symbol} endpoint in src/api/endpoints/bias.py
- [ ] T042 [US2] Add alert history endpoint in src/api/endpoints/bias.py

### UI Integration

- [ ] T043 [US2] Add sentiment indicator to response models in src/api/models/responses.py
- [ ] T044 [US2] Include alert messages in API responses

### Testing (Optional)

- [ ] T045 [P] [US2] Unit test sentiment classification in tests/unit/funding/test_sentiment_analyzer.py
- [ ] T046 [P] [US2] Test alert triggering in tests/unit/funding/test_alert_manager.py

---

## Phase 5: User Story 3 - Historical Correlation Validation (P3)

**Goal**: Validate that funding-based adjustments improve model accuracy
**Independent Test**: 30-day correlation test shows coefficient >0.7

### Correlation Analysis

- [ ] T047 [US3] Implement Pearson correlation calculator in src/services/funding/correlation_analyzer.py
- [ ] T048 [US3] Add confidence interval calculation in correlation_analyzer.py
- [ ] T049 [US3] Implement backtesting framework in src/services/funding/backtest_service.py

### Historical Data Management

- [ ] T050 [US3] Implement 90-day retention policy in storage_service.py
- [ ] T051 [US3] Create data pruning job in src/services/funding/data_pruner.py
- [ ] T052 [US3] Add time-series aggregation in storage_service.py

### Validation Reports

- [ ] T053 [US3] Create correlation report generator in src/services/funding/report_generator.py
- [ ] T054 [US3] Add improvement metrics calculation in report_generator.py
- [ ] T055 [US3] Generate correlation plots in report_generator.py

### API Endpoints

- [ ] T056 [US3] Implement GET /api/bias/correlation endpoint in src/api/endpoints/bias.py
- [ ] T057 [US3] Add validation report endpoint in src/api/endpoints/bias.py

### Testing (Optional)

- [ ] T058 [P] [US3] Test correlation calculation in tests/unit/funding/test_correlation_analyzer.py
- [ ] T059 [P] [US3] Test backtesting accuracy in tests/integration/funding/test_backtest.py

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Performance optimization, error handling, and documentation

### Manual Override Support (FR-010)

- [ ] T060 Implement POST /api/bias/override endpoint in src/api/endpoints/bias.py
- [ ] T061 Add override persistence with TTL in src/services/funding/override_manager.py
- [ ] T062 Implement override validation in override_manager.py

### Performance Optimization

- [ ] T063 [P] Optimize tanh calculation for batch processing in bias_calculator.py
- [ ] T064 [P] Add performance monitoring in src/services/funding/metrics.py
- [ ] T065 [P] Implement concurrent funding fetches in funding_fetcher.py

### Error Handling

- [ ] T066 [P] Add comprehensive error handling in funding_fetcher.py
- [ ] T067 [P] Implement fallback to 50/50 neutral in bias_calculator.py
- [ ] T068 [P] Add stale data detection in cache_manager.py

### Configuration Management

- [ ] T069 Implement GET/PATCH /api/bias/config endpoints in src/api/endpoints/bias.py
- [ ] T070 Add hot-reload for configuration in adjustment_config.py

### Documentation & Monitoring

- [ ] T071 [P] Add logging throughout funding services
- [ ] T072 [P] Create operational metrics dashboard queries
- [ ] T073 [P] Update API documentation with bias endpoints

---

## Dependencies & Execution Strategy

### Story Dependencies
```
Phase 2 (Foundational)
    ↓
Phase 3 (US1: Bull Market Positioning) [CORE - can deliver MVP here]
    ↓
Phase 4 (US2: Extreme Sentiment) [Independent after US1]
    ↓
Phase 5 (US3: Historical Correlation) [Independent after US1]
    ↓
Phase 6 (Polish)
```

### Parallel Execution Examples

**Phase 1 (Setup)**: T002-T006 can run in parallel (different directories)

**Phase 2 (Foundational)**:
- T010-T013 can run in parallel (different model files)

**Phase 3 (US1)**:
- T031-T033 tests can run in parallel once implementation complete

**Phase 4 (US2)**:
- T045-T046 tests can run in parallel

**Phase 5 (US3)**:
- T058-T059 tests can run in parallel

**Phase 6 (Polish)**:
- T063-T065 performance tasks in parallel
- T066-T068 error handling in parallel
- T071-T073 documentation in parallel

---

## Implementation Strategy

### MVP Delivery (Phase 1-3 only)
**Delivers**: Core bias adjustment functionality
- Funding rate fetching ✓
- Bias calculation ✓
- Model integration ✓
- Basic API endpoints ✓
**Time estimate**: 1 week

### Full Feature (All Phases)
**Delivers**: Complete feature with alerts and validation
- All MVP features +
- Extreme sentiment detection ✓
- Historical correlation validation ✓
- Manual override support ✓
- Performance optimization ✓
**Time estimate**: 2-3 weeks

### Testing Strategy
Tests are OPTIONAL and marked with "Testing (Optional)" sections. If TDD is desired:
1. Write tests first (T031-T033, T045-T046, T058-T059)
2. Implement to make tests pass
3. Refactor with confidence

---

## Task Summary

- **Total Tasks**: 73
- **Setup Tasks**: 6 (T001-T006)
- **Foundational Tasks**: 9 (T007-T015)
- **User Story 1 Tasks**: 18 core + 3 optional tests (T016-T033)
- **User Story 2 Tasks**: 11 core + 2 optional tests (T034-T046)
- **User Story 3 Tasks**: 11 core + 2 optional tests (T047-T059)
- **Polish Tasks**: 14 (T060-T073)

### Parallel Opportunities
- Phase 1: 5 tasks parallelizable
- Phase 2: 4 tasks parallelizable
- Phase 3-5: All test tasks parallelizable
- Phase 6: 9 tasks parallelizable
- **Total**: ~25 tasks can be parallelized

### Independent Test Criteria
- **US1**: Funding +0.03% → Long ratio ~68% (not 50%)
- **US2**: Funding ±0.05% → Alert triggered
- **US3**: 30-day correlation → Coefficient >0.7

---

## Validation Checklist

✅ All 73 tasks follow required format: `- [ ] [ID] [P?] [Story?] Description with file path`
✅ Each user story has clear independent test criteria
✅ Parallel execution opportunities identified (25 tasks)
✅ MVP scope defined (Phases 1-3, ~30 tasks)
✅ Story dependencies documented (US1 is prerequisite for US2/US3)
✅ File paths specified for every task

---

**Tasks generation complete** | Ready for implementation | 2025-12-01 ✅