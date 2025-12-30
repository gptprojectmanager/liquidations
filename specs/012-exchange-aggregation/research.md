# Research: Exchange Aggregation

**Feature**: 012-exchange-aggregation
**Date**: 2025-12-29
**Status**: Complete

## Research Questions

### RQ1: How to connect to Binance liquidation data?

**Finding**: REST polling is the reliable option.

| Method | Status | Notes |
|--------|--------|-------|
| WebSocket `wss://fstream.binance.com/ws/!forceOrder@arr` | BLOCKED (403) | Likely rate limit or auth issue |
| REST `/fapi/v1/forceOrders` | WORKING | 5s polling, up to 100 results |

**Decision**: Use REST polling with 5s interval
**Rationale**: WebSocket 403 issue unresolved; REST is reliable workaround
**Alternatives Rejected**:
- WebSocket with API key auth (untested, may not help)
- Third-party WebSocket proxies (reliability concerns)

**API Details**:
```
GET https://fapi.binance.com/fapi/v1/forceOrders
Parameters:
  - symbol: BTCUSDT
  - limit: 100 (max)
Response: [{orderId, symbol, price, origQty, side, time, ...}]
```

---

### RQ2: How to connect to Hyperliquid liquidation data?

**Finding**: WebSocket trades channel with liquidation filter.

| Method | Status | Notes |
|--------|--------|-------|
| WebSocket `wss://api.hyperliquid.xyz/ws` | WORKING | Real-time, low latency |
| REST API | N/A | No historical liquidation endpoint |

**Decision**: Use WebSocket with `trades` subscription, filter `liquidation: true`
**Rationale**: Only real-time option; works reliably
**Alternatives Rejected**: None available

**API Details**:
```json
// Subscribe
{"method": "subscribe", "subscription": {"type": "trades", "coin": "BTC"}}

// Response (liquidation event)
{
  "channel": "trades",
  "data": [{
    "coin": "BTC",
    "px": "95234.5",
    "sz": "0.5",
    "side": "A",  // A=Ask(short liq), B=Bid(long liq)
    "liquidation": true
  }]
}
```

**Caveats**:
- No timestamp in response (use `datetime.now()`)
- Symbol format: "BTC" not "BTCUSDT"
- Low BTC liquidation frequency (~1-2/hour)

---

### RQ3: What is Bybit liquidation API status?

**Finding**: Liquidation WebSocket topic removed.

| Method | Status | Notes |
|--------|--------|-------|
| WebSocket `liquidation` topic | REMOVED | As of 2024, topic no longer exists |
| REST API | UNTESTED | May have delay |

**Decision**: Implement stub with `NotImplementedError`
**Rationale**: No reliable real-time source; defer until topic restored
**Alternatives Considered**:
- Infer from volume spikes (low accuracy, ~60%)
- Use REST with delay (not real-time)

---

### RQ4: What is OKX liquidation API status?

**Finding**: Untested, deferred to Phase 2+.

**Decision**: Not in MVP scope
**Rationale**: Focus on Binance + Hyperliquid first
**Next Steps**: Research after MVP stable

---

### RQ5: How to normalize data across exchanges?

**Finding**: Unified schema with exchange-specific converters.

| Field | Binance | Hyperliquid | Standard |
|-------|---------|-------------|----------|
| Symbol | `BTCUSDT` | `BTC` | `BTCUSDT` |
| Side | `BUY`/`SELL` | `A`/`B` | `long`/`short` |
| Timestamp | Unix ms | N/A | `datetime` UTC |
| Price | `price` | `px` | `float` |
| Quantity | `origQty` | `sz` | `float` |

**Decision**: `NormalizedLiquidation` dataclass with:
- Common fields (exchange, symbol, price, quantity, side, timestamp)
- Confidence score (1.0 Binance, 0.9 Hyperliquid - missing timestamp)
- Raw data preserved for debugging

---

### RQ6: How to handle exchange failures?

**Finding**: Graceful degradation with per-adapter error handling.

**Strategy**:
1. Wrap each adapter in try/except
2. Log failures, continue with working exchanges
3. Auto-reconnect with exponential backoff (max 3 retries)
4. Health check endpoint shows real-time status

**Decision**: Continue serving partial data vs. complete failure
**Rationale**: Constitution requires graceful degradation
**User Experience**: Show warning banner when exchange is down

---

### RQ7: What DuckDB schema changes are needed?

**Finding**: Add `exchange` column to `liquidations` table.

```sql
-- Migration
ALTER TABLE liquidations ADD COLUMN exchange VARCHAR DEFAULT 'binance';
CREATE INDEX idx_liquidations_exchange ON liquidations(exchange);

-- Backfill
UPDATE liquidations SET exchange = 'binance' WHERE exchange IS NULL;
```

**Decision**: Default to 'binance' for existing data
**Rationale**: Preserves backward compatibility, existing data is Binance-only
**Risk**: 185GB migration - test on copy first

---

### RQ8: What are the performance implications?

**Finding**: Acceptable overhead with proper indexing.

| Scenario | Target | Notes |
|----------|--------|-------|
| Single exchange query | <5s | Existing performance |
| Aggregated query | <7s | +40% overhead acceptable |
| Health check | <100ms | Cached for 10s |

**Decision**: Accept 40% performance overhead for multi-exchange
**Rationale**: User value > marginal latency increase
**Optimization**: Index on `(exchange, timestamp, symbol)`

---

## Technology Choices

### WebSocket Library: `websockets`

**Decision**: Use `websockets` for Hyperliquid
**Rationale**:
- Standard async WebSocket library
- Good reconnection support
- Lightweight (~50KB)

**Alternatives Rejected**:
- `aiohttp.ws`: More complex, overkill
- `python-socketio`: For Socket.IO, not raw WS

### HTTP Library: `aiohttp`

**Decision**: Use `aiohttp` for Binance REST
**Rationale**:
- Already in project dependencies
- Async support
- Connection pooling

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Why Binance WS 403? | Likely rate limit; use REST workaround |
| Hyperliquid missing timestamp | Use `datetime.now()`, lower confidence |
| Bybit alternative | Defer - implement stub |
| OKX status | Out of MVP scope |

---

## References

- Binance Futures API: https://binance-docs.github.io/apidocs/futures/en/
- Hyperliquid API: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
- Bybit API (for reference): https://bybit-exchange.github.io/docs/v5/intro

---

**Status**: All clarifications resolved
**Next**: Phase 1 - data-model.md
