# Alert System - Implementation Tasks

**Feature**: Liquidation Zone Alert System
**Branch**: `alert-system-mvp`
**Estimated Effort**: 2-3 days
**Status**: Ready for Implementation

---

## Task Dependency Graph

```
[1.0] → [1.1] → [1.2] → [1.3]
                        ↓
[2.0] → [2.1] → [2.2] → [2.3]
                        ↓
[3.0] → [3.1] ←─────────┘
         ↓
[4.0] → [4.1] → [4.2]
```

**Legend**: `→` = Sequential dependency, `↓` = Can parallelize

---

## Phase 1: Core Alert Engine

### Task 1.0: Setup Module Structure
**Priority**: P0 (Blocker)
**Estimated**: 30 minutes
**Dependencies**: None

**Description**: Create module structure for alert system

**Acceptance Criteria**:
- [ ] Create `src/alerts/` directory
- [ ] Create `src/alerts/__init__.py`
- [ ] Create `src/alerts/engine.py` (stub)
- [ ] Create `src/alerts/config.py` (stub)
- [ ] Create `src/alerts/cooldown.py` (stub)
- [ ] Create `src/alerts/channels/__init__.py`
- [ ] Create `tests/test_alerts/` directory
- [ ] Module imports work: `from alerts.engine import AlertEngine`

**Files to Create**:
```
src/alerts/
├── __init__.py
├── engine.py
├── config.py
├── cooldown.py
└── channels/
    ├── __init__.py
    ├── discord.py
    ├── telegram.py
    └── email.py

tests/test_alerts/
├── __init__.py
├── test_config.py
├── test_engine.py
├── test_cooldown.py
└── test_channels.py
```

---

### Task 1.1: Implement Alert Configuration Loader
**Priority**: P0 (Blocker)
**Estimated**: 1 hour
**Dependencies**: Task 1.0

**Description**: Load and validate alert configuration from YAML

**TDD Steps**:
1. **RED**: Write test `test_load_valid_config_returns_alert_config_object`
2. **GREEN**: Implement `AlertConfig.from_yaml(path)` class method
3. **RED**: Write test `test_missing_config_file_raises_file_not_found`
4. **GREEN**: Add file existence check
5. **RED**: Write test `test_invalid_threshold_raises_validation_error`
6. **GREEN**: Add Pydantic validation for thresholds

**Acceptance Criteria**:
- [ ] `AlertConfig` Pydantic model with all fields from spec
- [ ] `AlertConfig.from_yaml()` loads `config/alert_settings.yaml`
- [ ] Environment variable substitution for secrets (webhook URLs)
- [ ] Validation: `distance_pct` must be > 0 and < 100
- [ ] Validation: `min_density` must be >= 0
- [ ] Validation: `cooldown.per_zone_minutes` must be >= 1
- [ ] Default values for optional fields
- [ ] Test coverage > 90%

**Example Test**:
```python
def test_load_valid_config_returns_alert_config_object():
    """Config loader should parse YAML and return AlertConfig instance."""
    config = AlertConfig.from_yaml("config/alert_settings.yaml")

    assert config.liquidation_alerts.enabled is True
    assert config.liquidation_alerts.thresholds.critical.distance_pct == 1.0
    assert config.liquidation_alerts.channels.discord.enabled is True
```

**Files to Modify**:
- `src/alerts/config.py`
- `tests/test_alerts/test_config.py`
- `config/alert_settings.yaml` (extend with liquidation_alerts section)

---

### Task 1.2: Implement Distance Calculator
**Priority**: P0 (Blocker)
**Estimated**: 1 hour
**Dependencies**: Task 1.1

**Description**: Calculate percentage distance between current price and liquidation zones

**TDD Steps**:
1. **RED**: Write test `test_calculate_distance_returns_correct_percentage`
2. **GREEN**: Implement `calculate_distance_pct(current_price, zone_price)`
3. **RED**: Write test `test_filter_zones_by_threshold_returns_only_matching`
4. **GREEN**: Implement `filter_zones_by_threshold(zones, current_price, threshold)`
5. **RED**: Write test `test_prioritize_zones_returns_closest_highest_density_first`
6. **GREEN**: Implement `prioritize_zones(zones, current_price)`

**Acceptance Criteria**:
- [ ] `calculate_distance_pct()` returns absolute percentage (positive value)
- [ ] Formula: `distance_pct = abs(current_price - zone_price) / current_price * 100`
- [ ] `filter_zones_by_threshold()` returns only zones within threshold
- [ ] `filter_zones_by_threshold()` also filters by `min_density`
- [ ] `prioritize_zones()` sorts by: 1) distance (ascending), 2) density (descending)
- [ ] Handles edge case: current_price == zone_price (distance = 0%)
- [ ] Test coverage > 90%

**Example Test**:
```python
def test_calculate_distance_returns_correct_percentage():
    """Distance should be calculated as absolute percentage from current price."""
    current_price = Decimal("50000.00")
    zone_price = Decimal("49000.00")

    distance_pct = calculate_distance_pct(current_price, zone_price)

    assert distance_pct == Decimal("2.00")  # 1000/50000 * 100 = 2%
```

**Files to Modify**:
- `src/alerts/engine.py`
- `tests/test_alerts/test_engine.py`

---

### Task 1.3: Implement Cooldown Manager
**Priority**: P0 (Blocker)
**Estimated**: 2 hours
**Dependencies**: Task 1.2

**Description**: Track alert history and enforce cooldown periods using DuckDB

**TDD Steps**:
1. **RED**: Write test `test_is_on_cooldown_returns_true_when_recent_alert_exists`
2. **GREEN**: Implement `CooldownManager.is_on_cooldown(zone_key)`
3. **RED**: Write test `test_record_alert_stores_timestamp_in_database`
4. **GREEN**: Implement `CooldownManager.record_alert(zone_key, timestamp)`
5. **RED**: Write test `test_get_daily_count_returns_correct_number`
6. **GREEN**: Implement `CooldownManager.get_daily_count()`
7. **RED**: Write test `test_cleanup_old_records_removes_expired_cooldowns`
8. **GREEN**: Implement `CooldownManager.cleanup_old_records(retention_days)`

**Acceptance Criteria**:
- [ ] `CooldownManager` uses DuckDB singleton service
- [ ] `alert_cooldowns` table created on first use
- [ ] `is_on_cooldown()` checks if last alert within cooldown period
- [ ] `record_alert()` inserts/updates cooldown record with timestamp
- [ ] `get_daily_count()` resets at UTC midnight
- [ ] `zone_key` format: `{symbol}_{zone_price:.2f}_{side}`
- [ ] Handles database lock with retry (max 3 attempts)
- [ ] Test coverage > 90%

**Example Test**:
```python
def test_is_on_cooldown_returns_true_when_recent_alert_exists():
    """Cooldown should prevent duplicate alerts within configured period."""
    manager = CooldownManager(cooldown_minutes=60)
    zone_key = "BTCUSDT_49000.00_short"

    # Record alert now
    manager.record_alert(zone_key, datetime.utcnow())

    # Check if on cooldown
    assert manager.is_on_cooldown(zone_key) is True

    # Simulate 61 minutes later
    future_time = datetime.utcnow() + timedelta(minutes=61)
    with freeze_time(future_time):
        assert manager.is_on_cooldown(zone_key) is False
```

**Files to Modify**:
- `src/alerts/cooldown.py`
- `tests/test_alerts/test_cooldown.py`
- `scripts/init_alert_db.py` (new - initialize schema)

**Database Schema** (in `cooldown.py`):
```python
CREATE_COOLDOWNS_TABLE = """
CREATE TABLE IF NOT EXISTS alert_cooldowns (
    zone_key VARCHAR(100) PRIMARY KEY,
    last_alert_time TIMESTAMP NOT NULL,
    alert_count_today INTEGER DEFAULT 0,
    last_reset_date DATE NOT NULL
)
"""
```

---

## Phase 2: Channel Integrations

### Task 2.0: Implement Base Channel Interface
**Priority**: P0 (Blocker)
**Estimated**: 30 minutes
**Dependencies**: Task 1.0

**Description**: Define abstract base class for alert channels

**TDD Steps**:
1. **RED**: Write test `test_base_channel_send_raises_not_implemented`
2. **GREEN**: Create `BaseChannel` ABC with `send()` method

**Acceptance Criteria**:
- [ ] `BaseChannel` abstract class with `send(alert: Alert) -> bool` method
- [ ] All channel implementations inherit from `BaseChannel`
- [ ] `send()` returns `True` on success, `False` on failure
- [ ] Type hints for all methods

**Files to Modify**:
- `src/alerts/channels/base.py` (new)
- `tests/test_alerts/test_channels.py`

---

### Task 2.1: Implement Discord Webhook Channel
**Priority**: P1
**Estimated**: 1 hour
**Dependencies**: Task 2.0

**Description**: Send alerts to Discord via webhook

**TDD Steps**:
1. **RED**: Write test `test_discord_send_posts_to_webhook_url`
2. **GREEN**: Implement `DiscordChannel.send()` with requests.post
3. **RED**: Write test `test_discord_format_message_returns_embed_json`
4. **GREEN**: Implement `DiscordChannel._format_message()`
5. **RED**: Write test `test_discord_handles_webhook_failure_gracefully`
6. **GREEN**: Add try/except with retry logic

**Acceptance Criteria**:
- [ ] `DiscordChannel` inherits from `BaseChannel`
- [ ] Uses Discord webhook embed format (rich formatting)
- [ ] Includes severity color: critical=red, warning=yellow, info=blue
- [ ] Includes emoji: 🚨 critical, ⚠️ warning, ℹ️ info
- [ ] Webhook URL from environment variable `DISCORD_WEBHOOK_URL`
- [ ] Retries with exponential backoff (max 3 attempts)
- [ ] Logs error if webhook fails after retries
- [ ] Returns `True` on success, `False` on failure
- [ ] Test coverage > 90% (use `responses` library to mock HTTP)

**Example Test**:
```python
@responses.activate
def test_discord_send_posts_to_webhook_url():
    """Discord channel should POST formatted message to webhook URL."""
    webhook_url = "https://discord.com/api/webhooks/123/abc"
    responses.add(responses.POST, webhook_url, status=204)

    channel = DiscordChannel(webhook_url)
    alert = Alert(
        symbol="BTCUSDT",
        current_price=Decimal("49500"),
        zone_price=Decimal("49000"),
        zone_density=Decimal("12500000"),
        zone_side="short",
        distance_pct=Decimal("1.01"),
        severity="critical"
    )

    result = channel.send(alert)

    assert result is True
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == webhook_url
```

**Files to Modify**:
- `src/alerts/channels/discord.py` (new)
- `tests/test_alerts/test_channels.py`

**Discord Embed Format**:
```json
{
  "embeds": [{
    "title": "🚨 LIQUIDATION ZONE ALERT - CRITICAL",
    "color": 15158332,
    "fields": [
      {"name": "Symbol", "value": "BTCUSDT", "inline": true},
      {"name": "Current Price", "value": "$49,500.00", "inline": true},
      {"name": "Liquidation Zone", "value": "$49,000.00 (SHORT)", "inline": true},
      {"name": "Distance", "value": "1.01% (⬇️ Approaching)", "inline": true},
      {"name": "Cluster Size", "value": "$12.5M", "inline": true}
    ],
    "footer": {"text": "LiquidationHeatmap Alert System"},
    "timestamp": "2025-12-28T14:35:22.000Z"
  }]
}
```

---

### Task 2.2: Implement Telegram Bot Channel
**Priority**: P1
**Estimated**: 1 hour
**Dependencies**: Task 2.0

**Description**: Send alerts to Telegram channel/chat via Bot API

**TDD Steps**:
1. **RED**: Write test `test_telegram_send_posts_to_bot_api`
2. **GREEN**: Implement `TelegramChannel.send()` using `python-telegram-bot`
3. **RED**: Write test `test_telegram_format_message_returns_markdown_text`
4. **GREEN**: Implement `TelegramChannel._format_message()` with Markdown
5. **RED**: Write test `test_telegram_handles_api_error_gracefully`
6. **GREEN**: Add error handling

**Acceptance Criteria**:
- [ ] `TelegramChannel` inherits from `BaseChannel`
- [ ] Uses `python-telegram-bot` library (add to pyproject.toml)
- [ ] Bot token from `TELEGRAM_BOT_TOKEN` environment variable
- [ ] Chat ID from `TELEGRAM_CHAT_ID` environment variable
- [ ] Message format: Markdown (bold, emoji, monospace)
- [ ] Retries with exponential backoff (max 3 attempts)
- [ ] Logs error if API fails after retries
- [ ] Test coverage > 90% (mock telegram.Bot)

**Example Test**:
```python
@patch('telegram.Bot')
def test_telegram_send_posts_to_bot_api(mock_bot):
    """Telegram channel should send formatted message via Bot API."""
    mock_bot_instance = MagicMock()
    mock_bot.return_value = mock_bot_instance

    channel = TelegramChannel(bot_token="123:ABC", chat_id="@test_channel")
    alert = Alert(
        symbol="BTCUSDT",
        current_price=Decimal("49500"),
        zone_price=Decimal("49000"),
        zone_density=Decimal("12500000"),
        zone_side="short",
        distance_pct=Decimal("1.01"),
        severity="critical"
    )

    result = channel.send(alert)

    assert result is True
    mock_bot_instance.send_message.assert_called_once()
    call_args = mock_bot_instance.send_message.call_args
    assert call_args.kwargs['chat_id'] == "@test_channel"
    assert "🚨 CRITICAL" in call_args.kwargs['text']
```

**Files to Modify**:
- `src/alerts/channels/telegram.py` (new)
- `tests/test_alerts/test_channels.py`
- `pyproject.toml` (add `python-telegram-bot` dependency)

**Telegram Message Format**:
```markdown
🚨 *LIQUIDATION ZONE ALERT - CRITICAL*

*Symbol:* BTCUSDT
*Current Price:* $49,500.00
*Liquidation Zone:* $49,000.00 (SHORT)
*Distance:* 1.01% (⬇️ Approaching)
*Cluster Size:* $12.5M

⚠️ Price approaching major liquidation zone!
Potential cascade if level breaks.

_Generated: 2025-12-28 14:35:22 UTC_
```

---

### Task 2.3: Implement Email (SMTP) Channel
**Priority**: P2 (Optional for MVP)
**Estimated**: 1 hour
**Dependencies**: Task 2.0

**Description**: Send alerts via email using SMTP

**TDD Steps**:
1. **RED**: Write test `test_email_send_creates_mime_message`
2. **GREEN**: Implement `EmailChannel.send()` using smtplib
3. **RED**: Write test `test_email_format_message_returns_html_body`
4. **GREEN**: Implement `EmailChannel._format_message()` with HTML template
5. **RED**: Write test `test_email_handles_smtp_connection_error`
6. **GREEN**: Add error handling

**Acceptance Criteria**:
- [ ] `EmailChannel` inherits from `BaseChannel`
- [ ] Uses stdlib `smtplib` and `email.mime`
- [ ] SMTP config from `config/alert_settings.yaml` (smtp.host, port, etc.)
- [ ] SMTP credentials from environment variables (optional)
- [ ] HTML email with styled template
- [ ] Subject line includes severity and symbol
- [ ] Retries with exponential backoff (max 3 attempts)
- [ ] Test coverage > 80% (use `smtplib` mock)

**Files to Modify**:
- `src/alerts/channels/email.py` (new)
- `tests/test_alerts/test_channels.py`

---

## Phase 3: Main Alert Loop

### Task 3.0: Implement Alert Engine
**Priority**: P0 (Blocker)
**Estimated**: 2 hours
**Dependencies**: Tasks 1.1, 1.2, 1.3, 2.1, 2.2

**Description**: Main orchestration logic for alert monitoring

**TDD Steps**:
1. **RED**: Write test `test_check_alerts_fetches_price_and_zones`
2. **GREEN**: Implement `AlertEngine.check_alerts()` to fetch data
3. **RED**: Write test `test_check_alerts_triggers_alert_when_threshold_met`
4. **GREEN**: Implement threshold evaluation logic
5. **RED**: Write test `test_check_alerts_respects_cooldown_period`
6. **GREEN**: Integrate cooldown manager
7. **RED**: Write test `test_check_alerts_sends_to_enabled_channels_only`
8. **GREEN**: Implement channel dispatcher
9. **RED**: Write test `test_check_alerts_logs_history_to_database`
10. **GREEN**: Implement history logging

**Acceptance Criteria**:
- [ ] `AlertEngine` class with `check_alerts()` method
- [ ] Fetches current price from Binance API or custom endpoint
- [ ] Fetches liquidation zones from `/liquidations/heatmap-timeseries`
- [ ] Calculates distance for all zones
- [ ] Filters by threshold and min_density
- [ ] Checks cooldown before sending alert
- [ ] Enforces daily alert limit
- [ ] Sends to all enabled channels (parallel if possible)
- [ ] Logs alert to `liquidation_alerts` table
- [ ] Handles API failures gracefully (retry + skip)
- [ ] Returns summary: `{alerts_triggered: int, alerts_sent: int, errors: list}`
- [ ] Test coverage > 85%

**Example Test**:
```python
@patch('requests.get')
def test_check_alerts_triggers_alert_when_threshold_met(mock_get):
    """Engine should trigger alert when price within threshold of zone."""
    # Mock price API
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"price": "49500.00"}
    )

    # Mock heatmap API (returns zone at $49,000)
    with patch.object(AlertEngine, '_fetch_zones') as mock_zones:
        mock_zones.return_value = [
            LiquidationZone(
                price=Decimal("49000"),
                density=Decimal("12500000"),
                side="short"
            )
        ]

        engine = AlertEngine(config)
        result = engine.check_alerts()

        assert result['alerts_triggered'] == 1
        assert result['alerts_sent'] >= 1  # At least one channel
```

**Files to Modify**:
- `src/alerts/engine.py`
- `tests/test_alerts/test_engine.py`

**Database Schema** (history table):
```python
CREATE_ALERTS_TABLE = """
CREATE TABLE IF NOT EXISTS liquidation_alerts (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    current_price DECIMAL(18,8) NOT NULL,
    zone_price DECIMAL(18,8) NOT NULL,
    zone_density DECIMAL(18,8) NOT NULL,
    zone_side VARCHAR(5) NOT NULL,
    distance_pct DECIMAL(8,4) NOT NULL,
    severity VARCHAR(10) NOT NULL,
    channels_sent VARCHAR(255),
    delivery_status VARCHAR(50),
    error_message TEXT
)
"""
```

---

### Task 3.1: Create CLI Runner Script
**Priority**: P0 (Blocker)
**Estimated**: 1 hour
**Dependencies**: Task 3.0

**Description**: Command-line script to run alert monitoring

**Acceptance Criteria**:
- [ ] Script: `scripts/run_alerts.py`
- [ ] Supports `--test` flag (trigger test alert to all channels)
- [ ] Supports `--daemon` flag (continuous monitoring loop)
- [ ] Supports `--once` flag (single check, then exit)
- [ ] Supports `--config` flag (custom config path)
- [ ] Daemon mode: configurable check interval (default 5 minutes)
- [ ] Graceful shutdown on SIGINT/SIGTERM
- [ ] Logs to stdout + file (`logs/alerts.log`)
- [ ] Returns appropriate exit codes (0=success, 1=error)

**Example Usage**:
```bash
# Test alert (manual trigger)
uv run python scripts/run_alerts.py --test

# Single check
uv run python scripts/run_alerts.py --once

# Continuous monitoring (daemon)
uv run python scripts/run_alerts.py --daemon --interval 300

# Custom config
uv run python scripts/run_alerts.py --config /path/to/alert_config.yaml
```

**Files to Create**:
- `scripts/run_alerts.py`
- `scripts/init_alert_db.py` (initialize schema)

**CLI Script Structure**:
```python
import argparse
import signal
import sys
import time
from pathlib import Path
from alerts.engine import AlertEngine
from alerts.config import AlertConfig

def signal_handler(sig, frame):
    """Handle graceful shutdown."""
    logger.info("Received shutdown signal, exiting...")
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Liquidation Alert Monitoring")
    parser.add_argument("--test", action="store_true", help="Send test alert")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=300, help="Check interval (seconds)")
    parser.add_argument("--config", type=Path, default="config/alert_settings.yaml")
    args = parser.parse_args()

    # Load config
    config = AlertConfig.from_yaml(args.config)
    engine = AlertEngine(config)

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.test:
        # Send test alert
        engine.send_test_alert()
        return 0

    if args.daemon:
        logger.info(f"Starting daemon mode (interval: {args.interval}s)")
        while True:
            try:
                result = engine.check_alerts()
                logger.info(f"Alert check complete: {result}")
            except Exception as e:
                logger.error(f"Alert check failed: {e}")
            time.sleep(args.interval)
    else:
        # Single check
        result = engine.check_alerts()
        logger.info(f"Alert check result: {result}")
        return 0 if result['errors'] == [] else 1

if __name__ == "__main__":
    sys.exit(main())
```

---

## Phase 4: Testing & Documentation

### Task 4.0: End-to-End Integration Test
**Priority**: P1
**Estimated**: 2 hours
**Dependencies**: All previous tasks

**Description**: Full integration test with mock APIs and channels

**Acceptance Criteria**:
- [ ] Test script: `tests/integration/test_alert_e2e.py`
- [ ] Mocks Binance API (price endpoint)
- [ ] Mocks heatmap API (returns test zones)
- [ ] Mocks Discord/Telegram webhooks (verify payloads)
- [ ] Verifies cooldown enforcement
- [ ] Verifies daily limit enforcement
- [ ] Verifies database logging
- [ ] Test passes with real config file
- [ ] Test runs in CI (GitHub Actions)

**Example Test**:
```python
@pytest.mark.integration
def test_alert_system_end_to_end(tmp_path):
    """Full alert cycle: fetch data, evaluate, send, log history."""
    # Setup test database
    test_db = tmp_path / "test_alerts.duckdb"

    # Mock APIs
    with responses.RequestsMock() as rsps:
        # Mock price API
        rsps.add(responses.GET,
                 "https://api.binance.com/api/v3/ticker/price",
                 json={"price": "49500.00"})

        # Mock heatmap API
        rsps.add(responses.GET,
                 "http://localhost:8000/liquidations/heatmap-timeseries",
                 json={"zones": [...]})

        # Mock Discord webhook
        rsps.add(responses.POST,
                 "https://discord.com/api/webhooks/test",
                 status=204)

        # Run alert check
        config = AlertConfig.from_yaml("config/alert_settings.yaml")
        config.history.db_path = str(test_db)
        engine = AlertEngine(config)

        result = engine.check_alerts()

        # Assertions
        assert result['alerts_triggered'] == 1
        assert result['alerts_sent'] == 1
        assert result['errors'] == []

        # Verify database log
        db = DuckDBService(db_path=test_db)
        alerts = db.conn.execute("SELECT * FROM liquidation_alerts").fetchall()
        assert len(alerts) == 1
        assert alerts[0][5] == Decimal("49000.00")  # zone_price
```

**Files to Create**:
- `tests/integration/test_alert_e2e.py`

---

### Task 4.1: Update Documentation
**Priority**: P1
**Estimated**: 1.5 hours
**Dependencies**: Task 4.0

**Description**: Update project documentation with alert system details

**Acceptance Criteria**:
- [ ] Update `docs/ARCHITECTURE.md` with alert system components
- [ ] Add "Alert System" section to README.md
- [ ] Create `docs/ALERT_SYSTEM_GUIDE.md` with:
  - Setup instructions
  - Configuration reference
  - Channel setup guides (Discord/Telegram/Email)
  - Troubleshooting section
  - Example use cases
- [ ] Update CLAUDE.md with alert module info

**Files to Modify**:
- `docs/ARCHITECTURE.md`
- `README.md`
- `docs/ALERT_SYSTEM_GUIDE.md` (new)
- `CLAUDE.md`

---

### Task 4.2: Setup Cron Job Template
**Priority**: P2
**Estimated**: 30 minutes
**Dependencies**: Task 3.1

**Description**: Provide cron job setup instructions and templates

**Acceptance Criteria**:
- [ ] Create `scripts/setup_alert_cron.sh` helper script
- [ ] Cron example in docs (every 5 minutes)
- [ ] Systemd service file template (optional)
- [ ] Docker compose example (optional)

**Cron Example** (in docs):
```bash
# Edit crontab
crontab -e

# Add line (check every 5 minutes)
*/5 * * * * cd /path/to/LiquidationHeatmap && uv run python scripts/run_alerts.py --once >> /var/log/liquidation-alerts.log 2>&1
```

**Systemd Service Template**:
```ini
[Unit]
Description=Liquidation Alert Monitoring
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/LiquidationHeatmap
Environment="PATH=/path/to/uv/bin:$PATH"
Environment="DISCORD_WEBHOOK_URL=https://..."
ExecStart=/usr/local/bin/uv run python scripts/run_alerts.py --daemon --interval 300
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Files to Create**:
- `scripts/setup_alert_cron.sh`
- `scripts/systemd/liquidation-alerts.service`
- `scripts/docker/docker-compose.alerts.yml` (optional)

---

## Testing Checklist

### Unit Tests
- [ ] Config loader (valid/invalid YAML)
- [ ] Distance calculator (various price scenarios)
- [ ] Cooldown manager (DuckDB operations)
- [ ] Discord channel (webhook formatting)
- [ ] Telegram channel (bot API)
- [ ] Email channel (SMTP)

### Integration Tests
- [ ] Full alert cycle (mock APIs)
- [ ] Multi-channel delivery
- [ ] Cooldown persistence
- [ ] Database logging

### Manual Tests
- [ ] Test alert to real Discord webhook
- [ ] Test alert to real Telegram channel
- [ ] Test alert to real email
- [ ] Daemon mode runs without crash
- [ ] Cron job executes successfully

---

## Definition of Done

A task is complete when:
- ✅ All acceptance criteria met
- ✅ Unit tests written and passing (coverage > 80%)
- ✅ Code passes `ruff check` and `ruff format`
- ✅ Type hints added (passes `mypy`)
- ✅ Docstrings added for public functions
- ✅ Integration test passes (if applicable)
- ✅ Documentation updated
- ✅ Reviewed by at least one other developer (optional for solo)
- ✅ Committed with descriptive message following TDD pattern

---

## Risk Mitigation Strategies

| Risk | Mitigation |
|------|------------|
| API rate limits | Cache responses, implement backoff |
| Webhook downtime | Independent channel delivery, retry logic |
| Database lock | WAL mode, quick transactions, timeout |
| Configuration errors | Pydantic validation, fail-fast on startup |
| Secret exposure | Environment variables only, never commit |

---

**Maintained by**: Claude Code
**Last Updated**: 2025-12-28
**Version**: 1.0
