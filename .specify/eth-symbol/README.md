# ETH/USDT Symbol Support - Specification Package

**Created**: 2024-12-28
**Status**: Ready for Implementation
**Effort**: 11-14 hours (2 days)
**Approach**: 100% Code Reuse via Parameterization

---

## Quick Navigation

📋 **[spec.md](spec.md)** - Complete Technical Specification
- Full problem analysis and architecture review
- 5-phase implementation plan (12 tasks)
- Testing strategy and success criteria
- 544 lines | 16KB

✅ **[tasks.md](tasks.md)** - Actionable Task Breakdown
- Dependency graph and critical path
- T001-T012 with detailed commands and validation
- Rollback procedures and testing checklist
- 771 lines | 21KB

⚡ **[quickstart.md](quickstart.md)** - Developer Quick Reference
- TL;DR 7-step bash sequence
- Step-by-step execution with verification
- Troubleshooting and rollback plan
- 420 lines | 12KB

📊 **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Meta Overview
- Decision rationale and architecture validation
- Success criteria and risk assessment
- Timeline, milestones, and reference architecture
- 396 lines | 13KB

---

## Start Here

**First-time reader**: Start with `quickstart.md` for high-level overview, then `tasks.md` for implementation

**Deep dive**: Read `spec.md` for complete technical details and decision rationale

**Quick reference**: Use `quickstart.md` during implementation for copy-paste commands

---

## Implementation Checklist

### Pre-Implementation
- [ ] Read `quickstart.md` (15 min)
- [ ] Verify ETH data exists at `/media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/`
- [ ] Confirm N8N screenshot directory path
- [ ] Approve 2-day timeline

### Phase 1: Data Ingestion (Day 1)
- [ ] **T001**: Verify data availability (30 min)
- [ ] **T002**: Ingest aggTrades (4-5h background)
- [ ] **T003**: Start OI collector (1h setup + 24h monitoring)
- [ ] **T004**: Ingest klines (1-2h)

### Phase 2: API Validation (Day 2 AM)
- [ ] **T005**: Test heatmap endpoint (1h)
- [ ] **T006**: Test klines endpoint (30 min)
- [ ] **T007**: Test date-range endpoint (15 min)

### Phase 3: Frontend (Day 2 AM)
- [ ] **T008**: Symbol selector integration (1h)

### Phase 4: Validation (Day 2 PM)
- [ ] **T009**: Coinglass validation (2h)
- [ ] **T010**: BTC vs ETH comparison (1h)

### Phase 5: Documentation (Day 2 EOD)
- [ ] **T011**: Update API docs (30 min)
- [ ] **T012**: Update README (30 min)

### Definition of Done
- [ ] All P0 tasks completed
- [ ] Hit rate > 0.60 (Coinglass validation)
- [ ] All tests pass (`uv run pytest -v`)
- [ ] Documentation updated
- [ ] PR merged

---

## Key Insights

### Why 100% Code Reuse Works

**Evidence from Architecture Audit**:
```bash
# All scripts parameterized
grep "argparse.*symbol" scripts/*.py
# → ingest_aggtrades.py, ingest_oi.py, ingest_klines_15m.py

# All database tables have symbol column
grep "WHERE symbol =" src/liquidationheatmap/
# → db_service.py, api/main.py (all queries)

# Whitelist already includes ETH
grep "SUPPORTED_SYMBOLS" src/liquidationheatmap/api/main.py
# → Line 229-241: {"BTCUSDT", "ETHUSDT", ...}
```

**Conclusion**: Architecture is truly symbol-agnostic. No code changes needed.

### Critical Path Dependencies

```
T001 (Data Discovery) → REQUIRED for all other tasks
  ↓
T002 (aggTrades) ─┬─→ T005 (API Test) → T009 (Validation) → MERGE
T003 (OI) ────────┤
T004 (Klines) ────┘
```

**Bottleneck**: T002 (aggTrades ingestion) = 4-5h streaming I/O

**Parallel Execution**: T002, T003, T004 can run simultaneously in separate tmux sessions

---

## Success Criteria

### P0 - Must Have (Blocking)
✅ **Data Integrity**: 1M+ ETH trades ingested  
✅ **API Functional**: Endpoints return valid ETH data  
✅ **Validation**: Coinglass hit_rate > 0.60  
✅ **Tests Pass**: No regressions in existing BTC pipeline  

### P1 - Should Have (Post-Merge)
- BTC vs ETH performance delta < 10%
- Frontend symbol selector functional
- Documentation updated

### P2 - Nice to Have (Future)
- Real-time OI collector 24/7 uptime
- Automated daily validation
- Public metrics dashboard

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Data quality issues | Low | Medium | Dry-run validation before ingestion |
| Performance degradation | Very Low | Low | Performance tests + caching |
| Validation failure | Low | Medium | Compare with BTC baseline |

**Overall Risk**: LOW (parameterization, not new features)

---

## Rollback Plan

**1-Line Disable** (instant):
```python
# src/liquidationheatmap/api/main.py:232
SUPPORTED_SYMBOLS = {"BTCUSDT"}  # Remove "ETHUSDT"
```

**Impact**: BTC unaffected (symbol-isolated data)

---

## Next Steps After ETH

**Remaining 8 Whitelisted Symbols**:
- BNB/USDT, ADA/USDT, DOGE/USDT, XRP/USDT
- SOL/USDT, DOT/USDT, MATIC/USDT, LINK/USDT

**Process** (same for each):
1. Ingest data (scripts already parameterized)
2. Validate against Coinglass
3. Approve if hit_rate > 0.60

**Roadmap**: 10 symbols validated by Q1 2025

---

## Contact & Approval

**Ready for Implementation**: YES

**Blockers**: None (data paths to be confirmed in T001)

**Implementation Start**: User discretion

**Expected Completion**: 2 days from start

---

## Files in This Package

```
.specify/eth-symbol/
├── README.md                    # This file (navigation guide)
├── spec.md                      # Complete technical specification
├── tasks.md                     # Actionable task breakdown
├── quickstart.md                # Developer quick reference
└── IMPLEMENTATION_SUMMARY.md    # Meta overview & decisions
```

**Total Documentation**: 2,131 lines | 62KB

**Quality**: Production-ready, copy-paste commands, full validation

---

## Feedback & Iteration

**Questions**:
- Data path confirmation needed in T001
- N8N screenshot directory path (T009)
- Any deviations from estimated timeline

**Updates**: This spec will be updated after T001 completion with actual date ranges

**Contact**: Created by Claude Code (2024-12-28)
