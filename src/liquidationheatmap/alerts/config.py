"""Alert configuration loading and validation.

This module provides dataclasses for alert configuration and
a loader that reads from YAML files with validation.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

# Valid severity levels
VALID_SEVERITIES = {"critical", "warning", "info"}
REQUIRED_THRESHOLD_LEVELS = {"critical", "warning", "info"}


@dataclass
class ThresholdConfig:
    """Alert threshold configuration for a severity level.

    Attributes:
        distance_pct: Distance from zone as percentage (0 < x <= 100)
        min_density: Minimum cluster size in USD (>= 0)
    """

    distance_pct: Decimal
    min_density: Decimal

    def __post_init__(self) -> None:
        """Validate threshold values."""
        if not (Decimal("0") < self.distance_pct <= Decimal("100")):
            raise ValueError(f"distance_pct must be > 0 and <= 100, got {self.distance_pct}")
        if self.min_density < Decimal("0"):
            raise ValueError(f"min_density must be >= 0, got {self.min_density}")


@dataclass
class CooldownConfig:
    """Rate limiting configuration.

    Attributes:
        per_zone_minutes: Cooldown period per zone in minutes (>= 1)
        max_daily_alerts: Maximum alerts per day (>= 1)
    """

    per_zone_minutes: int
    max_daily_alerts: int

    def __post_init__(self) -> None:
        """Validate cooldown values."""
        if self.per_zone_minutes < 1:
            raise ValueError(f"per_zone_minutes must be >= 1, got {self.per_zone_minutes}")
        if self.max_daily_alerts < 1:
            raise ValueError(f"max_daily_alerts must be >= 1, got {self.max_daily_alerts}")


@dataclass
class ChannelConfig:
    """Base notification channel configuration.

    Attributes:
        enabled: Whether the channel is enabled
        severity_filter: List of severity levels to send to this channel
    """

    enabled: bool
    severity_filter: list[str] = field(default_factory=lambda: ["critical"])

    def __post_init__(self) -> None:
        """Validate channel configuration."""
        for severity in self.severity_filter:
            if severity not in VALID_SEVERITIES:
                raise ValueError(
                    f"Invalid severity '{severity}'. Must be one of: {VALID_SEVERITIES}"
                )


@dataclass
class DiscordChannelConfig(ChannelConfig):
    """Discord webhook channel configuration.

    Attributes:
        webhook_url: Discord webhook URL (from env var if not specified)
    """

    webhook_url: str | None = None


@dataclass
class TelegramChannelConfig(ChannelConfig):
    """Telegram bot channel configuration.

    Attributes:
        bot_token: Telegram bot token (from env var if not specified)
        chat_id: Telegram chat ID (from env var if not specified)
    """

    bot_token: str | None = None
    chat_id: str | None = None


@dataclass
class EmailChannelConfig(ChannelConfig):
    """Email SMTP channel configuration.

    Attributes:
        recipients: List of email addresses to send alerts to
    """

    recipients: list[str] = field(default_factory=list)


@dataclass
class DataSourceConfig:
    """Data source endpoints configuration.

    Attributes:
        price_endpoint: Binance price API endpoint
        heatmap_endpoint: Internal heatmap API endpoint
        symbol: Trading pair symbol (e.g., BTCUSDT)
    """

    price_endpoint: str
    heatmap_endpoint: str
    symbol: str

    def __post_init__(self) -> None:
        """Validate data source configuration."""
        # Symbol must be 6-12 uppercase characters
        if not (6 <= len(self.symbol) <= 12 and self.symbol.isupper()):
            raise ValueError(f"symbol must be 6-12 uppercase characters, got '{self.symbol}'")


@dataclass
class HistoryConfig:
    """Alert history storage configuration.

    Attributes:
        enabled: Whether to store alert history
        db_path: Path to the DuckDB database file
        retention_days: Number of days to retain alerts
    """

    enabled: bool = True
    db_path: str = "data/processed/alerts.duckdb"
    retention_days: int = 90


@dataclass
class AlertConfig:
    """Root configuration for liquidation alerts.

    Attributes:
        enabled: Enable/disable alerts globally
        thresholds: Alert thresholds by severity level
        cooldown: Rate limiting configuration
        data_sources: API endpoint configuration
        channels: Notification channel configurations
        history: Alert history storage configuration
    """

    enabled: bool
    thresholds: dict[str, ThresholdConfig]
    cooldown: CooldownConfig
    data_sources: DataSourceConfig
    channels: dict[str, ChannelConfig]
    history: HistoryConfig = field(default_factory=HistoryConfig)


def _parse_threshold(data: dict[str, Any]) -> ThresholdConfig:
    """Parse threshold configuration from dict."""
    return ThresholdConfig(
        distance_pct=Decimal(str(data["distance_pct"])),
        min_density=Decimal(str(data["min_density"])),
    )


def _parse_channel(name: str, data: dict[str, Any] | None) -> ChannelConfig | None:
    """Parse channel configuration from dict."""
    if data is None:
        return None

    enabled = data.get("enabled", False)
    severity_filter = data.get("severity_filter", ["critical"])

    if name == "discord":
        return DiscordChannelConfig(
            enabled=enabled,
            severity_filter=severity_filter,
            webhook_url=data.get("webhook_url"),
        )
    elif name == "telegram":
        return TelegramChannelConfig(
            enabled=enabled,
            severity_filter=severity_filter,
            bot_token=data.get("bot_token"),
            chat_id=data.get("chat_id"),
        )
    elif name == "email":
        return EmailChannelConfig(
            enabled=enabled,
            severity_filter=severity_filter,
            recipients=data.get("recipients", []),
        )
    else:
        return ChannelConfig(
            enabled=enabled,
            severity_filter=severity_filter,
        )


def load_alert_config(config_path: Path) -> AlertConfig:
    """Load and validate alert configuration from YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Validated AlertConfig instance.

    Raises:
        ValueError: If configuration is invalid or missing required fields.
        FileNotFoundError: If config file doesn't exist.
    """
    with open(config_path) as f:
        raw_config = yaml.safe_load(f)

    if "liquidation_alerts" not in raw_config:
        raise ValueError("Configuration missing 'liquidation_alerts' section")

    alerts_config = raw_config["liquidation_alerts"]

    # Parse thresholds
    thresholds_data = alerts_config.get("thresholds", {})
    missing_thresholds = REQUIRED_THRESHOLD_LEVELS - set(thresholds_data.keys())
    if missing_thresholds:
        raise ValueError(
            f"Missing threshold levels: {missing_thresholds}. Required: {REQUIRED_THRESHOLD_LEVELS}"
        )

    thresholds = {level: _parse_threshold(data) for level, data in thresholds_data.items()}

    # Validate threshold ordering: critical < warning < info
    if thresholds["critical"].distance_pct >= thresholds["warning"].distance_pct:
        raise ValueError(
            f"critical threshold distance ({thresholds['critical'].distance_pct}%) must be "
            f"less than warning threshold ({thresholds['warning'].distance_pct}%)"
        )
    if thresholds["warning"].distance_pct >= thresholds["info"].distance_pct:
        raise ValueError(
            f"warning threshold distance ({thresholds['warning'].distance_pct}%) must be "
            f"less than info threshold ({thresholds['info'].distance_pct}%)"
        )

    # Parse cooldown
    cooldown_data = alerts_config.get("cooldown", {})
    cooldown = CooldownConfig(
        per_zone_minutes=cooldown_data.get("per_zone_minutes", 60),
        max_daily_alerts=cooldown_data.get("max_daily_alerts", 10),
    )

    # Parse data sources
    ds_data = alerts_config.get("data_sources", {})
    data_sources = DataSourceConfig(
        price_endpoint=ds_data.get("price_endpoint", ""),
        heatmap_endpoint=ds_data.get("heatmap_endpoint", ""),
        symbol=ds_data.get("symbol", "BTCUSDT"),
    )

    # Parse channels
    channels_data = alerts_config.get("channels", {})
    channels: dict[str, ChannelConfig] = {}
    for name in ["discord", "telegram", "email"]:
        channel = _parse_channel(name, channels_data.get(name))
        if channel:
            channels[name] = channel

    # Validate at least one channel is enabled
    enabled_channels = [c for c in channels.values() if c.enabled]
    if not enabled_channels:
        raise ValueError(
            "At least one channel must be enabled. "
            "Enable discord, telegram, or email in the configuration."
        )

    # Parse history config
    history_data = alerts_config.get("history", {})
    history = HistoryConfig(
        enabled=history_data.get("enabled", True),
        db_path=history_data.get("db_path", "data/processed/alerts.duckdb"),
        retention_days=history_data.get("retention_days", 90),
    )

    return AlertConfig(
        enabled=alerts_config.get("enabled", True),
        thresholds=thresholds,
        cooldown=cooldown,
        data_sources=data_sources,
        channels=channels,
        history=history,
    )
