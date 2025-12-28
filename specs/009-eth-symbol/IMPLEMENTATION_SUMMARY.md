# ETH/USDT Support - Implementation Summary

**Created**: 2024-12-28
**Status**: Ready for Implementation
**Estimated Effort**: 11-14 hours (2 days)
**Code Changes Required**: ZERO (100% parameterization)

---

## Executive Summary

This specification defines how to add ETH/USDT support to LiquidationHeatmap through **pure parameterization** - no new code, no new algorithms, just data ingestion and configuration.

**Key Insight**: The entire codebase was designed symbol-agnostic from day one. ETHUSDT is already whitelisted in `SUPPORTED_SYMBOLS`, all scripts accept `--symbol` parameter, all database tables have `symbol` column, and all API queries filter by `WHERE symbol = ?`.

**What This Proves**: If we need to write new code for ETH, the architecture is broken. This is a litmus test for the "KISS & Code Reuse First" principles.

---

## Files Created

### 1. `spec.md` (Complete Technical Specification)
**Location**: `/media/sam/1TB/LiquidationHeatmap/.specify/eth-symbol/spec.md`

**Contents**:
- **Section 1-2**: Problem statement and motivation
- **Section 3**: Existing BTC architecture (proves symbol-agnostic design)
- **Section 4**: Implementation plan in 5 phases
  - Phase 1: Data ingestion (T001-T004)
  - Phase 2: API validation (T005-T007)
  - Phase 3: Frontend integration (T008)
  - Phase 4: Coinglass validation (T009-T010)
  - Phase 5: Documentation (T011-T012)
- **Section 5-10**: Testing, success criteria, risks, timeline, references

**Key Sections**:
- **3.1 Data Flow**: Visual diagram showing symbol parameterization at every layer
- **3.2 Whitelist Validation**: Proof that ETHUSDT is already approved (line 232 in main.py)
- **4.0 Implementation Plan**: 12 tasks with detailed commands
- **6.0 Success Criteria**: P0 (must have), P1 (should have), P2 (nice to have)
- **8.0 Risk Assessment**: Overall risk = LOW (parameterization, not new features)

---

### 2. `tasks.md` (Actionable Task Breakdown)
**Location**: `/media/sam/1TB/LiquidationHeatmap/.specify/eth-symbol/tasks.md`

**Contents**:
- **Dependency Graph**: Visual task dependencies
- **12 Tasks** (T001-T012) with:
  - Priority (P0/P1)
  - Estimated time
  - Dependencies
  - Detailed implementation steps
  - Success criteria
  - Validation queries

**Critical Path** (blocking tasks):
```
T001 → T002 → T005 → T009 → MERGE
     → T003 ↗
     → T004 ↗
```

**Task Breakdown by Phase**:
- **Phase 1** (Data): T001-T004 (6-8 hours)
- **Phase 2** (API): T005-T007 (2 hours)
- **Phase 3** (Frontend): T008 (1 hour)
- **Phase 4** (Validation): T009-T010 (3 hours)
- **Phase 5** (Docs): T011-T012 (1 hour)

---

### 3. `quickstart.md` (Developer Quick Reference)
**Location**: `/media/sam/1TB/LiquidationHeatmap/.specify/eth-symbol/quickstart.md`

**Contents**:
- **TL;DR**: 7-step bash command sequence
- **Why This Works**: Explanation of symbol-agnostic design
- **Step-by-Step Execution**: Detailed walkthrough with verification at each step
- **Troubleshooting**: Common issues and solutions
- **Rollback Plan**: How to disable ETH if needed

**Use Case**: Quick copy-paste guide for implementation without reading full spec.

---

### 4. `IMPLEMENTATION_SUMMARY.md` (This File)
**Purpose**: Meta-document explaining the specification structure and decision rationale.

---

## Key Decisions & Rationale

### Decision 1: 100% Code Reuse Target
**Rationale**:
- BTC pipeline already handles symbol as parameter
- Adding ETH should prove symbol-agnostic design works
- If we need new code, architecture needs refactoring (not just adding ETH)

**Validation**:
- Grep audit shows all scripts accept `--symbol`
- Database schema has `symbol` column in all tables
- API whitelist already includes ETHUSDT

### Decision 2: Validation Before Expansion
**Rationale**:
- Can't expand to 10+ symbols without validating model accuracy
- Coinglass comparison requires 2+ symbols for confidence
- ETH is second largest market (40% of BTC volume) = good validation data

**Success Criteria**:
- ETH hit_rate > 0.60 (same threshold as BTC)
- BTC vs ETH performance delta < 10% (proves parameterization works)

### Decision 3: Phased Rollout
**Rationale**:
- Phase 1 (ingestion) can run in background
- Phase 2 (API) validates data without frontend changes
- Phase 3 (frontend) is optional (API works without UI)
- Phase 4 (validation) proves correctness before expansion

**Benefit**: Can stop at any phase if issues found, without affecting BTC.

### Decision 4: N8N Screenshot Integration
**Rationale**:
- N8N already captures Coinglass ETH screenshots
- Reuse existing validation pipeline (scripts/validate_vs_coinglass.py)
- No new tooling needed

**Requirement**: Confirm N8N screenshot directory path with user before T009.

---

## Data Requirements

### Historical Data Sources
- **aggTrades**: `/media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/*.csv`
- **Open Interest**: Binance API (real-time, no historical)
- **Klines**: Binance API (can backfill via scripts)
- **Funding Rate**: Not required for v1 (optional enhancement)

### Data Volume Estimates (30-day ingestion)
- **aggTrades**: ~2-3M rows (~500MB-1GB)
- **Open Interest**: ~86,400 rows (~10MB)
- **Klines (15m)**: ~2,880 rows (~500KB)
- **Klines (5m)**: ~8,640 rows (~1.5MB)
- **Total DB Growth**: +500MB-1GB (negligible vs 235GB current size)

### Ingestion Time Estimates
- **aggTrades**: 4-5 hours (streaming, I/O bound)
- **Open Interest**: Background task (30s snapshots)
- **Klines**: 1-2 hours (API rate limited)
- **Total**: 6-8 hours (can run in parallel with tmux/screen)

---

## Success Criteria (Definition of Done)

### P0 - Must Have (Blocking PR Merge)
- [ ] **T001-T004**: All ETH data ingested successfully
  - Validation: `SELECT COUNT(*) FROM aggtrades_history WHERE symbol = 'ETHUSDT'` > 1M
- [ ] **T005-T007**: All API endpoints return valid ETH data
  - Validation: `curl /liquidations/heatmap-timeseries?symbol=ETHUSDT` returns 200
- [ ] **T009**: Coinglass validation hit_rate > 0.60
  - Validation: `cat data/validation/price_level_comparison.jsonl | grep ETHUSDT | jq '.hit_rate'`
- [ ] **All tests pass**: `uv run pytest -v` (no regressions)

### P1 - Should Have (Post-Merge)
- [ ] **T010**: BTC vs ETH performance delta < 10%
- [ ] **T011-T012**: Documentation updated
- [ ] **T008**: Frontend symbol selector functional

### P2 - Nice to Have (Future Work)
- [ ] Real-time ETH OI collector running 24/7 in production
- [ ] Automated daily validation runs (cron job)
- [ ] Public dashboard showing ETH validation metrics

---

## Risk Mitigation

### Risk 1: ETH Data Quality Issues
**Likelihood**: Low
**Impact**: Medium (delays implementation, not blocks)
**Mitigation**:
- Run dry-run validation before production ingestion (T002 step 1)
- Verify date ranges with `ls` before starting (T001)
- Compare total volume with Binance public metrics

### Risk 2: Performance Degradation
**Likelihood**: Very Low (same queries, just different WHERE clause)
**Impact**: Low
**Mitigation**:
- Performance tests (T006) verify response time
- Cache hit rate monitored (existing /cache/stats endpoint)
- Symbol-isolated data (BTC unaffected even if ETH slow)

### Risk 3: Coinglass Validation Failure
**Likelihood**: Low (model already validated for BTC)
**Impact**: Medium (blocks expansion, not blocks ETH launch)
**Mitigation**:
- If hit_rate < 0.60, investigate data quality first (not model)
- Compare BTC vs ETH hit_rate (should be similar)
- Adjust date ranges or data sources if needed

**Overall Risk**: LOW (this is parameterization, not new features)

---

## Rollback Strategy

**If ETH needs to be disabled**:

1. **Whitelist Change** (1 line, instant):
   ```python
   # src/liquidationheatmap/api/main.py:232
   SUPPORTED_SYMBOLS = {"BTCUSDT"}  # Remove "ETHUSDT"
   ```

2. **Stop Background Processes**:
   ```bash
   tmux kill-session -t eth-oi  # Stop OI collector
   ```

3. **Optional: Truncate Data** (if permanent):
   ```sql
   DELETE FROM aggtrades_history WHERE symbol = 'ETHUSDT';
   DELETE FROM open_interest_history WHERE symbol = 'ETHUSDT';
   DELETE FROM klines_15m_history WHERE symbol = 'ETHUSDT';
   ```

4. **Restart API**:
   ```bash
   sudo systemctl restart liquidation-heatmap
   ```

**Impact**: BTC pipeline continues unaffected (data isolated by symbol column).

---

## Next Steps After ETH

**Once ETH is validated** (hit_rate > 0.60):

1. **Expand to remaining 8 symbols** (already whitelisted):
   - BNB/USDT, ADA/USDT, DOGE/USDT, XRP/USDT
   - SOL/USDT, DOT/USDT, MATIC/USDT, LINK/USDT

2. **Process per symbol**:
   ```bash
   # Ingest
   uv run python scripts/ingest_aggtrades.py --symbol BNBUSDT ...
   uv run python scripts/ingest_oi.py --symbol BNBUSDT

   # Validate
   uv run python scripts/validate_vs_coinglass.py --symbol BNBUSDT

   # Approve if hit_rate > 0.60
   ```

3. **Roadmap**:
   - Q1 2025: 10 symbols validated
   - Q2 2025: Multi-exchange support (Bybit, OKX)
   - Q3 2025: Real-time WebSocket streaming (all symbols)

---

## Testing Strategy

### Unit Tests (Existing - Should Pass)
- `tests/unit/models/test_time_evolving_heatmap.py`
- `tests/unit/ingestion/test_snapshot_schema.py`

**Command**: `uv run pytest tests/unit/ -v`

### Integration Tests (Add ETH-Specific)
- `tests/integration/test_multi_symbol.py::test_eth_data_completeness`
- `tests/integration/test_multi_symbol.py::test_eth_heatmap_calculation`

**Command**: `uv run pytest tests/integration/ -v -k eth`

### Contract Tests (Parameterize)
- `tests/contract/test_heatmap_timeseries.py::test_eth_endpoint`
  ```python
  @pytest.mark.parametrize("symbol", ["BTCUSDT", "ETHUSDT"])
  def test_heatmap_timeseries(symbol):
      response = client.get(f"/liquidations/heatmap-timeseries?symbol={symbol}")
      assert response.status_code == 200
  ```

**Command**: `uv run pytest tests/contract/ -v`

### Performance Tests (Regression Check)
- `tests/performance/test_api_performance.py::test_eth_response_time`
  - Verify ETH response time within 10% of BTC

**Command**: `uv run pytest tests/performance/ -v`

### Validation Tests (Coinglass)
- `scripts/validate_vs_coinglass.py --symbol ETHUSDT`
- Target: hit_rate > 0.60

**Command**: `uv run python scripts/validate_vs_coinglass.py --symbol ETHUSDT`

---

## Timeline & Milestones

| Day | Milestone | Tasks | Deliverable |
|-----|-----------|-------|-------------|
| **Day 1 AM** | Data Discovery | T001 | Date range identified |
| **Day 1 PM** | Ingestion Start | T002-T004 | Scripts running (background) |
| **Day 2 AM** | API Testing | T005-T007 | Endpoints validated |
| **Day 2 PM** | Validation | T009-T010 | Hit rate > 0.60 confirmed |
| **Day 2 EOD** | Documentation | T011-T012 | README updated, PR ready |

**Total**: 2 days (11-14 hours active work, rest is I/O wait time)

---

## Reference Architecture

### Existing BTC Implementation (100% Reusable)

**Ingestion Layer**:
- `scripts/ingest_aggtrades.py` (symbol parameterized)
- `scripts/ingest_oi.py` (symbol parameterized)
- `scripts/ingest_klines_15m.py` (symbol parameterized)

**Database Layer**:
- `src/liquidationheatmap/ingestion/db_service.py` (symbol-filtered queries)
- Tables: `aggtrades_history`, `open_interest_history`, `klines_15m_history`

**Calculation Layer**:
- `src/liquidationheatmap/models/time_evolving_heatmap.py::calculate_time_evolving_heatmap()`
- Accepts `symbol` parameter, no BTC-specific logic

**API Layer**:
- `src/liquidationheatmap/api/main.py::get_heatmap_timeseries()`
- Whitelist validation: `SUPPORTED_SYMBOLS` (line 229-241)

**Validation Layer**:
- `scripts/validate_vs_coinglass.py` (symbol parameterized)
- N8N screenshots (already captures ETH)

**Frontend Layer**:
- `frontend/coinglass_heatmap.html` (symbol selector already exists)

---

## Contacts & Dependencies

### Data Dependencies
- **ETH Historical Data**: `/media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/`
  - Owner: User (verify path in T001)
- **N8N Screenshots**: `/path/to/n8n/screenshots/ETH/` (TBD)
  - Owner: User (confirm path before T009)

### External APIs
- **Binance Futures API**: `https://fapi.binance.com/`
  - Rate limits: 2400 req/min (weight-based)
  - No API key required for public endpoints (OI, klines)

### Infrastructure
- **DuckDB**: `data/processed/liquidations.duckdb` (235GB)
  - Current symbols: BTCUSDT only
  - Available space: Check with `df -h`
- **API Server**: Assumed running at `http://localhost:8000`
  - Managed via: systemd/docker/manual (TBD)

---

## Approval & Sign-Off

**Ready for Implementation**: YES
- [ ] User confirms ETH data path
- [ ] User confirms N8N screenshot directory
- [ ] User approves 2-day timeline
- [ ] User commits to running validation (T009)

**Implementation Start**: After user confirmation

**Expected Completion**: 2024-12-30 (if started 2024-12-28)

---

## Document Changelog

- **2024-12-28**: Initial specification created
  - `spec.md`: Full technical specification (12 tasks, 5 phases)
  - `tasks.md`: Actionable task breakdown with dependency graph
  - `quickstart.md`: Developer quick reference guide
  - `IMPLEMENTATION_SUMMARY.md`: This meta-document

**Next Update**: After T001 completion (data discovery results)
