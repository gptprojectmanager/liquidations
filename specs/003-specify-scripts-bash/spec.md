# Feature Specification: Liquidation Model Validation Suite

**Feature ID**: LIQHEAT-003
**Priority**: HIGH
**Status**: APPROVED
**Created**: 2025-11-20
**Branch**: feature/003-validation-suite

## Executive Summary

A comprehensive validation framework that tests liquidation model accuracy using proxy metrics when ground truth data is unavailable. The suite uses funding rate correlation, open interest conservation laws, and directional positioning tests to validate model predictions, providing automated monitoring with graded reports for continuous quality assurance.

## Business Value

### Problem Statement
Liquidation models cannot be validated against actual position data (exchange privacy), making it impossible to directly measure accuracy. Without validation, model drift goes undetected, potentially leading to misleading predictions that harm trading decisions.

### Value Proposition
- **Confidence Metrics**: Quantifiable accuracy scores using proxy measurements
- **Drift Detection**: Automatic identification of model degradation over time
- **Quality Assurance**: Continuous monitoring with graded reports (A/B/C/F)
- **Statistical Rigor**: Multiple validation methods triangulate accuracy

### Success Metrics
- Validation suite runs automatically weekly without manual intervention
- Reports generated in under 5 minutes for 30-day analysis
- Funding correlation test achieves >0.7 correlation coefficient
- OI conservation error remains below 1%
- Zero false positives in drift detection over 3 months

## User Scenarios & Testing

### User Story 1 - Automated Weekly Validation (Priority: P1)

System administrators need automated validation that runs weekly and generates reports without manual intervention, detecting model drift before it impacts users.

**Why this priority**: Core functionality - without automated validation, the entire suite loses its value for continuous monitoring.

**Independent Test**: Can be fully tested by triggering scheduled run and verifying report generation within 5 minutes.

**Acceptance Scenarios**:

1. **Given** weekly schedule trigger at Sunday 2 AM UTC, **When** validation suite executes, **Then** complete report is generated within 5 minutes
2. **Given** validation completes successfully, **When** report generates, **Then** results are stored and accessible via dashboard
3. **Given** test failures occur, **When** grade drops to C or F, **Then** alerts are sent to configured recipients

---

### User Story 2 - Manual Validation Trigger (Priority: P2)

Model developers need to run validation on-demand to test improvements and catch regressions before deployment.

**Why this priority**: Critical for development workflow but not required for basic monitoring functionality.

**Independent Test**: Can be tested by manually triggering validation and comparing results across model versions.

**Acceptance Scenarios**:

1. **Given** developer has new model version, **When** manual validation triggered, **Then** results available within 5 minutes without affecting scheduled runs
2. **Given** multiple models exist, **When** validation runs, **Then** each model receives separate validation report
3. **Given** validation in progress, **When** another trigger attempted, **Then** request is queued to prevent resource conflicts

---

### User Story 3 - Historical Trend Analysis (Priority: P3)

Risk managers need to view validation trends over time to understand model reliability patterns.

**Why this priority**: Valuable for long-term analysis but system functions without it.

**Independent Test**: Can be tested by viewing dashboard with 90+ days of historical data and trend charts.

**Acceptance Scenarios**:

1. **Given** 90 days of validation history, **When** accessing dashboard, **Then** trend charts display for each metric
2. **Given** model degradation over time, **When** viewing trends, **Then** declining performance clearly visible
3. **Given** multiple validation runs, **When** comparing results, **Then** can select any two runs for detailed comparison

### Edge Cases

- What happens when 50% of historical data is missing?
  - System proceeds with available data and notes gaps in report
- How does system handle when funding rate API is down?
  - Marks funding correlation test as "INCOMPLETE" and adjusts overall grade
- What if OI conservation fails by 10%?
  - Immediate alert sent, grade set to F, detailed diagnostics in report
- How are simultaneous validation requests handled?
  - Queued with FIFO processing, maximum queue size of 10

## Requirements

### Functional Requirements

- **FR-001**: System MUST calculate Pearson correlation between estimated long/short ratios and funding rates over 30-day window
- **FR-002**: System MUST verify total estimated positions equal actual open interest with <1% error tolerance
- **FR-003**: System MUST confirm all long liquidations below and short liquidations above current price
- **FR-004**: System MUST generate weighted grades (A: 90-100%, B: 80-89%, C: 70-79%, F: <70%)
- **FR-005**: System MUST execute validation automatically every Sunday at 2 AM UTC
- **FR-006**: System MUST support manual validation triggers without affecting scheduled runs
- **FR-007**: System MUST retain validation results for minimum 90 days
- **FR-008**: System MUST send alerts when overall grade drops to C or F
- **FR-009**: System MUST export reports in both JSON and human-readable formats
- **FR-010**: System MUST complete full validation suite in under 5 minutes

### Key Entities

- **ValidationRun**: Represents a single validation execution (timestamp, model, status, duration)
- **ValidationTest**: Individual test within a run (type, result, score, diagnostics)
- **ValidationReport**: Aggregated results with grade (tests, overall_grade, metadata, recommendations)
- **AlertConfiguration**: Notification settings (thresholds, channels, recipients, suppression_rules)
- **HistoricalTrend**: Time-series of validation metrics (metric_name, values, timestamps)

## Success Criteria

### Measurable Outcomes

- **SC-001**: Full validation suite completes in under 5 minutes for 30-day data analysis
- **SC-002**: Weekly scheduled runs achieve 99.9% reliability (less than 1 missed run per year)
- **SC-003**: Funding correlation test produces statistically significant results (p-value < 0.05) in 90% of runs
- **SC-004**: System correctly identifies model degradation within 2 weeks of occurrence
- **SC-005**: Alert false positive rate remains below 5% over 3-month period
- **SC-006**: Dashboard loads validation history for 90 days in under 3 seconds
- **SC-007**: 95% of manual validation triggers complete without queuing delays

## Non-Functional Requirements

### Performance Requirements
- Report generation completes in under 10 seconds
- Dashboard queries return in under 3 seconds
- Parallel test execution reduces runtime by 60%
- Memory usage stays below 2GB during validation

### Reliability Requirements
- Automatic retry with exponential backoff for transient failures
- Graceful degradation when data sources unavailable
- Data consistency maintained across concurrent runs
- Rollback capability for failed partial validations

### Security Requirements
- Validation results accessible only to authorized users
- Sensitive configuration encrypted at rest
- API endpoints require authentication
- Audit log for all validation triggers and modifications

## Dependencies and Constraints

### Dependencies
- Liquidation models must be operational and queryable
- Historical market data available for 30+ day window
- Binance API access for funding rates and OI data
- PostgreSQL/DuckDB for report storage and querying

### Constraints
- Cannot access actual trader position data (privacy)
- Statistical tests assume sufficient data (minimum 30 days)
- Rate limits on external API calls (1200 req/min)
- Validation cannot run during market maintenance windows

## Assumptions
- Funding rate serves as reliable proxy for market sentiment
- OI conservation validates calculation correctness
- 30-day window provides statistically significant sample
- Normal distribution applies to most metrics
- Model drift occurs gradually over weeks, not hours

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Proxy metrics don't reflect true accuracy | HIGH | MEDIUM | Use multiple independent tests to triangulate |
| Data gaps invalidate statistical tests | MEDIUM | MEDIUM | Implement data quality checks and gap handling |
| Alert fatigue from false positives | LOW | HIGH | Tune thresholds based on historical patterns |
| Resource contention during validation | LOW | LOW | Schedule during off-peak hours (2-5 AM UTC) |
| API rate limits hit during testing | MEDIUM | LOW | Implement request throttling and caching |

## Test Scenarios

### Scenario 1: Perfect Model Performance
**Given**: Model with 100% directional accuracy and 0.9 funding correlation
**When**: Validation suite runs
**Then**: Grade A assigned with all tests passing

### Scenario 2: Degraded Model Detection
**Given**: Model accuracy decreases from 95% to 70% over 2 weeks
**When**: Weekly validations run
**Then**: Grade changes from A to C and alert is triggered

### Scenario 3: Incomplete Data Handling
**Given**: 6-hour gap in funding rate data
**When**: Validation runs
**Then**: Tests complete with data gap notation, grade adjusted proportionally

### Scenario 4: Concurrent Validation Requests
**Given**: 3 manual triggers while scheduled run in progress
**When**: Requests are queued
**Then**: Each completes in order without data corruption

## Acceptance Criteria Summary

Feature is complete when:
1. All three core validation tests operational (funding, OI, directional)
2. Weekly automated scheduling working reliably
3. Grading system produces A/B/C/F scores correctly
4. Alert system triggers on C/F grades
5. Dashboard displays current and historical validation status
6. 90+ days of results retained and queryable
7. Manual trigger functionality tested and documented
8. Performance meets <5 minute execution target

## Out of Scope
- Real-time continuous validation (only batch)
- Machine learning anomaly detection
- Cross-exchange validation comparison
- Custom metric development by users
- Integration with CI/CD pipelines
- Backtesting framework integration

## Future Enhancements
- Additional statistical tests (Sharpe ratio, MAE, RMSE)
- Real-time validation monitoring via WebSocket
- ML-based anomaly detection for subtle drift
- Cross-model comparison framework
- Custom metric plugin system
- A/B testing integration for model comparison
- Validation result API for external consumers

## Notes
This validation suite addresses the fundamental challenge of validating predictions without ground truth. By combining multiple proxy metrics and statistical tests, we create a robust framework that provides confidence in model accuracy while automatically detecting degradation over time. The grading system makes results accessible to non-technical stakeholders while detailed diagnostics support developer debugging.