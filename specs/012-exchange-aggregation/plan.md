# Implementation Plan: Exchange Aggregation

**Branch**: `012-exchange-aggregation` | **Date**: 2025-12-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-exchange-aggregation/spec.md`

## Summary

Multi-exchange liquidation data aggregation supporting Binance (REST polling), Hyperliquid (WebSocket), and Bybit (stub). Implements adapter pattern with unified `NormalizedLiquidation` schema, graceful degradation when exchanges fail, and aggregated heatmap visualization with per-exchange filtering.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, aiohttp, websockets, DuckDB, Pydantic (dataclasses for validation)
**Storage**: DuckDB (extend existing schema with `exchange` column)
**Testing**: pytest with pytest-asyncio for async tests
**Target Platform**: Linux server (existing infrastructure)
**Project Type**: Single project with web API + frontend
**Performance Goals**: <7s aggregated 24h heatmap query, warm cache, p95 latency (vs <5s single exchange)
**Constraints**: 5s polling interval for Binance REST, graceful degradation
**Scale/Scope**: 2-3 exchanges initially (Binance + Hyperliquid), extensible to 5+

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **Mathematical Correctness** | PASS | Reuses validated liquidation formulas |
| **Test-Driven Development** | PASS | TDD approach defined in tasks.md |
| **Exchange Compatibility** | PASS | Adapter pattern handles exchange quirks |
| **Performance Efficiency** | PASS | <7s target, indexed queries |
| **Data Integrity** | PASS | Atomic schema migration, backfill preserves data |
| **Graceful Degradation** | PASS | System survives exchange failures |
| **Progressive Enhancement** | PASS | Phased rollout: Binance+HL first, others later |
| **Documentation Completeness** | PASS | API docs, integration guide planned |

## Project Structure

### Documentation (this feature)

```
specs/012-exchange-aggregation/
├── plan.md              # This file
├── research.md          # Exchange API research
├── data-model.md        # NormalizedLiquidation, ExchangeHealth schemas
├── quickstart.md        # Integration guide
├── contracts/           # API contracts (OpenAPI)
│   ├── heatmap-api.yaml
│   └── health-api.yaml
└── tasks.md             # Task breakdown (already exists)
```

### Source Code (repository root)

```
src/
├── exchanges/                    # NEW: Exchange adapters module
│   ├── __init__.py
│   ├── base.py                   # Abstract adapter interface
│   ├── binance.py                # Binance REST adapter
│   ├── hyperliquid.py            # Hyperliquid WebSocket adapter
│   ├── bybit.py                  # Bybit stub
│   └── aggregator.py             # Multi-exchange aggregator
├── liquidationheatmap/
│   ├── api/
│   │   └── main.py               # MODIFY: Add exchanges param, health endpoints
│   └── ingestion/
│       └── db_service.py         # MODIFY: Add exchange column support

scripts/
├── migrate_add_exchange_column.py  # NEW: DuckDB migration
└── init_database.py                # MODIFY: Add exchange_health table

frontend/
├── heatmap.html                  # MODIFY: Add exchange selector, badges

tests/
├── test_exchanges/               # NEW: Adapter tests
│   ├── __init__.py
│   ├── test_base.py
│   ├── test_binance.py
│   ├── test_hyperliquid.py
│   └── test_bybit.py
└── integration/
    └── test_aggregator.py        # NEW: Multi-exchange integration tests
```

**Structure Decision**: Extends existing single-project structure. New `src/exchanges/` module isolates exchange-specific code. Minimal changes to existing API and ingestion modules.

## Phase Overview

### Phase 1: Core Infrastructure (Days 1-3)
- Create exchange adapters module structure
- Implement base adapter interface with dataclasses
- Implement Binance adapter (REST polling)
- Implement Hyperliquid adapter (WebSocket)
- Implement Bybit stub
- Write unit tests

### Phase 2: Aggregation Service (Days 3-5)
- Implement ExchangeAggregator with asyncio.Queue multiplexing
- Add health check aggregation
- Add graceful degradation logic
- Write integration tests

### Phase 3: Database Integration (Days 5-6)
- Add exchange column to DuckDB schema
- Create migration script
- Update ingestion pipeline
- Optimize multi-exchange queries

### Phase 4: API Extension (Days 6-7)
- Add exchanges parameter to /liquidations/heatmap
- Add /exchanges/health endpoint
- Add /exchanges list endpoint
- Update API documentation

### Phase 5: Frontend Integration (Days 7-8)
- Add exchange selector dropdown
- Add health indicator badges
- Color-code zones by exchange
- Update tooltips

### Phase 6: Validation & Documentation (Days 8-10)
- Hyperliquid validation (target: 60% hit rate)
- Load testing
- Exchange failover testing
- Documentation

## Key Design Decisions

### 1. REST Polling for Binance (vs WebSocket)
- **Decision**: Use REST `/fapi/v1/forceOrders` with 5s polling
- **Rationale**: WebSocket returns 403 (likely rate limit or auth issue)
- **Trade-off**: Higher latency (5s vs real-time) but reliable

### 2. Adapter Pattern
- **Decision**: Abstract base class with exchange-specific implementations
- **Rationale**: Clean separation, easy to add new exchanges
- **Trade-off**: More boilerplate but better maintainability

### 3. Graceful Degradation
- **Decision**: Continue with available exchanges, log failures
- **Rationale**: Constitution requires system resilience
- **Trade-off**: Potentially incomplete data vs system crash

### 4. Single Queue Multiplexing
- **Decision**: asyncio.Queue to merge all exchange streams
- **Rationale**: Simple, efficient, no external dependencies
- **Trade-off**: Single consumer, but sufficient for current scale

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Binance rate limits | 5s polling interval, exponential backoff |
| Hyperliquid low volume | Accept as secondary source, longer validation window |
| DuckDB migration on 185GB | Test on copy first, have rollback script |
| Exchange API changes | Version endpoints, monitor for schema drift |

## Complexity Tracking

*No Constitution violations - all design choices align with principles.*

## Dependencies

### New Python Packages
```toml
websockets = "^12.0"        # Hyperliquid WebSocket
aiohttp = "^3.9.0"          # Binance REST (may already exist)
```

### External APIs
- Binance Futures REST: `https://fapi.binance.com/fapi/v1/forceOrders`
- Hyperliquid WebSocket: `wss://api.hyperliquid.xyz/ws`

## Success Criteria

- [ ] Binance + Hyperliquid adapters functional
- [ ] 100% liquidations pass normalization schema
- [ ] Aggregator uptime >= 99% over 7 days
- [ ] Aggregated heatmap loads in <7s
- [ ] Hyperliquid validation >= 60% hit rate
- [ ] System survives single exchange failure

---

**Status**: Ready for implementation
**Last Updated**: 2025-12-29
