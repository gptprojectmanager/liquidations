# Quickstart: Testing Tiered Margin Enhancement

**Feature**: Tiered Margin with Mathematical Continuity
**Prerequisites**: Python 3.11+, pytest, hypothesis

## Installation

```bash
# Install dependencies
uv add decimal pytest hypothesis numpy duckdb pydantic

# Install dev dependencies
uv add --dev pytest-benchmark pytest-cov mypy
```

## Quick Validation

### 1. Test Mathematical Continuity (CRITICAL)

```bash
# Verify continuity at all tier boundaries
pytest tests/contract/test_tier_continuity.py -v

# Expected output:
# test_tier_boundary_50k ... PASSED ✓ (margin = $250 both sides)
# test_tier_boundary_250k ... PASSED ✓ (margin = $2,500 both sides)
# test_tier_boundary_1m ... PASSED ✓ (margin = $21,000 both sides)
# test_tier_boundary_10m ... PASSED ✓ (margin = $471,000 both sides)
```

### 2. Test Decimal Precision

```bash
# Verify 128-bit precision for large positions
pytest tests/unit/test_decimal_precision.py -v

# Test extreme values
python -c "
from decimal import Decimal, getcontext
getcontext().prec = 28
notional = Decimal('999999999.99')
rate = Decimal('0.050')
ma = Decimal('29000')
margin = notional * rate - ma
print(f'${notional:,.2f} position: margin = ${margin:,.2f}')
print(f'Precision: {margin.as_tuple().exponent} decimal places')
"

# Expected: No rounding errors, exact calculation
```

### 3. Property-Based Testing with Hypothesis

```bash
# Run property tests for continuity invariants
pytest tests/unit/test_margin_calculator.py::test_continuity_property -v

# This generates thousands of random test cases
# to verify continuity holds for all values
```

### 4. Binance Accuracy Validation

```bash
# Compare against official Binance calculator
# Requires BINANCE_API_KEY environment variable
export BINANCE_API_KEY=your_api_key_here

pytest tests/integration/test_binance_accuracy.py -v

# Tests 2,628 positions (statistically significant sample)
# Expected: 99%+ accuracy vs exchange
```

## Manual Testing

### Test Continuity at Boundaries

```python
# tests/manual_continuity_check.py
from decimal import Decimal

def check_boundary(boundary, rate1, ma1, rate2, ma2):
    """Verify continuity at tier boundary."""
    margin_left = boundary * Decimal(str(rate1)) - Decimal(str(ma1))
    margin_right = boundary * Decimal(str(rate2)) - Decimal(str(ma2))
    difference = abs(margin_left - margin_right)

    print(f"Boundary: ${boundary:,}")
    print(f"  Left:  ${margin_left:,.2f} (rate={rate1}, MA=${ma1})")
    print(f"  Right: ${margin_right:,.2f} (rate={rate2}, MA=${ma2})")
    print(f"  Diff:  ${difference:,.2f} {'✓' if difference < 0.01 else '✗'}")
    return difference < Decimal('0.01')

# Test all boundaries
boundaries = [
    (50_000, 0.005, 0, 0.010, 250),
    (250_000, 0.010, 250, 0.025, 4_000),
    (1_000_000, 0.025, 4_000, 0.050, 29_000),
]

for boundary, r1, ma1, r2, ma2 in boundaries:
    assert check_boundary(Decimal(boundary), r1, ma1, r2, ma2)
print("\nAll boundaries continuous! ✓")
```

### API Testing

```bash
# Start the API server
uvicorn src.api.main:app --reload

# Test calculation endpoint
curl "http://localhost:8000/api/margin/calculate?notional=75000&symbol=BTCUSDT"

# Expected response:
# {
#   "notional_value": 75000,
#   "margin_required": 500,
#   "margin_rate_effective": 0.00667,
#   "tier_number": 2,
#   "tier_details": {
#     "min_notional": 50000,
#     "max_notional": 250000,
#     "margin_rate": 0.01,
#     "maintenance_amount": 250
#   }
# }

# Test tier configuration endpoint
curl "http://localhost:8000/api/margin/tiers/BTCUSDT"

# Validate configuration
curl -X POST "http://localhost:8000/api/margin/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "tiers": [
      {"min_notional": 0, "max_notional": 50000,
       "margin_rate": 0.005, "maintenance_amount": 0},
      {"min_notional": 50000, "max_notional": 250000,
       "margin_rate": 0.01, "maintenance_amount": 250}
    ]
  }'
```

## Performance Testing

```bash
# Benchmark single calculation
pytest tests/performance/test_calculation_speed.py::test_single_calc --benchmark

# Benchmark batch calculation (10k positions)
pytest tests/performance/test_calculation_speed.py::test_batch_calc --benchmark

# Expected results:
# Single: <10ms
# Batch (10k): <100ms
```

## Test Coverage

```bash
# Run all tests with coverage
pytest --cov=src.models.margin_tier --cov=src.services.margin_calculator \
       --cov-report=html --cov-report=term

# View coverage report
open htmlcov/index.html

# Target: 100% coverage for boundary conditions
```

## Regression Testing

```bash
# Save current results as baseline
pytest tests/ --json-report --json-report-file=baseline.json

# After changes, compare against baseline
pytest tests/ --json-report --json-report-file=current.json
python scripts/compare_test_results.py baseline.json current.json
```

## Common Issues & Solutions

### Issue: Discontinuity Detected

```python
# Error: Discontinuity at tier boundary 50000
# Solution: Check maintenance_amount calculation

MA2 = MA1 + boundary * (rate2 - rate1)
# MA2 = 0 + 50000 * (0.01 - 0.005) = 250 ✓
```

### Issue: Precision Loss with Float

```python
# Wrong (loses precision)
margin = float(notional) * 0.05 - 29000

# Correct (maintains precision)
from decimal import Decimal
margin = Decimal(str(notional)) * Decimal('0.05') - Decimal('29000')
```

### Issue: Performance Degradation

```python
# Slow (repeated lookups)
for position in positions:
    tier = find_tier(position)  # O(n) lookup

# Fast (vectorized)
import numpy as np
margins = calculate_margins_batch(np.array(positions))  # O(1) per position
```

## Validation Checklist

- [ ] All tier boundaries continuous (difference < $0.01)
- [ ] Decimal precision maintained for $1B positions
- [ ] 2,628+ test cases pass (99% confidence)
- [ ] Performance <10ms single, <100ms batch
- [ ] API returns correct tier details
- [ ] Sync with Binance successful
- [ ] Coverage 100% for boundary conditions
- [ ] Property tests pass (10,000+ random cases)

## Next Steps

1. Run continuity tests first (TDD approach)
2. Implement decimal precision throughout
3. Add property-based tests for invariants
4. Benchmark against performance targets
5. Validate against live Binance data