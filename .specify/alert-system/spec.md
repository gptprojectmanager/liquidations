# Feature Specification: Liquidation Zone Alert System

**Feature Branch**: `alert-system-mvp`
**Created**: 2025-12-28
**Status**: Draft
**Priority**: P1 - High Value (Real-time risk monitoring)
**Estimated Effort**: 2-3 days (MVP)

---

## 1. Problem Statement

### Current State
- Liquidation heatmap visualizes high-density liquidation zones
- Users must manually monitor charts to detect price approaching danger zones
- No proactive notifications when price moves toward liquidation clusters

### Opportunity
- Alert traders BEFORE price hits major liquidation zones
- Enable automated risk management strategies
- Reduce manual monitoring burden

### Risk Without Alerts
| Scenario | Impact |
|----------|--------|
| Price approaches liquidation zone | Traders miss opportunity to adjust positions |
| Major liquidation cascade | No advance warning for risk management |
| Funding rate spikes | Positions get liquidated without notification |

---

## 2. User Scenarios & Testing

### User Story 1 - Price Proximity Alert (Priority: P1)

A trader wants to be notified when BTC price moves within 2% of a high-density liquidation zone (>$10M cluster).

**Why this priority**: Core value proposition - prevents unexpected liquidations

**Independent Test**: Configure threshold via config file, trigger test alert when price approaches zone

**Acceptance Scenarios**:

1. **Given** BTC price is $50,000 and liquidation cluster at $49,000 (2% away)
   **When** alert threshold is set to 2%
   **Then** alert is sent via configured channels (Discord/Telegram/Email)

2. **Given** alert already sent for zone at $49,000
   **When** price still within threshold (no cooldown expired)
   **Then** no duplicate alert sent (rate limiting works)

3. **Given** multiple liquidation zones detected
   **When** price approaches closest high-density zone
   **Then** alert prioritizes by density and proximity

---

### User Story 2 - Multi-Channel Delivery (Priority: P1)

A trader configures alerts to be sent to Discord webhook and Telegram bot simultaneously.

**Why this priority**: Flexibility in notification delivery is core requirement

**Independent Test**: Configure multiple channels, verify test alert reaches all enabled channels

**Acceptance Scenarios**:

1. **Given** Discord webhook and Telegram bot configured in alert_config.yaml
   **When** alert triggers
   **Then** message sent to both channels with consistent formatting

2. **Given** Discord webhook fails (network error)
   **When** alert triggers
   **Then** Telegram delivery still succeeds (channels independent)

3. **Given** no channels configured
   **When** alert would trigger
   **Then** error logged, no crash, alert skipped

---

### User Story 3 - Configurable Thresholds (Priority: P2)

A trader wants different alert thresholds for different risk levels (critical <1%, warning <3%, info <5%).

**Why this priority**: Enables fine-tuned risk management strategies

**Independent Test**: Set multiple threshold tiers in config, verify correct severity levels

**Acceptance Scenarios**:

1. **Given** thresholds: critical=1%, warning=3%, info=5%
   **When** price is 0.8% from liquidation zone
   **Then** alert sent with "CRITICAL" severity

2. **Given** same threshold configuration
   **When** price is 2.5% from liquidation zone
   **Then** alert sent with "WARNING" severity

3. **Given** user configures Discord for critical only, Telegram for all
   **When** warning-level alert triggers
   **Then** only Telegram receives notification

---

### User Story 4 - Alert Frequency Control (Priority: P2)

A trader wants to limit alerts to max 1 per zone per hour to avoid notification spam.

**Why this priority**: Prevents alert fatigue while maintaining usefulness

**Independent Test**: Trigger multiple alerts for same zone, verify cooldown enforced

**Acceptance Scenarios**:

1. **Given** cooldown period is 60 minutes
   **When** alert sent for zone at $49,000
   **Then** subsequent alerts for same zone suppressed for 60 minutes

2. **Given** cooldown active for zone A
   **When** price approaches different zone B
   **Then** alert for zone B sent immediately (cooldowns per-zone)

3. **Given** max 10 alerts per day configured
   **When** 10 alerts already sent
   **Then** further alerts suppressed until next UTC day

---

### Edge Cases

- **What happens when API `/liquidations/heatmap-timeseries` is unreachable?**
  → Log error, retry with exponential backoff (max 3 attempts), skip alert if fails

- **What happens when multiple zones have same density?**
  → Alert for closest zone first, batch others if within same threshold tier

- **What happens when price moves rapidly through multiple zones?**
  → Cooldown prevents spam, alert for highest-density zone only

- **What happens when Discord/Telegram webhook is invalid?**
  → Log error, mark channel as failed, continue with other channels

- **What happens when database is locked during alert check?**
  → Retry with backoff, skip alert cycle if timeout, log warning

---

## 3. Requirements

### Functional Requirements

- **FR-001**: System MUST fetch current price from Binance API or `/data/current-price` endpoint
- **FR-002**: System MUST fetch liquidation zones from `/liquidations/heatmap-timeseries` endpoint
- **FR-003**: System MUST calculate distance percentage between current price and each liquidation zone
- **FR-004**: System MUST send alerts when distance < threshold (configurable %, default 2%)
- **FR-005**: System MUST support Discord webhook notifications
- **FR-006**: System MUST support Telegram bot notifications
- **FR-007**: System MUST support Email (SMTP) notifications
- **FR-008**: System MUST enforce per-zone cooldown period (default 60 minutes)
- **FR-009**: System MUST enforce daily alert limit (default 10 alerts/day)
- **FR-010**: System MUST log all alert events to DuckDB for history tracking
- **FR-011**: System MUST be runnable as cron job or continuous background service
- **FR-012**: System MUST handle API failures gracefully (retry + skip)

### Non-Functional Requirements

- **NFR-001**: Alert latency < 60 seconds from threshold crossing to notification delivery
- **NFR-002**: Configuration via YAML file (extend existing `config/alert_settings.yaml`)
- **NFR-003**: No external dependencies beyond existing stack (requests, pyyaml, duckdb)
- **NFR-004**: Memory footprint < 100MB for background service
- **NFR-005**: Secrets (webhook URLs, API keys) via environment variables

### Key Entities

- **AlertConfig**: Thresholds, channel configurations, cooldown settings
- **LiquidationZone**: Price level, density (volume), side (long/short), cluster size
- **Alert**: Timestamp, zone details, severity, channels sent, delivery status
- **AlertHistory**: Persistent log of all alerts (DuckDB table)

---

## 4. Technical Design

### 4.1 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ALERT MONITORING LOOP                     │
│  (Cron job: */5 * * * * or continuous daemon)                │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐       ┌──────────────────────┐         │
│  │ Binance API      │       │ Heatmap API          │         │
│  │ /ticker/price    │       │ /heatmap-timeseries  │         │
│  └────────┬─────────┘       └──────────┬───────────┘         │
│           │                             │                     │
│           ▼                             ▼                     │
│  ┌────────────────────────────────────────────────┐          │
│  │        Alert Evaluation Engine                 │          │
│  │  - Calculate distance to zones                 │          │
│  │  - Check thresholds (critical/warning/info)    │          │
│  │  - Apply cooldown filters                      │          │
│  │  - Apply daily limit                           │          │
│  └─────────────────┬──────────────────────────────┘          │
│                    │                                          │
│                    ▼                                          │
│  ┌────────────────────────────────────────────────┐          │
│  │         Alert Dispatcher                       │          │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐     │          │
│  │  │ Discord  │  │ Telegram │  │ Email    │     │          │
│  │  │ Webhook  │  │ Bot API  │  │ SMTP     │     │          │
│  │  └──────────┘  └──────────┘  └──────────┘     │          │
│  └─────────────────┬──────────────────────────────┘          │
│                    │                                          │
│                    ▼                                          │
│  ┌────────────────────────────────────────────────┐          │
│  │      Alert History (DuckDB)                    │          │
│  │  - Log all alerts                              │          │
│  │  - Track cooldown state                        │          │
│  │  - Daily counter                               │          │
│  └────────────────────────────────────────────────┘          │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 4.2 Configuration Schema

Extend `config/alert_settings.yaml`:

```yaml
# Liquidation Zone Alerts
liquidation_alerts:
  enabled: true

  # Alert thresholds (distance from zone as %)
  thresholds:
    critical:
      distance_pct: 1.0      # Alert when within 1%
      min_density: 10000000  # Min $10M cluster size
    warning:
      distance_pct: 3.0      # Alert when within 3%
      min_density: 5000000   # Min $5M cluster size
    info:
      distance_pct: 5.0      # Alert when within 5%
      min_density: 1000000   # Min $1M cluster size

  # Rate limiting
  cooldown:
    per_zone_minutes: 60     # Max 1 alert per zone per hour
    max_daily_alerts: 10     # Total alerts per day

  # Data sources
  data_sources:
    price_endpoint: "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    heatmap_endpoint: "http://localhost:8000/liquidations/heatmap-timeseries"
    symbol: "BTCUSDT"

  # Alert channels (same as existing config)
  channels:
    discord:
      enabled: true
      webhook_url: null  # Set via DISCORD_WEBHOOK_URL env var
      severity_filter: ["critical", "warning", "info"]

    telegram:
      enabled: false
      bot_token: null    # Set via TELEGRAM_BOT_TOKEN env var
      chat_id: null      # Set via TELEGRAM_CHAT_ID env var
      severity_filter: ["critical", "warning"]

    email:
      enabled: false
      recipients: ["trader@example.com"]
      severity_filter: ["critical"]

  # Alert history
  history:
    enabled: true
    db_path: "data/processed/alerts.duckdb"
    retention_days: 90
```

### 4.3 Database Schema

New DuckDB table in `data/processed/alerts.duckdb`:

```sql
CREATE TABLE IF NOT EXISTS liquidation_alerts (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    current_price DECIMAL(18,8) NOT NULL,
    zone_price DECIMAL(18,8) NOT NULL,
    zone_density DECIMAL(18,8) NOT NULL,
    zone_side VARCHAR(5) NOT NULL,  -- 'long' or 'short'
    distance_pct DECIMAL(8,4) NOT NULL,
    severity VARCHAR(10) NOT NULL,  -- 'critical', 'warning', 'info'
    channels_sent VARCHAR(255),     -- JSON array: ["discord", "telegram"]
    delivery_status VARCHAR(50),    -- 'success', 'partial', 'failed'
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS alert_cooldowns (
    zone_key VARCHAR(100) PRIMARY KEY,  -- "{symbol}_{zone_price}_{side}"
    last_alert_time TIMESTAMP NOT NULL,
    alert_count_today INTEGER DEFAULT 0,
    last_reset_date DATE NOT NULL
);
```

### 4.4 Alert Message Format

**Discord/Telegram Message Template**:

```
🚨 LIQUIDATION ZONE ALERT - CRITICAL

Symbol: BTCUSDT
Current Price: $49,500.00
Liquidation Zone: $49,000.00 (SHORT)
Distance: 1.01% (⬇️ Approaching)
Cluster Size: $12.5M

⚠️ Price approaching major liquidation zone!
Potential cascade if level breaks.

Generated: 2025-12-28 14:35:22 UTC
```

**Email Subject**: `[CRITICAL] BTC Liquidation Alert - $49K Zone (1.01% away)`

---

## 5. Implementation Plan (MVP)

### Phase 1: Core Alert Engine (Day 1)

| Task | Description | Effort |
|------|-------------|--------|
| 1.1 | Create `src/alerts/` module structure | 30m |
| 1.2 | Implement config loader (`alert_config.py`) | 1h |
| 1.3 | Implement zone fetcher (API client) | 1h |
| 1.4 | Implement distance calculator | 1h |
| 1.5 | Implement cooldown manager (DuckDB) | 2h |
| 1.6 | Write unit tests for core logic | 2h |

**Deliverable**: `src/alerts/engine.py`, `src/alerts/config.py`, `src/alerts/cooldown.py`

### Phase 2: Channel Integrations (Day 1-2)

| Task | Description | Effort |
|------|-------------|--------|
| 2.1 | Implement Discord webhook client | 1h |
| 2.2 | Implement Telegram bot client | 1h |
| 2.3 | Implement Email (SMTP) client | 1h |
| 2.4 | Implement message formatter | 1h |
| 2.5 | Write integration tests (mock webhooks) | 2h |

**Deliverable**: `src/alerts/channels/`, `tests/test_alerts/test_channels.py`

### Phase 3: Monitoring Loop (Day 2)

| Task | Description | Effort |
|------|-------------|--------|
| 3.1 | Implement main monitoring loop | 2h |
| 3.2 | Add error handling + retry logic | 1h |
| 3.3 | Add logging and metrics | 1h |
| 3.4 | Create CLI script (`scripts/run_alerts.py`) | 1h |

**Deliverable**: `scripts/run_alerts.py`, systemd service file (optional)

### Phase 4: Testing & Documentation (Day 3)

| Task | Description | Effort |
|------|-------------|--------|
| 4.1 | End-to-end test (mock API + channels) | 2h |
| 4.2 | Manual testing with real webhooks | 1h |
| 4.3 | Update ARCHITECTURE.md | 1h |
| 4.4 | Write user guide (README section) | 1h |
| 4.5 | Setup cron job example | 30m |

**Deliverable**: Documentation, test coverage >80%

---

## 6. Success Criteria

### Measurable Outcomes

- **SC-001**: Alert latency < 60 seconds from threshold crossing to notification
- **SC-002**: Zero missed alerts when API is healthy (100% delivery rate)
- **SC-003**: Cooldown prevents spam (max 1 alert per zone per hour enforced)
- **SC-004**: Multi-channel delivery success rate > 95% (handles individual channel failures)
- **SC-005**: Configuration changes take effect without code modification (YAML only)
- **SC-006**: Alert history stored for 90 days with queryable interface

---

## 7. Future Enhancements (Out of Scope for MVP)

- **P3**: Web dashboard for alert history visualization
- **P3**: SMS alerts via Twilio integration
- **P3**: Slack integration
- **P3**: PagerDuty integration for critical alerts
- **P3**: Alert rules engine (e.g., "only alert if funding rate > 0.1%")
- **P3**: Multi-symbol support (ETH, SOL, etc.)
- **P3**: Machine learning for adaptive thresholds

---

## 8. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| API rate limits (Binance) | Cache price for 10s, use heatmap endpoint for zones |
| Channel downtime (Discord/Telegram) | Independent delivery, retry with backoff |
| Database lock during alert write | Use WAL mode, quick transactions, timeout handling |
| Alert spam during high volatility | Cooldown + daily limit enforced |
| Configuration errors | Schema validation on startup, fail-fast |

---

## 9. Dependencies

### Existing Infrastructure
- `/liquidations/heatmap-timeseries` API endpoint (✅ exists)
- `config/alert_settings.yaml` (✅ exists, needs extension)
- DuckDB service singleton (✅ exists)

### New Dependencies
- `requests` - HTTP client for webhooks (already in project)
- `python-telegram-bot` - Telegram API client (NEW - add to pyproject.toml)
- Existing `smtplib` for email (stdlib)

---

## 10. Testing Strategy

### Unit Tests
- Config parser handles missing/invalid values
- Distance calculator returns correct percentages
- Cooldown manager enforces time limits
- Message formatter generates valid templates

### Integration Tests
- Mock API responses (price + heatmap)
- Mock webhook endpoints (Discord/Telegram)
- Database writes/reads for history

### End-to-End Tests
- Full alert cycle with test configuration
- Multi-channel delivery verification
- Cooldown state persistence across runs

---

## Appendix: Example Usage

### Setup

```bash
# 1. Configure alert settings
cp config/alert_settings.yaml config/alert_settings.yaml.bak
# Edit config/alert_settings.yaml

# 2. Set environment variables
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
export TELEGRAM_CHAT_ID="@your_channel"

# 3. Initialize alert database
uv run python scripts/init_alert_db.py

# 4. Test alert (manual trigger)
uv run python scripts/run_alerts.py --test

# 5. Run continuous monitoring
uv run python scripts/run_alerts.py --daemon

# OR setup cron (check every 5 minutes)
# */5 * * * * cd /path/to/LiquidationHeatmap && uv run python scripts/run_alerts.py
```

### Query Alert History

```sql
-- Recent alerts
SELECT * FROM liquidation_alerts
ORDER BY timestamp DESC
LIMIT 10;

-- Alert frequency by severity
SELECT severity, COUNT(*) as count, AVG(distance_pct) as avg_distance
FROM liquidation_alerts
WHERE timestamp > NOW() - INTERVAL 7 DAY
GROUP BY severity;

-- Delivery success rate
SELECT
    delivery_status,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) as percentage
FROM liquidation_alerts
GROUP BY delivery_status;
```

---

**Maintained by**: Claude Code
**Last Updated**: 2025-12-28
**Version**: 1.0 (MVP Spec)
