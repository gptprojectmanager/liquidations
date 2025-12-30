# Implementation Plan: 014-validation-pipeline

**Branch**: `014-validation-pipeline` | **Date**: 2025-12-30 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/014-validation-pipeline/spec.md`

## Summary

Build a unified validation pipeline that integrates existing validation components (Coinglass OCR comparison, backtest framework, validation API) into an automated CI/CD system with real-time monitoring dashboard. Leverages existing `src/liquidationheatmap/validation/` and `src/validation/` modules.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, DuckDB, httpx, pytest, pytest-benchmark, pytesseract (OCR), scikit-learn (metrics), APScheduler (cron)
**Storage**: DuckDB (`data/processed/liquidations.duckdb`), validation results in `data/validation/`
**Testing**: pytest with pytest-asyncio, hypothesis for property-based tests
**Target Platform**: Linux server
**Project Type**: Single project
**Performance Goals**: Validation run <5min, API response <100ms, Dashboard refresh <30s
**Constraints**: Must not block main API performance, OCR requires Tesseract installed
**Scale/Scope**: Initial: BTC/USDT, expandable to ETH and multi-exchange

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design Evaluation

| Principle | Status | Compliance Notes |
|-----------|--------|------------------|
| **1. Mathematical Correctness (MUST)** | ✅ PASS | F1/Precision/Recall calculations in `backtest.py` verified, correlation metrics defined |
| **2. Test-Driven Development (MUST)** | ✅ PASS | Tests exist in `tests/validation/`, will extend with CI integration tests |
| **3. Exchange Compatibility (MUST)** | ✅ PASS | Validates against Binance liquidation formula, Coinglass as external reference |
| **4. Performance Efficiency (SHOULD)** | ✅ PASS | Background processing, won't block API (<100ms p95) |
| **5. Data Integrity (MUST)** | ✅ PASS | DuckDB ACID, validation results logged with timestamps |
| **6. Graceful Degradation (SHOULD)** | ✅ PASS | Fallback to cached results, retry logic in place |
| **7. Progressive Enhancement (SHOULD)** | ✅ PASS | Phases: Coinglass → Backtest → CI → Dashboard |
| **8. Documentation Completeness (MUST)** | ✅ PASS | Thresholds documented in spec.md, interpretation in research.md |

**Gate Status**: ✅ **PASS** - No blocking violations

## Project Structure

### Documentation (this feature)

```
specs/014-validation-pipeline/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```
src/
├── liquidationheatmap/validation/   # EXISTING - OCR-based Coinglass comparison
│   ├── backtest.py                  # ✅ Historical backtest (F1 metrics)
│   ├── zone_comparator.py           # ✅ Coinglass vs API comparison
│   ├── ocr_extractor.py             # ✅ Screenshot OCR parsing
│   └── screenshot_parser.py         # ✅ Coinglass screenshot processing
├── validation/                      # EXISTING - Model validation API
│   ├── test_runner.py               # ✅ Validation orchestrator
│   ├── comparison.py                # ✅ Model comparison utilities
│   ├── storage.py                   # ✅ DuckDB persistence
│   └── tests/                       # ✅ Funding/OI/Directional tests
│
│   # NEW - Pipeline integration
├── validation/pipeline/             # NEW - Unified pipeline
│   ├── __init__.py
│   ├── orchestrator.py              # Master coordinator for all validation types
│   ├── ci_runner.py                 # GitHub Actions entry point
│   └── metrics_aggregator.py        # Combine all metrics into unified report
│
├── api/endpoints/
│   └── dashboard.py                 # NEW - Real-time monitoring endpoint

scripts/
├── validate_vs_coinglass.py         # ✅ EXISTS - Coinglass validation
├── run_backtest.py                  # ✅ EXISTS - Historical backtest
└── run_validation_pipeline.py       # NEW - Unified pipeline CLI

tests/
├── validation/                      # EXISTING
│   ├── test_backtest.py             # ✅ Backtest unit tests
│   ├── test_zone_comparator.py      # ✅ Zone comparison tests
│   └── test_screenshot_parser.py    # ✅ OCR tests
└── pipeline/                        # NEW
    ├── test_orchestrator.py
    ├── test_ci_integration.py
    └── test_metrics_aggregator.py

.github/workflows/
└── validation.yml                   # NEW - CI workflow

frontend/
└── validation_dashboard.html        # NEW - Real-time monitoring UI
```

**Structure Decision**: Extends existing validation architecture. New code in `src/validation/pipeline/` and `.github/workflows/`. Frontend dashboard is a single HTML file (consistent with KISS approach).

## Complexity Tracking

*No constitution violations requiring justification.*

---

## Key Technical Decisions

### 1. Leverage Existing Validation Modules

**Decision**: Integrate, don't replace, existing validation code.

**Rationale**:
- `src/liquidationheatmap/validation/backtest.py` already implements F1/Precision/Recall ✅
- `src/liquidationheatmap/validation/zone_comparator.py` already implements Coinglass comparison ✅
- `src/validation/test_runner.py` already orchestrates validation tests ✅

**What's NEW**:
- Pipeline orchestrator to run all validations in sequence
- CI integration (GitHub Actions workflow)
- Dashboard endpoint for real-time monitoring
- Unified metrics aggregation

### 2. OCR-Based Coinglass Comparison (Not API)

**Decision**: Use screenshot OCR instead of reverse-engineering Coinglass API.

**Rationale**:
- Coinglass API is undocumented and may change
- Screenshot comparison is more robust
- Already implemented in `ocr_extractor.py`
- Manual screenshot collection acceptable for validation cadence

### 3. Gate-Based Decision Flow

**Decision**: Implement spec's gate system (Phase 1 → Phase 2 → CI).

**Rationale**:
- Correlation > 0.7 → proceed (from spec)
- F1 > 0.6 → model validated (from spec)
- Early termination prevents wasted effort

### 4. DuckDB for Validation Results

**Decision**: Store validation history in DuckDB (not separate database).

**Rationale**:
- Consistent with existing architecture
- No additional infrastructure
- Fast queries for dashboard

---

## Dependencies Analysis

### Existing (Already Available)

| Module | Location | Purpose |
|--------|----------|---------|
| BacktestConfig/Result | `src/liquidationheatmap/validation/backtest.py` | Historical validation |
| ZoneComparator | `src/liquidationheatmap/validation/zone_comparator.py` | Coinglass comparison |
| ValidationTestRunner | `src/validation/test_runner.py` | Test orchestration |
| ValidationStorage | `src/validation/storage.py` | Results persistence |

### New Dependencies (From pyproject.toml)

| Package | Version | Already Present | Purpose |
|---------|---------|-----------------|---------|
| pytest | >=7.4.0 | ✅ Yes | CI testing |
| pytest-benchmark | >=4.0.0 | ✅ Yes | Performance validation |
| APScheduler | >=3.10.0 | ✅ Yes | Scheduled validation |
| pytesseract | >=0.3.13 | ✅ Yes | OCR extraction |
| scipy | >=1.11.0 | ✅ Yes | Correlation metrics |

**Conclusion**: No new dependencies required.

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| OCR accuracy varies | Medium | Medium | Confidence threshold (>0.8), multiple screenshot samples |
| Coinglass format changes | Low | High | Flexible OCR parser, manual fallback |
| Model fundamentally flawed | Low | High | Early gate check prevents scaling broken model |
| CI too slow | Medium | Medium | Parallel test execution, cache invalidation |
| Dashboard overwhelms API | Low | Medium | Separate endpoint, rate limiting |

---

## Phase Summary

### Phase 0: Research (research.md)
- Resolve: Coinglass screenshot format consistency
- Resolve: Optimal correlation calculation method
- Resolve: CI workflow best practices for validation

### Phase 1: Design (data-model.md, contracts/, quickstart.md)
- Define ValidationPipelineResult model
- Define dashboard API contract
- Document quickstart for running pipeline

### Phase 2: Tasks (tasks.md - via /speckit.tasks)
- Implement orchestrator
- Create CI workflow
- Build dashboard

---

## Success Metrics (from spec)

| Metric | Threshold | Target |
|--------|-----------|--------|
| Coinglass Correlation | > 0.7 | 0.8+ |
| Backtest Precision | > 60% | 70%+ |
| Backtest Recall | > 50% | 60%+ |
| Real-time Hit Rate | > 50% | 65%+ |

---

## Post-Design Constitution Check

*Re-evaluation after Phase 1 design completion.*

### Post-Design Evaluation

| Principle | Status | Compliance Notes |
|-----------|--------|------------------|
| **1. Mathematical Correctness (MUST)** | ✅ PASS | F1/Precision/Recall formulas verified in `data-model.md`. Gate 2 thresholds documented. |
| **2. Test-Driven Development (MUST)** | ✅ PASS | Test structure defined in `Project Structure`. Existing tests cover backtest/zone_comparator. |
| **3. Exchange Compatibility (MUST)** | ✅ PASS | Validates Binance formula. Coinglass comparison informational only (methodology mismatch documented in research.md). |
| **4. Performance Efficiency (SHOULD)** | ✅ PASS | <5min validation run, <100ms API. Dashboard uses separate endpoint with rate limiting. |
| **5. Data Integrity (MUST)** | ✅ PASS | DuckDB schema defined with timestamps, run_id tracking. Immutable validation results. |
| **6. Graceful Degradation (SHOULD)** | ✅ PASS | Pipeline handles missing data (returns error, doesn't crash). Fallback to cached metrics. |
| **7. Progressive Enhancement (SHOULD)** | ✅ PASS | Design supports: backtest-only → + Coinglass → + real-time. CI optional. |
| **8. Documentation Completeness (MUST)** | ✅ PASS | API contracts in OpenAPI format. Quickstart documented. Threshold interpretation in research.md. |

**Final Gate Status**: ✅ **PASS** - All constitution principles satisfied

---

## Artifacts Generated

| Artifact | Path | Status |
|----------|------|--------|
| Implementation Plan | `specs/014-validation-pipeline/plan.md` | ✅ Complete |
| Research Document | `specs/014-validation-pipeline/research.md` | ✅ Complete |
| Data Model | `specs/014-validation-pipeline/data-model.md` | ✅ Complete |
| API Contract | `specs/014-validation-pipeline/contracts/dashboard_api.json` | ✅ Complete |
| CI Contract | `specs/014-validation-pipeline/contracts/ci_workflow.yml` | ✅ Complete |
| Quickstart Guide | `specs/014-validation-pipeline/quickstart.md` | ✅ Complete |
| Tasks | `specs/014-validation-pipeline/tasks.md` | ✅ Complete |

---

## Next Steps

1. Run `/speckit.tasks` to generate implementation tasks
2. Implement orchestrator (`src/validation/pipeline/orchestrator.py`)
3. Create CI workflow (`.github/workflows/validation.yml`)
4. Build dashboard endpoint and frontend
