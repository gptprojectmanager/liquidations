# Liquidation Heatmap V2 - Implementation Tasks

## Overview
Implementation tasks for the time-evolving liquidation heatmap model.

---

## Phase 1: Core Algorithm

### Task 1.1: Create Position Data Models
- **Priority**: P0 (Critical)
- **File**: `src/liquidationheatmap/models/position.py`
- **Description**: Define Pydantic models for position lifecycle tracking
- **Acceptance Criteria**:
  - [ ] `LiquidationLevel` model with entry_price, liq_price, volume, side, leverage, timestamps
  - [ ] `HeatmapCell` model for aggregated density per timestamp/price
  - [ ] `HeatmapSnapshot` model for full state at one timestamp
  - [ ] Unit tests for model validation

### Task 1.2: Implement Time-Evolving Calculator
- **Priority**: P0 (Critical)
- **File**: `src/liquidationheatmap/models/time_evolving_heatmap.py`
- **Description**: Core algorithm for calculating time-series of liquidation states
- **Dependencies**: Task 1.1
- **Acceptance Criteria**:
  - [ ] `calculate_time_evolving_heatmap()` function implemented
  - [ ] Position creation from positive OI delta
  - [ ] Position consumption when price crosses level
  - [ ] Position removal from negative OI delta
  - [ ] Returns `List[HeatmapSnapshot]`
  - [ ] Unit tests with mock data (>80% coverage)

### Task 1.3: Implement Price Crossing Detection
- **Priority**: P0 (Critical)
- **File**: `src/liquidationheatmap/models/time_evolving_heatmap.py`
- **Description**: Logic to detect when candle price action triggers liquidations
- **Dependencies**: Task 1.1
- **Acceptance Criteria**:
  - [ ] `should_liquidate(position, candle)` function
  - [ ] Long liquidation: `candle.low <= liq_price`
  - [ ] Short liquidation: `candle.high >= liq_price`
  - [ ] Edge cases: exact price match, wick-only crosses
  - [ ] Unit tests for all scenarios

### Task 1.4: Implement Side Inference
- **Priority**: P1 (High)
- **File**: `src/liquidationheatmap/models/time_evolving_heatmap.py`
- **Description**: Infer position side from candle direction + OI delta
- **Acceptance Criteria**:
  - [ ] Bullish candle + OI increase → LONG
  - [ ] Bearish candle + OI increase → SHORT
  - [ ] Neutral/doji handling (skip or distribute)
  - [ ] Unit tests

---

## Phase 2: Database Schema

### Task 2.1: Create Migration - liquidation_snapshots
- **Priority**: P1 (High)
- **File**: `scripts/migrations/add_liquidation_snapshots.sql`
- **Description**: Create table for pre-computed heatmap snapshots
- **Acceptance Criteria**:
  - [ ] Table created with all required columns
  - [ ] Proper indexes for query performance
  - [ ] Migration script tested on dev database

```sql
CREATE TABLE IF NOT EXISTS liquidation_snapshots (
    id BIGINT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    price_bucket DECIMAL(18,2) NOT NULL,
    side VARCHAR(10) NOT NULL,
    active_volume DECIMAL(20,8) DEFAULT 0,
    consumed_volume DECIMAL(20,8) DEFAULT 0,
    UNIQUE(timestamp, symbol, price_bucket, side)
);

CREATE INDEX idx_liq_snap_ts_sym ON liquidation_snapshots(timestamp, symbol);
CREATE INDEX idx_liq_snap_price ON liquidation_snapshots(price_bucket);
```

### Task 2.2: Create Migration - position_events
- **Priority**: P2 (Medium)
- **File**: `scripts/migrations/add_position_events.sql`
- **Description**: Event log for position lifecycle tracking
- **Acceptance Criteria**:
  - [ ] Table for tracking open/close/liquidate events
  - [ ] Useful for debugging and audit trail

---

## Phase 3: API Updates

### Task 3.1: New Endpoint - Heatmap Timeseries
- **Priority**: P0 (Critical)
- **File**: `src/liquidationheatmap/api/main.py`
- **Description**: API endpoint returning time-series heatmap data
- **Dependencies**: Task 1.2
- **Acceptance Criteria**:
  - [ ] `GET /liquidations/heatmap-timeseries`
  - [ ] Parameters: symbol, start_time, end_time, interval
  - [ ] Response includes per-timestamp density levels
  - [ ] Pagination for large time ranges
  - [ ] OpenAPI documentation
  - [ ] Integration tests

### Task 3.2: Update Existing Levels Endpoint
- **Priority**: P2 (Medium)
- **File**: `src/liquidationheatmap/api/main.py`
- **Description**: Deprecation notice on old static endpoint
- **Acceptance Criteria**:
  - [ ] Add deprecation header to `/liquidations/levels`
  - [ ] Point to new endpoint in response
  - [ ] Update documentation

---

## Phase 4: Frontend Updates

### Task 4.1: Fetch Timeseries Data
- **Priority**: P0 (Critical)
- **File**: `frontend/coinglass_heatmap.html`
- **Description**: Update frontend to call new timeseries endpoint
- **Dependencies**: Task 3.1
- **Acceptance Criteria**:
  - [ ] Call `/liquidations/heatmap-timeseries` instead of static endpoint
  - [ ] Parse response with per-timestamp levels
  - [ ] Handle loading states

### Task 4.2: Render Time-Varying Heatmap
- **Priority**: P0 (Critical)
- **File**: `frontend/coinglass_heatmap.html`
- **Description**: Each heatmap column shows density at that timestamp
- **Dependencies**: Task 4.1
- **Acceptance Criteria**:
  - [ ] Build heatmap matrix where Z[t][p] = density at time t, price p
  - [ ] Density varies across time (not constant horizontal bands)
  - [ ] Visual distinction between active and consumed levels
  - [ ] Smooth color transitions

### Task 4.3: Add Liquidation Event Indicators
- **Priority**: P3 (Low)
- **File**: `frontend/coinglass_heatmap.html`
- **Description**: Visual markers when major liquidations occur
- **Acceptance Criteria**:
  - [ ] Highlight moments of high liquidation consumption
  - [ ] Optional toggle to show/hide

---

## Phase 5: Performance Optimization

### Task 5.1: Implement Pre-computation Pipeline
- **Priority**: P1 (High)
- **File**: `scripts/precompute_heatmap.py`
- **Description**: Batch job to pre-calculate and cache snapshots
- **Dependencies**: Task 1.2, Task 2.1
- **Acceptance Criteria**:
  - [ ] Script to calculate snapshots for date range
  - [ ] Store results in `liquidation_snapshots` table
  - [ ] Incremental mode (only new data)
  - [ ] CLI arguments for symbol, date range

### Task 5.2: Add Caching Layer
- **Priority**: P2 (Medium)
- **File**: `src/liquidationheatmap/api/main.py`
- **Description**: Redis or in-memory cache for hot data
- **Acceptance Criteria**:
  - [ ] Cache recent heatmap data
  - [ ] TTL-based invalidation
  - [ ] Cache hit/miss metrics

---

## Phase 6: Testing & Validation

### Task 6.1: Unit Test Suite
- **Priority**: P0 (Critical)
- **Files**: `tests/unit/models/test_time_evolving_heatmap.py`
- **Acceptance Criteria**:
  - [ ] Test position creation logic
  - [ ] Test liquidation trigger for long/short
  - [ ] Test snapshot generation
  - [ ] Test edge cases (empty data, single candle)
  - [ ] >80% code coverage

### Task 6.2: Integration Test Suite
- **Priority**: P1 (High)
- **Files**: `tests/integration/test_heatmap_api.py`
- **Acceptance Criteria**:
  - [ ] Test full pipeline with real data subset
  - [ ] Test API endpoint response format
  - [ ] Test performance within SLA

### Task 6.3: Visual Validation
- **Priority**: P1 (High)
- **Description**: Manual and automated visual comparison
- **Acceptance Criteria**:
  - [ ] Compare output with Coinglass (qualitative)
  - [ ] Verify liquidations disappear after price cross
  - [ ] Screenshot-based regression test

---

## Task Dependencies Graph

```
Task 1.1 (Models)
    │
    ├──→ Task 1.2 (Calculator) ──→ Task 3.1 (API) ──→ Task 4.1 (Frontend Fetch)
    │         │                                              │
    │         └──→ Task 5.1 (Pre-compute)                    ├──→ Task 4.2 (Render)
    │                    │                                   │
    │                    └──→ Task 2.1 (DB Schema)           └──→ Task 4.3 (Indicators)
    │
    └──→ Task 1.3 (Price Crossing)
              │
              └──→ Task 1.4 (Side Inference)
```

---

## Priority Matrix

| Priority | Tasks | Description |
|----------|-------|-------------|
| P0 | 1.1, 1.2, 1.3, 3.1, 4.1, 4.2, 6.1 | Core functionality, must have |
| P1 | 1.4, 2.1, 5.1, 6.2, 6.3 | Important for production quality |
| P2 | 2.2, 3.2, 5.2 | Nice to have, can defer |
| P3 | 4.3 | Enhancement, future iteration |

---

## Definition of Done

For each task:
1. [ ] Code implemented and passing lint/type checks
2. [ ] Unit tests written and passing
3. [ ] Documentation updated (if public API)
4. [ ] Code reviewed (self or peer)
5. [ ] Integrated and tested on dev environment
6. [ ] No regressions in existing functionality
