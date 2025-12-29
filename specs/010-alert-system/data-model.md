# Data Model: Liquidation Zone Alert System

**Feature**: spec-010 (Alert System MVP)
**Date**: 2025-12-29
**Version**: 1.0

---

## 1. Entity Definitions

### 1.1 AlertConfig

Configuration for the alert system, loaded from YAML.

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

@dataclass
class ThresholdConfig:
    """Alert threshold configuration for a severity level."""
    distance_pct: Decimal      # Distance from zone as percentage
    min_density: Decimal       # Minimum cluster size in USD

@dataclass
class CooldownConfig:
    """Rate limiting configuration."""
    per_zone_minutes: int      # Cooldown per zone (default: 60)
    max_daily_alerts: int      # Max alerts per day (default: 10)

@dataclass
class ChannelConfig:
    """Notification channel configuration."""
    enabled: bool
    severity_filter: list[str]  # ["critical", "warning", "info"]
    # Channel-specific fields set via environment variables

@dataclass
class DiscordChannelConfig(ChannelConfig):
    """Discord webhook channel."""
    webhook_url: Optional[str] = None  # From DISCORD_WEBHOOK_URL env

@dataclass
class TelegramChannelConfig(ChannelConfig):
    """Telegram bot channel."""
    bot_token: Optional[str] = None    # From TELEGRAM_BOT_TOKEN env
    chat_id: Optional[str] = None      # From TELEGRAM_CHAT_ID env

@dataclass
class EmailChannelConfig(ChannelConfig):
    """Email SMTP channel."""
    recipients: list[str] = None       # List of email addresses

@dataclass
class DataSourceConfig:
    """Data source endpoints."""
    price_endpoint: str                # Binance price API
    heatmap_endpoint: str              # Internal heatmap API
    symbol: str                        # Trading pair (BTCUSDT)

@dataclass
class AlertConfig:
    """Root configuration for liquidation alerts."""
    enabled: bool
    thresholds: dict[str, ThresholdConfig]  # "critical", "warning", "info"
    cooldown: CooldownConfig
    data_sources: DataSourceConfig
    channels: dict[str, ChannelConfig]      # "discord", "telegram", "email"
```

**Validation Rules**:
- `distance_pct` must be > 0 and <= 100
- `min_density` must be >= 0
- `per_zone_minutes` must be >= 1
- `max_daily_alerts` must be >= 1
- At least one channel must be enabled

---

### 1.2 LiquidationZone

Represents a liquidation level from the heatmap API.

```python
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class LiquidationZone:
    """A liquidation zone from heatmap data."""
    price: Decimal              # Zone price level
    long_density: Decimal       # Long liquidation volume at this level
    short_density: Decimal      # Short liquidation volume at this level

    @property
    def total_density(self) -> Decimal:
        """Total liquidation volume at this zone."""
        return self.long_density + self.short_density

    @property
    def dominant_side(self) -> str:
        """Returns 'long' or 'short' based on higher density."""
        return "long" if self.long_density > self.short_density else "short"

@dataclass
class ZoneProximity:
    """Zone with calculated distance from current price."""
    zone: LiquidationZone
    current_price: Decimal
    distance_pct: Decimal       # Absolute percentage distance
    direction: str              # "above" or "below" current price

    @property
    def zone_key(self) -> str:
        """Unique key for cooldown tracking."""
        bucket = int(self.zone.price / 100) * 100
        return f"{bucket}_{self.zone.dominant_side}"
```

**Calculation**:
```python
distance_pct = abs(current_price - zone.price) / current_price * 100
direction = "above" if zone.price > current_price else "below"
```

---

### 1.3 Alert

An alert event to be dispatched to notification channels.

```python
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

class AlertSeverity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

class DeliveryStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"   # Some channels failed
    FAILED = "failed"

@dataclass
class Alert:
    """An alert event with delivery tracking."""
    id: Optional[int] = None           # DB primary key (assigned on insert)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    symbol: str = "BTCUSDT"
    current_price: Decimal = Decimal("0")
    zone_price: Decimal = Decimal("0")
    zone_density: Decimal = Decimal("0")
    zone_side: str = "long"            # "long" or "short"
    distance_pct: Decimal = Decimal("0")
    severity: AlertSeverity = AlertSeverity.INFO
    channels_sent: list[str] = field(default_factory=list)  # ["discord", "telegram"]
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "current_price": str(self.current_price),
            "zone_price": str(self.zone_price),
            "zone_density": str(self.zone_density),
            "zone_side": self.zone_side,
            "distance_pct": str(self.distance_pct),
            "severity": self.severity.value,
            "channels_sent": self.channels_sent,
            "delivery_status": self.delivery_status.value,
            "error_message": self.error_message,
        }
```

---

### 1.4 AlertCooldown

Tracks cooldown state for rate limiting.

```python
from dataclasses import dataclass
from datetime import datetime, date

@dataclass
class AlertCooldown:
    """Cooldown state for a specific zone."""
    zone_key: str               # "{bucket}_{side}" or "{symbol}_{bucket}_{side}"
    last_alert_time: datetime   # Last alert sent for this zone
    alert_count_today: int      # Alerts sent today (resets at UTC midnight)
    last_reset_date: date       # Date of last daily counter reset

    def is_on_cooldown(self, cooldown_minutes: int) -> bool:
        """Check if zone is still on cooldown."""
        from datetime import timedelta
        return datetime.utcnow() - self.last_alert_time < timedelta(minutes=cooldown_minutes)

    def should_reset_daily_count(self) -> bool:
        """Check if daily counter should reset (new UTC day)."""
        return date.today() > self.last_reset_date
```

---

## 2. Database Schema

### 2.1 Alerts Database (DuckDB)

**File**: `data/processed/alerts.duckdb`

```sql
-- Liquidation alerts history
CREATE TABLE IF NOT EXISTS liquidation_alerts (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    symbol VARCHAR(20) NOT NULL,
    current_price DECIMAL(18,8) NOT NULL,
    zone_price DECIMAL(18,8) NOT NULL,
    zone_density DECIMAL(18,8) NOT NULL,
    zone_side VARCHAR(5) NOT NULL CHECK (zone_side IN ('long', 'short')),
    distance_pct DECIMAL(8,4) NOT NULL,
    severity VARCHAR(10) NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    channels_sent VARCHAR(255),      -- JSON array: '["discord", "telegram"]'
    delivery_status VARCHAR(50) NOT NULL CHECK (delivery_status IN ('pending', 'success', 'partial', 'failed')),
    error_message TEXT
);

-- Index for querying recent alerts
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON liquidation_alerts(timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON liquidation_alerts(symbol);

-- Cooldown state persistence
CREATE TABLE IF NOT EXISTS alert_cooldowns (
    zone_key VARCHAR(100) PRIMARY KEY,  -- "{symbol}_{bucket}_{side}"
    last_alert_time TIMESTAMP NOT NULL,
    alert_count_today INTEGER DEFAULT 0,
    last_reset_date DATE NOT NULL
);

-- Index for cooldown lookups
CREATE INDEX IF NOT EXISTS idx_cooldowns_zone ON alert_cooldowns(zone_key);
```

### 2.2 Schema Notes

- **WAL Mode**: Enable for concurrent reads during alert writes
  ```sql
  PRAGMA wal_autocheckpoint = 1000;
  ```
- **Retention**: Daily cleanup of alerts older than 90 days
  ```sql
  DELETE FROM liquidation_alerts
  WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '90 days';
  ```

---

## 3. State Transitions

### 3.1 Alert Lifecycle

```
                  ┌─────────────┐
                  │   CREATED   │
                  └──────┬──────┘
                         │
                         ▼
          ┌──────────────────────────────┐
          │     EVALUATE THRESHOLDS      │
          │  (distance < threshold?)     │
          └──────────────┬───────────────┘
                         │
           ┌─────────────┴─────────────┐
           │                           │
           ▼                           ▼
    ┌─────────────┐             ┌─────────────┐
    │  NO ALERT   │             │ CHECK COOL- │
    │  (discard)  │             │    DOWN     │
    └─────────────┘             └──────┬──────┘
                                       │
                          ┌────────────┴────────────┐
                          │                         │
                          ▼                         ▼
                   ┌─────────────┐          ┌─────────────┐
                   │ ON COOLDOWN │          │   DISPATCH  │
                   │  (skip)     │          │   ALERT     │
                   └─────────────┘          └──────┬──────┘
                                                   │
                                    ┌──────────────┴──────────────┐
                                    │                              │
                                    ▼                              ▼
                             ┌─────────────┐               ┌─────────────┐
                             │   SUCCESS   │               │   PARTIAL   │
                             │ (all sent)  │               │ (some fail) │
                             └─────────────┘               └─────────────┘
                                                                  │
                                                                  ▼
                                                           ┌─────────────┐
                                                           │   FAILED    │
                                                           │ (all fail)  │
                                                           └─────────────┘
```

### 3.2 Cooldown State Machine

```
┌───────────────────┐
│  ZONE DETECTED    │
│  (new proximity)  │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐        ┌───────────────────┐
│  CHECK COOLDOWN   │───────▶│  ON COOLDOWN      │
│  (query DB)       │  yes   │  (skip alert)     │
└─────────┬─────────┘        └───────────────────┘
          │ no
          ▼
┌───────────────────┐
│  CHECK DAILY      │        ┌───────────────────┐
│  LIMIT            │───────▶│  LIMIT REACHED    │
└─────────┬─────────┘  yes   │  (skip alert)     │
          │ no               └───────────────────┘
          ▼
┌───────────────────┐
│  SEND ALERT       │
│  UPDATE COOLDOWN  │
└───────────────────┘
```

---

## 4. Relationships

```
AlertConfig ──────────────────────────────────────┐
    │                                              │
    │ contains                                     │
    ▼                                              │
ThresholdConfig (critical, warning, info)         │
    │                                              │
    │ defines thresholds for                       │
    ▼                                              │
LiquidationZone ──────▶ ZoneProximity ─────────┐  │
    │                       │                   │  │
    │ transformed to        │ evaluated by      │  │
    │                       ▼                   │  │
    │              AlertEvaluationEngine        │  │
    │                       │                   │  │
    │                       │ produces          │  │
    │                       ▼                   │  │
    └──────────────────▶ Alert ◀───────────────┘  │
                            │                      │
                            │ checked against      │
                            ▼                      │
                      AlertCooldown                │
                            │                      │
                            │ if allowed           │
                            ▼                      │
                      AlertDispatcher ◀────────────┘
                            │                 uses config
                            │ sends to
                            ▼
                ┌───────────────────────┐
                │  Discord │ Telegram │ Email
                └───────────────────────┘
```

---

## 5. Validation Summary

| Entity | Field | Validation |
|--------|-------|------------|
| AlertConfig | enabled | boolean |
| ThresholdConfig | distance_pct | 0 < x <= 100 |
| ThresholdConfig | min_density | x >= 0 |
| CooldownConfig | per_zone_minutes | x >= 1 |
| CooldownConfig | max_daily_alerts | x >= 1 |
| LiquidationZone | price | x > 0 |
| LiquidationZone | long_density | x >= 0 |
| LiquidationZone | short_density | x >= 0 |
| Alert | zone_side | in ["long", "short"] |
| Alert | severity | in ["critical", "warning", "info"] |
| Alert | delivery_status | in ["pending", "success", "partial", "failed"] |
| AlertCooldown | zone_key | non-empty string, format: "{bucket}_{side}" |

---

**Next**: Generate contracts and quickstart documentation.
