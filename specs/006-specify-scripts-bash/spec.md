# Feature Specification: Order Flow Imbalance (OFI) Distribution

**Feature ID**: LIQHEAT-006
**Priority**: LOW
**Status**: DEFERRED
**Created**: 2025-11-20
**Branch**: feature/006-ofi-distribution

## Executive Summary

An advanced liquidation distribution model that uses bid-ask order flow imbalance (OFI) to dynamically adjust position distribution assumptions. By analyzing the delta between bid and ask volumes over time windows, the model estimates directional bias beyond simple funding rate correlations. However, requires 10x more data processing and provides only marginal accuracy improvements over simpler approaches.

## Business Value

### Problem Statement
Current models use funding rate as the sole market sentiment indicator. While funding provides an 8-hour average sentiment, it misses intraday microstructure dynamics. Order flow imbalance captures real-time supply/demand pressure but requires processing massive tick-by-tick trade data, making it resource-intensive for marginal gains.

### Value Proposition
- **Microstructure Insight**: Captures sub-minute sentiment shifts invisible to funding
- **Leading Indicator**: OFI often leads price movements by seconds to minutes
- **Institutional Behavior**: Detects large player accumulation/distribution patterns
- **Academic Rigor**: Based on proven market microstructure research

### Why DEFERRED
- **10x Data Requirements**: Need tick-by-tick trades (100GB+ daily vs 10GB for OHLC)
- **Marginal Improvement**: Only 3-5% accuracy gain over funding rate model
- **Complexity Cost**: Requires real-time streaming infrastructure
- **Storage Explosion**: 30-day history would require 3TB+ storage
- **Alternative Available**: Funding rate model provides 80% of benefit at 10% cost

### Success Metrics (If Implemented)
- OFI calculation latency under 100ms per update
- Storage optimized to under 2TB for 30-day window
- Correlation with subsequent price movements >0.6
- Directional accuracy improvement of 5% over baseline
- Real-time streaming without data loss

## User Scenarios & Testing

### User Story 1 - Institutional Flow Detection (Priority: P1)

Professional traders need to identify when large institutions are building or unwinding positions through order flow analysis, as this precedes major price movements.

**Why this priority**: Core value proposition - detecting smart money flow before it impacts price.

**Independent Test**: During known institutional trading hours, OFI should show sustained directional bias preceding price moves.

**Acceptance Scenarios**:

1. **Given** sustained positive OFI (bid > ask) for 5 minutes, **When** analyzing subsequent price, **Then** upward movement occurs within 15 minutes in 70% of cases
2. **Given** OFI spike >3 standard deviations, **When** detected, **Then** alert generated for abnormal flow
3. **Given** OFI divergence from price (price up, OFI negative), **When** identified, **Then** reversal warning issued

---

### User Story 2 - Microstructure Liquidation Zones (Priority: P2)

Algorithmic traders need sub-minute granularity on liquidation clustering to place orders between major levels identified by coarser models.

**Why this priority**: Enables precise order placement for algorithmic execution strategies.

**Independent Test**: OFI-adjusted zones should show 20% tighter spreads than funding-only model.

**Acceptance Scenarios**:

1. **Given** high-frequency OFI data, **When** calculating liquidation clusters, **Then** identifies 2-3x more granular levels
2. **Given** rapid OFI reversal, **When** detected within 30 seconds, **Then** liquidation zones dynamically adjust
3. **Given** OFI-based zones, **When** backtested, **Then** show higher hit rate than static levels

---

### User Story 3 - Flow Toxicity Measurement (Priority: P3)

Risk managers need to measure "flow toxicity" - the probability that current order flow represents informed trading that will move against market makers.

**Why this priority**: Advanced risk metric for professional market making operations.

**Independent Test**: High toxicity scores should correlate with subsequent volatility spikes.

**Acceptance Scenarios**:

1. **Given** calculated VPIN (Volume-synchronized Probability of Informed Trading), **When** exceeds threshold, **Then** toxicity alert triggered
2. **Given** historical toxicity scores, **When** correlated with losses, **Then** shows >0.7 correlation
3. **Given** real-time toxicity monitoring, **When** spike detected, **Then** risk reduction recommended

### Edge Cases

- What happens during exchange maintenance when trade flow stops?
  - Gracefully degrade to funding-only model with quality indicator
- How to handle spoofing/manipulation in order flow?
  - Apply volume-weighted filters, ignore micro-orders (<$1000)
- What about cross-exchange arbitrage distorting OFI?
  - Focus on single exchange or implement cross-exchange normalization
- How to handle tick data gaps or corruption?
  - Interpolation for <1min gaps, fallback mode for larger gaps

## Requirements

### Functional Requirements

- **FR-001**: System MUST ingest tick-by-tick trade data with microsecond timestamps
- **FR-002**: System MUST calculate bid/ask volume imbalance over configurable windows (1s to 5min)
- **FR-003**: System MUST apply exponential decay weighting to recent vs older trades
- **FR-004**: System MUST normalize OFI by total volume to enable cross-period comparison
- **FR-005**: System MUST detect and filter wash trading/spoofing patterns
- **FR-006**: System MUST store rolling 24-hour tick data in memory for fast access
- **FR-007**: Calculation MUST complete within 100ms of new tick arrival
- **FR-008**: System MUST handle 10,000+ ticks/second during peak volatility
- **FR-009**: System MUST provide confidence scores based on data quality
- **FR-010**: System MUST support graceful degradation when tick data unavailable

### Key Entities

- **TickTrade**: Individual trade (price, size, side, timestamp_us, trade_id)
- **OFIWindow**: Calculated imbalance (window_start, window_end, bid_volume, ask_volume, imbalance, normalized_ofi)
- **FlowToxicity**: VPIN and related metrics (toxicity_score, bucket_size, sample_size, confidence)
- **MicrostructureZone**: Granular liquidation levels (price_level, ofi_adjusted_density, confidence_band)

## Success Criteria

### Measurable Outcomes

- **SC-001**: OFI calculation latency remains under 100ms for 99.9% of updates
- **SC-002**: System processes 10,000 ticks/second without data loss
- **SC-003**: Storage optimized to under 2TB for complete 30-day tick history
- **SC-004**: OFI correlation with 1-minute future returns exceeds 0.6
- **SC-005**: Liquidation zone predictions improve by 5% over funding-only model
- **SC-006**: Flow toxicity alerts have <20% false positive rate
- **SC-007**: Real-time streaming maintains <1 second end-to-end latency

## Non-Functional Requirements

### Performance Requirements
- Sub-100ms tick-to-calculation latency
- Support 10,000 ticks/second sustained, 50,000 peak
- In-memory storage for 24-hour rolling window
- Columnar storage for historical analysis (Parquet/Arrow)

### Data Requirements
- Tick data retention for 30 days minimum
- Nanosecond timestamp precision
- Lossless compression for archival (ZSTD)
- Real-time replication for redundancy

### Infrastructure Requirements
- Dedicated tick data ingestion pipeline
- High-memory servers (256GB+ RAM)
- NVMe SSD storage array (10TB+)
- 10Gbps network connectivity

## Dependencies and Constraints

### Dependencies
- WebSocket feed for real-time ticks
- Historical tick data access (3TB+)
- High-performance compute infrastructure
- Columnar database (DuckDB/ClickHouse)

### Constraints
- Exchange rate limits on tick data requests
- Storage costs for massive tick history
- Network bandwidth for streaming
- Regulatory requirements for data retention

## Assumptions
- Tick data accurately represents all trades
- No significant latency in data feed
- Bid/ask classification algorithm 95%+ accurate
- Market microstructure patterns remain stable
- Exchange doesn't throttle high-frequency connections

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Tick data feed interruption | HIGH | MEDIUM | Multiple redundant data sources, fallback to funding |
| Storage costs exceed budget | HIGH | HIGH | Implement aggressive data pruning, sampling strategies |
| Computational requirements spike | MEDIUM | MEDIUM | Auto-scaling infrastructure, circuit breakers |
| Model overfits to noise | HIGH | HIGH | Robust statistical filters, out-of-sample validation |
| Exchange API changes | MEDIUM | LOW | Abstraction layer, versioned API clients |

## Test Scenarios

### Scenario 1: Normal Trading Conditions
**Given**: Steady tick flow at 1,000 ticks/second
**When**: Calculating OFI over 1-minute windows
**Then**: Results available within 100ms, memory usage stable

### Scenario 2: Flash Crash Event
**Given**: Tick rate spikes to 50,000/second
**When**: System processes extreme volatility
**Then**: Gracefully handles load, may sample ticks, alerts operators

### Scenario 3: Data Feed Outage
**Given**: Primary tick feed disconnects for 5 minutes
**When**: Fallback activated
**Then**: Switches to funding-only model, marks confidence as degraded

### Scenario 4: Order Book Spoofing
**Given**: Detected wash trading pattern in ticks
**When**: Filtering applied
**Then**: Suspicious trades excluded from OFI calculation

## Acceptance Criteria Summary

Feature is complete when:
1. Tick ingestion pipeline operational at 10k ticks/second
2. OFI calculation implemented with <100ms latency
3. 30-day rolling window storage optimized under 2TB
4. VPIN flow toxicity scoring functional
5. Microstructure zones generated at 10-second intervals
6. Fallback to funding model tested
7. Performance benchmarks achieved across all metrics
8. Real-time monitoring dashboard operational

## Out of Scope
- Cross-exchange OFI aggregation
- Options flow integration
- Level 3 order book reconstruction
- Machine learning OFI prediction
- Custom exchange protocol implementations
- Regulatory reporting features

## Future Enhancements
- Multi-exchange OFI correlation
- ML-based tick classification
- Hardware acceleration (FPGA/GPU)
- Options flow toxicity
- Cross-asset OFI analysis
- Predictive OFI modeling

## Notes
This feature represents the cutting edge of market microstructure analysis but comes with significant infrastructure costs. The 10x increase in data requirements (tick vs OHLC) and marginal accuracy improvement (3-5%) make this a poor ROI for most deployments. Teams should exhaust simpler approaches (funding rate, volume profiles) before considering OFI implementation. If pursued, recommend starting with sampled tick data (every 10th tick) to validate value before full implementation.

## Recommendation: DEFER
Given the massive infrastructure requirements and marginal benefit, this feature should remain DEFERRED until:
1. Funding rate model proven insufficient for use case
2. Infrastructure costs decrease significantly
3. Clear evidence of 10%+ accuracy improvement potential
4. Dedicated team available for maintenance

The funding rate bias adjustment (Feature 005) provides 80% of the sentiment analysis value at 10% of the cost.