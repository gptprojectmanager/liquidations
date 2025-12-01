# Data Model: Funding Rate Bias Adjustment

**Feature**: LIQHEAT-005 | **Date**: 2025-12-01 | **Input**: research.md

This document defines the entities, relationships, validation rules, and state transitions for the funding rate bias adjustment feature.

---

## Entity Overview

```
┌─────────────────┐
│  AdjustmentConfig│  (1)
│  (configuration)│
└─────────────────┘
         │
         │ uses
         ▼
┌─────────────────┐       provides       ┌──────────────────┐
│  FundingRate    │──────────────────────▶│ BiasAdjustment   │
│  (external data)│                       │  (calculation)   │
└─────────────────┘                       └──────────────────┘
                                                  │
                                                  │ classifies
                                                  ▼
                                          ┌──────────────────┐
                                          │SentimentIndicator│
                                          │ (alert/display)  │
                                          └──────────────────┘
```

**Relationships**:
1. FundingRate → BiasAdjustment (1:1, provides input)
2. BiasAdjustment → SentimentIndicator (1:1, derives classification)
3. AdjustmentConfig → BiasAdjustment (1:*, configures calculation)

---

## Entity 1: FundingRate

**Purpose**: Represents funding rate data fetched from Binance API

**Python Definition**:
```python
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

class FundingRate(BaseModel):
    """Funding rate from exchange API."""

    symbol: str = Field(
        ...,
        pattern=r"^[A-Z]{3,10}USDT$",
        description="Trading pair symbol (e.g., BTCUSDT)",
        examples=["BTCUSDT", "ETHUSDT"]
    )

    rate: Decimal = Field(
        ...,
        ge=Decimal("-0.10"),
        le=Decimal("0.10"),
        description="Funding rate as decimal (e.g., 0.0001 = 0.01%)",
        examples=[Decimal("0.0001"), Decimal("-0.0005")]
    )

    funding_time: datetime = Field(
        ...,
        description="UTC timestamp when funding rate applied",
    )

    source: str = Field(
        default="binance",
        pattern=r"^[a-z_]+$",
        description="Data source identifier",
        examples=["binance", "binance_testnet"]
    )

    @field_validator("funding_time")
    @classmethod
    def validate_utc(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC."""
        if v.tzinfo is None:
            raise ValueError("funding_time must have timezone info")
        return v.astimezone(datetime.UTC)

    @field_validator("rate")
    @classmethod
    def validate_rate_precision(cls, v: Decimal) -> Decimal:
        """Ensure rate has appropriate precision."""
        if v.as_tuple().exponent < -8:
            raise ValueError("rate precision exceeds 8 decimal places")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "BTCUSDT",
                "rate": "0.00010000",
                "funding_time": "2025-12-01T08:00:00Z",
                "source": "binance"
            }
        }
```

**Validation Rules**:
- `symbol`: Must match perpetual futures naming (uppercase + "USDT")
- `rate`: Clamped to [-0.10, +0.10] (extreme outlier cap from spec)
- `funding_time`: Must be UTC timezone-aware
- `source`: Lowercase identifier for data provenance

**Storage**:
- **Cache**: In-memory (cachetools TTLCache, 5min)
- **Persistent**: DuckDB `funding_rates` table for historical (90-day retention)

**DuckDB Schema**:
```sql
CREATE TABLE funding_rates (
    id INTEGER PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    rate DECIMAL(18, 8) NOT NULL,
    funding_time TIMESTAMP NOT NULL,
    source VARCHAR NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, funding_time)
);

CREATE INDEX idx_funding_symbol_time ON funding_rates(symbol, funding_time DESC);
```

---

## Entity 2: BiasAdjustment

**Purpose**: Calculated long/short ratio adjustment based on funding rate

**Python Definition**:
```python
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, model_validator

class BiasAdjustment(BaseModel):
    """Calculated bias adjustment from funding rate."""

    funding_input: Decimal = Field(
        ...,
        ge=Decimal("-0.10"),
        le=Decimal("0.10"),
        description="Input funding rate used for calculation"
    )

    long_ratio: Decimal = Field(
        ...,
        ge=Decimal("0.20"),  # Min with max_adjustment=0.30
        le=Decimal("0.80"),  # Max with max_adjustment=0.30
        description="Adjusted long position ratio [0.20, 0.80]"
    )

    short_ratio: Decimal = Field(
        ...,
        ge=Decimal("0.20"),
        le=Decimal("0.80"),
        description="Adjusted short position ratio [0.20, 0.80]"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score [0, 1] based on data recency and magnitude"
    )

    applied_at: datetime = Field(
        default_factory=lambda: datetime.now(datetime.UTC),
        description="UTC timestamp when adjustment calculated"
    )

    scale_factor: float = Field(
        default=50.0,
        gt=0,
        description="Tanh scale factor used in calculation"
    )

    max_adjustment: float = Field(
        default=0.20,
        gt=0,
        le=0.30,
        description="Maximum deviation from neutral (0.5)"
    )

    @model_validator(mode='after')
    def validate_ratios_sum_to_one(self):
        """Ensure long_ratio + short_ratio = 1.0 (OI conservation)."""
        total = float(self.long_ratio + self.short_ratio)
        if abs(total - 1.0) > 1e-6:  # Floating point tolerance
            raise ValueError(
                f"Ratios must sum to 1.0, got {total:.10f} "
                f"(long={self.long_ratio}, short={self.short_ratio})"
            )
        return self

    @model_validator(mode='after')
    def validate_neutral_baseline(self):
        """Ensure ratios deviate appropriately from 0.5 baseline."""
        long_dev = abs(float(self.long_ratio) - 0.5)
        short_dev = abs(float(self.short_ratio) - 0.5)

        if abs(long_dev - short_dev) > 1e-6:
            raise ValueError("Deviations from 0.5 must be symmetric")

        if long_dev > self.max_adjustment + 1e-6:
            raise ValueError(
                f"Long ratio deviation {long_dev:.4f} exceeds "
                f"max_adjustment {self.max_adjustment}"
            )

        return self

    class Config:
        json_schema_extra = {
            "example": {
                "funding_input": "0.00030000",
                "long_ratio": "0.68100000",
                "short_ratio": "0.31900000",
                "confidence": 0.85,
                "applied_at": "2025-12-01T12:34:56Z",
                "scale_factor": 50.0,
                "max_adjustment": 0.20
            }
        }
```

**Validation Rules**:
- `long_ratio + short_ratio = 1.0` (OI conservation, verified in validator)
- Ratios within `[0.5 - max_adjustment, 0.5 + max_adjustment]`
- Symmetric deviation from 0.5 baseline
- `confidence ∈ [0, 1]`

**State Transitions**:
```
CREATED → VALIDATED → APPLIED
         ↓
      REJECTED (if validation fails)
```

**Storage**: Not persisted (ephemeral calculation result), but logged for audit trail

---

## Entity 3: SentimentIndicator

**Purpose**: Market sentiment classification derived from BiasAdjustment

**Python Definition**:
```python
from enum import Enum
from decimal import Decimal
from pydantic import BaseModel, Field

class SentimentClassification(str, Enum):
    """Market sentiment categories."""
    EXTREME_BULLISH = "extreme_bullish"  # funding > +0.05%
    BULLISH = "bullish"                  # funding > +0.01%
    NEUTRAL = "neutral"                  # funding ≈ 0
    BEARISH = "bearish"                  # funding < -0.01%
    EXTREME_BEARISH = "extreme_bearish"  # funding < -0.05%

class SentimentIndicator(BaseModel):
    """Market sentiment indicator for UI/alerts."""

    classification: SentimentClassification = Field(
        ...,
        description="Sentiment category based on funding rate"
    )

    funding_rate: Decimal = Field(
        ...,
        description="Input funding rate that determined classification"
    )

    long_bias_pct: float = Field(
        ...,
        ge=-30.0,
        le=30.0,
        description="Long bias as percentage deviation from 50% (e.g., +15.2 means 65.2% longs)"
    )

    threshold_exceeded: bool = Field(
        default=False,
        description="True if extreme threshold (±0.05%) exceeded, triggering alert"
    )

    alert_message: str | None = Field(
        default=None,
        max_length=200,
        description="Alert message if threshold_exceeded=True"
    )

    @classmethod
    def from_bias_adjustment(cls, adjustment: BiasAdjustment) -> "SentimentIndicator":
        """Factory method to create from BiasAdjustment."""
        funding = adjustment.funding_input
        long_bias_pct = (float(adjustment.long_ratio) - 0.5) * 100

        # Classify sentiment
        if funding >= Decimal("0.05"):
            classification = SentimentClassification.EXTREME_BULLISH
            alert = "Extreme long bias detected - high liquidation cascade risk"
        elif funding >= Decimal("0.01"):
            classification = SentimentClassification.BULLISH
            alert = None
        elif funding <= Decimal("-0.05"):
            classification = SentimentClassification.EXTREME_BEARISH
            alert = "Extreme short bias detected - high liquidation cascade risk"
        elif funding <= Decimal("-0.01"):
            classification = SentimentClassification.BEARISH
            alert = None
        else:
            classification = SentimentClassification.NEUTRAL
            alert = None

        return cls(
            classification=classification,
            funding_rate=funding,
            long_bias_pct=long_bias_pct,
            threshold_exceeded=(alert is not None),
            alert_message=alert
        )

    class Config:
        json_schema_extra = {
            "example": {
                "classification": "bullish",
                "funding_rate": "0.00030000",
                "long_bias_pct": 18.1,
                "threshold_exceeded": False,
                "alert_message": None
            }
        }
```

**Validation Rules**:
- `classification` must be valid enum value
- `long_bias_pct` within ±30% (from max_adjustment constraint)
- `alert_message` only present if `threshold_exceeded=True`

**State Transitions**:
```
DERIVED (from BiasAdjustment) → ALERTED (if threshold exceeded)
```

**Storage**: Not persisted (ephemeral display data), alerts logged to audit trail

---

## Entity 4: AdjustmentConfig

**Purpose**: Configuration parameters for bias calculation

**Python Definition**:
```python
from pydantic import BaseModel, Field, field_validator

class AdjustmentConfig(BaseModel):
    """Configuration for bias adjustment calculation."""

    enabled: bool = Field(
        default=False,
        description="Master switch to enable/disable bias adjustment"
    )

    symbol: str = Field(
        default="BTCUSDT",
        pattern=r"^[A-Z]{3,10}USDT$",
        description="Symbol to fetch funding rate for"
    )

    sensitivity: float = Field(
        default=50.0,
        gt=0.0,
        le=100.0,
        description="Tanh scale factor (higher = more sensitive to funding changes)"
    )

    max_adjustment: float = Field(
        default=0.20,
        gt=0.0,
        le=0.30,
        description="Maximum ratio deviation from neutral 0.5"
    )

    outlier_cap: Decimal = Field(
        default=Decimal("0.10"),
        gt=Decimal("0.0"),
        description="Funding rate cap (±) for outlier detection"
    )

    cache_ttl_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Cache TTL in seconds (default 5 minutes)"
    )

    extreme_alert_threshold: Decimal = Field(
        default=Decimal("0.05"),
        gt=Decimal("0.0"),
        le=Decimal("0.10"),
        description="Funding rate threshold for extreme sentiment alerts"
    )

    @field_validator("max_adjustment")
    @classmethod
    def validate_max_adjustment_reasonable(cls, v: float) -> float:
        """Ensure max_adjustment doesn't create unrealistic distributions."""
        if v > 0.30:
            raise ValueError(
                "max_adjustment > 0.30 would allow >80% long/short, "
                "which is unrealistic for most markets"
            )
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "symbol": "BTCUSDT",
                "sensitivity": 50.0,
                "max_adjustment": 0.20,
                "outlier_cap": "0.10",
                "cache_ttl_seconds": 300,
                "extreme_alert_threshold": "0.05"
            }
        }
```

**Validation Rules**:
- `sensitivity > 0` (must have positive scale)
- `max_adjustment ≤ 0.30` (prevent unrealistic >80% distributions)
- `cache_ttl_seconds ≥ 60` (minimum 1-minute cache to respect API limits)
- `outlier_cap > 0` (must have some outlier detection)

**Storage**:
- **File**: `config/bias_settings.yaml`
- **Runtime**: Loaded at startup, hot-reloadable

**YAML Format**:
```yaml
bias_adjustment:
  enabled: false
  symbol: "BTCUSDT"
  sensitivity: 50.0
  max_adjustment: 0.20
  outlier_cap: 0.10
  cache_ttl_seconds: 300
  extreme_alert_threshold: 0.05
```

---

## Relationships & Workflow

### Data Flow

```
1. FundingRate (fetched from Binance)
       ↓
2. BiasAdjustment (calculated via tanh formula + config)
       ↓
3. SentimentIndicator (classified for UI/alerts)
       ↓
4. Applied to position distribution in liquidation models
```

### Calculation Workflow

```python
# Pseudocode
def apply_bias_to_model(
    model: LiquidationModel,
    config: AdjustmentConfig
) -> LiquidationModel:
    """Apply bias adjustment to liquidation model."""

    if not config.enabled:
        return model  # No-op if disabled

    # 1. Fetch funding rate (cached)
    funding = fetch_funding_rate(config.symbol, config.cache_ttl_seconds)

    # 2. Calculate bias adjustment
    adjustment = calculate_bias_adjustment(
        funding_rate=funding.rate,
        scale_factor=config.sensitivity,
        max_adjustment=config.max_adjustment
    )

    # 3. Derive sentiment indicator
    sentiment = SentimentIndicator.from_bias_adjustment(adjustment)

    # 4. Alert if extreme
    if sentiment.threshold_exceeded:
        trigger_alert(sentiment.alert_message)

    # 5. Apply to model
    return model.with_bias(adjustment)
```

---

## Database Schema (DuckDB)

### Table: funding_rates (historical persistence)

```sql
CREATE TABLE funding_rates (
    id INTEGER PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    rate DECIMAL(18, 8) NOT NULL CHECK (rate BETWEEN -0.10 AND 0.10),
    funding_time TIMESTAMP NOT NULL,
    source VARCHAR NOT NULL DEFAULT 'binance',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, funding_time)
);

CREATE INDEX idx_funding_symbol_time ON funding_rates(symbol, funding_time DESC);
CREATE INDEX idx_funding_fetched ON funding_rates(fetched_at) WHERE fetched_at > NOW() - INTERVAL '90 days';
```

**Retention**: 90 days (automated cleanup via cron job)

### Table: bias_audit_log (optional, for debugging)

```sql
CREATE TABLE bias_audit_log (
    id INTEGER PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    funding_input DECIMAL(18, 8) NOT NULL,
    long_ratio DECIMAL(10, 8) NOT NULL,
    short_ratio DECIMAL(10, 8) NOT NULL,
    confidence REAL NOT NULL,
    applied_at TIMESTAMP NOT NULL,
    model_name VARCHAR,
    calculation_ms INTEGER
);

CREATE INDEX idx_audit_symbol_time ON bias_audit_log(symbol, applied_at DESC);
```

**Retention**: 30 days (for performance debugging)

---

## API Response Formats

### GET /api/bias/funding/{symbol}

**Response**:
```json
{
  "symbol": "BTCUSDT",
  "rate": "0.00030000",
  "funding_time": "2025-12-01T08:00:00Z",
  "source": "binance",
  "cached": true,
  "cache_expires_at": "2025-12-01T08:05:00Z"
}
```

### GET /api/bias/adjustment/{symbol}

**Response**:
```json
{
  "funding_input": "0.00030000",
  "long_ratio": "0.68100000",
  "short_ratio": "0.31900000",
  "confidence": 0.85,
  "applied_at": "2025-12-01T08:05:23Z",
  "scale_factor": 50.0,
  "max_adjustment": 0.20,
  "sentiment": {
    "classification": "bullish",
    "long_bias_pct": 18.1,
    "threshold_exceeded": false,
    "alert_message": null
  }
}
```

### GET /api/bias/sentiment/{symbol}

**Response**:
```json
{
  "classification": "bullish",
  "funding_rate": "0.00030000",
  "long_bias_pct": 18.1,
  "threshold_exceeded": false,
  "alert_message": null
}
```

---

## Validation Summary

| Entity | Key Validations |
|--------|----------------|
| FundingRate | Symbol format, rate [-0.10, 0.10], UTC timestamp |
| BiasAdjustment | Ratios sum to 1.0, symmetric deviation, within max_adjustment |
| SentimentIndicator | Valid enum, bias_pct within ±30% |
| AdjustmentConfig | max_adjustment ≤ 0.30, cache_ttl ≥ 60, sensitivity > 0 |

---

**Data Model Complete** | 2025-12-01 | Ready for contracts design ✅
