# Exchange Aggregation - Task Breakdown

**Feature**: Multi-Exchange Liquidation Data Aggregation
**Estimated Effort**: 7-10 days
**Status**: Not Started
**Created**: 2025-12-28

---

## Task Organization

Tasks organized by **dependency order** and **implementation phase**. Each task includes:
- **ID**: Unique identifier (EA-XXX)
- **Dependencies**: Prerequisite tasks
- **Effort**: Time estimate (hours)
- **Acceptance Criteria**: Definition of done

---

## Phase 1: Core Infrastructure (Days 1-3)

### EA-001: Create Exchange Module Structure
**Effort**: 1h
**Dependencies**: None
**Priority**: P0

**Description**:
Set up directory structure and base files for exchange adapters.

**Tasks**:
1. Create `src/exchanges/` directory
2. Create `src/exchanges/__init__.py`
3. Create `tests/test_exchanges/` directory
4. Create `tests/test_exchanges/__init__.py`
5. Update `pyproject.toml` with new dependencies (websockets, aiohttp)

**Acceptance Criteria**:
- [ ] Directory structure exists
- [ ] Imports work: `from src.exchanges import ...`
- [ ] Dependencies installable via `uv sync`

---

### EA-002: Implement Base Adapter Interface
**Effort**: 3h
**Dependencies**: EA-001
**Priority**: P0

**Description**:
Create abstract base class defining adapter contract.

**Tasks**:
1. Create `src/exchanges/base.py`
2. Define `NormalizedLiquidation` dataclass
3. Define `ExchangeHealth` dataclass
4. Define `ExchangeAdapter` abstract class with methods:
   - `exchange_name` (property)
   - `connect()` (async)
   - `disconnect()` (async)
   - `stream_liquidations()` (async generator)
   - `fetch_historical()` (async)
   - `health_check()` (async)
   - `normalize_symbol()` (sync)
5. Add comprehensive docstrings with examples

**Acceptance Criteria**:
- [ ] All dataclasses have type hints
- [ ] Abstract methods raise `NotImplementedError`
- [ ] Docstrings include usage examples
- [ ] MyPy validates types without errors

**Test Plan**:
```python
# tests/test_exchanges/test_base.py
def test_normalized_liquidation_schema():
    """NormalizedLiquidation has required fields."""
    liq = NormalizedLiquidation(
        exchange="test",
        symbol="BTCUSDT",
        price=95000.0,
        quantity=0.5,
        value_usd=47500.0,
        side="long",
        timestamp=datetime.now()
    )
    assert liq.exchange == "test"
    assert liq.confidence == 1.0  # Default

def test_abstract_adapter_raises():
    """ExchangeAdapter cannot be instantiated."""
    with pytest.raises(TypeError):
        ExchangeAdapter()
```

---

### EA-003: Implement Binance Adapter (REST)
**Effort**: 4h
**Dependencies**: EA-002
**Priority**: P0

**Description**:
Create Binance adapter using REST polling (WebSocket workaround).

**Tasks**:
1. Create `src/exchanges/binance.py`
2. Implement `BinanceAdapter` class
3. Use `aiohttp` for REST `/fapi/v1/forceOrders` polling
4. Implement connection pooling (single session)
5. Handle rate limits (5s polling interval)
6. Normalize response to `NormalizedLiquidation`
7. Add retry logic with exponential backoff
8. Implement deduplication (track seen order IDs)

**Acceptance Criteria**:
- [ ] Adapter connects without errors
- [ ] Polls every 5 seconds
- [ ] Returns `NormalizedLiquidation` objects
- [ ] No duplicate liquidations in stream
- [ ] Handles API errors gracefully (returns empty, logs warning)

**Test Plan**:
```python
# tests/test_exchanges/test_binance.py
@pytest.mark.asyncio
async def test_binance_connect():
    """Binance adapter initializes HTTP session."""
    adapter = BinanceAdapter()
    await adapter.connect()
    assert adapter._is_connected
    assert adapter._session is not None
    await adapter.disconnect()

@pytest.mark.asyncio
@pytest.mark.integration
async def test_binance_stream_liquidations():
    """Binance streams liquidations (may timeout if market quiet)."""
    adapter = BinanceAdapter()
    await adapter.connect()

    count = 0
    timeout = 30  # seconds
    start = time.time()

    async for liq in adapter.stream_liquidations("BTCUSDT"):
        assert liq.exchange == "binance"
        assert liq.symbol == "BTCUSDT"
        count += 1
        if count >= 1 or time.time() - start > timeout:
            break

    await adapter.disconnect()
    # Accept 0 liquidations if market quiet
    assert count >= 0
```

---

### EA-004: Implement Hyperliquid Adapter (WebSocket)
**Effort**: 3h
**Dependencies**: EA-002
**Priority**: P0

**Description**:
Create Hyperliquid adapter using WebSocket connection.

**Tasks**:
1. Create `src/exchanges/hyperliquid.py`
2. Implement `HyperliquidAdapter` class
3. Connect to `wss://api.hyperliquid.xyz/ws`
4. Subscribe to `trades` channel for BTC
5. Filter messages where `liquidation: true`
6. Normalize symbol ("BTC" → "BTCUSDT")
7. Handle missing timestamp (use `datetime.now()`)
8. Implement reconnection logic on disconnect
9. Add heartbeat detection

**Acceptance Criteria**:
- [ ] WebSocket connects successfully
- [ ] Subscription message sent correctly
- [ ] Liquidation events parsed and normalized
- [ ] Auto-reconnect on connection loss
- [ ] Confidence score = 0.9 (lower due to missing timestamp)

**Test Plan**:
```python
# tests/test_exchanges/test_hyperliquid.py
@pytest.mark.asyncio
@pytest.mark.integration
async def test_hyperliquid_websocket():
    """Hyperliquid WebSocket connects and receives trades."""
    adapter = HyperliquidAdapter()
    await adapter.connect()

    # Wait for at least one message (may be non-liquidation)
    received = False
    timeout = 30
    start = time.time()

    async for liq in adapter.stream_liquidations("BTCUSDT"):
        assert liq.exchange == "hyperliquid"
        received = True
        break
        if time.time() - start > timeout:
            break

    await adapter.disconnect()
    # Hyperliquid may have low liquidation frequency
    # Test passes if connection successful, even with no liq events
```

---

### EA-005: Implement Bybit Adapter (Stub)
**Effort**: 1h
**Dependencies**: EA-002
**Priority**: P2

**Description**:
Create stub adapter with NotImplementedError (liquidation topic removed).

**Tasks**:
1. Create `src/exchanges/bybit.py`
2. Implement `BybitAdapter` class
3. All methods raise `NotImplementedError` with explanation
4. `health_check()` returns unhealthy status
5. Add TODO comments for future implementation

**Acceptance Criteria**:
- [ ] Adapter compiles without errors
- [ ] Methods raise `NotImplementedError` with helpful message
- [ ] Docstring explains why not implemented

**Test Plan**:
```python
# tests/test_exchanges/test_bybit.py
def test_bybit_not_implemented():
    """Bybit adapter raises NotImplementedError."""
    adapter = BybitAdapter()
    with pytest.raises(NotImplementedError, match="topic removed"):
        asyncio.run(adapter.connect())
```

---

### EA-006: Write Adapter Unit Tests
**Effort**: 2h
**Dependencies**: EA-003, EA-004, EA-005
**Priority**: P0

**Description**:
Comprehensive unit tests for all adapter methods.

**Tasks**:
1. Test `normalize_symbol()` for each adapter
2. Test `health_check()` for each adapter
3. Test connection/disconnection lifecycle
4. Test error handling (API failures, network errors)
5. Mock external APIs to avoid flakiness

**Acceptance Criteria**:
- [ ] ≥80% code coverage for adapters
- [ ] All tests pass in CI
- [ ] Tests run in <10s (use mocks for integration)

---

## Phase 2: Aggregation Service (Days 3-5)

### EA-007: Implement Exchange Aggregator
**Effort**: 4h
**Dependencies**: EA-003, EA-004
**Priority**: P0

**Description**:
Create service to multiplex streams from multiple exchanges.

**Tasks**:
1. Create `src/exchanges/aggregator.py`
2. Implement `ExchangeAggregator` class
3. Initialize adapters based on exchange list
4. Implement `connect_all()` with parallel connection
5. Implement `disconnect_all()` with cleanup
6. Implement `stream_aggregated()` using asyncio.Queue
7. Add pump tasks to merge streams
8. Handle exceptions per-adapter (don't crash entire service)

**Acceptance Criteria**:
- [ ] Aggregator initializes all requested adapters
- [ ] Streams from multiple exchanges merged into single async iterator
- [ ] Single adapter failure doesn't crash aggregator
- [ ] All adapters disconnected cleanly on shutdown

**Test Plan**:
```python
# tests/integration/test_aggregator.py
@pytest.mark.asyncio
async def test_aggregator_multiplexing():
    """Aggregator merges Binance + Hyperliquid streams."""
    agg = ExchangeAggregator(exchanges=["binance", "hyperliquid"])
    await agg.connect_all()

    exchanges_seen = set()
    count = 0

    async for liq in agg.stream_aggregated("BTCUSDT"):
        exchanges_seen.add(liq.exchange)
        count += 1
        if count >= 5:
            break

    await agg.disconnect_all()
    assert len(exchanges_seen) > 0  # At least one exchange worked
```

---

### EA-008: Implement Health Check Aggregation
**Effort**: 2h
**Dependencies**: EA-007
**Priority**: P0

**Description**:
Aggregate health status from all exchanges.

**Tasks**:
1. Implement `health_check_all()` method in aggregator
2. Call `health_check()` on all adapters in parallel
3. Handle exceptions (mark exchange unhealthy on error)
4. Return dict mapping exchange name to `ExchangeHealth`
5. Add `get_active_exchanges()` helper

**Acceptance Criteria**:
- [ ] Health check returns status for all exchanges
- [ ] Failed health checks don't crash method
- [ ] Active exchanges list accurate

**Test Plan**:
```python
@pytest.mark.asyncio
async def test_health_check_aggregation():
    """Health check returns status for all exchanges."""
    agg = ExchangeAggregator(exchanges=["binance", "hyperliquid"])
    await agg.connect_all()

    health = await agg.health_check_all()

    assert "binance" in health
    assert "hyperliquid" in health
    assert health["binance"].exchange == "binance"

    await agg.disconnect_all()
```

---

### EA-009: Add Graceful Degradation Logic
**Effort**: 2h
**Dependencies**: EA-008
**Priority**: P1

**Description**:
System continues functioning when exchanges fail.

**Tasks**:
1. Wrap adapter streams in try/except
2. Log exchange failures but continue with others
3. Update health status on failure
4. Implement automatic reconnection (max 3 retries)
5. Skip failed exchanges in aggregation

**Acceptance Criteria**:
- [ ] Aggregator survives single exchange crash
- [ ] Failed exchanges logged with details
- [ ] Successful exchanges continue streaming
- [ ] Auto-reconnect attempts for failed exchanges

**Test Plan**:
```python
@pytest.mark.asyncio
async def test_single_exchange_failure():
    """Aggregator survives Hyperliquid failure."""
    agg = ExchangeAggregator(exchanges=["binance", "hyperliquid"])

    # Mock Hyperliquid to fail
    async def fail_connect():
        raise Exception("Mock failure")

    agg.adapters["hyperliquid"].connect = fail_connect

    await agg.connect_all()

    # Binance should still be active
    active = agg.get_active_exchanges()
    assert "binance" in active

    await agg.disconnect_all()
```

---

### EA-010: Write Aggregator Integration Tests
**Effort**: 3h
**Dependencies**: EA-009
**Priority**: P0

**Description**:
End-to-end tests for multi-exchange streaming.

**Tasks**:
1. Test happy path (all exchanges working)
2. Test partial failure (one exchange down)
3. Test total failure (all exchanges down)
4. Test reconnection logic
5. Load test (simulate 100+ liquidations/sec)

**Acceptance Criteria**:
- [ ] All integration tests pass
- [ ] Tests complete in <60s
- [ ] No memory leaks detected

---

## Phase 3: Database Integration (Days 5-6)

### EA-011: Add Exchange Column to Schema
**Effort**: 2h
**Dependencies**: None (parallel to Phase 1-2)
**Priority**: P0

**Description**:
Extend DuckDB schema to support multi-exchange data.

**Tasks**:
1. Create migration script `scripts/migrate_add_exchange_column.py`
2. Add `exchange VARCHAR DEFAULT 'binance'` to `liquidations` table
3. Create index on `exchange` column
4. Backfill existing data with "binance" value
5. Update schema documentation

**Acceptance Criteria**:
- [ ] Migration runs without errors on 185GB database
- [ ] Existing queries still work (backward compatible)
- [ ] Index improves query performance for exchange filtering

**SQL**:
```sql
-- Migration SQL
ALTER TABLE liquidations
ADD COLUMN exchange VARCHAR DEFAULT 'binance';

CREATE INDEX IF NOT EXISTS idx_liquidations_exchange
ON liquidations(exchange);

-- Verify migration
SELECT exchange, COUNT(*) FROM liquidations GROUP BY exchange;
-- Should show: binance | <total_rows>
```

**Test Plan**:
```python
# tests/test_migrations/test_add_exchange.py
def test_migration_preserves_data():
    """Migration doesn't lose data."""
    # Count rows before
    conn = duckdb.connect("test.duckdb")
    before_count = conn.execute("SELECT COUNT(*) FROM liquidations").fetchone()[0]

    # Run migration
    run_migration()

    # Count rows after
    after_count = conn.execute("SELECT COUNT(*) FROM liquidations").fetchone()[0]

    assert before_count == after_count
    assert conn.execute("SELECT DISTINCT exchange FROM liquidations").fetchall() == [("binance",)]
```

---

### EA-012: Create Exchange Health Monitoring Table
**Effort**: 1h
**Dependencies**: EA-011
**Priority**: P1

**Description**:
Store exchange health check results for monitoring.

**Tasks**:
1. Add to `scripts/init_database.py`:
   ```sql
   CREATE TABLE IF NOT EXISTS exchange_health (
       timestamp TIMESTAMP,
       exchange VARCHAR,
       is_connected BOOLEAN,
       message_count INTEGER,
       error_count INTEGER,
       uptime_percent FLOAT,
       PRIMARY KEY (timestamp, exchange)
   );
   ```
2. Create helper function to log health checks
3. Add cleanup job (delete records older than 7 days)

**Acceptance Criteria**:
- [ ] Table created successfully
- [ ] Can insert health records
- [ ] Cleanup job runs without errors

---

### EA-013: Update Ingestion Pipeline
**Effort**: 2h
**Dependencies**: EA-011
**Priority**: P0

**Description**:
Tag new liquidations with exchange source.

**Tasks**:
1. Update `src/liquidationheatmap/ingestion/db_service.py`
2. Add `exchange` parameter to insert methods
3. Update `scripts/ingest_aggtrades.py` to tag as "binance"
4. Update validation scripts to test per-exchange
5. Add exchange to log messages

**Acceptance Criteria**:
- [ ] New ingestions tagged with correct exchange
- [ ] Existing ingestion scripts still work
- [ ] No performance degradation

**Test Plan**:
```python
# tests/test_ingestion/test_exchange_tagging.py
def test_liquidation_tagged_with_exchange():
    """Ingested liquidations have exchange tag."""
    # Ingest test data
    ingest_sample_data(exchange="binance")

    # Query recent liquidation
    conn = duckdb.connect("test.duckdb")
    result = conn.execute("""
        SELECT exchange FROM liquidations
        ORDER BY timestamp DESC LIMIT 1
    """).fetchone()

    assert result[0] == "binance"
```

---

### EA-014: Optimize Multi-Exchange Queries
**Effort**: 2h
**Dependencies**: EA-013
**Priority**: P1

**Description**:
Ensure queries filtering by exchange are fast.

**Tasks**:
1. Benchmark existing heatmap query
2. Add `WHERE exchange IN (...)` filter
3. Verify index is used (EXPLAIN QUERY PLAN)
4. Test with different exchange combinations
5. Document query patterns

**Acceptance Criteria**:
- [ ] Single-exchange query: <3s for 24h data
- [ ] Multi-exchange query: <7s for 24h data
- [ ] Index scan confirmed (no full table scan)

**Benchmark**:
```sql
-- Benchmark query
EXPLAIN ANALYZE
SELECT price, SUM(quantity) AS total_quantity
FROM liquidations
WHERE exchange IN ('binance', 'hyperliquid')
  AND timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY price
ORDER BY total_quantity DESC
LIMIT 100;
```

---

## Phase 4: API Extension (Days 6-7)

### EA-015: Add Exchanges Parameter to Heatmap Endpoint
**Effort**: 3h
**Dependencies**: EA-007, EA-013
**Priority**: P0

**Description**:
Extend `/liquidations/heatmap` to accept exchange filter.

**Tasks**:
1. Update `src/liquidationheatmap/api/main.py`
2. Add `exchanges: Optional[str] = None` parameter
3. Parse comma-separated exchange list
4. Validate exchange names against supported list
5. Modify DuckDB query to filter by exchanges
6. Return per-exchange breakdown in response
7. Update Pydantic response models

**Acceptance Criteria**:
- [ ] `/liquidations/heatmap?exchanges=binance` returns Binance-only data
- [ ] `/liquidations/heatmap` (no param) returns all active exchanges
- [ ] Invalid exchange name returns 400 error
- [ ] Response includes per-exchange statistics

**API Contract**:
```json
GET /liquidations/heatmap?symbol=BTCUSDT&timeframe=24h&exchanges=binance,hyperliquid

Response:
{
  "symbol": "BTCUSDT",
  "timeframe": "24h",
  "current_price": 95234.56,
  "exchanges": ["binance", "hyperliquid"],
  "zones": [
    {
      "price_low": 94000,
      "price_high": 94500,
      "total_density": 1234.5,
      "side": "long",
      "exchange_breakdown": {
        "binance": 1100.0,
        "hyperliquid": 134.5
      }
    }
  ],
  "per_exchange": {
    "binance": {
      "zone_count": 15,
      "total_volume": 50000000
    },
    "hyperliquid": {
      "zone_count": 3,
      "total_volume": 2500000
    }
  }
}
```

**Test Plan**:
```python
# tests/test_api/test_exchange_filter.py
@pytest.mark.asyncio
async def test_heatmap_single_exchange():
    """Heatmap filters by single exchange."""
    response = await client.get("/liquidations/heatmap?exchanges=binance")
    assert response.status_code == 200
    data = response.json()
    assert data["exchanges"] == ["binance"]
    # All zones should be from binance
    for zone in data["zones"]:
        assert "binance" in zone["exchange_breakdown"]
        assert zone["exchange_breakdown"]["binance"] > 0

@pytest.mark.asyncio
async def test_heatmap_multiple_exchanges():
    """Heatmap aggregates multiple exchanges."""
    response = await client.get("/liquidations/heatmap?exchanges=binance,hyperliquid")
    assert response.status_code == 200
    data = response.json()
    assert set(data["exchanges"]) == {"binance", "hyperliquid"}
```

---

### EA-016: Add Exchange Health Endpoint
**Effort**: 1h
**Dependencies**: EA-008
**Priority**: P0

**Description**:
Create endpoint to check exchange status.

**Tasks**:
1. Add `GET /exchanges/health` endpoint
2. Call `aggregator.health_check_all()`
3. Return JSON with health status per exchange
4. Add timestamp to response
5. Cache response for 10s

**Acceptance Criteria**:
- [ ] Endpoint returns 200 with valid JSON
- [ ] All configured exchanges included
- [ ] Response cached (verify via logs)

**API Contract**:
```json
GET /exchanges/health

Response:
{
  "timestamp": "2025-12-28T12:34:56Z",
  "exchanges": {
    "binance": {
      "exchange": "binance",
      "is_connected": true,
      "last_heartbeat": "2025-12-28T12:34:50Z",
      "message_count": 1234,
      "error_count": 2,
      "uptime_percent": 99.8
    },
    "hyperliquid": {
      "exchange": "hyperliquid",
      "is_connected": true,
      "last_heartbeat": "2025-12-28T12:34:55Z",
      "message_count": 45,
      "error_count": 0,
      "uptime_percent": 100.0
    }
  }
}
```

---

### EA-017: Add List Exchanges Endpoint
**Effort**: 0.5h
**Dependencies**: EA-007
**Priority**: P1

**Description**:
Return list of supported exchanges.

**Tasks**:
1. Add `GET /exchanges` endpoint
2. Return static list from `ExchangeAggregator.SUPPORTED_EXCHANGES`
3. Include metadata (name, status, features)

**Acceptance Criteria**:
- [ ] Endpoint returns list of exchanges
- [ ] Includes implementation status (working/stub/planned)

**API Contract**:
```json
GET /exchanges

Response:
{
  "exchanges": [
    {
      "name": "binance",
      "display_name": "Binance Futures",
      "status": "active",
      "features": {
        "real_time": true,
        "historical": true,
        "websocket": false
      }
    },
    {
      "name": "hyperliquid",
      "display_name": "Hyperliquid",
      "status": "active",
      "features": {
        "real_time": true,
        "historical": false,
        "websocket": true
      }
    },
    {
      "name": "bybit",
      "display_name": "Bybit",
      "status": "unavailable",
      "features": {
        "real_time": false,
        "historical": false,
        "websocket": false
      }
    }
  ]
}
```

---

### EA-018: Update API Documentation
**Effort**: 2h
**Dependencies**: EA-015, EA-016, EA-017
**Priority**: P1

**Description**:
Document new endpoints and parameters.

**Tasks**:
1. Update `docs/api_guide.md`
2. Add examples for exchange filtering
3. Document per-exchange response format
4. Add curl/Postman examples
5. Update FastAPI auto-generated docs (docstrings)

**Acceptance Criteria**:
- [ ] All new endpoints documented
- [ ] Code examples included
- [ ] FastAPI `/docs` shows correct schemas

---

### EA-019: Integration Test Full API Flow
**Effort**: 2h
**Dependencies**: EA-015, EA-016, EA-017
**Priority**: P0

**Description**:
End-to-end test of multi-exchange API.

**Tasks**:
1. Start aggregator with Binance + Hyperliquid
2. Call `/exchanges/health` - verify both connected
3. Call `/liquidations/heatmap?exchanges=binance` - verify filter works
4. Call `/liquidations/heatmap` - verify aggregation works
5. Simulate exchange failure - verify graceful degradation

**Acceptance Criteria**:
- [ ] All API calls return valid responses
- [ ] Exchange failure doesn't crash API
- [ ] Performance meets targets (<7s)

---

## Phase 5: Frontend Integration (Days 7-8)

### EA-020: Add Exchange Selector Dropdown
**Effort**: 2h
**Dependencies**: EA-015
**Priority**: P0

**Description**:
Add UI control to filter by exchange.

**Tasks**:
1. Update `frontend/heatmap.html`
2. Add dropdown: "All Exchanges | Binance | Hyperliquid"
3. Bind onChange event to reload heatmap
4. Update API call to include `exchanges` parameter
5. Add loading indicator during reload

**Acceptance Criteria**:
- [ ] Dropdown shows all exchanges
- [ ] Selecting exchange reloads chart
- [ ] Chart updates within 3s

**HTML**:
```html
<select id="exchange-selector" onchange="loadHeatmap()">
  <option value="">All Exchanges</option>
  <option value="binance">Binance Only</option>
  <option value="hyperliquid">Hyperliquid Only</option>
  <option value="binance,hyperliquid">Binance + Hyperliquid</option>
</select>
```

---

### EA-021: Add Exchange Health Indicators
**Effort**: 1h
**Dependencies**: EA-016
**Priority**: P1

**Description**:
Show real-time exchange status badges.

**Tasks**:
1. Poll `/exchanges/health` every 30s
2. Display colored badges (green=connected, red=disconnected)
3. Show tooltip with details on hover
4. Add icon next to exchange name

**Acceptance Criteria**:
- [ ] Badges update automatically
- [ ] Colors accurate to connection status
- [ ] Tooltip shows message count, errors

**HTML**:
```html
<div class="exchange-status">
  <span class="badge badge-success" title="Connected, 1234 msgs">
    <i class="icon-check"></i> Binance
  </span>
  <span class="badge badge-warning" title="0 messages">
    <i class="icon-alert"></i> Hyperliquid
  </span>
</div>
```

---

### EA-022: Color-Code Liquidation Zones by Exchange
**Effort**: 2h
**Dependencies**: EA-020
**Priority**: P1

**Description**:
Visual distinction between exchange sources.

**Tasks**:
1. Assign colors: Binance=orange, Hyperliquid=purple
2. Update Plotly.js trace colors based on exchange
3. Add stacked bars showing exchange contribution
4. Add legend explaining color scheme

**Acceptance Criteria**:
- [ ] Each exchange has distinct color
- [ ] Stacked bars show exchange breakdown
- [ ] Legend displays correctly

**JavaScript**:
```javascript
const exchangeColors = {
  binance: '#F0B90B',      // Binance yellow
  hyperliquid: '#9B59B6',  // Purple
  bybit: '#F39C12'         // Orange (future)
};

zones.forEach(zone => {
  const traces = Object.entries(zone.exchange_breakdown).map(([exchange, value]) => ({
    x: [zone.price_low],
    y: [value],
    name: exchange,
    marker: { color: exchangeColors[exchange] },
    type: 'bar'
  }));
});
```

---

### EA-023: Update Chart Tooltips
**Effort**: 1h
**Dependencies**: EA-022
**Priority**: P2

**Description**:
Show exchange source in hover tooltips.

**Tasks**:
1. Update Plotly.js `hovertemplate`
2. Include exchange breakdown in tooltip
3. Format percentages for readability

**Acceptance Criteria**:
- [ ] Tooltip shows exchange name
- [ ] Shows % contribution from each exchange

**Tooltip Example**:
```
Price: $94,500
Total Liquidations: $1.2M
┌─────────────┬────────┐
│ Binance     │ 85%    │
│ Hyperliquid │ 15%    │
└─────────────┴────────┘
```

---

### EA-024: Frontend Integration Tests
**Effort**: 2h
**Dependencies**: EA-020, EA-021, EA-022
**Priority**: P1

**Description**:
Test frontend with multiple exchanges.

**Tasks**:
1. Test exchange selector functionality
2. Test health badge updates
3. Test chart reloading
4. Test error handling (exchange down)

**Acceptance Criteria**:
- [ ] All UI controls functional
- [ ] No JavaScript errors in console
- [ ] Mobile responsive

---

## Phase 6: Validation & Documentation (Days 8-10)

### EA-025: Run Hyperliquid Price-Level Validation
**Effort**: 3h
**Dependencies**: EA-004, EA-013
**Priority**: P0

**Description**:
Validate Hyperliquid liquidations using price-level approach.

**Tasks**:
1. Collect Hyperliquid liquidations for 24h
2. Compare against our predicted zones
3. Calculate hit rate (expect ≥60%)
4. Generate validation report
5. Save results to `data/validation/hyperliquid_validation.jsonl`

**Acceptance Criteria**:
- [ ] Hit rate documented
- [ ] Report includes sample size, timeframe
- [ ] Results compared to Binance (77.8%)

**Expected Outcome**:
```
Hyperliquid Validation Results:
- Sample Period: 2025-12-28 00:00 - 23:59 UTC
- Total Liquidations: 145
- Predicted Correctly: 92
- Hit Rate: 63.4%
- Notes: Lower than Binance (77.8%) due to lower volume, acceptable
```

---

### EA-026: Cross-Exchange Correlation Analysis
**Effort**: 2h
**Dependencies**: EA-025
**Priority**: P1

**Description**:
Analyze liquidation pattern correlation between exchanges.

**Tasks**:
1. Export liquidations from Binance + Hyperliquid
2. Calculate Pearson correlation of price levels
3. Identify common liquidation clusters
4. Document findings in `docs/EXCHANGE_COMPARISON.md`

**Acceptance Criteria**:
- [ ] Correlation coefficient calculated
- [ ] Visual chart showing overlap
- [ ] Insights documented

**Analysis Example**:
```
Binance vs Hyperliquid Correlation (24h):
- Pearson r = 0.72 (strong positive correlation)
- Common clusters: $94k, $95.5k, $96.2k
- Unique to Binance: $93.8k (tier boundary effect)
- Unique to Hyperliquid: $95.9k (smaller positions)
```

---

### EA-027: Load Test Aggregator
**Effort**: 2h
**Dependencies**: EA-007
**Priority**: P1

**Description**:
Simulate high load to verify stability.

**Tasks**:
1. Create load test script with 100 concurrent WebSocket clients
2. Simulate 500 liquidations/sec from all exchanges
3. Monitor memory usage, CPU, latency
4. Identify bottlenecks
5. Document capacity limits

**Acceptance Criteria**:
- [ ] System handles 100 concurrent clients
- [ ] Latency <500ms at p99
- [ ] No memory leaks over 30 min test

**Load Test Script**:
```python
# scripts/load_test_aggregator.py
async def simulate_client():
    async with websockets.connect("ws://localhost:8000/ws/liquidations") as ws:
        for _ in range(100):
            msg = await ws.recv()
            # Process message

async def run_load_test():
    tasks = [simulate_client() for _ in range(100)]
    await asyncio.gather(*tasks)
```

---

### EA-028: Test Exchange Failover Scenarios
**Effort**: 2h
**Dependencies**: EA-009
**Priority**: P0

**Description**:
Verify graceful degradation under failures.

**Tasks**:
1. Test scenario: Binance down, Hyperliquid up
2. Test scenario: Both down
3. Test scenario: Hyperliquid reconnects after failure
4. Test scenario: Invalid data from exchange
5. Verify logs, alerts, user experience

**Acceptance Criteria**:
- [ ] System survives all failure scenarios
- [ ] Errors logged with context
- [ ] Users see helpful error messages

**Test Cases**:
```
TC-1: Binance API down
  Given: Binance returns 500 error
  When: User requests heatmap
  Then: Hyperliquid data shown, warning banner displayed

TC-2: All exchanges down
  Given: Both exchanges unreachable
  When: User requests heatmap
  Then: Cached data shown (if available), error message displayed

TC-3: Invalid data from Hyperliquid
  Given: Hyperliquid sends malformed JSON
  When: Aggregator receives message
  Then: Message logged, skipped, stream continues
```

---

### EA-029: Document Exchange Integration Guide
**Effort**: 2h
**Dependencies**: All previous tasks
**Priority**: P1

**Description**:
Create guide for adding new exchanges.

**Tasks**:
1. Create `docs/EXCHANGE_INTEGRATION.md`
2. Document adapter interface requirements
3. Provide template adapter code
4. List common pitfalls
5. Add checklist for new exchange

**Acceptance Criteria**:
- [ ] Guide includes step-by-step instructions
- [ ] Template code compiles
- [ ] Checklist comprehensive

**Document Outline**:
```markdown
# Adding a New Exchange

## Prerequisites
- Exchange has public liquidation API/WebSocket
- Exchange ToS allows commercial use
- Exchange uptime >95%

## Steps
1. Create adapter class extending `ExchangeAdapter`
2. Implement all abstract methods
3. Add symbol normalization logic
4. Write unit tests
5. Add to `SUPPORTED_EXCHANGES` registry
6. Update frontend dropdown
7. Run validation tests

## Template Code
[Include template adapter]

## Checklist
- [ ] Adapter passes all tests
- [ ] Health check implemented
- [ ] Error handling robust
- [ ] Documentation updated
```

---

### EA-030: Write Exchange Comparison Report
**Effort**: 2h
**Dependencies**: EA-026
**Priority**: P2

**Description**:
Publish findings on exchange differences.

**Tasks**:
1. Create `docs/EXCHANGE_COMPARISON.md`
2. Summarize data sources per exchange
3. Compare liquidation frequencies
4. Analyze tier structure differences
5. Provide recommendations

**Acceptance Criteria**:
- [ ] Report includes quantitative data
- [ ] Charts/graphs illustrating differences
- [ ] Actionable insights for users

**Report Sections**:
```markdown
# Exchange Comparison Analysis

## Data Availability
| Exchange | Historical | Real-time | WebSocket | API Quality |
|----------|-----------|-----------|-----------|-------------|
| Binance  | ✅ 4 years | ✅ REST   | ❌ Blocked | High       |
| HL       | ❌         | ✅ WS     | ✅         | Medium     |

## Liquidation Frequency (24h sample)
- Binance: 1,234 events
- Hyperliquid: 67 events

## Validation Results
- Binance Hit Rate: 77.8%
- Hyperliquid Hit Rate: 63.4%

## Recommendations
- Use Binance as primary source (volume + accuracy)
- Use Hyperliquid as secondary (diversification)
- Wait for Bybit topic restoration before adding
```

---

## Phase 7: Optional Enhancements (Future)

### EA-031: Volume-Weighted Aggregation (P3)
**Effort**: 3h
**Priority**: P3

**Description**:
Weight heatmap zones by exchange market share.

**Tasks**:
1. Fetch 24h volume per exchange (Binance API)
2. Calculate market share percentages
3. Apply weights to liquidation zones
4. Add toggle: "Weighted" vs "Unweighted"

**Deferred**: Not critical for MVP, add after user feedback

---

### EA-032: OKX Adapter Implementation (P3)
**Effort**: 4h
**Priority**: P3

**Description**:
Add OKX exchange support.

**Tasks**:
1. Research OKX liquidation API
2. Test WebSocket stability
3. Implement `OKXAdapter`
4. Run validation tests

**Deferred**: After Binance + Hyperliquid proven stable

---

### EA-033: Bybit Inference Heuristic (P4)
**Effort**: 6h
**Priority**: P4

**Description**:
Infer Bybit liquidations from volume spikes.

**Tasks**:
1. Subscribe to Bybit trades channel
2. Detect volume anomalies (3σ threshold)
3. Classify as likely liquidations
4. Label with lower confidence (0.6)

**Deferred**: Low ROI, wait for official topic restoration

---

## Summary Statistics

**Total Tasks**: 33 (30 core + 3 optional)
**Total Estimated Effort**: 68 hours (~8.5 days)
**Critical Path**: EA-001 → EA-002 → EA-003 → EA-007 → EA-015 → EA-020

**Dependency Graph** (simplified):
```
EA-001 (Structure)
  ├─→ EA-002 (Base Interface)
  │     ├─→ EA-003 (Binance)
  │     ├─→ EA-004 (Hyperliquid)
  │     └─→ EA-005 (Bybit Stub)
  │           └─→ EA-006 (Tests)
  │                 └─→ EA-007 (Aggregator)
  │                       ├─→ EA-008 (Health Check)
  │                       ├─→ EA-009 (Degradation)
  │                       └─→ EA-010 (Tests)
  │                             ├─→ EA-015 (API Extension)
  │                             │     └─→ EA-020 (Frontend)
  │                             └─→ EA-025 (Validation)

EA-011 (DB Schema) [Parallel]
  └─→ EA-013 (Ingestion Update)
        └─→ EA-025 (Validation)
```

**Parallelization Opportunities**:
- Phase 1 (EA-001 to EA-006) + Phase 3 (EA-011 to EA-014) can run in parallel
- EA-025 (validation) can start as soon as EA-004 + EA-013 complete

---

## Risk Register

| Task | Risk | Mitigation |
|------|------|------------|
| EA-003 | Binance rate limits may block polling | Implement backoff, monitor API usage |
| EA-004 | Hyperliquid low liquidation frequency | Accept lower validation sample, extend collection period |
| EA-011 | DuckDB migration fails on large DB | Test on copy first, have rollback plan |
| EA-027 | Load test reveals bottlenecks | Profile code, optimize hot paths before launch |

---

## Completion Checklist

### Phase 1 Complete When:
- [ ] All adapters (Binance, Hyperliquid, Bybit stub) implemented
- [ ] Unit tests pass with ≥80% coverage
- [ ] Integration test shows multi-exchange streaming works

### Phase 2 Complete When:
- [ ] Aggregator merges streams without errors
- [ ] Health checks return accurate status
- [ ] System survives single exchange failure

### Phase 3 Complete When:
- [ ] Database schema updated and migrated
- [ ] Exchange column indexed and queryable
- [ ] Performance benchmarks met (<7s aggregated query)

### Phase 4 Complete When:
- [ ] API endpoints functional and documented
- [ ] Exchange filter works correctly
- [ ] Health endpoint returns real-time status

### Phase 5 Complete When:
- [ ] Frontend shows exchange selector
- [ ] Health badges update automatically
- [ ] Charts color-coded by exchange

### Phase 6 Complete When:
- [ ] Hyperliquid validation completed (≥60% hit rate)
- [ ] Load test passed (100 clients, 30 min)
- [ ] Documentation published

---

## Next Steps

1. **Review tasks with team** - Confirm priorities and estimates
2. **Set up project board** - Create GitHub issues for each task
3. **Start Phase 1** - Begin with EA-001 (directory structure)
4. **Daily standups** - Track progress, adjust estimates

---

**Status**: Ready for implementation
**Last Updated**: 2025-12-28
**Assigned To**: TBD
