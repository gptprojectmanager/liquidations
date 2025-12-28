# Implementation Plan: ETH/USDT Symbol Support

**Branch**: `009-eth-symbol` | **Date**: 2025-12-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-eth-symbol/spec.md`

## Summary

Add ETH/USDT support to LiquidationHeatmap via **100% code reuse** - pure parameterization of existing symbol-agnostic pipeline. Zero new algorithms, zero new logic, only data ingestion and validation.

**Key Insight**: Every layer (ingestion scripts, DuckDB schema, API endpoints, frontend) already accepts a `symbol` parameter. ETHUSDT is already in the `SUPPORTED_SYMBOLS` whitelist.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: DuckDB, FastAPI, Binance API (existing)
**Storage**: DuckDB (`data/processed/liquidations.duckdb` - 235GB)
**Testing**: pytest (existing test suite, add multi-symbol tests)
**Target Platform**: Linux server (existing deployment)
**Project Type**: Single project (existing structure)
**Performance Goals**: API <2s uncached, <500ms cached (same as BTC)
**Constraints**: 4-5h ingestion time, 500MB-1GB DB growth
**Scale/Scope**: 30 days ETH data, ~2M trades, ~87K OI snapshots

## Constitution Check

*GATE: All checks PASS. No violations.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **Mathematical Correctness** | ✅ PASS | Same formulas as BTC, no changes |
| **Test-Driven Development** | ✅ PASS | Existing tests parameterized for multi-symbol |
| **Exchange Compatibility** | ✅ PASS | Binance ETH/USDT uses identical liquidation rules |
| **Performance Efficiency** | ✅ PASS | Same queries, just `WHERE symbol = 'ETHUSDT'` |
| **Data Integrity** | ✅ PASS | Symbol column isolation, no BTC regression |
| **Graceful Degradation** | ✅ PASS | Whitelist disable = instant rollback |
| **Progressive Enhancement** | ✅ PASS | BTC → ETH → BNB → etc progression |
| **Documentation Completeness** | ✅ PASS | quickstart.md and tasks.md already complete |

**Gate Decision**: PROCEED - No constitution violations.

## Project Structure

### Documentation (this feature)

```
specs/009-eth-symbol/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 output - MINIMAL (no unknowns)
├── data-model.md        # Phase 1 output - N/A (no schema changes)
├── quickstart.md        # ALREADY EXISTS - comprehensive guide
├── contracts/           # N/A - no API contract changes
└── tasks.md             # ALREADY EXISTS - 12 detailed tasks
```

### Source Code (repository root)

**No source changes required** - 100% code reuse.

```
# Existing structure (unchanged)
src/liquidationheatmap/
├── api/main.py          # ETHUSDT already in SUPPORTED_SYMBOLS
├── models/              # Symbol-agnostic
└── db/                  # Symbol column in all tables

scripts/
├── ingest_aggtrades.py  # Accepts --symbol ETHUSDT
├── ingest_oi.py         # Accepts --symbol ETHUSDT
├── ingest_klines_15m.py # Accepts --symbol ETHUSDT
└── validate_vs_coinglass.py # Accepts --symbol ETHUSDT

frontend/
└── coinglass_heatmap.html # Symbol selector already exists

tests/
├── integration/test_multi_symbol.py # Add ETH test cases
└── contract/test_heatmap_timeseries.py # Parameterize for ETH
```

**Structure Decision**: Use existing structure. This is a **data operations** feature, not a code feature.

## Complexity Tracking

*No violations - table left empty.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| - | - | - |

---

## Phase 0: Research (MINIMAL)

**Status**: TRIVIAL - No unknowns to resolve.

All technical questions are already answered by the existing BTC implementation:
- Ingestion scripts: Verified symbol-agnostic via `--symbol` param
- DuckDB schema: Verified `symbol` column in all tables
- API endpoints: Verified `symbol` query param support
- Whitelist: ETHUSDT already present (line 230 in main.py)

**Research Output**: See `research.md` (minimal, confirms code reuse approach).

---

## Phase 1: Design (N/A - No New Design)

**Status**: NOT APPLICABLE - Zero new code required.

This feature requires:
1. **Data Ingestion** (T001-T004): Run existing scripts with `--symbol ETHUSDT`
2. **API Validation** (T005-T007): Test existing endpoints with `symbol=ETHUSDT`
3. **Frontend Testing** (T008): Select ETHUSDT in existing dropdown
4. **Coinglass Validation** (T009-T010): Run existing validation script
5. **Documentation** (T011-T012): Update README with ETH results

**Design Output**: No new artifacts needed. `data-model.md` and `contracts/` not applicable.

---

## Implementation Summary

### Critical Path

```
T001 (Data Discovery) → T002 (aggTrades) → T003 (OI) → T004 (Klines)
                                    ↓
                              T005-T007 (API Tests)
                                    ↓
                              T008 (Frontend)
                                    ↓
                              T009-T010 (Validation)
                                    ↓
                              T011-T012 (Docs)
```

### Effort Breakdown

| Phase | Tasks | Effort | Notes |
|-------|-------|--------|-------|
| **Data Ingestion** | T001-T004 | 4-6 hours | Mostly wait time |
| **API Validation** | T005-T007 | 2 hours | Read-only testing |
| **Frontend** | T008 | 1 hour | Already parameterized |
| **Validation** | T009-T010 | 3-4 hours | Requires N8N screenshots |
| **Documentation** | T011-T012 | 1 hour | Update README |
| **TOTAL** | - | **11-14 hours** | ~2 days |

### Success Criteria

- [ ] ETH data ingested (trades, OI, klines)
- [ ] API endpoints return valid ETH data
- [ ] Frontend shows ETH heatmap
- [ ] Coinglass validation hit_rate > 0.60
- [ ] All tests pass
- [ ] Documentation updated

---

## References

- **Feature Spec**: [spec.md](./spec.md) - Full requirements
- **Quickstart Guide**: [quickstart.md](./quickstart.md) - Step-by-step execution
- **Task Breakdown**: [tasks.md](./tasks.md) - Detailed task definitions
- **Data Path**: `/media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/`
- **Database**: `data/processed/liquidations.duckdb`
