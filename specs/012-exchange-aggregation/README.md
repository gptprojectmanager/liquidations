# Exchange Aggregation Feature

**Status**: Draft Specification
**Created**: 2025-12-28
**Priority**: P3 (Post-Validation Expansion)
**Estimated Effort**: 7-10 days

---

## Quick Links

- **Specification**: [`spec.md`](spec.md) - Complete technical design
- **Tasks**: [`tasks.md`](tasks.md) - Implementation breakdown (33 tasks, 68 hours)
- **Parent Roadmap**: [`../.specify/roadmap-expansion/spec.md`](../roadmap-expansion/spec.md)

---

## Overview

Aggregate liquidation data from multiple cryptocurrency exchanges (Binance, Bybit, Hyperliquid, OKX) into a unified heatmap view.

**Problem**: Current implementation is Binance-only (45% market coverage).
**Solution**: Adapter pattern to normalize data from multiple exchanges.
**Goal**: 70%+ market coverage with graceful degradation.

---

## Exchange Status

| Exchange | REST API | WebSocket | Historical Data | Status |
|----------|----------|-----------|----------------|--------|
| **Binance** | ✅ Working | ❌ 403 blocked | ✅ 4 years | **Phase 1** |
| **Hyperliquid** | ❌ N/A | ✅ Working | ❌ Real-time only | **Phase 1** |
| **Bybit** | ⚠️ Untested | ❌ Topic removed | ⚠️ Untested | **Stub** |
| **OKX** | ❓ Unknown | ❓ Unknown | ❓ Unknown | **Phase 2+** |

---

## Key Design Decisions

### 1. Adapter Pattern
Each exchange has a dedicated adapter implementing `ExchangeAdapter` interface:
- `BinanceAdapter` - REST polling (WebSocket workaround)
- `HyperliquidAdapter` - WebSocket streaming
- `BybitAdapter` - Stub with NotImplementedError
- `OKXAdapter` - Future implementation

### 2. Data Normalization
All exchanges map to common schema:
```python
@dataclass
class NormalizedLiquidation:
    exchange: str           # "binance" | "hyperliquid" | ...
    symbol: str             # "BTCUSDT" (standardized)
    price: float
    quantity: float
    value_usd: float
    side: str               # "long" | "short"
    timestamp: datetime
    confidence: float       # 0.0-1.0
```

### 3. Graceful Degradation
System continues functioning when exchanges fail:
- **All exchanges working**: Full aggregated view
- **Binance only**: 45% market coverage (acceptable)
- **Hyperliquid only**: 5% coverage (degraded)
- **All failed**: Cached data + error banner

### 4. Database Schema Extension
```sql
ALTER TABLE liquidations ADD COLUMN exchange VARCHAR DEFAULT 'binance';
CREATE INDEX idx_liquidations_exchange ON liquidations(exchange);
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (Days 1-3)
- **EA-001 to EA-006**: Adapter implementations + tests
- **Deliverables**: `src/exchanges/binance.py`, `hyperliquid.py`, `base.py`
- **Milestone**: Multi-exchange streaming functional

### Phase 2: Aggregation Service (Days 3-5)
- **EA-007 to EA-010**: Aggregator + health checks
- **Deliverables**: `src/exchanges/aggregator.py`
- **Milestone**: Streams merged, graceful degradation working

### Phase 3: Database Integration (Days 5-6)
- **EA-011 to EA-014**: Schema migration + query optimization
- **Deliverables**: Migration scripts, updated ingestion
- **Milestone**: Exchange filtering performant (<7s)

### Phase 4: API Extension (Days 6-7)
- **EA-015 to EA-019**: REST endpoints + documentation
- **Deliverables**: `/liquidations/heatmap?exchanges=...`, `/exchanges/health`
- **Milestone**: API supports multi-exchange queries

### Phase 5: Frontend Integration (Days 7-8)
- **EA-020 to EA-024**: UI controls + visualization
- **Deliverables**: Exchange selector, health badges, color-coded charts
- **Milestone**: Users can filter by exchange

### Phase 6: Validation & Documentation (Days 8-10)
- **EA-025 to EA-030**: Validation, load testing, docs
- **Deliverables**: Validation reports, integration guide
- **Milestone**: Production-ready

---

## Success Criteria

### P0 - Must Have
- ✅ Binance + Hyperliquid adapters functional
- ✅ Data normalization 100% accurate
- ✅ System survives single exchange failure
- ✅ Aggregated heatmap loads in <7s

### P1 - Should Have
- ✅ Hyperliquid hit rate ≥60%
- ✅ Per-exchange toggle in UI
- ✅ Exchange health monitoring

### P2 - Nice to Have
- ⏸️ OKX adapter (defer to Phase 2)
- ⏸️ Bybit workaround (defer pending topic restoration)
- ⏸️ Volume-weighted aggregation (defer to user feedback)

---

## Known Limitations

1. **Binance WebSocket Blocked**: Using REST polling (5s latency) as workaround
2. **Hyperliquid No Historical Data**: Cannot backtest, real-time only
3. **Bybit Liquidation Topic Removed**: Deferred until alternative solution found
4. **OKX Untested**: Research needed before implementation

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| **Exchange API changes** | Version endpoints, change detection alerts |
| **Low Hyperliquid volume** | Acceptable - use as secondary source |
| **Database migration failure** | Test on copy first, have rollback plan |
| **Performance degradation** | Query optimization, index tuning, caching |

---

## Dependencies

### External Libraries
```toml
[project.dependencies]
websockets = "^12.0"    # Hyperliquid WebSocket
aiohttp = "^3.9.0"      # Binance REST API
```

### Infrastructure
- DuckDB (existing)
- FastAPI (existing)
- Redis (optional - defer to real-time streaming feature)

---

## Testing Strategy

### Unit Tests (EA-006)
- Adapter initialization
- Symbol normalization
- Health checks
- Error handling

### Integration Tests (EA-010)
- Multi-exchange streaming
- Failover scenarios
- Data consistency

### Load Tests (EA-027)
- 100 concurrent WebSocket clients
- 500 liquidations/sec throughput
- 30-minute stability test

### Validation Tests (EA-025)
- Hyperliquid price-level validation (target: ≥60% hit rate)
- Cross-exchange correlation analysis
- Comparison vs Binance (baseline: 77.8%)

---

## Documentation

### Developer Docs
- `docs/EXCHANGE_INTEGRATION.md` - How to add new exchange
- `docs/EXCHANGE_COMPARISON.md` - Exchange analysis and insights
- `docs/api_guide.md` - API reference (updated)

### User Docs
- FAQ: "Which exchanges are supported?"
- Tutorial: "How to filter liquidations by exchange"
- Changelog: New feature announcement

---

## Rollout Plan

### Week 1-2: Alpha (Internal)
- Binance + Hyperliquid only
- Dev team testing
- Bug fixes

### Week 3: Beta (10-20 users)
- Public beta release
- Gather UX feedback
- Stability monitoring

### Week 4: Production
- Public launch
- Marketing announcement
- 7-day close monitoring

### Month 2+: Expansion
- Add OKX (if feasible)
- Investigate Bybit alternatives
- Publish exchange comparison report

---

## Related Work

### Completed
- ✅ BTC/USDT validation (77.8% hit rate)
- ✅ DuckDB ingestion pipeline (1.9B trades)
- ✅ FastAPI heatmap endpoints
- ✅ Hyperliquid WebSocket testing

### Parallel Tracks
- 🔄 ETH/USDT expansion (P1 - separate feature)
- 🔄 Real-time streaming (P2 - separate feature)
- 📅 Alert system (P2 - separate feature)

### Future Enhancements
- Volume-weighted aggregation
- Arbitrage detection
- Predictive ensemble models

---

## References

- **Binance API**: https://binance-docs.github.io/apidocs/futures/en/
- **Bybit API**: https://bybit-exchange.github.io/docs/v5/intro
- **Hyperliquid API**: https://hyperliquid.gitbook.io/hyperliquid-docs/
- **OKX API**: https://www.okx.com/docs-v5/en/

---

## Contact

**Questions?** Open issue or discussion in GitHub repo.

**Contributing?** See `docs/EXCHANGE_INTEGRATION.md` for adapter template.

---

**Last Updated**: 2025-12-28
**Next Review**: After Phase 1 completion
