# Troubleshooting Guide

## Common Issues

### API Errors

#### 404: Symbol Not Found
```
{"detail": "Symbol INVALIDUSDT not found"}
```

**Solution**: Currently only `BTCUSDT` is supported. Check symbol name.

#### 400: Negative Notional
```
{"detail": "Notional must be positive"}
```

**Solution**: Ensure notional value is > 0.

#### 422: Validation Error
```
{"detail": [{"loc": ["body", "notional"], "msg": "field required"}]}
```

**Solution**: Provide either `notional` OR (`entry_price` + `position_size`).

### Calculation Discrepancies

#### Margin differs from Binance by small amount

**Expected**: Differences up to $0.01 due to rounding.

**Solution**: Use Decimal precision, not float.

#### Liquidation price seems incorrect

**Check**:
1. Correct tier being used?
2. Using correct formula for long/short?
3. Maintenance amount included?

**Debug**:
```python
# Get tier details
response = requests.post(
    f"{API_BASE}/margin/calculate",
    json={
        "symbol": "BTCUSDT",
        "notional": "100000",
        "include_tier_details": True
    }
)
print(response.json()["tier_details"])
```

### Performance Issues

#### Slow API responses

**Check**:
1. First request is always slower (cold start)
2. Batch endpoint for multiple calculations
3. Use `include_display=False` if not needed

**Benchmark**:
```bash
# Should be <100ms
time curl -X POST "http://localhost:8000/api/margin/calculate" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "notional": "50000"}'
```

## Testing

### Run Tests
```bash
# All tests
uv run pytest

# API tests only
uv run pytest tests/contract/

# Performance tests
uv run pytest tests/performance/
```

### Manual Testing
```bash
# Start server
uvicorn src.api.main:app --reload

# Test calculate
curl -X POST "http://localhost:8000/api/margin/calculate" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "notional": "50000"}'
```

## Getting Help

1. Check logs for detailed error messages
2. Review API documentation: `/docs`
3. Verify input parameters match schema
4. Test with known good values first
