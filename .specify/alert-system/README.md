# Alert System - Quick Reference

**Status**: Ready for Implementation
**Estimated Effort**: 2-3 days (MVP)
**Priority**: P1 - High Value

---

## Overview

Alert system monitors liquidation heatmap zones and sends notifications when price approaches high-density clusters.

**Key Features**:
- Real-time price proximity alerts (configurable thresholds)
- Multi-channel delivery (Discord, Telegram, Email)
- Smart rate limiting (per-zone cooldown + daily limits)
- Persistent history tracking (DuckDB)
- Integration with existing `/liquidations/heatmap-timeseries` API

---

## Quick Start

### 1. Review Documentation
```bash
# Read full specification
cat .specify/alert-system/spec.md

# Review implementation tasks
cat .specify/alert-system/tasks.md
```

### 2. Key Integration Points

**Existing APIs to Use**:
- `/liquidations/heatmap-timeseries` - Liquidation zone data
- `https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT` - Current price

**Existing Config to Extend**:
- `config/alert_settings.yaml` - Add `liquidation_alerts` section

**Existing Services to Leverage**:
- `DuckDBService` - Database singleton for alert history
- `src/liquidationheatmap/utils/logging_config.py` - Logging setup

### 3. Module Structure

```
src/alerts/                    # New module
├── __init__.py
├── engine.py                  # Main orchestration
├── config.py                  # YAML config loader
├── cooldown.py                # DuckDB cooldown manager
└── channels/
    ├── __init__.py
    ├── base.py                # Abstract channel interface
    ├── discord.py             # Discord webhook
    ├── telegram.py            # Telegram bot API
    └── email.py               # SMTP email

scripts/
├── run_alerts.py              # CLI runner (--test, --daemon, --once)
└── init_alert_db.py           # Initialize schema

tests/test_alerts/             # Test suite
└── integration/
    └── test_alert_e2e.py      # Full integration test
```

---

## Implementation Order

### Phase 1: Core Engine (Day 1)
1. **Task 1.0**: Module structure setup (30min)
2. **Task 1.1**: Config loader with Pydantic (1h)
3. **Task 1.2**: Distance calculator (1h)
4. **Task 1.3**: Cooldown manager + DuckDB (2h)

**Checkpoint**: Can load config, calculate distances, track cooldowns

### Phase 2: Channels (Day 1-2)
1. **Task 2.0**: Base channel interface (30min)
2. **Task 2.1**: Discord webhook (1h)
3. **Task 2.2**: Telegram bot API (1h)
4. **Task 2.3**: Email SMTP [OPTIONAL] (1h)

**Checkpoint**: Can send test alerts to all channels

### Phase 3: Orchestration (Day 2)
1. **Task 3.0**: Alert engine main loop (2h)
2. **Task 3.1**: CLI runner script (1h)

**Checkpoint**: Full alert cycle works end-to-end

### Phase 4: Polish (Day 3)
1. **Task 4.0**: E2E integration test (2h)
2. **Task 4.1**: Documentation updates (1.5h)
3. **Task 4.2**: Cron/systemd templates (30min)

**Checkpoint**: Production-ready, documented, tested

---

## Key Design Decisions

### 1. Keep It Simple (KISS)
- **No Redis**: In-memory cooldown state via DuckDB (sufficient for single-server)
- **No complex rules engine**: Simple threshold-based alerts (MVP)
- **No WebSocket**: Polling Binance API every 5 minutes (good enough)

### 2. Leverage Existing Stack
- **Use DuckDBService singleton**: No new database dependencies
- **Use existing API endpoint**: `/liquidations/heatmap-timeseries` already provides zone data
- **Extend existing config**: `config/alert_settings.yaml` pattern

### 3. Fail-Safe Defaults
- **Cooldown prevents spam**: Max 1 alert per zone per hour
- **Daily limit prevents abuse**: Max 10 alerts per day
- **Independent channels**: Discord failure doesn't block Telegram
- **Graceful degradation**: Skip alerts if API unreachable

---

## Configuration Example

**Extend `config/alert_settings.yaml`**:

```yaml
liquidation_alerts:
  enabled: true

  thresholds:
    critical:
      distance_pct: 1.0      # Alert when within 1%
      min_density: 10000000  # Min $10M cluster
    warning:
      distance_pct: 3.0
      min_density: 5000000
    info:
      distance_pct: 5.0
      min_density: 1000000

  cooldown:
    per_zone_minutes: 60
    max_daily_alerts: 10

  channels:
    discord:
      enabled: true
      webhook_url: null  # Set via DISCORD_WEBHOOK_URL env var
      severity_filter: ["critical", "warning", "info"]

    telegram:
      enabled: false
      bot_token: null    # Set via TELEGRAM_BOT_TOKEN env var
      chat_id: null      # Set via TELEGRAM_CHAT_ID env var
      severity_filter: ["critical"]
```

---

## Testing Strategy

### Unit Tests (High Priority)
- ✅ Config parsing and validation
- ✅ Distance calculation accuracy
- ✅ Cooldown enforcement (time-based)
- ✅ Channel message formatting

### Integration Tests (Medium Priority)
- ✅ Full alert cycle with mocked APIs
- ✅ Multi-channel delivery
- ✅ Database persistence

### Manual Tests (Before Production)
- ✅ Real Discord webhook delivery
- ✅ Real Telegram bot delivery
- ✅ Daemon mode stability (run 24h)
- ✅ Cron job execution

---

## Success Metrics

**MVP Definition of Done**:
- ✅ Alert triggers when price within threshold of zone
- ✅ Notifications sent to Discord and/or Telegram
- ✅ Cooldown prevents duplicate alerts
- ✅ Daily limit enforced
- ✅ Alert history logged to DuckDB
- ✅ CLI script runs via cron
- ✅ Test coverage > 80%
- ✅ Documentation complete

**Post-MVP Success Criteria**:
- Alert latency < 60 seconds
- Zero missed alerts when API healthy
- Multi-channel delivery > 95% success rate
- No false positives (spam)

---

## Future Enhancements (Out of Scope)

**P3 - Nice to Have**:
- Web dashboard for alert history visualization
- SMS alerts via Twilio
- Slack integration
- PagerDuty for critical alerts
- Alert rules engine (advanced logic)
- Multi-symbol support (ETH, SOL)
- Machine learning for adaptive thresholds

---

## Common Issues & Solutions

### Issue: "Alert not sending to Discord"
**Solution**:
1. Verify webhook URL in environment variable
2. Check Discord webhook is not rate-limited
3. Review logs in `logs/alerts.log`

### Issue: "Cooldown not working"
**Solution**:
1. Verify DuckDB connection
2. Check `alert_cooldowns` table exists
3. Verify system clock is UTC

### Issue: "Too many alerts"
**Solution**:
1. Increase `cooldown.per_zone_minutes` in config
2. Decrease `max_daily_alerts` limit
3. Increase `thresholds.critical.distance_pct`

---

## Dependencies

### New Dependencies (Add to pyproject.toml)
```toml
[project.dependencies]
python-telegram-bot = "^20.0"  # For Telegram integration
```

### Existing Dependencies (Already in project)
- `requests` - HTTP client for webhooks
- `pyyaml` - Config parsing
- `duckdb` - Alert history storage
- `pydantic` - Config validation
- `pytest` - Testing framework

---

## Contacts & Resources

**Spec Documents**:
- Full specification: `.specify/alert-system/spec.md`
- Implementation tasks: `.specify/alert-system/tasks.md`

**External Resources**:
- Discord Webhooks: https://discord.com/developers/docs/resources/webhook
- Telegram Bot API: https://core.telegram.org/bots/api
- Binance API Docs: https://binance-docs.github.io/apidocs/

**Related Features**:
- Heatmap API: `src/liquidationheatmap/api/main.py`
- Alert Settings: `config/alert_settings.yaml`
- DuckDB Service: `src/liquidationheatmap/ingestion/db_service.py`

---

**Created**: 2025-12-28
**Version**: 1.0 (MVP)
**Maintained by**: Claude Code
