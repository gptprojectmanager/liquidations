# Quickstart: Funding Rate Bias Adjustment

**Feature**: LIQHEAT-005 | **Time to integrate**: ~5 minutes

This guide shows how to integrate funding rate bias adjustment into your existing liquidation models.

---

## Prerequisites

- Python 3.11+
- Existing liquidation model (e.g., `BinanceStandardModel`)
- Internet access (for Binance API)

---

## Installation

```bash
# Install new dependencies
uv add httpx cachetools

# Dependencies already in project: numpy, pydantic, fastapi
```

---

## Quick Integration (3 Steps)

### Step 1: Enable Bias in Configuration

Create or update `config/bias_settings.yaml`:

```yaml
bias_adjustment:
  enabled: true                    # Master switch
  symbol: "BTCUSDT"                # Symbol to track
  sensitivity: 50.0                # Tanh scale factor
  max_adjustment: 0.20             # Max ±20% deviation from 50%
  outlier_cap: 0.10                # Cap funding at ±10%
  cache_ttl_seconds: 300           # 5-minute cache
  extreme_alert_threshold: 0.05    # Alert at ±5% funding
```

### Step 2: Apply Bias to Your Model

```python
from src.models.bias_adjustment import calculate_bias_adjustment
from src.services.funding_fetcher import get_funding_rate
from src.services.adjustment_config import load_config

# Load configuration
config = load_config("config/bias_settings.yaml")

if config.enabled:
    # 1. Fetch current funding rate (cached automatically)
    funding = await get_funding_rate(config.symbol)
    print(f"Current funding: {funding.rate}%")

    # 2. Calculate bias adjustment
    adjustment = calculate_bias_adjustment(
        funding_rate=funding.rate,
        scale_factor=config.sensitivity,
        max_adjustment=config.max_adjustment
    )
    print(f"Long ratio: {adjustment.long_ratio:.1%}")
    print(f"Short ratio: {adjustment.short_ratio:.1%}")

    # 3. Apply to your model
    model = BinanceStandardModel(symbol=config.symbol)
    adjusted_model = model.with_bias(adjustment)
else:
    # Bias disabled - use baseline 50/50
    model = BinanceStandardModel(symbol=config.symbol)
```

### Step 3: Integrate with Position Distribution

```python
# Before: Naive 50/50 distribution
def calculate_positions(total_oi: float) -> tuple[float, float]:
    long_oi = total_oi * 0.5  # Always 50%
    short_oi = total_oi * 0.5
    return long_oi, short_oi

# After: Bias-adjusted distribution
def calculate_positions_with_bias(
    total_oi: float,
    adjustment: BiasAdjustment
) -> tuple[float, float]:
    long_oi = total_oi * float(adjustment.long_ratio)
    short_oi = total_oi * float(adjustment.short_ratio)

    # Verify OI conservation
    assert abs((long_oi + short_oi) - total_oi) < 1e-6

    return long_oi, short_oi
```

---

## Complete Example: Liquidation Heatmap with Bias

```python
import asyncio
from decimal import Decimal
from src.models.funding_rate import FundingRate
from src.models.bias_adjustment import BiasAdjustment
from src.services.funding_fetcher import FundingFetcher
from src.services.bias_calculator import BiasCalculator
from src.liquidationheatmap.models.binance_standard import BinanceStandardModel

async def generate_heatmap_with_bias(symbol: str = "BTCUSDT"):
    """Generate liquidation heatmap with funding rate bias adjustment."""

    # 1. Initialize services
    fetcher = FundingFetcher(cache_ttl=300)  # 5-minute cache
    calculator = BiasCalculator(
        scale_factor=50.0,
        max_adjustment=0.20
    )

    # 2. Fetch funding rate (cached)
    funding: FundingRate = await fetcher.get_funding_rate(symbol)
    print(f"📊 Funding Rate: {funding.rate} ({funding.funding_time})")

    # 3. Calculate bias adjustment
    adjustment: BiasAdjustment = calculator.calculate(funding.rate)
    print(f"🎯 Long Ratio: {adjustment.long_ratio:.1%}")
    print(f"🎯 Short Ratio: {adjustment.short_ratio:.1%}")
    print(f"✅ Confidence: {adjustment.confidence:.1%}")

    # 4. Create bias-adjusted liquidation model
    model = BinanceStandardModel(symbol=symbol)
    adjusted_model = model.with_bias_adjustment(adjustment)

    # 5. Generate heatmap
    heatmap_data = adjusted_model.generate_heatmap(
        current_price=45000.0,
        price_range=(-5, 5),  # ±5% from current
        bins=50
    )

    # 6. Check for extreme sentiment alerts
    from src.models.sentiment_indicator import SentimentIndicator
    sentiment = SentimentIndicator.from_bias_adjustment(adjustment)

    if sentiment.threshold_exceeded:
        print(f"⚠️ ALERT: {sentiment.alert_message}")

    return heatmap_data, adjustment, sentiment

# Run
if __name__ == "__main__":
    heatmap, adjustment, sentiment = asyncio.run(
        generate_heatmap_with_bias("BTCUSDT")
    )
    print(f"\n✨ Heatmap generated with {sentiment.classification} bias")
```

**Output Example**:
```
📊 Funding Rate: 0.00030000 (2025-12-01 08:00:00+00:00)
🎯 Long Ratio: 68.1%
🎯 Short Ratio: 31.9%
✅ Confidence: 85.0%

✨ Heatmap generated with bullish bias
```

---

## API Usage Examples

### Get Current Funding Rate

```python
import httpx

async def get_funding():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/bias/funding/BTCUSDT"
        )
        data = response.json()
        print(f"Rate: {data['rate']}")
        print(f"Cached: {data['cached']}")

asyncio.run(get_funding())
```

### Get Bias Adjustment with Custom Parameters

```python
async def get_custom_bias():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/bias/adjustment/BTCUSDT",
            params={
                "scale_factor": 75.0,      # More sensitive
                "max_adjustment": 0.25      # Larger deviations
            }
        )
        data = response.json()
        print(f"Long: {data['long_ratio']}")
        print(f"Sentiment: {data['sentiment']['classification']}")

asyncio.run(get_custom_bias())
```

### Manual Override (Emergency)

```python
async def force_neutral_bias():
    """Force neutral 50/50 distribution (e.g., suspected manipulation)."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/bias/override",
            json={
                "symbol": "BTCUSDT",
                "long_ratio": "0.50000000",
                "short_ratio": "0.50000000",
                "duration_seconds": 3600,  # 1 hour
                "reason": "Suspected funding manipulation"
            },
            headers={"X-API-Key": "your-api-key"}
        )
        print(f"Override active until: {response.json()['expires_at']}")

asyncio.run(force_neutral_bias())
```

---

## Fallback Scenarios

### Scenario 1: API Unavailable

```python
from src.services.funding_fetcher import FundingFetchError

try:
    funding = await fetcher.get_funding_rate("BTCUSDT")
except FundingFetchError as e:
    print(f"⚠️ API error: {e}")
    # Fallback to cached value (24h max)
    funding = fetcher.get_cached_funding("BTCUSDT")

    if funding is None:
        # Last resort: neutral 50/50
        adjustment = BiasAdjustment(
            funding_input=Decimal("0.0"),
            long_ratio=Decimal("0.5"),
            short_ratio=Decimal("0.5"),
            confidence=0.0  # Zero confidence for fallback
        )
```

### Scenario 2: Extreme Funding Rate (Outlier)

```python
def handle_outlier(funding_rate: Decimal) -> Decimal:
    """Cap outliers at ±0.10 as per spec."""
    outlier_cap = Decimal("0.10")

    if funding_rate > outlier_cap:
        print(f"⚠️ Outlier detected: {funding_rate}, capping at {outlier_cap}")
        return outlier_cap
    elif funding_rate < -outlier_cap:
        print(f"⚠️ Outlier detected: {funding_rate}, capping at -{outlier_cap}")
        return -outlier_cap

    return funding_rate
```

### Scenario 3: Stale Data (>24h old)

```python
from datetime import datetime, timedelta

def check_data_freshness(funding: FundingRate) -> bool:
    """Warn if data is stale."""
    age = datetime.now(datetime.UTC) - funding.funding_time

    if age > timedelta(hours=24):
        print(f"⚠️ Stale data: {age.total_seconds() / 3600:.1f} hours old")
        return False

    return True

if not check_data_freshness(funding):
    # Use degraded confidence or fallback to neutral
    adjustment.confidence *= 0.5  # Reduce confidence
```

---

## Testing Integration

### Unit Test: Verify OI Conservation

```python
from hypothesis import given, strategies as st
import pytest

@given(
    total_oi=st.floats(min_value=1e6, max_value=1e9),
    funding_rate=st.decimals(
        min_value=Decimal("-0.10"),
        max_value=Decimal("0.10"),
        places=8
    )
)
def test_oi_conservation(total_oi, funding_rate):
    """Property test: Total OI always conserved."""
    calculator = BiasCalculator(scale_factor=50.0, max_adjustment=0.20)
    adjustment = calculator.calculate(funding_rate)

    long_oi = total_oi * float(adjustment.long_ratio)
    short_oi = total_oi * float(adjustment.short_ratio)

    assert abs((long_oi + short_oi) - total_oi) < 1e-6
```

### Integration Test: Binance API

```python
@pytest.mark.asyncio
async def test_binance_funding_api():
    """Integration test with real Binance API."""
    fetcher = FundingFetcher(cache_ttl=300)

    funding = await fetcher.get_funding_rate("BTCUSDT")

    assert funding.symbol == "BTCUSDT"
    assert -0.10 <= float(funding.rate) <= 0.10
    assert funding.source == "binance"
    assert funding.funding_time.tzinfo is not None  # UTC
```

---

## Performance Validation

### Benchmark: <50ms Target

```python
import time

async def benchmark_bias_calculation():
    """Verify <50ms performance requirement."""
    fetcher = FundingFetcher(cache_ttl=300)
    calculator = BiasCalculator(scale_factor=50.0, max_adjustment=0.20)

    # Warmup cache
    await fetcher.get_funding_rate("BTCUSDT")

    # Measure cached performance
    times = []
    for _ in range(100):
        start = time.perf_counter()

        funding = await fetcher.get_funding_rate("BTCUSDT")
        adjustment = calculator.calculate(funding.rate)

        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)

    p95 = sorted(times)[94]  # 95th percentile
    print(f"P95 latency: {p95:.2f}ms (target: <50ms)")
    assert p95 < 50.0, f"Performance target missed: {p95:.2f}ms"

asyncio.run(benchmark_bias_calculation())
```

**Expected output**:
```
P95 latency: 6.23ms (target: <50ms)
✅ Performance requirement met
```

---

## Configuration Best Practices

### Development Environment

```yaml
bias_adjustment:
  enabled: true
  symbol: "BTCUSDT"
  sensitivity: 50.0
  max_adjustment: 0.20
  cache_ttl_seconds: 60           # 1-minute for faster testing
  extreme_alert_threshold: 0.03   # Lower threshold for testing alerts
```

### Production Environment

```yaml
bias_adjustment:
  enabled: true
  symbol: "BTCUSDT"
  sensitivity: 50.0
  max_adjustment: 0.20
  cache_ttl_seconds: 300          # 5-minute (respects API limits)
  extreme_alert_threshold: 0.05   # Conservative threshold
```

### Disable for Backward Compatibility

```yaml
bias_adjustment:
  enabled: false  # Reverts to naive 50/50 distribution
```

---

## Monitoring & Alerts

### Log Bias Adjustments

```python
import logging

logger = logging.getLogger(__name__)

def log_adjustment(adjustment: BiasAdjustment, sentiment: SentimentIndicator):
    """Log bias adjustments for monitoring."""
    logger.info(
        "Bias adjustment applied",
        extra={
            "funding_rate": float(adjustment.funding_input),
            "long_ratio": float(adjustment.long_ratio),
            "short_ratio": float(adjustment.short_ratio),
            "confidence": adjustment.confidence,
            "sentiment": sentiment.classification.value,
            "alert": sentiment.threshold_exceeded
        }
    )

    if sentiment.threshold_exceeded:
        logger.warning(
            f"⚠️ EXTREME SENTIMENT: {sentiment.alert_message}",
            extra={"funding_rate": float(adjustment.funding_input)}
        )
```

### Prometheus Metrics (Optional)

```python
from prometheus_client import Gauge, Histogram

bias_long_ratio = Gauge('bias_long_ratio', 'Current long position ratio')
bias_confidence = Gauge('bias_confidence', 'Bias adjustment confidence')
bias_calc_duration = Histogram('bias_calc_duration_seconds', 'Calculation time')

def export_metrics(adjustment: BiasAdjustment):
    """Export to Prometheus."""
    bias_long_ratio.set(float(adjustment.long_ratio))
    bias_confidence.set(adjustment.confidence)
```

---

## Troubleshooting

### Issue: "Rate limit exceeded (429)"

**Solution**: Increase cache TTL or implement exponential backoff

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60)
)
async def fetch_with_retry(symbol: str):
    return await fetcher.get_funding_rate(symbol)
```

### Issue: "Ratios don't sum to 1.0"

**Solution**: Check Decimal precision and rounding

```python
# Use Decimal for precision
from decimal import Decimal, getcontext

getcontext().prec = 28  # Set precision for Decimal128

# Ensure sum equals 1.0
long_ratio = Decimal("0.681")
short_ratio = Decimal("1.0") - long_ratio  # Computed, not hardcoded
```

### Issue: "Stale funding data"

**Solution**: Check data age and fallback gracefully

```python
if (datetime.now(datetime.UTC) - funding.funding_time) > timedelta(hours=8):
    # Funding should update every 8 hours
    logger.warning("Funding data >8h old, may be stale")
    adjustment.confidence *= 0.5  # Degrade confidence
```

---

## Next Steps

1. **Run tests**: `uv run pytest tests/unit/test_bias_calculator.py -v`
2. **Start API**: `uvicorn src.api.validation_app:app --reload`
3. **Try examples**: Copy code snippets from this guide
4. **Monitor**: Check logs for bias adjustments and alerts
5. **Validate**: Use `/api/bias/correlation` to verify >0.7 correlation

---

## Additional Resources

- **API Documentation**: `/docs` (Swagger UI) or `/redoc` (ReDoc)
- **Data Model**: `specs/005-specify-scripts-bash/data-model.md`
- **Research & Formulas**: `specs/005-specify-scripts-bash/research.md`
- **OpenAPI Contract**: `specs/005-specify-scripts-bash/contracts/bias-api.yaml`

---

**Quickstart Complete** | Integration time: ~5 minutes | 2025-12-01 ✅
