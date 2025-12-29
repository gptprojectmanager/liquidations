# Implementation Plan: Liquidation Zone Alert System

**Branch**: `010-alert-system` | **Date**: 2025-12-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/010-alert-system/spec.md`

## Summary

Implement a proactive alert system that monitors BTC price proximity to high-density liquidation zones and sends multi-channel notifications (Discord/Telegram/Email) when thresholds are crossed. The system uses existing `/liquidations/heatmap-timeseries` API for zone data, stores alert history in DuckDB, and enforces rate limiting via per-zone cooldowns and daily limits.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI (existing), httpx (existing), pyyaml (existing), DuckDB (existing)
**Storage**: DuckDB (`data/processed/alerts.duckdb`) - new database for alert history
**Testing**: pytest with TDD (Red-Green-Refactor)
**Target Platform**: Linux server (background daemon or cron job)
**Project Type**: Single Python project with modular structure
**Performance Goals**: Alert latency < 60 seconds from threshold crossing to notification
**Constraints**: Memory < 100MB for background service, no new heavy dependencies
**Scale/Scope**: Single symbol (BTCUSDT) initially, 10 alerts/day limit

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **Mathematical Correctness (MUST)** | PASS | Distance calculation: `abs(current_price - zone_price) / current_price * 100`. Simple percentage math. |
| **Test-Driven Development (MUST)** | PASS | All components will follow Red-Green-Refactor. TDD guard enforced. |
| **Exchange Compatibility (MUST)** | N/A | Alert system is downstream of liquidation calculations; no direct exchange formulas. |
| **Performance Efficiency (SHOULD)** | PASS | Single API call per check cycle, O(n) zone scanning, lightweight HTTP clients. Target <60s latency. |
| **Data Integrity (MUST)** | PASS | DuckDB for atomic alert history writes. Cooldown state persisted between runs. |
| **Graceful Degradation (SHOULD)** | PASS | Channel failures isolated. Retry with exponential backoff. Skip cycle on API failure. |
| **Progressive Enhancement (SHOULD)** | PASS | MVP: Discord only. Phase 2: Telegram/Email. Phase 3: Web dashboard. |
| **Documentation Completeness (MUST)** | PASS | Config YAML documented. CLI usage examples. Alert message templates. |

**Verdict**: All gates PASS. No violations requiring justification.

## Project Structure

### Documentation (this feature)

```
specs/010-alert-system/
├── spec.md              # Feature specification (input)
├── plan.md              # This file (Phase 0-1 output)
├── research.md          # Research findings (Phase 0 output)
├── data-model.md        # Entity definitions (Phase 1 output)
├── quickstart.md        # Setup guide (Phase 1 output)
├── contracts/           # API contracts (Phase 1 output)
│   └── alert_config_schema.yaml
└── tasks.md             # Implementation tasks (Phase 2 - NOT created by /speckit.plan)
```

### Source Code (repository root)

```
src/
├── liquidationheatmap/
│   ├── alerts/                # NEW: Alert system module
│   │   ├── __init__.py
│   │   ├── config.py          # AlertConfig loader from YAML
│   │   ├── engine.py          # AlertEvaluationEngine (zone distance, threshold check)
│   │   ├── cooldown.py        # CooldownManager (DuckDB-backed state)
│   │   ├── dispatcher.py      # AlertDispatcher (multi-channel delivery)
│   │   └── channels/          # Notification channel implementations
│   │       ├── __init__.py
│   │       ├── discord.py     # Discord webhook client
│   │       ├── telegram.py    # Telegram bot client
│   │       └── email.py       # SMTP email client
│   └── ...existing modules...

tests/
├── unit/
│   └── alerts/
│       ├── test_config.py
│       ├── test_engine.py
│       ├── test_cooldown.py
│       └── test_channels.py
├── integration/
│   └── test_alert_system.py
└── contract/
    └── test_alert_config_schema.py

scripts/
├── run_alerts.py              # CLI entry point (daemon/cron mode)
└── init_alert_db.py           # One-time DB initialization

config/
└── alert_settings.yaml        # Extended with liquidation_alerts section
```

**Structure Decision**: Single project structure following existing `src/liquidationheatmap/` pattern. New `alerts/` submodule mirrors `validation/` pattern. Tests parallel source structure.

## Complexity Tracking

*No violations requiring justification.*

## Key Design Decisions

### 1. Channel Independence
Each notification channel (Discord, Telegram, Email) operates independently:
- Failure in one channel does not block others
- Per-channel retry with exponential backoff
- Delivery status tracked per channel in alert history

### 2. Cooldown State Persistence
Cooldown tracking stored in DuckDB (not in-memory):
- Survives daemon restarts
- Supports cron mode (stateless between runs)
- Daily counter resets at UTC midnight

### 3. Price Source Strategy
1. **Primary**: Binance API (`/api/v3/ticker/price`)
2. **Fallback**: Internal heatmap-timeseries response (if API fails)

### 4. Zone Data Source
Use existing `/liquidations/heatmap-timeseries` endpoint:
- Already returns zone prices and densities
- No database direct access needed (API-first approach)
- Reduces coupling to implementation details

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Binance API rate limits | 10-second price cache, batch zone fetch |
| Webhook URL exposure in logs | Mask secrets in log output |
| Database lock contention | WAL mode, quick transactions, timeout handling |
| Alert fatigue | Cooldown + daily limit + severity filters |

## Next Steps

1. **Phase 0**: Complete research.md (dependency analysis, best practices)
2. **Phase 1**: Generate data-model.md, contracts/, quickstart.md
3. **Phase 2**: Generate tasks.md via `/speckit.tasks` command
4. **Implementation**: Follow TDD workflow (Red-Green-Refactor)
