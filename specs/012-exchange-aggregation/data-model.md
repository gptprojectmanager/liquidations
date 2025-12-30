# Data Model: Exchange Aggregation

**Feature**: 012-exchange-aggregation
**Date**: 2025-12-29

## Entities

### NormalizedLiquidation

Unified liquidation event across all exchanges.

```python
@dataclass
class NormalizedLiquidation:
    """Normalized liquidation event across all exchanges."""

    # Required fields
    exchange: str              # "binance" | "hyperliquid" | "bybit"
    symbol: str                # Normalized: "BTCUSDT"
    price: float               # Liquidation price in quote currency
    quantity: float            # Position size in base asset
    value_usd: float           # Notional value (price * quantity)
    side: str                  # "long" | "short"
    timestamp: datetime        # Event timestamp (UTC)

    # Optional metadata
    raw_data: dict | None = None        # Original exchange response
    liquidation_type: str | None = None # "forced" | "adl" | "isolated" | "cross"
    leverage: float | None = None       # If available from exchange

    # Validation
    is_validated: bool = False   # Passed schema validation
    confidence: float = 1.0      # 0.0-1.0, lower for uncertain data
```

**Validation Rules**:
- `exchange` must be in `["binance", "hyperliquid", "bybit"]`
- `symbol` must match pattern `^[A-Z]+USDT$`
- `price` must be > 0
- `quantity` must be > 0
- `value_usd` must equal `price * quantity`
- `side` must be in `["long", "short"]`
- `confidence` must be in range [0.0, 1.0]

**Exchange-Specific Confidence**:
| Exchange | Confidence | Reason |
|----------|------------|--------|
| Binance | 1.0 | Complete data with timestamp |
| Hyperliquid | 0.9 | Missing timestamp (use current time) |
| Bybit | N/A | Not implemented |

---

### ExchangeHealth

Health status of exchange connection.

```python
@dataclass
class ExchangeHealth:
    """Health status of exchange connection."""

    exchange: str              # Exchange identifier
    is_connected: bool         # Current connection status
    last_heartbeat: datetime   # Last successful message/ping
    message_count: int         # Messages received in last 60s
    error_count: int           # Errors in last 60s
    uptime_percent: float      # Last 24h uptime (0.0-100.0)
```

**Validation Rules**:
- `exchange` must be in supported exchanges list
- `uptime_percent` must be in range [0.0, 100.0]
- `message_count` >= 0
- `error_count` >= 0

---

### ExchangeInfo

Metadata about supported exchanges.

```python
@dataclass
class ExchangeInfo:
    """Metadata about a supported exchange."""

    name: str                  # Internal identifier (lowercase)
    display_name: str          # Human-readable name
    status: str                # "active" | "unavailable" | "planned"
    features: ExchangeFeatures # Capability flags
```

```python
@dataclass
class ExchangeFeatures:
    """Exchange capability flags."""

    real_time: bool            # Supports real-time streaming
    historical: bool           # Supports historical data fetch
    websocket: bool            # Uses WebSocket (vs REST polling)
```

---

## Database Schema

### liquidations table (MODIFIED)

```sql
-- Existing columns preserved
-- New column added:

ALTER TABLE liquidations
ADD COLUMN exchange VARCHAR DEFAULT 'binance';

-- Index for exchange filtering
CREATE INDEX IF NOT EXISTS idx_liquidations_exchange
ON liquidations(exchange);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_liquidations_exchange_timestamp
ON liquidations(exchange, timestamp DESC);
```

---

### exchange_health table (NEW)

```sql
CREATE TABLE IF NOT EXISTS exchange_health (
    timestamp TIMESTAMP NOT NULL,
    exchange VARCHAR NOT NULL,
    is_connected BOOLEAN NOT NULL,
    message_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    uptime_percent FLOAT DEFAULT 0.0,
    PRIMARY KEY (timestamp, exchange)
);

-- Index for recent health queries
CREATE INDEX IF NOT EXISTS idx_exchange_health_recent
ON exchange_health(exchange, timestamp DESC);
```

**Retention**: Delete records older than 7 days.

---

## Relationships

```
┌─────────────────────┐
│  ExchangeAggregator │
│  (runtime service)  │
└──────────┬──────────┘
           │ manages 1..n
           ▼
┌─────────────────────┐
│   ExchangeAdapter   │
│   (abstract base)   │
└──────────┬──────────┘
           │ implements
    ┌──────┼──────┬─────────────┐
    ▼      ▼      ▼             ▼
┌───────┐ ┌────┐ ┌────────────┐ ┌─────┐
│Binance│ │HL  │ │Hyperliquid │ │Bybit│
│Adapter│ │    │ │  Adapter   │ │Stub │
└───┬───┘ └────┘ └─────┬──────┘ └─────┘
    │                  │
    │ produces         │ produces
    ▼                  ▼
┌─────────────────────────────────┐
│     NormalizedLiquidation       │
│   (unified data structure)      │
└─────────────────────────────────┘
           │
           │ persisted to
           ▼
┌─────────────────────────────────┐
│   DuckDB: liquidations table    │
│   (with exchange column)        │
└─────────────────────────────────┘
```

---

## State Transitions

### Adapter Connection States

```
                    ┌──────────────┐
                    │ DISCONNECTED │
                    └──────┬───────┘
                           │ connect()
                           ▼
                    ┌──────────────┐
          ┌────────│  CONNECTING  │────────┐
          │        └──────────────┘        │
          │ success                failure │
          ▼                                ▼
   ┌──────────────┐                ┌──────────────┐
   │  CONNECTED   │◄───────────────│    ERROR     │
   └──────┬───────┘   reconnect    └──────┬───────┘
          │                               │
          │ disconnect() or error         │ max retries
          ▼                               ▼
   ┌──────────────┐                ┌──────────────┐
   │ DISCONNECTING│                │    FAILED    │
   └──────┬───────┘                └──────────────┘
          │
          ▼
   ┌──────────────┐
   │ DISCONNECTED │
   └──────────────┘
```

---

## Type Mappings

### Python to DuckDB

| Python Type | DuckDB Type | Notes |
|-------------|-------------|-------|
| `str` (exchange) | `VARCHAR` | Max 20 chars |
| `str` (symbol) | `VARCHAR` | Max 20 chars |
| `float` (price) | `DOUBLE` | 64-bit |
| `float` (quantity) | `DOUBLE` | 64-bit |
| `str` (side) | `VARCHAR` | "long" or "short" |
| `datetime` | `TIMESTAMP` | UTC timezone |
| `dict` (raw_data) | `VARCHAR` | JSON string |
| `bool` | `BOOLEAN` | |

### Exchange Symbol Formats

| Exchange | Format | Example | Normalized |
|----------|--------|---------|------------|
| Binance | `{BASE}{QUOTE}` | `BTCUSDT` | `BTCUSDT` |
| Hyperliquid | `{BASE}` | `BTC` | `BTCUSDT` |
| Bybit | `{BASE}{QUOTE}` | `BTCUSDT` | `BTCUSDT` |
| OKX (future) | `{BASE}-{QUOTE}-SWAP` | `BTC-USDT-SWAP` | `BTCUSDT` |

### Exchange Side Formats

| Exchange | Long Liquidation | Short Liquidation |
|----------|-----------------|-------------------|
| Binance | `BUY` | `SELL` |
| Hyperliquid | `B` (Bid) | `A` (Ask) |
| Bybit | `Buy` | `Sell` |

---

## Pydantic Models (API)

### HeatmapRequest

```python
class HeatmapRequest(BaseModel):
    symbol: str = "BTCUSDT"
    timeframe: str = "24h"  # 24h, 7d, 30d
    exchanges: list[str] | None = None  # None = all active

    @field_validator("exchanges")
    def validate_exchanges(cls, v):
        if v is None:
            return v
        valid = {"binance", "hyperliquid", "bybit"}
        invalid = set(v) - valid
        if invalid:
            raise ValueError(f"Unknown exchanges: {invalid}")
        return v
```

### HeatmapResponse

```python
class ExchangeBreakdown(BaseModel):
    binance: float | None = None
    hyperliquid: float | None = None

class HeatmapZone(BaseModel):
    price_low: float
    price_high: float
    total_density: float
    side: str  # "long" | "short"
    exchange_breakdown: ExchangeBreakdown

class ExchangeStats(BaseModel):
    zone_count: int
    total_volume: float

class HeatmapResponse(BaseModel):
    symbol: str
    timeframe: str
    current_price: float
    exchanges: list[str]
    zones: list[HeatmapZone]
    per_exchange: dict[str, ExchangeStats]
```

### HealthResponse

```python
class ExchangeHealthDetail(BaseModel):
    exchange: str
    is_connected: bool
    last_heartbeat: datetime
    message_count: int
    error_count: int
    uptime_percent: float

class HealthResponse(BaseModel):
    timestamp: datetime
    exchanges: dict[str, ExchangeHealthDetail]
```

---

**Status**: Complete
**Next**: contracts/ (OpenAPI specs)
