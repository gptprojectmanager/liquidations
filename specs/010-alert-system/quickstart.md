# Quickstart: Liquidation Zone Alert System

**Feature**: spec-010 (Alert System MVP)
**Date**: 2025-12-29

---

## Prerequisites

1. **API Server Running**: The heatmap API must be accessible at `http://localhost:8000`
   ```bash
   uv run uvicorn src.liquidationheatmap.api.main:app --host 0.0.0.0 --port 8000
   ```

2. **Environment Variables**: Set secrets for notification channels
   ```bash
   # Discord (required for Discord alerts)
   export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"

   # Telegram (optional)
   export TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"
   export TELEGRAM_CHAT_ID="@your_channel_or_chat_id"

   # Email (optional - SMTP settings)
   export SMTP_HOST="smtp.gmail.com"
   export SMTP_PORT="587"
   export SMTP_USERNAME="your-email@gmail.com"
   export SMTP_PASSWORD="your-app-password"
   ```

---

## Quick Setup (5 Minutes)

### Step 1: Configure Alerts

Edit `config/alert_settings.yaml` to enable liquidation alerts:

```yaml
# Add this section to existing alert_settings.yaml
liquidation_alerts:
  enabled: true

  thresholds:
    critical:
      distance_pct: 1.0      # Alert when within 1%
      min_density: 10000000  # Min $10M cluster
    warning:
      distance_pct: 3.0      # Alert when within 3%
      min_density: 5000000   # Min $5M cluster
    info:
      distance_pct: 5.0      # Alert when within 5%
      min_density: 1000000   # Min $1M cluster

  cooldown:
    per_zone_minutes: 60     # 1 alert per zone per hour
    max_daily_alerts: 10     # Max 10 alerts per day

  data_sources:
    price_endpoint: "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    heatmap_endpoint: "http://localhost:8000/liquidations/heatmap-timeseries"
    symbol: "BTCUSDT"

  channels:
    discord:
      enabled: true
      webhook_url: null      # Uses DISCORD_WEBHOOK_URL env var
      severity_filter: ["critical", "warning", "info"]

    telegram:
      enabled: false
      severity_filter: ["critical", "warning"]

    email:
      enabled: false
      recipients: ["trader@example.com"]
      severity_filter: ["critical"]

  history:
    enabled: true
    db_path: "data/processed/alerts.duckdb"
    retention_days: 90
```

### Step 2: Initialize Alert Database

```bash
uv run python scripts/init_alert_db.py
```

Expected output:
```
[INFO] Creating alerts database: data/processed/alerts.duckdb
[INFO] Created table: liquidation_alerts
[INFO] Created table: alert_cooldowns
[INFO] Database initialized successfully
```

### Step 3: Test Alert (Manual Trigger)

```bash
# Send a test alert to verify channel configuration
uv run python scripts/run_alerts.py --test
```

Expected output:
```
[INFO] Test mode: Sending test alert...
[INFO] Current price: $94,523.00
[INFO] Test zone: $93,000.00 (1.61% away)
[INFO] Sending to Discord... OK
[INFO] Test alert sent successfully!
```

Check your Discord channel for the test message.

### Step 4: Run Alert Monitor

**Option A: One-shot check (cron mode)**
```bash
uv run python scripts/run_alerts.py
```

**Option B: Continuous daemon**
```bash
uv run python scripts/run_alerts.py --daemon --interval 60
```

**Option C: Cron job (recommended for production)**
```bash
# Add to crontab: check every 5 minutes
*/5 * * * * cd /path/to/LiquidationHeatmap && uv run python scripts/run_alerts.py >> logs/alerts.log 2>&1
```

---

## Usage Examples

### Check Alert Status

```bash
# View recent alerts
uv run python scripts/run_alerts.py --history 10
```

Output:
```
Recent Alerts (last 10):
────────────────────────────────────────────────────────────────
| Timestamp           | Severity | Zone      | Distance | Status  |
|---------------------|----------|-----------|----------|---------|
| 2025-12-28 14:35:22 | CRITICAL | $49,000   | 1.01%    | SUCCESS |
| 2025-12-28 12:15:08 | WARNING  | $52,500   | 2.45%    | SUCCESS |
| 2025-12-28 09:42:31 | INFO     | $55,000   | 4.82%    | PARTIAL |
────────────────────────────────────────────────────────────────
```

### Clear Cooldowns

```bash
# Reset all cooldowns (useful after testing)
uv run python scripts/run_alerts.py --reset-cooldowns
```

### Validate Configuration

```bash
# Check config without sending alerts
uv run python scripts/run_alerts.py --dry-run
```

---

## Alert Message Format

### Discord Embed

![Discord Alert Example](./assets/discord_alert_example.png)

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

### Telegram Message

```
*🚨 LIQUIDATION ZONE ALERT - CRITICAL*

Symbol: `BTCUSDT`
Current Price: `$49,500.00`
Liquidation Zone: `$49,000.00` (SHORT)
Distance: `1.01%` (Approaching)
Cluster Size: `$12.5M`

_Generated: 2025-12-28 14:35:22 UTC_
```

### Email Subject Line

```
[CRITICAL] BTC Liquidation Alert - $49K Zone (1.01% away)
```

---

## Troubleshooting

### "No zones found"

Check that the heatmap API is running and has data:
```bash
curl http://localhost:8000/liquidations/heatmap-timeseries?symbol=BTCUSDT | jq '.data | length'
```

### "Discord webhook failed"

Verify the webhook URL is valid:
```bash
curl -X POST "$DISCORD_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"content": "Test from CLI"}'
```

### "Cooldown preventing alerts"

Reset cooldowns:
```bash
uv run python scripts/run_alerts.py --reset-cooldowns
```

### "Daily limit reached"

Wait until UTC midnight, or temporarily increase limit:
```yaml
cooldown:
  max_daily_alerts: 50  # Increase temporarily
```

---

## Advanced Configuration

### Custom Thresholds per Symbol (Future)

```yaml
# NOT implemented in MVP - placeholder for multi-symbol support
liquidation_alerts:
  symbols:
    BTCUSDT:
      thresholds:
        critical: {distance_pct: 1.0, min_density: 10000000}
    ETHUSDT:
      thresholds:
        critical: {distance_pct: 1.5, min_density: 5000000}
```

### Systemd Service (Production)

Create `/etc/systemd/system/liquidation-alerts.service`:

```ini
[Unit]
Description=Liquidation Zone Alert Daemon
After=network.target

[Service]
Type=simple
User=liquidation
WorkingDirectory=/opt/LiquidationHeatmap
Environment="PATH=/opt/LiquidationHeatmap/.venv/bin:/usr/bin"
EnvironmentFile=/opt/LiquidationHeatmap/.env
ExecStart=/opt/LiquidationHeatmap/.venv/bin/python scripts/run_alerts.py --daemon --interval 60
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable liquidation-alerts
sudo systemctl start liquidation-alerts
sudo systemctl status liquidation-alerts
```

---

## Next Steps

1. **Monitor alerts**: Check Discord channel for incoming alerts
2. **Tune thresholds**: Adjust `distance_pct` based on volatility
3. **Add channels**: Enable Telegram or Email for redundancy
4. **Review history**: Query `alerts.duckdb` for analytics

---

**Questions?** Open an issue on GitHub or check the [full specification](./spec.md).
