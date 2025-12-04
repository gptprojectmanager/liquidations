# Feature Specification: Funding Rate Bias Adjustment

**Feature ID**: LIQHEAT-005
**Priority**: MEDIUM
**Status**: APPROVED
**Created**: 2025-11-20
**Branch**: 005-funding-rate-bias

## Executive Summary

A market sentiment adjustment module that uses funding rate as a proxy to estimate long/short position ratios. This replaces the naive 50/50 assumption with a dynamic distribution that reflects actual market sentiment - positive funding indicates more longs, negative funding indicates more shorts.

## Business Value

### Problem Statement
Current models assume equal distribution of long and short positions (50/50 split), which rarely reflects reality. During bull markets, longs can dominate 70/30 or more, while bear markets see the opposite. This incorrect assumption leads to misallocated liquidation volumes and unrealistic risk assessments.

### Value Proposition
- **Market-Adaptive**: Automatically adjusts to bull/bear market conditions
- **Data-Driven**: Uses real funding rate data instead of assumptions
- **Simple Integration**: Can enhance any existing model as adjustment layer
- **Improved Accuracy**: Better reflects actual market positioning

### Success Metrics
- Long/short ratio correlates with funding rate at >0.7 coefficient
- Distribution adjustments complete within 50ms
- Zero errors in funding rate data retrieval
- Model predictions improve by 15-20% in backtests
- Seamless integration with existing models

## User Scenarios & Testing

### User Story 1 - Bull Market Positioning (Priority: P1)

During strong bull markets when funding is consistently positive, traders need liquidation models that reflect the reality that 70%+ of positions are long, not the naive 50/50 assumption.

**Why this priority**: Core functionality - without sentiment adjustment, models show unrealistic short liquidations during obvious bull markets.

**Independent Test**: During period with +0.05% funding, verify long ratio shows 65-70% vs baseline 50%.

**Acceptance Scenarios**:

1. **Given** funding rate of +0.03% (strongly positive), **When** calculating position distribution, **Then** long ratio adjusts to approximately 65%
2. **Given** funding rate of -0.02% (negative), **When** calculating distribution, **Then** short ratio increases to approximately 60%
3. **Given** funding rate of 0.0001% (neutral), **When** calculating distribution, **Then** ratio remains near 50/50

---

### User Story 2 - Extreme Sentiment Detection (Priority: P2)

Risk managers need to identify when extreme funding rates indicate dangerous one-sided positioning that increases systemic liquidation risk.

**Why this priority**: Helps identify market extremes where cascading liquidations are more likely.

**Independent Test**: Alert triggers when funding exceeds ±0.05% threshold indicating extreme sentiment.

**Acceptance Scenarios**:

1. **Given** funding rate exceeds +0.05%, **When** calculating positions, **Then** system flags "extreme long bias" warning
2. **Given** funding rate below -0.05%, **When** calculating positions, **Then** system flags "extreme short bias" warning
3. **Given** rapid funding change (>0.03% in 8 hours), **When** detected, **Then** "sentiment shift" alert generated

---

### User Story 3 - Historical Correlation Validation (Priority: P3)

Analysts need to validate that funding-based adjustments actually improve model accuracy through historical correlation analysis.

**Why this priority**: Provides confidence metrics and validation for the adjustment methodology.

**Independent Test**: Run 30-day correlation test between predicted ratios and subsequent liquidation events.

**Acceptance Scenarios**:

1. **Given** 30 days of historical data, **When** running correlation test, **Then** coefficient exceeds 0.7
2. **Given** backtesting period, **When** comparing with/without adjustment, **Then** adjusted model shows 15%+ improvement
3. **Given** validation report request, **When** generated, **Then** includes correlation plots and confidence intervals

### Edge Cases

- What happens when funding rate data is unavailable?
  - Fallback to 50/50 neutral distribution with warning flag
- How to handle funding rate spikes/anomalies?
  - Apply 3-sigma outlier detection, cap at ±0.1%
- What about perpetual contracts without funding?
  - Skip adjustment, use baseline distribution
- How are multi-period funding rates handled?
  - Use weighted average of last 3 periods (24 hours)

## Requirements

### Functional Requirements

- **FR-001**: System MUST fetch current funding rate from exchange API
- **FR-002**: System MUST convert funding rate to long/short bias factor using calibrated formula
- **FR-003**: Adjustment MUST preserve total open interest (sum remains constant)
- **FR-004**: System MUST handle positive, negative, and neutral funding rates
- **FR-005**: Conversion formula MUST use smooth, continuous function (no jumps)
- **FR-006**: System MUST cache funding rates with 5-minute TTL
- **FR-007**: Adjustment MUST complete within 50ms of funding fetch
- **FR-008**: System MUST provide confidence score for adjustment
- **FR-009**: API responses MUST include funding rate and bias applied
- **FR-010**: System MUST support manual override of bias factor

### Key Entities

- **FundingRate**: Current and historical funding values (rate, timestamp, symbol)
- **BiasAdjustment**: Calculated long/short adjustment (funding_input, long_ratio, short_ratio, confidence)
- **SentimentIndicator**: Market sentiment classification (bullish, bearish, neutral, extreme)
- **AdjustmentConfig**: Configuration parameters (sensitivity, caps, thresholds)

## Success Criteria

### Measurable Outcomes

- **SC-001**: Funding rate correlation with long/short ratio exceeds 0.7
- **SC-002**: Adjustment calculation completes in under 50ms
- **SC-003**: 99.9% availability for funding rate data retrieval
- **SC-004**: Model accuracy improves by 15-20% in backtests
- **SC-005**: Zero adjustment errors over 10,000 calculations
- **SC-006**: Extreme sentiment alerts have <10% false positive rate
- **SC-007**: 90% of users understand bias indicator in UI

## Non-Functional Requirements

### Performance Requirements
- Funding rate fetch cached for 5 minutes minimum
- Bias calculation uses O(1) formula
- Supports 1000 concurrent adjustments
- Memory overhead under 10MB

### Data Requirements
- Historical funding rates retained for 90 days
- 8-hour funding periods aggregated correctly
- Missing data handled with interpolation
- Outliers detected and capped automatically

### Integration Requirements
- Works as optional enhancement to any model
- Clean API for bias factor retrieval
- Configurable sensitivity parameters (range: 10.0 to 100.0)
- Enable/disable toggle per model

## Development Process Requirements

### Test-Driven Development (TDD)
Per project constitution, all implementation MUST follow TDD principles:
- **Red Phase**: Write failing tests first (T031-T033, T045-T046, T058-T059)
- **Green Phase**: Implement minimal code to pass tests
- **Refactor Phase**: Clean up while maintaining green tests
- **Coverage Target**: 95% for critical paths (bias calculation, OI conservation)
- **Property Testing**: Use hypothesis for mathematical invariants

### Mathematical Validation
- Tanh formula continuity proven mathematically
- OI conservation validated: long_ratio + short_ratio = 1.0 exactly
- Boundary conditions tested at funding rate extremes (±0.10%)
- No discontinuities or jumps in adjustment curve

**Core Formula Proof**:
```
long_ratio = 0.5 + (tanh(funding_rate × scale_factor) × max_adjustment)
short_ratio = 1.0 - long_ratio

Proof of continuity:
- tanh(x) is continuous for all x ∈ ℝ
- Linear scaling preserves continuity
- Addition/subtraction preserves continuity
∴ long_ratio is continuous for all funding_rate values

Proof of boundedness:
- tanh(x) ∈ [-1, 1] for all x
- With max_adjustment = 0.20:
  long_ratio ∈ [0.5 - 0.20, 0.5 + 0.20] = [0.30, 0.70]
∴ Ratios bounded to [30%, 70%] range
```

## Dependencies and Constraints

### Dependencies
- Access to exchange funding rate API
- Existing position distribution models
- Historical funding rate data
- Mathematical transformation functions

### Constraints
- Funding rate updates every 8 hours only
- API rate limits on funding queries
- Must maintain total OI conservation
- Cannot exceed ±20% adjustment from baseline (long_ratio ∈ [0.30, 0.70])

## Assumptions
- Funding rate correlates with actual positioning
- Market makers don't significantly distort funding
- 8-hour funding periods are representative
- Tanh function appropriate for conversion
- Extreme rates (>0.1%) are anomalies

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Funding manipulation by whales | HIGH | LOW | Cap maximum adjustment at ±20% |
| API downtime blocks adjustments | MEDIUM | LOW | Cache last known values for 24h |
| Incorrect bias during transitions | MEDIUM | MEDIUM | Use moving average smoothing |
| Overreaction to temporary spikes | LOW | HIGH | Apply outlier detection |

## Test Scenarios

### Scenario 1: Typical Bull Market
**Given**: Funding rate +0.02% for 3 days
**When**: Calculating position distribution
**Then**: Long ratio stabilizes around 62%

### Scenario 2: Funding Reversal
**Given**: Funding changes from +0.03% to -0.03%
**When**: Next adjustment calculated
**Then**: Smooth transition from long to short bias

### Scenario 3: Extreme Funding Event
**Given**: Funding spikes to +0.15%
**When**: Processing adjustment
**Then**: Capped at maximum, alert generated

### Scenario 4: Missing Data Handling
**Given**: Funding API returns error
**When**: Adjustment requested
**Then**: Uses cached value with degraded confidence

## Acceptance Criteria Summary

Feature is complete when:
1. Funding rate fetching operational and cached
2. Bias conversion formula implemented and tested
3. Long/short ratios adjust smoothly with funding
4. Total OI conservation verified
5. Performance under 50ms confirmed
6. UI shows funding rate and applied bias
7. Historical correlation exceeds 0.7
8. Integration with existing models tested

## Out of Scope
- Complex multi-factor sentiment models
- Cross-exchange funding arbitrage
- Predictive funding rate forecasting
- Automated bias optimization
- Real-time funding streaming

## Future Enhancements
- Multi-factor sentiment (add volume, volatility)
- Machine learning bias optimization
- Cross-pair funding correlation
- Predictive sentiment indicators
- Custom bias curves per market condition
- WebSocket funding rate updates

## Notes
This module serves as a simple but effective enhancement to any position distribution model. The funding rate provides a reliable, exchange-provided signal of market sentiment that significantly improves upon naive 50/50 assumptions. Implementation should prioritize simplicity and reliability over complex optimizations.