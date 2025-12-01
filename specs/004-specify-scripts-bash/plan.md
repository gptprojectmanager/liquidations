# Implementation Plan: Tiered Margin Enhancement

**Branch**: `feature/004-tiered-margin` | **Date**: 2025-11-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-specify-scripts-bash/spec.md`

## Summary

Enhancement to liquidation price calculations implementing Binance's position size-dependent maintenance margin rates with **continuous mathematical functions** to eliminate discontinuities. Replaces flat 0.5% margin with tiered system (0.5% to 5%) using Maintenance Amount offsets to ensure smooth transitions at tier boundaries.

## Technical Context

**Language/Version**: Python 3.11+ (for decimal precision support)
**Primary Dependencies**:
- `decimal` (built-in for 128-bit precision)
- `numpy` (for vectorized calculations)
- `duckdb` (for tier configuration storage)
- `pydantic` (for data validation)

**Storage**: DuckDB for tier configurations and caching
**Testing**: pytest with hypothesis for property-based testing
**Target Platform**: Linux server (containerized)
**Project Type**: Single library module integrated into existing system
**Performance Goals**: <10ms calculation time for single position, <100ms for 10k batch
**Constraints**: Must match Binance with 99% accuracy, zero discontinuities
**Scale/Scope**: Handle positions from $1 to $1B notional, 5 tiers initially

## Mathematical Foundation (CRITICAL - Addresses Gemini Findings)

### Continuous Margin Function

Based on Gemini's analysis, we MUST implement Maintenance Amount offsets to ensure continuity:

```python
# Tier structure with Maintenance Amounts
TIERS = [
    # (min_notional, max_notional, rate, maintenance_amount)
    (0,        50_000,     0.005, 0),       # Tier 1
    (50_000,   250_000,    0.010, 250),     # Tier 2
    (250_000,  1_000_000,  0.025, 4_000),   # Tier 3
    (1_000_000, 10_000_000, 0.050, 29_000), # Tier 4
    (10_000_000, float('inf'), 0.050, 29_000), # Tier 5
]

def calculate_margin(notional: Decimal, tier: Tuple) -> Decimal:
    """
    Continuous margin calculation with Maintenance Amount
    Formula: M_total = notional * rate - maintenance_amount
    """
    _, _, rate, maintenance_amount = tier
    return notional * Decimal(str(rate)) - Decimal(str(maintenance_amount))
```

### Proof of Continuity

At boundary b = $50,000:
- From left: M = 50,000 × 0.005 - 0 = $250
- From right: M = 50,000 × 0.010 - 250 = $250
- ✅ Continuous!

## Constitution Check

*No constitution file exists - using project principles from CLAUDE.md*

**KISS Principle**: ✅ Using simple lookup table, no complex algorithms
**YAGNI Principle**: ✅ Only implementing Binance tiers, not generic system
**Code Reuse**: ✅ Leveraging existing liquidation calculation module
**TDD Approach**: ✅ Tests will be written first (see Phase 0 research)

## Project Structure

### Documentation (this feature)

```
specs/004-specify-scripts-bash/
├── plan.md              # This file (architectural design)
├── spec.md              # Feature specification (complete)
├── research.md          # Phase 0: Mathematical validation
├── data-model.md        # Phase 1: Tier configuration schema
├── quickstart.md        # Phase 1: Testing guide
├── contracts/           # Phase 1: API contracts
│   └── tier-api.yaml    # OpenAPI spec for tier endpoints
└── tasks.md             # Phase 2: Implementation tasks (to be regenerated)
```

### Source Code (repository root)

```
src/
├── models/
│   ├── margin_tier.py       # MarginTier dataclass with Decimal precision
│   └── tier_config.py       # TierConfiguration management
├── services/
│   ├── margin_calculator.py # Core calculation logic with continuity
│   └── tier_updater.py      # Binance tier sync service
└── validation/
    └── tier_validator.py     # Continuity and accuracy validation

tests/
├── contract/
│   └── test_tier_continuity.py  # Mathematical continuity tests
├── integration/
│   └── test_binance_accuracy.py # 99% accuracy validation
└── unit/
    ├── test_margin_calculator.py # Unit tests with edge cases
    └── test_decimal_precision.py # Precision validation tests

config/
└── tiers/
    └── binance.yaml         # Tier configuration (versioned)
```

**Structure Decision**: Single project structure chosen for clean integration with existing liquidation module.

---

## Phase 0: Research & Validation

### Mathematical Validation Tasks

1. **Verify Maintenance Amount Formula**
   - Calculate MA for all Binance tier transitions
   - Prove continuity at all boundaries
   - Document in research.md

2. **Precision Analysis**
   - Compare float64 vs decimal128 for $1B positions
   - Quantify error accumulation
   - Determine minimum required precision

3. **Performance Benchmarking**
   - Test binary search vs if-chain for 5 tiers
   - Measure vectorization benefits for batch calculations
   - Profile memory usage with different data types

4. **Statistical Validation Design**
   - Calculate required sample size (2,628 per Gemini)
   - Design hypothesis tests for accuracy claims
   - Plan walk-forward validation strategy

**Output**: `research.md` with mathematical proofs and benchmarks

---

## Phase 1: Design & Contracts

### Data Model (data-model.md)

```yaml
MarginTier:
  fields:
    min_notional: Decimal
    max_notional: Decimal
    margin_rate: Decimal(precision=6, scale=5)
    maintenance_amount: Decimal
  validation:
    - min_notional < max_notional
    - margin_rate > 0 and margin_rate <= 1
    - maintenance_amount >= 0

TierConfiguration:
  fields:
    symbol: String
    tiers: List[MarginTier]
    last_updated: DateTime
    version: String
  validation:
    - tiers are sorted by min_notional
    - no gaps between tiers
    - continuity check at boundaries
```

### API Contracts (contracts/tier-api.yaml)

```yaml
endpoints:
  GET /api/margin/calculate:
    parameters:
      - notional: number (required)
      - symbol: string (default: "BTCUSDT")
    response:
      margin_required: number
      tier_applied: integer
      margin_rate: number
      maintenance_amount: number

  GET /api/margin/tiers/{symbol}:
    response:
      symbol: string
      tiers: array[MarginTier]
      last_updated: datetime

  POST /api/margin/tiers/sync:
    description: Sync with Binance tier updates
    response:
      updated_symbols: array[string]
      changes: array[TierChange]
```

### Quickstart Testing Guide (quickstart.md)

```bash
# Test continuity at boundaries
pytest tests/contract/test_tier_continuity.py -v

# Validate against Binance (requires API key)
BINANCE_API_KEY=xxx pytest tests/integration/test_binance_accuracy.py

# Property-based testing with Hypothesis
pytest tests/unit/test_margin_calculator.py::test_continuity_property

# Performance benchmarks
python -m pytest tests/performance/test_calculation_speed.py --benchmark
```

---

## Phase 2: Task Generation (NOT part of /speckit.plan)

Will run `/speckit.tasks` after this plan is complete to generate granular tasks with:
- Proper task size (1-4 hours each)
- Clear acceptance criteria
- Test-first approach
- Parallel execution opportunities

---

## Critical Implementation Notes

### Addressing Gemini's Findings

1. **Discontinuity Fix**: ✅ Maintenance Amounts implemented
2. **Precision**: ✅ Using Decimal(128) for guaranteed accuracy
3. **Concurrency**: CAS updates via DuckDB transactions
4. **Statistical Validation**: 2,628 test positions minimum
5. **Formal Specification**: Consider TLA+ in future iteration

### Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Tier data staleness | Daily sync with checksum validation |
| Calculation precision | Decimal128 with unit tests for extremes |
| Performance regression | Benchmarks in CI/CD pipeline |
| Boundary edge cases | Property-based testing with Hypothesis |

### Success Criteria

- Zero discontinuities (mathematically proven)
- 99% accuracy vs Binance (2,628+ test cases)
- <10ms single calculation latency
- <100ms for 10k batch calculations
- 100% test coverage on boundary conditions

---

## Next Steps

1. Complete Phase 0 research tasks
2. Generate detailed data-model.md
3. Create OpenAPI contracts
4. Run `/speckit.tasks` to generate implementation tasks
5. Begin TDD implementation with continuity tests first