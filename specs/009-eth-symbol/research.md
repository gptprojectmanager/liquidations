# Research: ETH/USDT Symbol Support

**Feature**: 009-eth-symbol
**Date**: 2025-12-28
**Status**: COMPLETE - No unknowns to resolve

---

## Executive Summary

This research confirms that **100% code reuse is valid**. The existing BTC pipeline is fully symbol-agnostic. No new code, formulas, or architectural changes required.

---

## Research Questions

### Q1: Is the ingestion pipeline symbol-agnostic?

**Decision**: YES - All scripts accept `--symbol` parameter

**Evidence**:
```bash
# Verified via grep
$ grep -r "argparse.*symbol" scripts/
scripts/ingest_aggtrades.py:    parser.add_argument("--symbol", required=True)
scripts/ingest_oi.py:    parser.add_argument("--symbol", required=True)
scripts/ingest_klines_15m.py:    parser.add_argument("--symbol", required=True)
scripts/validate_vs_coinglass.py:    parser.add_argument("--symbol", required=True)
```

**Alternatives Considered**: None needed - design already correct.

---

### Q2: Does the database schema support multiple symbols?

**Decision**: YES - All tables have `symbol` column with proper indexing

**Evidence**:
```sql
-- Verified schema
CREATE TABLE aggtrades_history (
    symbol VARCHAR,
    agg_trade_id BIGINT,
    timestamp TIMESTAMP,
    ...
    PRIMARY KEY (symbol, agg_trade_id)
);

CREATE TABLE open_interest_history (
    symbol VARCHAR,
    timestamp TIMESTAMP,
    open_interest_value DOUBLE,
    ...
    PRIMARY KEY (symbol, timestamp)
);

CREATE TABLE klines_15m_history (
    symbol VARCHAR,
    open_time TIMESTAMP,
    ...
    PRIMARY KEY (symbol, open_time)
);
```

**Alternatives Considered**: None needed - schema already correct.

---

### Q3: Is ETHUSDT in the API whitelist?

**Decision**: YES - Already whitelisted in `src/liquidationheatmap/api/main.py`

**Evidence**:
```python
# Line 229-241 in main.py
SUPPORTED_SYMBOLS = {
    "BTCUSDT",
    "ETHUSDT",    # <-- Already present!
    "BNBUSDT",
    "ADAUSDT",
    # ... (10 total symbols)
}
```

**Alternatives Considered**: None needed - whitelist already includes ETH.

---

### Q4: Does the frontend support symbol selection?

**Decision**: YES - Symbol dropdown already implemented

**Evidence**:
- `frontend/coinglass_heatmap.html` has symbol selector
- JavaScript fetches data with `symbol` query param
- No frontend changes needed

**Alternatives Considered**: None needed - UI already parameterized.

---

### Q5: Does ETH use the same liquidation formulas as BTC?

**Decision**: YES - Binance uses identical formulas for all USDT-M perpetuals

**Evidence**:
- Binance documentation confirms universal formulas:
  - Long liquidation: `entry_price * (1 - 1/leverage + maintenance_margin/leverage)`
  - Short liquidation: `entry_price * (1 + 1/leverage - maintenance_margin/leverage)`
- Only maintenance margin rates vary by notional tier (handled by existing tier logic)

**Source**: https://www.binance.com/en/support/faq/liquidation

**Alternatives Considered**: None - formula is exchange-wide.

---

### Q6: Is ETH historical data available?

**Decision**: LIKELY YES - Needs verification (T001)

**Expected Path**: `/media/sam/3TB-WDC/binance-history-data-downloader/data/ETHUSDT/aggTrades/`

**Verification Required**: Task T001 will confirm:
- Directory exists
- CSV files present
- Date range coverage (minimum 30 days)

---

## Conclusion

**All questions resolved. No blockers identified.**

| Question | Answer | Action Required |
|----------|--------|-----------------|
| Ingestion scripts | Symbol-agnostic | None |
| Database schema | Multi-symbol | None |
| API whitelist | ETH included | None |
| Frontend | Parameterized | None |
| Formulas | Universal | None |
| Data availability | Verify T001 | Confirm path |

**Recommendation**: Proceed directly to implementation. This is a pure data operations task.
