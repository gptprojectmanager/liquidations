# Data Models: Liquidation Heatmap System

**Version**: 1.0.0
**Last Updated**: 2025-10-29
**Status**: Approved for Implementation

---

## Overview

This document defines the data models for the Liquidation Heatmap System, including database schemas (DuckDB), API request/response models (Pydantic), and internal domain models.

**Guiding Principles**:
- **Immutable historical data**: Never modify raw Binance CSV
- **Denormalized for speed**: Pre-compute aggregations in `heatmap_cache`
- **Strong typing**: Use Pydantic for validation
- **Time-series optimized**: All tables indexed by timestamp

---

## Database Schema (DuckDB)

### Database File

**Location**: `data/processed/liquidations.duckdb`
**Size**: ~2GB per month of data (compressed)
**Backup**: Daily snapshot to `data/backup/liquidations_YYYYMMDD.duckdb`

### Table 1: `liquidation_levels`

**Purpose**: Calculated liquidation prices from Open Interest data

**Schema**:
```sql
CREATE TABLE liquidation_levels (
    id BIGINT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    model VARCHAR(50) NOT NULL,  -- 'binance_standard', 'funding_adjusted', 'ensemble'
    price_level DECIMAL(18, 2) NOT NULL,
    liquidation_volume DECIMAL(18, 8) NOT NULL,  -- Notional USDT
    leverage_tier VARCHAR(10),  -- '5x', '10x', '25x', '50x', '100x'
    side VARCHAR(10) NOT NULL,  -- 'long' or 'short'
    confidence DECIMAL(3, 2) NOT NULL,  -- 0.00 to 1.00
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_liquidation_levels_timestamp ON liquidation_levels(timestamp);
CREATE INDEX idx_liquidation_levels_symbol_model ON liquidation_levels(symbol, model);
CREATE INDEX idx_liquidation_levels_price ON liquidation_levels(price_level);
```

**Example Row**:
```sql
INSERT INTO liquidation_levels VALUES (
    1,
    '2024-10-29 12:00:00',
    'BTCUSDT',
    'binance_standard',
    66000.00,
    1234567.89,
    '10x',
    'long',
    0.95,
    '2024-10-29 12:05:00'
);
```

**Constraints**:
- `confidence` BETWEEN 0.0 AND 1.0
- `side` IN ('long', 'short')
- `model` IN ('binance_standard', 'funding_adjusted', 'py_liquidation_map', 'ensemble')
- `leverage_tier` IN ('5x', '10x', '25x', '50x', '100x', NULL)

**Notes**:
- `leverage_tier` is NULL for ensemble model (aggregated across leverages)
- `liquidation_volume` is always positive (use `side` to determine long/short)

---

### Table 2: `heatmap_cache`

**Purpose**: Pre-aggregated heatmap buckets for fast API queries

**Schema**:
```sql
CREATE TABLE heatmap_cache (
    id BIGINT PRIMARY KEY,
    time_bucket TIMESTAMP NOT NULL,  -- Rounded to 1-hour intervals
    price_bucket DECIMAL(18, 2) NOT NULL,  -- Rounded to $100 intervals
    symbol VARCHAR(20) NOT NULL,
    model VARCHAR(50) NOT NULL,
    density BIGINT NOT NULL,  -- Count of liquidations in bucket
    volume DECIMAL(18, 8) NOT NULL,  -- Total USDT liquidated in bucket
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_heatmap_time_price ON heatmap_cache(time_bucket, price_bucket);
CREATE INDEX idx_heatmap_symbol_model ON heatmap_cache(symbol, model);
```

**Aggregation Logic**:
```sql
INSERT INTO heatmap_cache
SELECT
    date_trunc('hour', timestamp) AS time_bucket,
    FLOOR(price_level / 100) * 100 AS price_bucket,
    symbol,
    model,
    COUNT(*) AS density,
    SUM(liquidation_volume) AS volume,
    CURRENT_TIMESTAMP AS last_updated
FROM liquidation_levels
GROUP BY time_bucket, price_bucket, symbol, model;
```

**Example Row**:
```sql
INSERT INTO heatmap_cache VALUES (
    1,
    '2024-10-29 12:00:00',
    66000.00,
    'BTCUSDT',
    'ensemble',
    42,  -- 42 liquidations in this bucket
    5678901.23,  -- $5.67M total volume
    '2024-10-29 12:05:00'
);
```

**Notes**:
- Time buckets: 1-hour intervals (configurable)
- Price buckets: $100 intervals (dynamic based on price range)
- Re-computed daily via `scripts/update_heatmap_cache.py`

---

### Table 3: `open_interest_history`

**Purpose**: Historical Open Interest data from Binance

**Schema**:
```sql
CREATE TABLE open_interest_history (
    id BIGINT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open_interest_value DECIMAL(18, 8) NOT NULL,  -- Notional USDT
    open_interest_contracts DECIMAL(18, 8),  -- Number of contracts
    source VARCHAR(50) DEFAULT 'binance_csv'
);

CREATE INDEX idx_oi_timestamp_symbol ON open_interest_history(timestamp, symbol);
```

**Data Source**: `data/raw/BTCUSDT/metrics/BTCUSDT-metrics-YYYY-MM-DD.csv`

**CSV Format** (Binance):
```csv
timestamp,symbol,sumOpenInterest,sumOpenInterestValue,countTopTraderLongShortRatio
1635724800000,BTCUSDT,123456.78,8123456789.12,1.23
```

**Ingestion**:
```sql
COPY open_interest_history(timestamp, symbol, open_interest_value)
FROM 'data/raw/BTCUSDT/metrics/*.csv'
(AUTO_DETECT TRUE, HEADER TRUE, DELIMITER ',');
```

---

### Table 4: `funding_rate_history`

**Purpose**: 8-hour funding rate history from Binance

**Schema**:
```sql
CREATE TABLE funding_rate_history (
    id BIGINT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    funding_rate DECIMAL(10, 8) NOT NULL,  -- -1.0 to +1.0
    funding_interval_hours INT DEFAULT 8
);

CREATE INDEX idx_funding_timestamp_symbol ON funding_rate_history(timestamp, symbol);
```

**Data Source**: `data/raw/BTCUSDT/fundingRate/BTCUSDT-fundingRate-YYYY-MM-DD.csv`

**CSV Format** (Binance):
```csv
timestamp,symbol,fundingRate,markPrice
1635724800000,BTCUSDT,0.0001,67234.56
```

**Interpretation**:
- `funding_rate > 0`: Longs pay shorts (bullish sentiment)
- `funding_rate < 0`: Shorts pay longs (bearish sentiment)
- `funding_rate > 0.001` (0.1%): Strong bullish pressure
- `funding_rate < -0.001`: Strong bearish pressure

---

### Table 5: `liquidation_history`

**Purpose**: Historical liquidation events (actual occurred liquidations from Binance)

**Schema**:
```sql
CREATE TABLE liquidation_history (
    id BIGINT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(18, 2) NOT NULL,
    quantity DECIMAL(18, 8) NOT NULL,
    side VARCHAR(10) NOT NULL,  -- 'long' or 'short'
    leverage INT
);

CREATE INDEX idx_liquidation_history_timestamp ON liquidation_history(timestamp);
CREATE INDEX idx_liquidation_history_symbol ON liquidation_history(symbol);
```

**Data Source**: `data/raw/BTCUSDT/trades/` (filtered for liquidation events)

**Note**: This table stores **actual historical liquidations** that occurred, used for:
- Backtesting model accuracy
- Validating predictions vs reality
- Analyzing liquidation cascade patterns

**Difference from `liquidation_levels`**:
- `liquidation_levels` = **Predictions** (calculated from Open Interest)
- `liquidation_history` = **Actual events** (observed from trade data)

**Population Strategy**:
- Phase 7 task: Ingest historical liquidation events from Binance CSV
- Filter trades where `is_liquidation=true` flag present
- Or identify liquidations by large volume + price spike pattern

---

## Domain Models (Python)

### Model 1: `LiquidationLevel`

**Purpose**: Represents a calculated liquidation price level

**Pydantic Model**:
```python
from decimal import Decimal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator

class SideEnum(str, Enum):
    LONG = "long"
    SHORT = "short"

class ModelEnum(str, Enum):
    BINANCE_STANDARD = "binance_standard"
    FUNDING_ADJUSTED = "funding_adjusted"
    PY_LIQUIDATION_MAP = "py_liquidation_map"
    ENSEMBLE = "ensemble"

class LiquidationLevel(BaseModel):
    """Domain model for liquidation level."""

    timestamp: datetime
    symbol: str = Field(..., min_length=1, max_length=20)
    model: ModelEnum
    price_level: Decimal = Field(..., gt=0, decimal_places=2)
    liquidation_volume: Decimal = Field(..., gt=0, decimal_places=8)
    leverage_tier: str | None = Field(None, regex=r"^\d+x$")
    side: SideEnum
    confidence: Decimal = Field(..., ge=0, le=1, decimal_places=2)

    @validator('symbol')
    def validate_symbol(cls, v):
        if not v.endswith('USDT'):
            raise ValueError('Only USDT pairs supported in MVP')
        return v

    class Config:
        use_enum_values = True
```

**Usage**:
```python
level = LiquidationLevel(
    timestamp=datetime.now(),
    symbol='BTCUSDT',
    model=ModelEnum.BINANCE_STANDARD,
    price_level=Decimal('66000.00'),
    liquidation_volume=Decimal('1234567.89'),
    leverage_tier='10x',
    side=SideEnum.LONG,
    confidence=Decimal('0.95')
)
```

---

### Model 2: `HeatmapBucket`

**Purpose**: Aggregated heatmap data for visualization

**Pydantic Model**:
```python
class HeatmapBucket(BaseModel):
    """Heatmap bucket with aggregated liquidation data."""

    time_bucket: datetime
    price_bucket: Decimal = Field(..., decimal_places=2)
    symbol: str
    model: ModelEnum
    density: int = Field(..., ge=0)  # Count of liquidations
    volume: Decimal = Field(..., ge=0, decimal_places=8)

    class Config:
        use_enum_values = True
```

---

### Model 3: `AbstractLiquidationModel` (Interface)

**Purpose**: Black box interface for liquidation models

**ABC**:
```python
from abc import ABC, abstractmethod
import pandas as pd

class AbstractLiquidationModel(ABC):
    """Base interface for liquidation calculation models."""

    @abstractmethod
    def calculate_liquidations(
        self,
        open_interest: pd.DataFrame,
        current_price: float,
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate liquidation levels from open interest data.

        Args:
            open_interest: DataFrame with columns [timestamp, price, oi_volume, leverage]
            current_price: Current BTC/USDT price
            **kwargs: Model-specific parameters (e.g., funding_rate)

        Returns:
            DataFrame with columns [price_level, volume, side, confidence]
        """
        pass

    @abstractmethod
    def confidence_score(self) -> float:
        """
        Return model confidence score [0-1] based on data quality.

        Returns:
            float: Confidence score (0.0 = no confidence, 1.0 = full confidence)
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Unique identifier for this model."""
        pass
```

**Implementations**:
1. `BinanceStandardModel` (`src/models/binance_standard.py`)
2. `FundingAdjustedModel` (`src/models/funding_adjusted.py`)
3. `py_liquidation_mapModel` (`src/models/py_liquidation_map.py`)
4. `EnsembleModel` (`src/models/ensemble.py`)

---

## API Request/Response Models (Pydantic)

### Request: `HeatmapRequest`

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class HeatmapRequest(BaseModel):
    """Query parameters for heatmap endpoint."""

    symbol: str = Field(default='BTCUSDT', regex=r'^[A-Z]+USDT$')
    model: ModelEnum = Field(default=ModelEnum.ENSEMBLE)
    timeframe: str = Field(default='1d', regex=r'^\d+(h|d|w)$')
    start: Optional[datetime] = None
    end: Optional[datetime] = None

    @validator('timeframe')
    def validate_timeframe(cls, v):
        """Validate timeframe format (e.g., '1h', '24h', '7d', '1w')."""
        if v not in ['1h', '4h', '12h', '1d', '7d', '30d']:
            raise ValueError('Timeframe must be one of: 1h, 4h, 12h, 1d, 7d, 30d')
        return v
```

---

### Response: `HeatmapResponse`

```python
class HeatmapDataPoint(BaseModel):
    """Single data point in heatmap."""
    time: datetime
    price_bucket: Decimal
    density: int
    volume: Decimal

class HeatmapMetadata(BaseModel):
    """Metadata for heatmap response."""
    total_liquidation_volume: Decimal
    highest_density_price: Decimal
    num_buckets: int
    data_quality_score: Decimal

class HeatmapResponse(BaseModel):
    """Response for /liquidations/heatmap endpoint."""

    symbol: str
    model: ModelEnum
    timeframe: str
    current_price: Decimal
    data: list[HeatmapDataPoint]
    metadata: HeatmapMetadata

    class Config:
        use_enum_values = True
```

**Example JSON**:
```json
{
  "symbol": "BTCUSDT",
  "model": "ensemble",
  "timeframe": "1d",
  "current_price": 67234.56,
  "data": [
    {
      "time": "2024-10-29T00:00:00Z",
      "price_bucket": 66000.00,
      "density": 42,
      "volume": 5678901.23
    }
  ],
  "metadata": {
    "total_liquidation_volume": 123456789.01,
    "highest_density_price": 66000.00,
    "num_buckets": 300,
    "data_quality_score": 0.94
  }
}
```

---

### Response: `LiquidationLevelsResponse`

```python
class LiquidationLevelData(BaseModel):
    """Single liquidation level."""
    price: Decimal
    volume: Decimal
    side: SideEnum
    leverage: str
    confidence: Decimal

class LiquidationLevelsResponse(BaseModel):
    """Response for /liquidations/levels endpoint."""

    symbol: str
    model: ModelEnum
    current_price: Decimal
    levels: list[LiquidationLevelData]
    timestamp: datetime

    class Config:
        use_enum_values = True
```

---

## Data Validation Rules

### Price Validation

```python
def validate_price(price: Decimal) -> bool:
    """Validate BTC price is within reasonable bounds."""
    MIN_PRICE = Decimal('10000')  # $10k
    MAX_PRICE = Decimal('500000')  # $500k
    return MIN_PRICE <= price <= MAX_PRICE
```

### Volume Validation

```python
def validate_volume(volume: Decimal) -> bool:
    """Validate liquidation volume is positive."""
    return volume > 0
```

### Confidence Validation

```python
def validate_confidence(confidence: Decimal) -> bool:
    """Validate confidence score is between 0 and 1."""
    return Decimal('0') <= confidence <= Decimal('1')
```

---

## State Transitions

### Heatmap Cache Update Workflow

```
1. NEW DATA AVAILABLE (Binance CSV updated)
   ↓
2. INGESTION TRIGGERED (cron job)
   ↓
3. CALCULATE LIQUIDATIONS (all 3 models)
   ↓
4. AGGREGATE INTO BUCKETS (binning algorithm)
   ↓
5. UPDATE CACHE (INSERT INTO heatmap_cache)
   ↓
6. CACHE READY (API serves new data)
```

**Idempotency**: Running update script multiple times with same date is safe (UPSERT logic).

---

## Data Migration Strategy

### Initial Load (One-time)

```bash
# Step 1: Create database
uv run python scripts/init_database.py

# Step 2: Ingest historical data (30 days)
uv run python scripts/ingest_historical.py \
  --symbol BTCUSDT \
  --start-date 2024-10-01 \
  --end-date 2024-10-29

# Step 3: Calculate liquidations
uv run python scripts/calculate_liquidations.py --model all

# Step 4: Generate cache
uv run python scripts/update_heatmap_cache.py
```

### Daily Updates (Cron)

```bash
# Cron: Every day at 1 AM
0 1 * * * cd /media/sam/1TB/LiquidationHeatmap && \
  uv run python scripts/daily_update.py >> logs/daily_update.log 2>&1
```

---

## Performance Optimization

### Indexing Strategy

**Critical indexes** (80% of queries):
1. `idx_liquidation_levels_timestamp` - Time-range queries
2. `idx_heatmap_time_price` - Heatmap bucket lookups
3. `idx_liquidation_levels_symbol_model` - Model filtering

**Query Optimization**:
```sql
-- Fast query (uses indexes)
SELECT * FROM heatmap_cache
WHERE symbol = 'BTCUSDT'
  AND model = 'ensemble'
  AND time_bucket BETWEEN '2024-10-01' AND '2024-10-29'
ORDER BY time_bucket, price_bucket;
```

### Caching Strategy

- **DuckDB query cache**: Automatic (LRU cache)
- **FastAPI response cache**: HTTP caching headers (`Cache-Control: max-age=3600`)
- **Pre-computed aggregations**: `heatmap_cache` table

---

**Data Model Status**: ✅ **APPROVED - Ready for Implementation**
