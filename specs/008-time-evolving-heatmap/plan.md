# Implementation Plan: Time-Evolving Liquidation Heatmap

**Branch**: `008-time-evolving-heatmap` | **Date**: 2025-12-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-time-evolving-heatmap/spec.md`

## Summary

Redesign the liquidation heatmap to implement a **time-evolving model** where liquidation levels are dynamically created from OI increases and consumed when price crosses them. This fixes the fundamental flaw where static liquidation bands persist incorrectly after being triggered.

**Technical Approach**: Forward iteration through candles, tracking position lifecycle (creation → consumption → closure) with proper price-crossing detection logic.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, DuckDB, Pydantic, Plotly.js
**Storage**: DuckDB (`data/processed/liquidations.duckdb`)
**Testing**: pytest with TDD guard
**Target Platform**: Linux server + Web browser (frontend)
**Project Type**: Web application (backend API + frontend visualization)
**Performance Goals**:
  - Single heatmap calculation: <500ms for 1000 candles
  - API response: <100ms p95 (cached)
  - Frontend render: <1s for 200 timestamps
**Constraints**:
  - Must handle 417K+ OI records efficiently
  - Memory-efficient for large time ranges
  - Real-time capable (future: WebSocket streaming)
**Scale/Scope**:
  - Initial: BTCUSDT only
  - Data: 14K 5m candles, 417K OI records
  - Output: 100-500 timestamps × 100 price buckets

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design Gate (PASS/FAIL)

| Principle | Status | Evidence |
|-----------|--------|----------|
| **Mathematical Correctness (MUST)** | ✅ PASS | Liquidation formulas from Binance specs; price-crossing logic is deterministic |
| **Test-Driven Development (MUST)** | ⏳ PENDING | Will follow Red-Green-Refactor; tests defined in tasks.md |
| **Exchange Compatibility (MUST)** | ✅ PASS | Uses Binance liquidation formula; validated against exchange docs |
| **Performance Efficiency (SHOULD)** | ⏳ PENDING | Performance budgets defined; pre-computation strategy planned |
| **Data Integrity (MUST)** | ✅ PASS | Read-only calculations; no destructive mutations |
| **Graceful Degradation (SHOULD)** | ✅ PASS | Fallback to static model if time-evolving fails |
| **Progressive Enhancement (SHOULD)** | ✅ PASS | MVP: core algorithm → Phase 2: caching → Phase 3: real-time |
| **Documentation Completeness (MUST)** | ⏳ PENDING | API docs planned; mathematical documentation in spec |

### Quality Gates - Specification Phase

- [x] All functional requirements have acceptance criteria (spec.md §5)
- [x] Non-functional requirements have measurable thresholds (spec.md §6)
- [x] Edge cases explicitly documented (spec.md §2.4)
- [x] Mathematical formulas verified (Binance official documentation)

### Quality Gates - Planning Phase

- [x] Architecture addresses all requirements
- [x] Technology choices justified (DuckDB for analytics, FastAPI for async)
- [x] Risk mitigations identified (spec.md §7)
- [x] Performance budgets allocated (spec.md §6)

## Project Structure

### Documentation (this feature)

```
specs/008-time-evolving-heatmap/
├── plan.md              # This file
├── spec.md              # Feature specification (created)
├── tasks.md             # Implementation tasks (created)
├── research.md          # Phase 0 output (to create)
├── data-model.md        # Phase 1 output (to create)
├── quickstart.md        # Phase 1 output (to create)
└── contracts/           # Phase 1 output (to create)
    └── openapi.yaml
```

### Source Code (repository root)

```
# Web application structure (backend + frontend)

backend/
src/liquidationheatmap/
├── models/
│   ├── position.py              # NEW: LiquidationLevel, HeatmapSnapshot
│   └── time_evolving_heatmap.py # NEW: Core algorithm
├── api/
│   └── main.py                  # UPDATE: New /heatmap-timeseries endpoint
└── ingestion/
    └── db_service.py            # UPDATE: Add time-series queries

frontend/
├── coinglass_heatmap.html       # UPDATE: Time-varying rendering

tests/
├── unit/
│   └── models/
│       └── test_time_evolving_heatmap.py  # NEW
└── integration/
    └── test_heatmap_api.py      # NEW

scripts/
└── precompute_heatmap.py        # NEW: Pre-computation pipeline
```

**Structure Decision**: Web application with Python backend (FastAPI) serving a vanilla JS frontend. No build step required for frontend (matches KISS principle).

## Complexity Tracking

*No constitution violations requiring justification.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | - | - |

## Phase 0 Research Targets

Based on Technical Context unknowns:

1. **OI Delta Interpretation**: How to handle negative OI delta (positions closed)
   - Option A: Remove positions proportionally across all price levels
   - Option B: Remove from nearest price levels first
   - Option C: Ignore (overestimates liquidation density)

2. **Price Crossing Edge Cases**: Exact match vs. wick-only crosses
   - When `candle.low == liq_price` exactly, is it liquidated?
   - Gap scenarios: candle opens below liq_price

3. **Leverage Distribution**: Industry-standard estimates
   - Current hardcoded: 5x(15%), 10x(30%), 25x(25%), 50x(20%), 100x(10%)
   - Validate against Coinglass/industry research

4. **Performance Optimization**: Pre-computation strategy
   - Calculate once, cache in DuckDB
   - Incremental updates for new candles

## Dependencies

```
Required (existing):
- duckdb >= 0.9.0
- fastapi >= 0.100.0
- pydantic >= 2.0.0
- plotly (frontend CDN)

Required (new):
- None (pure Python algorithm)
```
