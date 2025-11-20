# Feature Specification: Hybrid Real-Time Historical Model

**Feature ID**: LIQHEAT-002
**Priority**: HIGH
**Status**: APPROVED
**Created**: 2025-11-20
**Branch**: feature/002-hybrid-realtime-model

## Executive Summary

A liquidation prediction model that combines the stability of 30-day historical volume profiles with real-time market adjustments. This hybrid approach adapts to recent market conditions while maintaining baseline accuracy, providing traders with more responsive liquidation level predictions.

## Business Value

### Problem Statement
Current liquidation models use static historical data that doesn't adapt to sudden market changes. When open interest spikes 20% in 24 hours or funding rates shift dramatically, static models fail to capture where new positions are concentrated.

### Value Proposition
- **Adaptive Accuracy**: Captures recent position changes within seconds
- **Market Sentiment**: Incorporates funding rate for long/short bias estimation
- **Stability**: Maintains baseline accuracy even when real-time data fails
- **Performance**: Maintains sub-second query response times

### Success Metrics
- Query response time remains under 1 second (99th percentile)
- System adapts to 20%+ OI changes within 5 minutes
- Funding rate correlation exceeds 0.7 (statistical validation)
- Zero downtime when real-time data unavailable (graceful degradation)

## User Stories

### As a Day Trader
I want liquidation predictions that reflect recent market movements so that I can identify high-risk zones based on current conditions rather than week-old data.

**Acceptance Criteria:**
- See liquidation levels update when market conditions change significantly
- Get visual indication when predictions are using real-time adjustments
- Maintain view even if real-time data temporarily unavailable

### As a Risk Manager
I want to understand how recent position changes affect liquidation clusters so that I can adjust exposure based on current market dynamics.

**Acceptance Criteria:**
- View metadata showing what adjustments were applied
- See confidence indicators for real-time vs historical components
- Get alerts when major shifts detected (>10% OI change)

## Functional Requirements

### FR1: Baseline Historical Distribution
**Priority**: HIGH
System shall maintain a 30-day volume profile baseline that updates daily.

**Acceptance Criteria:**
- Baseline regenerates automatically every 24 hours
- Historical data covers minimum 30 days of trading
- Cache hit rate exceeds 95% for baseline queries
- Baseline remains available during regeneration

### FR2: Real-Time Signal Collection
**Priority**: HIGH
System shall collect current market signals for adjustment calculations.

**Acceptance Criteria:**
- Fetch current open interest value
- Retrieve 24-hour historical open interest
- Collect latest funding rate (8-hour period)
- Complete all fetches within 500ms (parallel execution)

### FR3: Dynamic Adjustment Logic
**Priority**: HIGH
System shall apply market-based adjustments to baseline distribution.

**Acceptance Criteria:**
- When OI changes >5%, adjust volume near current price (±5% range)
- When funding rate exceeds ±0.01%, adjust long/short ratio accordingly
- Adjustments scale proportionally (no cliff effects)
- Total volume remains conserved (sum unchanged)

### FR4: Graceful Degradation
**Priority**: MEDIUM
System shall continue functioning when real-time data unavailable.

**Acceptance Criteria:**
- If real-time fetch times out (>1s), use baseline only
- Log degradation events for monitoring
- Display indicator when using baseline-only mode
- Automatically retry real-time on next request

### FR5: Model Selection Interface
**Priority**: HIGH
Users shall select between baseline and hybrid models via interface.

**Acceptance Criteria:**
- Dropdown menu shows available models clearly
- Current model selection persists across sessions
- Model change takes effect immediately
- Visual feedback confirms model switch

## Non-Functional Requirements

### Performance Requirements
- **NFR1**: Query latency under 1 second for 99% of requests
- **NFR2**: Real-time signal fetches complete within 500ms
- **NFR3**: Baseline cache regeneration completes within 5 minutes
- **NFR4**: Support 100 concurrent model queries

### Reliability Requirements
- **NFR5**: 99.9% availability (allows 8.76 hours downtime/year)
- **NFR6**: Graceful degradation when external data unavailable
- **NFR7**: Automatic recovery from transient failures

### Scalability Requirements
- **NFR8**: Support multiple trading pairs simultaneously
- **NFR9**: Handle 10x traffic spikes without degradation

## Data Requirements

### Input Data Sources
1. **Historical Volume Profile** (30 days, cached daily)
2. **Current Open Interest** (real-time fetch)
3. **24-hour Historical OI** (real-time fetch)
4. **Latest Funding Rate** (8-hour period)
5. **Current Mark Price** (for adjustment zones)

### Output Data Format
- Price bucket levels with adjusted long/short volumes
- Metadata showing adjustments applied
- Confidence scores for each component
- Timestamp of last update

## User Interface Requirements

### Model Selection
- Clear dropdown with model names and descriptions
- "Hybrid Real-Time + Historical" option visible
- Indicator showing active adjustments
- Tooltip explaining model differences

### Visual Indicators
- Badge showing "Real-Time Active" when adjustments applied
- Color coding for adjustment intensity
- Timestamp of last real-time update
- Warning icon if degraded to baseline-only

## Dependencies and Constraints

### Dependencies
- Existing baseline Open Interest model must be operational
- External market data sources must be accessible
- Caching layer must be configured

### Constraints
- Cannot exceed 1-second total query time
- Must maintain backward compatibility with existing model
- Real-time fetches limited by rate limits
- Must handle market data gaps gracefully

## Assumptions
- Market data providers maintain >99% uptime
- 30-day historical window provides sufficient baseline
- Funding rate correlates with position sentiment
- Position concentration near current price during high volatility

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Real-time data provider outage | HIGH | LOW | Graceful degradation to baseline |
| Rate limiting on API calls | MEDIUM | MEDIUM | Implement caching and throttling |
| Incorrect adjustment calculations | HIGH | LOW | Extensive validation testing |
| Performance degradation | MEDIUM | LOW | Circuit breakers and monitoring |

## Success Criteria

### Quantitative Metrics
1. Query response time: <1 second (99th percentile)
2. Funding rate correlation: >0.7 (statistical significance)
3. OI conservation error: <1% (total volume preserved)
4. Cache hit rate: >95% for baseline queries
5. Adaptation time: <5 minutes for 20% OI changes

### Qualitative Metrics
1. User feedback indicates improved accuracy during volatility
2. Risk managers report better position insights
3. System maintains stability during market stress
4. Clear visual feedback on model status

## Test Scenarios

### Scenario 1: Normal Market Conditions
**Given**: Market with typical 2-3% daily OI changes
**When**: User queries hybrid model
**Then**: Results show minor adjustments near current price

### Scenario 2: High Volatility Event
**Given**: OI increases 25% in 2 hours
**When**: User queries hybrid model
**Then**: Significant volume concentration appears near current price

### Scenario 3: Real-Time Data Failure
**Given**: External API timeout occurs
**When**: User queries hybrid model
**Then**: System returns baseline with degradation indicator

### Scenario 4: Funding Rate Spike
**Given**: Funding rate reaches 0.05% (extreme)
**When**: User queries hybrid model
**Then**: Long/short ratio shifts significantly toward shorts

## Acceptance Criteria Summary

Feature is complete when:
1. Hybrid model available in dropdown menu
2. Real-time adjustments applied successfully
3. Performance remains under 1 second
4. Graceful degradation works correctly
5. Validation tests show >0.7 funding correlation
6. Visual indicators show model status
7. Documentation updated for users

## Out of Scope
- Machine learning predictions
- Options market integration
- Cross-exchange arbitrage signals
- Automated trading signals
- Historical backtesting interface

## Future Enhancements
- Additional real-time signals (volume, volatility)
- Multi-timeframe adjustments
- Cross-pair correlation analysis
- Websocket real-time updates
- Custom adjustment parameters

## Notes
This specification focuses on business requirements without implementation details. The hybrid approach balances real-time responsiveness with baseline stability, providing practical value for traders while maintaining system reliability.