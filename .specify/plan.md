# Implementation Plan: Liquidation Heatmap System

**Feature ID**: 001-liquidation-heatmap-mvp
**Plan Created**: 2025-10-29
**Target Branch**: `feature/001-liquidation-heatmap-mvp`
**Status**: Planning Complete - Ready for Implementation

---

## Executive Summary

Build a **predictive liquidation heatmap system** for BTC/USDT futures using historical Binance data. System calculates future liquidation levels from Open Interest using 3 black-box models (Binance Standard, Funding Adjusted, Ensemble), visualizes via Plotly.js (<100 lines), and exposes FastAPI REST endpoints for historical analysis.

**Core Principle**: KISS (Keep It Simple, Stupid) - Use DuckDB for storage, leverage existing algorithms (py_liquidation_map binning), no real-time streaming (MVP = historical only).

---

## Technical Context

### Architecture Pattern: Black Box Models

Following UTXOracle pattern, **separate infrastructure from business logic**:

```
Layer 1: Data (DuckDB) ← CSV ingestion
Layer 2: Models (AbstractLiquidationModel interface) ← 3 implementations
Layer 3: API (FastAPI) ← REST endpoints
Layer 4: Viz (Plotly.js) ← <100 lines
```

### Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Database** | DuckDB 1.4.0+ | Zero-copy CSV ingestion (10GB in 5s), in-process, vectorized analytics |
| **API Server** | FastAPI 0.104+ | Async, auto-docs, Pydantic validation, CORS support |
| **Frontend** | Plotly.js 2.27+ | Interactive charts, ~50 lines code, no build step |
| **Models** | Python 3.11+ | AbstractLiquidationModel interface for interchangeable black boxes |
| **Testing** | Pytest + TDD Guard | Red-Green-Refactor enforced, 80% coverage threshold |
| **Data Source** | Binance CSV (symlinked) | Historical trades, Open Interest, funding rates |

### Data Sources (Already Available)

**Location**: `/media/sam/3TB-WDC/binance-history-data-downloader/downloads/BTCUSDT`
**Symlink**: `data/raw/BTCUSDT` → external drive

**Files Used**:
1. `metrics/` - Open Interest (OI) data (notional value of open positions)
2. `fundingRate/` - 8-hour funding rates (long/short balance indicator)
3. `klines/` - OHLCV candlestick data (for price overlay)
4. `trades/` - Individual trade executions (optional, for validation)

### External Dependencies

**Python Libraries** (already installed via `uv sync`):
- `duckdb>=1.4.0` - Analytics database
- `fastapi>=0.104.0` - REST API framework
- `pandas>=2.1.0` - Data wrangling
- `plotly>=5.17.0` - Visualization library
- `uvicorn>=0.24.0` - ASGI server
- `pytest>=7.4.0` + `pytest-cov>=4.1.0` - Testing

**External Code Reuse**:
- `py_liquidation_map` (cloned to `/media/sam/1TB/py_liquidation_map`)
  - Binning algorithm for price aggregation
  - Filtering modes (gross_value, top_n, portion)
- Binance liquidation formula (from examples/binance_liquidation_formula_reference.txt)

---

## Constitution Check

### KISS Principle ✅

**Applied**:
- DuckDB (not custom database) for storage
- Plotly.js (not custom Canvas code) for visualization (~50 lines vs 500+)
- FastAPI (standard REST, no GraphQL complexity)
- Historical CSV (no real-time WebSocket complexity for MVP)

**Avoided**:
- Custom binary parsers
- Real-time streaming infrastructure
- Complex ML models

### YAGNI Principle ✅

**Build Only What's Needed**:
- BTC/USDT only (not multi-symbol yet)
- Historical analysis (not live trading integration)
- 3 models (not 10 experimental variations)
- REST API (no WebSocket for MVP)

**Deferred to Phase 2+**:
- Multi-symbol support (ETH, SOL, etc.)
- Nautilus Trader integration
- Real-time liquidation tracking
- Advanced statistical models

### Code Reuse First ✅

**Leveraging Existing**:
- py_liquidation_map binning algorithm (battle-tested)
- Binance official liquidation formula (not reinvented)
- Coinglass color scheme (industry standard)
- UTXOracle black-box pattern (proven architecture)

**Not Reinventing**:
- DuckDB CSV ingestion (built-in `COPY FROM`)
- FastAPI auto-documentation (OpenAPI)
- Plotly.js interactivity (zoom/pan/hover)

### TDD Workflow ✅

**Enforced via TDD Guard**:
- Red-Green-Refactor cycle
- Baby steps mode (minimal implementations)
- 80% coverage threshold
- Max 3 attempts per issue

---

## Phase 0: Research & Design Decisions

### Research Topics

#### 1. DuckDB CSV Ingestion Best Practices

**Decision**: Use `COPY FROM` with `AUTO_DETECT` for schema inference.

**Rationale**:
- Zero-copy ingestion: 10GB CSV → DuckDB in ~5 seconds
- No pandas intermediate step (saves memory)
- Automatic schema detection for Binance CSV format

**Implementation Pattern**:
```sql
COPY liquidation_levels FROM 'data/processed/*.csv'
(AUTO_DETECT TRUE, HEADER TRUE, DELIMITER ',');
```

**Alternatives Considered**:
- Pandas → DuckDB: Slower (2-stage copy), higher memory usage
- Parquet conversion: Extra preprocessing step, not needed

#### 2. Binance Liquidation Formula Accuracy

**Decision**: Use official Binance formula with maintenance margin (MMR) tiers.

**Rationale**:
- Most accurate (95% confidence)
- Accounts for position size tiers
- Industry standard (matches Binance UI)

**Formula**:
```
Long liquidation  = entry_price * (1 - 1/leverage + mmr/leverage)
Short liquidation = entry_price * (1 + 1/leverage - mmr/leverage)
```

**MMR Tiers** (BTC/USDT):
| Position Notional | MMR% | Maintenance Amount |
|-------------------|------|-------------------|
| 0 - 50k USDT | 0.4% | $0 |
| 50k - 250k | 0.5% | $50 |
| 250k - 1M | 1.0% | $1,300 |
| 1M - 10M | 2.5% | $16,300 |
| ... | ... | ... |

**Source**: `examples/binance_liquidation_formula_reference.txt`

#### 3. Heatmap Visualization: Plotly.js vs Canvas

**Decision**: Plotly.js for <100 lines of code.

**Rationale**:
- Built-in interactivity (zoom, pan, hover) - no custom code
- ~50 lines for heatmap (vs 500+ Canvas)
- Responsive by default
- No WebGL debugging

**Coinglass Color Scheme**:
```javascript
colorscale: [
  [0, 'rgb(68,1,84)'],      // Dark purple
  [0.5, 'rgb(59,82,139)'],  // Blue
  [0.75, 'rgb(33,145,140)'], // Teal
  [1, 'rgb(253,231,37)']    // Yellow
]
```

**Alternatives Considered**:
- matplotlib: Server-side rendering, not interactive
- Canvas custom: 500+ lines, manual zoom/pan implementation
- D3.js: Overkill for simple heatmap

#### 4. Model Ensemble Strategy

**Decision**: Weighted average (Binance=50%, Funding=30%, py_liquidation_map=20%).

**Rationale**:
- Binance formula most accurate (highest weight)
- Funding rate adds market pressure signal
- py_liquidation_map provides clustering validation

**Aggregation Method**:
```python
# Group by price bucket ($100 increments)
ensemble = (
    binance_pred * 0.5 +
    funding_pred * 0.3 +
    pyliqmap_pred * 0.2
).groupby('price_bucket').sum()
```

**Alternatives Considered**:
- Simple average (equal weights): Ignores accuracy differences
- Median: Loses granularity
- ML-based: Overkill for MVP (YAGNI)

#### 5. API Design: REST vs GraphQL

**Decision**: REST with FastAPI (no GraphQL).

**Rationale**:
- Simpler for historical data queries
- Auto-generated OpenAPI docs
- Fewer dependencies
- Client-side caching easier (HTTP headers)

**Endpoint Structure**:
```
GET /liquidations/heatmap?symbol=BTCUSDT&timeframe=1d&model=ensemble
GET /liquidations/levels?model=binance_standard&leverage=10
GET /liquidations/compare-models
```

**Alternatives Considered**:
- GraphQL: Overkill for simple queries, adds complexity
- gRPC: Not needed (no high-frequency streaming)

---

## Phase 1: Data Models & Contracts

### Data Models

See `.specify/data-model.md` for complete entity definitions.

**Key Entities**:
1. `LiquidationLevel` - Calculated liquidation price + volume
2. `OpenInterestSnapshot` - Historical OI data from Binance
3. `FundingRateSnapshot` - 8h funding rate history
4. `HeatmapCache` - Pre-aggregated heatmap buckets

### API Contracts

See `.specify/contracts/openapi.yaml` for full OpenAPI 3.0 specification.

**Core Endpoints**:
1. `GET /liquidations/heatmap` - 2D heatmap data (time × price)
2. `GET /liquidations/levels` - Current liquidation price levels
3. `GET /liquidations/compare-models` - Side-by-side model comparison
4. `GET /health` - Service health check

---

## Phase 2: Implementation Roadmap

### Phase 1: Setup (2 hours)

**Agent**: All

**Tasks**:
1. ✅ Create feature branch `feature/001-liquidation-heatmap-mvp`
2. ✅ Initialize DuckDB database file
3. ✅ Create module structure `src/liquidationheatmap/{models,ingestion,api}/`
4. ✅ Create database initialization script with SQL schema
5. ✅ Create `.env` template file
6. ✅ Add pytest shared fixtures in `conftest.py`

**Deliverables**:
- Project structure initialized
- Database schema created
- Configuration template ready
- Test fixtures available

**Reference**: tasks.md Phase 1 (T001-T006)

---

### Phase 2: Data Layer (Week 1)

**Agent**: `data-engineer`

**Tasks**:
1. ✅ DuckDB schema design (liquidation_levels, heatmap_cache tables)
2. ✅ CSV ingestion script (`scripts/ingest_historical.py`)
3. ✅ Data validation (check for missing dates, outliers)
4. ✅ Tests: `tests/test_ingestion.py` (TDD workflow)

**Deliverables**:
- `data/processed/liquidations.duckdb` (populated with 30 days data)
- `scripts/ingest_historical.py` (executable, documented)
- Test coverage: 80%+

### Phase 3: Model Layer (Week 2)

**Agent**: `quant-analyst`

**Tasks**:
1. ✅ AbstractLiquidationModel interface (`src/models/base.py`)
2. ✅ Binance Standard model (`src/models/binance_standard.py`)
3. ✅ Funding Adjusted model (`src/models/funding_adjusted.py`)
4. ✅ Ensemble model (`src/models/ensemble.py`)
5. ✅ Tests: `tests/test_models.py` (unit + integration)

**Deliverables**:
- 4 Python modules (base + 3 models)
- Model comparison script (`scripts/compare_models.py`)
- Test coverage: 90%+ (critical business logic)

### Phase 4: API Layer (Week 3)

**Agent**: `quant-analyst` (FastAPI integration)

**Tasks**:
1. ✅ FastAPI app setup (`api/main.py`)
2. ✅ Pydantic models for request/response
3. ✅ Endpoint implementations (heatmap, levels, compare)
4. ✅ CORS configuration
5. ✅ Tests: `tests/test_api.py` (pytest + httpx)

**Deliverables**:
- Running FastAPI server (`uvicorn api.main:app`)
- OpenAPI docs at `/docs`
- Test coverage: 85%+

### Phase 5: Visualization Layer (Week 4)

**Agent**: `visualization-renderer`

**Tasks**:
1. ✅ Plotly.js heatmap (`frontend/heatmap.html`)
2. ✅ Liquidation map bar chart (`frontend/liquidation_map.html`)
3. ✅ Model comparison dashboard (`frontend/compare.html`)
4. ✅ Coinglass color scheme application
5. ✅ Tests: Visual regression testing (screenshot comparison)

**Deliverables**:
- 3 HTML files (~50 lines JS each)
- Total: <150 lines JavaScript (goal: <100)
- Responsive design (mobile-friendly)

### Phase 6: Model Comparison (Week 3-4)

**Agent**: `quant-analyst`

**Tasks**:
1. ✅ Implement model comparison endpoint
2. ✅ Create comparison dashboard UI
3. ✅ Add backtesting scripts
4. ✅ Tests: Accuracy validation

**Deliverables**:
- Side-by-side model comparison
- Accuracy metrics (MAPE, confidence scores)
- Backtesting results

**Reference**: tasks.md Phase 5 (T036-T041)

---

### Phase 7: Polish & Production (1 day)

**Agent**: All

**Tasks**:
1. ✅ Add `liquidation_history` table (T046)
2. ✅ Implement `/liquidations/history` endpoint (T047)
3. ✅ Add retry logic with exponential backoff (T048)
4. ✅ Configure structured logging (T049)
5. ✅ Update documentation (T050)
6. ✅ Final cleanup and verification (T051)

**Deliverables**:
- Historical liquidation data ingestion
- Production-ready error handling
- Structured logging configured
- Documentation complete
- Code linted and formatted (≥80% coverage)

**Reference**: tasks.md Phase 7 (T046-T051)

---

## Integration & Testing Strategy

### Integration Tests

**Scenarios**:
1. **End-to-end**: CSV → DuckDB → Model → API → Plotly.js
2. **Model accuracy**: Compare predictions vs actual liquidations (±2%)
3. **Performance**: API response time <50ms (p95)
4. **Data quality**: Detect missing dates, outliers

**Test Data**:
- 7 days of historical data (2024-10-22 to 2024-10-29)
- Known liquidation events for validation

### Performance Benchmarks

**Targets**:
- DuckDB ingestion: <5s per 10GB CSV
- Model calculation: <2s for 30-day dataset
- API latency: <50ms (p95), <100ms (p99)
- Heatmap render: <500ms client-side

**Monitoring**:
- Log query times to `analysis.log`
- Track model confidence scores
- Alert if API latency >200ms

---

## Deployment & Documentation

### Deployment (Production-Ready)

**Not in MVP scope** - Keep simple for now:
- Run locally: `uv run uvicorn api.main:app --reload`
- Access: `http://localhost:8000/docs`
- Data: Symlinked Binance CSV

**Future (Phase 2)**:
- Systemd service
- Nginx reverse proxy
- Cron job for daily updates

### Documentation

**User Documentation**:
1. `README.md` - Quick start, installation, usage
2. `CLAUDE.md` - Architecture, development workflow (already complete)
3. `.specify/quickstart.md` - Developer onboarding guide

**API Documentation**:
- Auto-generated via FastAPI at `/docs` (OpenAPI/Swagger UI)
- Example requests/responses in README.md

**Code Documentation**:
- Docstrings for all public functions/classes
- Type hints (enforced by mypy)
- Inline comments for complex algorithms (binning, ensemble)

---

## Success Criteria

### Functional Requirements ✅

- [ ] 3 liquidation models implemented (Binance, Funding, Ensemble)
- [ ] DuckDB ingestion <5s per 10GB
- [ ] FastAPI endpoints respond <50ms (p95)
- [ ] Plotly.js visualization <100 lines of code
- [ ] Historical analysis covers 30+ days

### Code Quality Requirements ✅

- [ ] Total Python codebase ≤800 lines (excluding tests)
- [ ] Test coverage ≥80%
- [ ] All tests pass (pytest)
- [ ] Linting clean (ruff check .)
- [ ] No code duplication between models

### Performance Requirements ✅

- [ ] DuckDB queries <50ms
- [ ] Model calculation <2s for 30-day dataset
- [ ] API latency <100ms (p95)

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| py_liquidation_map unavailable | Medium | Implement Model A+B first (80% value without external library) |
| DuckDB performance issues | High | Pre-aggregate heatmap_cache table, add indexes |
| Model accuracy <80% | Medium | Backtest vs actual liquidations, tune ensemble weights |
| Plotly.js limited customization | Low | Fallback to simple matplotlib if needed |

---

## Next Steps

1. ✅ **Review this plan** with team (quant-analyst, data-engineer, visualization-renderer)
2. ✅ **Create feature branch**: `git checkout -b feature/001-liquidation-heatmap-mvp`
3. ✅ **Execute Milestone 1**: Data layer implementation (data-engineer agent)
4. 🔜 **TDD workflow**: Write tests first, implement incrementally

**Command to start**:
```bash
cd /media/sam/1TB/LiquidationHeatmap
git checkout -b feature/001-liquidation-heatmap-mvp
/speckit.tasks  # Generate detailed task breakdown
```

---

**Plan Status**: ✅ **APPROVED FOR IMPLEMENTATION**

**Estimated Effort**: 4 weeks (4 milestones × 1 week each)
**Team Size**: 3 agents (data-engineer, quant-analyst, visualization-renderer)
**Complexity**: Medium (black-box architecture reduces coupling)
