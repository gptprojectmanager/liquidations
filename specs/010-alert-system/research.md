# Research: Liquidation Zone Alert System

**Date**: 2025-12-29
**Feature**: spec-010 (Alert System MVP)
**Status**: Complete

---

## 1. Dependency Analysis

### 1.1 Discord Webhook Integration

**Decision**: Use `httpx` (already in project) for webhook calls

**Rationale**:
- `httpx` already in `pyproject.toml` for async HTTP
- Discord webhook is simple POST with JSON payload
- No need for `discord.py` library (overkill for webhooks)

**Alternatives Rejected**:
- `discord.py`: Full Discord bot library, 15MB+ dependency, not needed for webhook-only
- `requests`: Sync-only, `httpx` is already async-compatible

**Webhook Format** (Discord Embed):
```python
{
    "embeds": [{
        "title": "LIQUIDATION ZONE ALERT - CRITICAL",
        "description": "Price approaching major liquidation zone",
        "color": 0xFF0000,  # Red for critical
        "fields": [
            {"name": "Symbol", "value": "BTCUSDT", "inline": True},
            {"name": "Current Price", "value": "$49,500.00", "inline": True},
            {"name": "Zone Price", "value": "$49,000.00", "inline": True},
            {"name": "Distance", "value": "1.01%", "inline": True},
            {"name": "Cluster Size", "value": "$12.5M", "inline": True},
            {"name": "Side", "value": "SHORT", "inline": True},
        ],
        "footer": {"text": "Generated: 2025-12-28 14:35:22 UTC"}
    }]
}
```

### 1.2 Telegram Bot Integration

**Decision**: Use `httpx` for Telegram Bot API calls

**Rationale**:
- Telegram Bot API is REST-based, no special library needed
- Endpoint: `https://api.telegram.org/bot{token}/sendMessage`
- Supports Markdown formatting for rich messages

**Alternatives Rejected**:
- `python-telegram-bot`: Full async framework, adds complexity
- `telethon`: User-auth focused, not bot-friendly

**Message Format** (Telegram Markdown):
```
*LIQUIDATION ZONE ALERT - CRITICAL*

Symbol: BTCUSDT
Current Price: $49,500.00
Liquidation Zone: $49,000.00 (SHORT)
Distance: 1.01% (Approaching)
Cluster Size: $12.5M

_Generated: 2025-12-28 14:35:22 UTC_
```

### 1.3 Email (SMTP) Integration

**Decision**: Use stdlib `smtplib` + `email.mime`

**Rationale**:
- Already in Python stdlib, zero new dependencies
- Supports TLS/SSL encryption
- Proven reliable for alert systems

**Configuration Pattern**:
```python
# Environment variables (secrets)
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USERNAME")
SMTP_PASS = os.getenv("SMTP_PASSWORD")
```

---

## 2. Existing Infrastructure Reuse

### 2.1 Alert Settings YAML

**Finding**: `config/alert_settings.yaml` already exists for validation alerts

**Decision**: Extend existing file with `liquidation_alerts` section

**Rationale**:
- Single config file for all alerts (consistency)
- Existing YAML loader pattern in codebase
- Channels section already defined (Discord, Slack, PagerDuty)

**Schema Extension**:
```yaml
# NEW: Add to existing alert_settings.yaml
liquidation_alerts:
  enabled: true
  thresholds:
    critical: {distance_pct: 1.0, min_density: 10000000}
    warning: {distance_pct: 3.0, min_density: 5000000}
    info: {distance_pct: 5.0, min_density: 1000000}
  cooldown:
    per_zone_minutes: 60
    max_daily_alerts: 10
  data_sources:
    price_endpoint: "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    heatmap_endpoint: "http://localhost:8000/liquidations/heatmap-timeseries"
    symbol: "BTCUSDT"
```

### 2.2 Heatmap Timeseries API

**Finding**: `/liquidations/heatmap-timeseries` endpoint exists and returns zone data

**Response Structure** (from main.py):
```python
{
    "data": [
        {
            "timestamp": "2025-12-28T14:00:00",
            "levels": [
                {"price": 49000.0, "long_density": 1250000.0, "short_density": 8500000.0},
                {"price": 49100.0, "long_density": 800000.0, "short_density": 5200000.0},
                ...
            ]
        }
    ],
    "meta": {
        "symbol": "BTCUSDT",
        "total_long_volume": 45000000.0,
        "total_short_volume": 78000000.0,
        ...
    }
}
```

**Zone Extraction Strategy**:
1. Fetch latest snapshot (last item in `data` array)
2. Filter levels by `long_density + short_density >= min_density`
3. Calculate distance: `abs(current_price - level.price) / current_price * 100`
4. Sort by distance, check against thresholds

### 2.3 DuckDB Service

**Finding**: `DuckDBService` singleton pattern exists in `src/liquidationheatmap/ingestion/db_service.py`

**Decision**: Create separate alerts database (`data/processed/alerts.duckdb`)

**Rationale**:
- Avoids lock contention with main heatmap database
- Alerts are independent domain (separation of concerns)
- Can be backed up/archived separately

---

## 3. Best Practices Research

### 3.1 Alert System Patterns

**Pattern: Circuit Breaker for Channels**

When a channel fails repeatedly (3+ times), disable it temporarily:
```python
class ChannelCircuitBreaker:
    def __init__(self, failure_threshold=3, reset_timeout=300):
        self.failures = 0
        self.last_failure_time = None
        self.is_open = False

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.is_open = True
            self.last_failure_time = time.time()

    def is_available(self):
        if self.is_open and time.time() - self.last_failure_time > self.reset_timeout:
            self.is_open = False
            self.failures = 0
        return not self.is_open
```

**Pattern: Exponential Backoff**

```python
def exponential_backoff(attempt, base=1, max_delay=60):
    """Calculate delay: 1s, 2s, 4s, 8s, ... up to max_delay"""
    delay = min(base * (2 ** attempt), max_delay)
    return delay + random.uniform(0, 0.1 * delay)  # Add jitter
```

### 3.2 Rate Limiting Best Practices

**Per-Zone Cooldown Strategy**:
```sql
-- Zone key: "{symbol}_{price_bucket}_{side}"
CREATE TABLE alert_cooldowns (
    zone_key VARCHAR PRIMARY KEY,
    last_alert_time TIMESTAMP NOT NULL,
    alert_count INTEGER DEFAULT 1
);

-- Check cooldown before alerting
SELECT 1 FROM alert_cooldowns
WHERE zone_key = ?
  AND last_alert_time > NOW() - INTERVAL '60 minutes'
```

**Daily Limit Strategy**:
```sql
-- Count alerts today (UTC)
SELECT COUNT(*) FROM liquidation_alerts
WHERE DATE(timestamp) = CURRENT_DATE
  AND symbol = ?
```

### 3.3 Message Deduplication

**Decision**: Use zone_key + timestamp truncated to cooldown window

**Implementation**:
```python
def get_zone_key(symbol: str, zone_price: float, side: str) -> str:
    # Round price to nearest bucket for stability
    bucket = int(zone_price / 100) * 100
    return f"{symbol}_{bucket}_{side}"
```

---

## 4. Technology Decisions Summary

| Component | Technology | Justification |
|-----------|------------|---------------|
| Discord client | httpx | Already in project, async-ready |
| Telegram client | httpx | REST API, no special library |
| Email client | smtplib (stdlib) | Zero new dependencies |
| Config storage | YAML (pyyaml) | Consistent with existing config |
| State persistence | DuckDB | Matches project stack, atomic writes |
| Background runner | APScheduler | Already in pyproject.toml |

---

## 5. Open Questions Resolved

### Q1: Should alerts use WebSocket or polling?

**Decision**: Polling (5-minute cron or daemon loop)

**Rationale**:
- Simpler implementation
- Matches heatmap cache TTL (5 minutes)
- WebSocket adds complexity without significant latency benefit
- Alert latency <60s requirement met with 1-minute polling

### Q2: How to handle multi-symbol support?

**Decision**: BTCUSDT only for MVP (P1)

**Rationale**:
- Reduce scope for MVP
- Multi-symbol is P3 enhancement per spec
- Config structure allows easy extension later

### Q3: Should alert history be in main DuckDB or separate?

**Decision**: Separate `data/processed/alerts.duckdb`

**Rationale**:
- Avoids lock contention during ingestion
- Independent lifecycle (alerts vs heatmap data)
- Simpler backup/retention management

---

## 6. Implementation Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Binance API downtime | Low | Medium | Fallback to cached price, skip cycle |
| Discord webhook rate limit | Low | Low | 1 alert/minute is well under limit |
| Database corruption | Very Low | High | WAL mode, regular backups |
| Alert storm during volatility | Medium | Medium | Cooldown + daily limit |

---

## 7. References

- [Discord Webhook Documentation](https://discord.com/developers/docs/resources/webhook)
- [Telegram Bot API](https://core.telegram.org/bots/api#sendmessage)
- [Python smtplib Documentation](https://docs.python.org/3/library/smtplib.html)
- [DuckDB WAL Mode](https://duckdb.org/docs/sql/pragmas.html#wal_autocheckpoint)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)

---

**Status**: All NEEDS CLARIFICATION items resolved. Ready for Phase 1 design.
