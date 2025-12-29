"""Contract tests for alert configuration schema.

Tests validate that:
1. The config schema matches the expected structure
2. Config loading produces correct dataclasses
3. Invalid configs are rejected with clear errors
"""

from decimal import Decimal
from pathlib import Path

import pytest

from src.liquidationheatmap.alerts.config import (
    CooldownConfig,
    DataSourceConfig,
    DiscordChannelConfig,
    EmailChannelConfig,
    TelegramChannelConfig,
    ThresholdConfig,
    load_alert_config,
)


class TestThresholdConfig:
    """Tests for ThresholdConfig validation."""

    def test_valid_threshold(self) -> None:
        """Valid threshold config should be created."""
        threshold = ThresholdConfig(
            distance_pct=Decimal("1.0"),
            min_density=Decimal("10000000"),
        )
        assert threshold.distance_pct == Decimal("1.0")
        assert threshold.min_density == Decimal("10000000")

    def test_distance_pct_must_be_positive(self) -> None:
        """distance_pct must be > 0."""
        with pytest.raises(ValueError, match="distance_pct must be"):
            ThresholdConfig(
                distance_pct=Decimal("0"),
                min_density=Decimal("10000000"),
            )

    def test_distance_pct_max_100(self) -> None:
        """distance_pct must be <= 100."""
        with pytest.raises(ValueError, match="distance_pct must be"):
            ThresholdConfig(
                distance_pct=Decimal("101"),
                min_density=Decimal("10000000"),
            )

    def test_min_density_non_negative(self) -> None:
        """min_density must be >= 0."""
        with pytest.raises(ValueError, match="min_density must be"):
            ThresholdConfig(
                distance_pct=Decimal("1.0"),
                min_density=Decimal("-1"),
            )


class TestCooldownConfig:
    """Tests for CooldownConfig validation."""

    def test_valid_cooldown(self) -> None:
        """Valid cooldown config should be created."""
        cooldown = CooldownConfig(
            per_zone_minutes=60,
            max_daily_alerts=10,
        )
        assert cooldown.per_zone_minutes == 60
        assert cooldown.max_daily_alerts == 10

    def test_per_zone_minutes_minimum(self) -> None:
        """per_zone_minutes must be >= 1."""
        with pytest.raises(ValueError, match="per_zone_minutes must be"):
            CooldownConfig(
                per_zone_minutes=0,
                max_daily_alerts=10,
            )

    def test_max_daily_alerts_minimum(self) -> None:
        """max_daily_alerts must be >= 1."""
        with pytest.raises(ValueError, match="max_daily_alerts must be"):
            CooldownConfig(
                per_zone_minutes=60,
                max_daily_alerts=0,
            )


class TestChannelConfig:
    """Tests for channel configuration validation."""

    def test_discord_channel_config(self) -> None:
        """Discord channel config should be created."""
        discord = DiscordChannelConfig(
            enabled=True,
            severity_filter=["critical", "warning"],
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )
        assert discord.enabled is True
        assert discord.severity_filter == ["critical", "warning"]

    def test_telegram_channel_config(self) -> None:
        """Telegram channel config should be created."""
        telegram = TelegramChannelConfig(
            enabled=True,
            severity_filter=["critical"],
            bot_token="123456:ABC",
            chat_id="@mychannel",
        )
        assert telegram.enabled is True
        assert telegram.bot_token == "123456:ABC"

    def test_email_channel_config(self) -> None:
        """Email channel config should be created."""
        email = EmailChannelConfig(
            enabled=True,
            severity_filter=["critical"],
            recipients=["test@example.com"],
        )
        assert email.enabled is True
        assert email.recipients == ["test@example.com"]

    def test_invalid_severity_filter(self) -> None:
        """Invalid severity filter values should be rejected."""
        with pytest.raises(ValueError, match="Invalid severity"):
            DiscordChannelConfig(
                enabled=True,
                severity_filter=["critical", "invalid"],
            )


class TestDataSourceConfig:
    """Tests for DataSourceConfig validation."""

    def test_valid_data_sources(self) -> None:
        """Valid data source config should be created."""
        ds = DataSourceConfig(
            price_endpoint="https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            heatmap_endpoint="http://localhost:8000/liquidations/heatmap-timeseries",
            symbol="BTCUSDT",
        )
        assert ds.symbol == "BTCUSDT"

    def test_invalid_symbol_format(self) -> None:
        """Symbol must match expected format."""
        with pytest.raises(ValueError, match="symbol must be"):
            DataSourceConfig(
                price_endpoint="https://api.binance.com/api/v3/ticker/price",
                heatmap_endpoint="http://localhost:8000/api",
                symbol="BTC",  # Too short
            )


class TestAlertConfigLoading:
    """Tests for loading AlertConfig from YAML."""

    def test_load_valid_config(self, tmp_path: Path) -> None:
        """Valid YAML config should load successfully."""
        config_content = """
liquidation_alerts:
  enabled: true
  thresholds:
    critical:
      distance_pct: 1.0
      min_density: 10000000
    warning:
      distance_pct: 3.0
      min_density: 5000000
    info:
      distance_pct: 5.0
      min_density: 1000000
  cooldown:
    per_zone_minutes: 60
    max_daily_alerts: 10
  data_sources:
    price_endpoint: "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    heatmap_endpoint: "http://localhost:8000/liquidations/heatmap-timeseries"
    symbol: "BTCUSDT"
  channels:
    discord:
      enabled: true
      severity_filter:
        - critical
        - warning
    telegram:
      enabled: false
      severity_filter:
        - critical
    email:
      enabled: false
      recipients:
        - test@example.com
      severity_filter:
        - critical
  history:
    enabled: true
    db_path: "data/processed/alerts.duckdb"
    retention_days: 90
"""
        config_file = tmp_path / "alert_settings.yaml"
        config_file.write_text(config_content)

        config = load_alert_config(config_file)

        assert config.enabled is True
        assert config.thresholds["critical"].distance_pct == Decimal("1.0")
        assert config.cooldown.per_zone_minutes == 60
        assert config.data_sources.symbol == "BTCUSDT"
        assert config.channels["discord"].enabled is True

    def test_missing_required_section(self, tmp_path: Path) -> None:
        """Missing liquidation_alerts section should raise error."""
        config_content = """
alerts:
  enabled: true
"""
        config_file = tmp_path / "alert_settings.yaml"
        config_file.write_text(config_content)

        with pytest.raises(ValueError, match="liquidation_alerts"):
            load_alert_config(config_file)

    def test_missing_threshold_levels(self, tmp_path: Path) -> None:
        """Missing threshold levels should raise error."""
        config_content = """
liquidation_alerts:
  enabled: true
  thresholds:
    critical:
      distance_pct: 1.0
      min_density: 10000000
  cooldown:
    per_zone_minutes: 60
    max_daily_alerts: 10
  data_sources:
    price_endpoint: "https://api.binance.com/api/v3/ticker/price"
    heatmap_endpoint: "http://localhost:8000/api"
    symbol: "BTCUSDT"
  channels:
    discord:
      enabled: true
      severity_filter:
        - critical
"""
        config_file = tmp_path / "alert_settings.yaml"
        config_file.write_text(config_content)

        with pytest.raises(ValueError, match="Missing threshold"):
            load_alert_config(config_file)

    def test_at_least_one_channel_enabled(self, tmp_path: Path) -> None:
        """At least one channel must be enabled."""
        config_content = """
liquidation_alerts:
  enabled: true
  thresholds:
    critical:
      distance_pct: 1.0
      min_density: 10000000
    warning:
      distance_pct: 3.0
      min_density: 5000000
    info:
      distance_pct: 5.0
      min_density: 1000000
  cooldown:
    per_zone_minutes: 60
    max_daily_alerts: 10
  data_sources:
    price_endpoint: "https://api.binance.com/api/v3/ticker/price"
    heatmap_endpoint: "http://localhost:8000/api"
    symbol: "BTCUSDT"
  channels:
    discord:
      enabled: false
      severity_filter:
        - critical
    telegram:
      enabled: false
      severity_filter:
        - critical
    email:
      enabled: false
      severity_filter:
        - critical
"""
        config_file = tmp_path / "alert_settings.yaml"
        config_file.write_text(config_content)

        with pytest.raises(ValueError, match="At least one channel"):
            load_alert_config(config_file)
