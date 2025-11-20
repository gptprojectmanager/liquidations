# Feature Specification: Tiered Margin Enhancement

**Feature ID**: LIQHEAT-004
**Priority**: HIGH
**Status**: APPROVED
**Created**: 2025-11-20
**Branch**: feature/004-tiered-margin

## Executive Summary

Enhancement to liquidation price calculations that implements Binance's position size-dependent maintenance margin rates. This replaces the current flat margin rate with a tiered system where larger positions require higher maintenance margins, improving liquidation price accuracy from approximately 85% to 99% fidelity.

## Business Value

### Problem Statement
Current liquidation calculations use a flat 0.5% maintenance margin rate regardless of position size. In reality, Binance applies progressive margin requirements based on notional value - small positions require 0.5% while whale positions can require up to 5%. This discrepancy causes significant miscalculation of liquidation prices for large positions.

### Value Proposition
- **Accuracy Improvement**: Liquidation price fidelity increases from 85% to 99%
- **Whale Position Precision**: Correctly identifies risk levels for institutional traders
- **Exchange Compliance**: Matches actual Binance liquidation mechanics
- **Risk Management**: More accurate assessments for large position holders

### Success Metrics
- Liquidation price calculations match Binance formulas with 99% accuracy
- Whale positions ($5M+) show correct 5% margin requirement
- All tier transitions calculated correctly without gaps
- Zero calculation errors across all position sizes
- Backward compatibility maintained for existing features

## User Scenarios & Testing

### User Story 1 - Whale Position Accuracy (Priority: P1)

Institutional traders with positions over $1M need accurate liquidation prices that reflect actual exchange mechanics, as even 1% error can mean millions in miscalculated risk.

**Why this priority**: Large positions are most affected by incorrect margin calculations - a $5M position with wrong margin could show liquidation $50k off actual level.

**Independent Test**: Can be tested by calculating liquidation price for $5M position and comparing against Binance's official calculator.

**Acceptance Scenarios**:

1. **Given** a $5M long position at 10x leverage, **When** calculating liquidation price, **Then** system applies 5% maintenance margin rate correctly
2. **Given** a position crossing from $999k to $1.001M, **When** calculating margins, **Then** tier transition applies smoothly without jumps
3. **Given** multiple positions at different sizes, **When** calculating liquidations, **Then** each uses its appropriate tier rate

---

### User Story 2 - Retail Trader Transparency (Priority: P2)

Retail traders need to understand how position size affects their liquidation risk, especially when scaling up positions.

**Why this priority**: Educational value helps traders understand risk as they grow positions, preventing surprise liquidations.

**Independent Test**: Display margin tier information in UI and verify correct tier shown for various position sizes.

**Acceptance Scenarios**:

1. **Given** a $50k position, **When** viewing liquidation info, **Then** system shows 0.5% margin rate applied
2. **Given** user increases position from $200k to $300k, **When** margin updates, **Then** new tier (1% to 2.5%) is clearly indicated
3. **Given** any position size, **When** hovering over margin info, **Then** tier breakdown tooltip appears

---

### User Story 3 - API Consistency (Priority: P3)

API consumers need consistent liquidation calculations that match exchange standards for automated risk management systems.

**Why this priority**: Ensures external systems can rely on our calculations for automated trading decisions.

**Independent Test**: API returns same liquidation prices as Binance for identical positions across all tiers.

**Acceptance Scenarios**:

1. **Given** API request with position details, **When** calculating liquidation, **Then** response includes tier information
2. **Given** batch calculation request, **When** processing multiple positions, **Then** each applies correct tier independently

### Edge Cases

- What happens at exact tier boundaries (e.g., exactly $1,000,000)?
  - Upper tier rate applies (conservative approach for safety)
- How are cross-margin positions handled?
  - Each position calculated independently with its own tier
- What if Binance updates tier levels?
  - Tier tables stored in configuration for easy updates
- How are partial position closures handled?
  - Remaining position recalculated with new size tier

## Requirements

### Functional Requirements

- **FR-001**: System MUST implement Binance's official tier structure with rates from 0.5% to 5%
- **FR-002**: System MUST calculate maintenance margin based on position notional value
- **FR-003**: System MUST apply tier rates progressively without discontinuities
- **FR-004**: System MUST support all Binance perpetual contract symbols
- **FR-005**: System MUST update tier tables when exchange modifies them
- **FR-006**: Calculation MUST complete within existing performance budgets (<100ms)
- **FR-007**: System MUST provide tier information in calculation results
- **FR-008**: System MUST handle positions from $1 to $1 billion notional
- **FR-009**: API responses MUST include applied tier details
- **FR-010**: System MUST maintain backward compatibility with flat-rate option

### Key Entities

- **MarginTier**: Defines tier boundaries and rates (min_notional, max_notional, maint_margin_rate, maint_amount)
- **TierConfiguration**: Collection of tiers per symbol (symbol, tiers[], last_updated)
- **PositionMargin**: Calculated margin for position (notional_value, tier_applied, margin_required, liquidation_price)
- **TierTransition**: Handles position changes across tiers (old_tier, new_tier, margin_delta)

## Success Criteria

### Measurable Outcomes

- **SC-001**: Liquidation price accuracy improves from 85% to 99% fidelity against exchange
- **SC-002**: 100% of whale positions ($1M+) show correct tiered margin rates
- **SC-003**: Tier lookup and calculation adds less than 10ms to existing computation
- **SC-004**: Zero calculation errors in 10,000 test positions across all tiers
- **SC-005**: Tier configuration updates propagate within 5 minutes of exchange changes
- **SC-006**: 95% of users understand tier impact via UI indicators
- **SC-007**: API maintains sub-100ms response time with tier calculations

## Non-Functional Requirements

### Performance Requirements
- Tier lookup optimized with O(log n) binary search
- Margin calculation remains O(1) complexity
- Memory footprint under 1MB for tier tables
- Supports 1000 concurrent calculations

### Data Requirements
- Tier tables cached with 1-hour TTL
- Configuration stored in versioned format
- Historical tier changes tracked for backtesting
- Fallback to flat rate if tier data unavailable

### Maintenance Requirements
- Tier updates via configuration without code changes
- Automated validation against exchange documentation
- Alert on tier mismatch detection
- Monthly reconciliation with exchange specs

## Dependencies and Constraints

### Dependencies
- Existing liquidation calculation module operational
- Access to position size/notional value data
- Binance tier specification documentation
- Configuration management system

### Constraints
- Must match Binance's exact tier boundaries
- Cannot modify existing API contracts
- Must handle all perpetual contracts uniformly
- Performance cannot degrade beyond 10ms

## Assumptions
- Binance tier structure remains relatively stable
- Position sizes provided in USD notional terms
- Tier rates apply uniformly across all markets
- Linear interpolation acceptable between tiers
- Exchange notifications available for tier updates

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Tier data becomes stale | HIGH | LOW | Automated daily validation against exchange |
| Calculation complexity increases latency | MEDIUM | LOW | Pre-compute common scenarios, cache results |
| Tier boundary edge cases | LOW | MEDIUM | Comprehensive test suite with boundary values |
| Exchange changes tier structure | HIGH | LOW | Configuration-driven updates, version control |

## Test Scenarios

### Scenario 1: Small Position
**Given**: $10,000 position at 20x leverage
**When**: Calculating liquidation price
**Then**: 0.5% maintenance margin applied correctly

### Scenario 2: Tier Boundary Crossing
**Given**: Position increases from $990k to $1.1M
**When**: Recalculating margin
**Then**: Smoothly transitions from 2.5% to 5% tier

### Scenario 3: Maximum Position
**Given**: $50M position at 5x leverage
**When**: Calculating liquidation
**Then**: Maximum tier (5%) applied with correct formula

### Scenario 4: Rapid Size Changes
**Given**: Position scaled from $50k to $5M in steps
**When**: Each calculation performed
**Then**: Appropriate tier applied at each level

## Acceptance Criteria Summary

Feature is complete when:
1. All Binance margin tiers implemented correctly
2. Liquidation calculations match exchange with 99% accuracy
3. Performance impact less than 10ms per calculation
4. Tier information exposed in API responses
5. UI displays current tier and requirements
6. Configuration system supports tier updates
7. Full test coverage across all tiers and boundaries
8. Documentation updated with tier examples

## Out of Scope
- Custom tier structures for other exchanges
- Dynamic tier adjustment algorithms
- Position netting across accounts
- Tier optimization recommendations
- Historical tier analysis tools

## Future Enhancements
- Multi-exchange tier support
- Tier-based risk scoring
- Optimal position sizing calculator
- Tier arbitrage detection
- Custom tier configurations for private deployments
- Real-time tier update subscriptions

## Notes
This enhancement is critical for institutional users who need accurate liquidation prices for large positions. The implementation should prioritize accuracy over performance, though both must meet specified thresholds. Tier data should be treated as critical configuration requiring validation and version control.