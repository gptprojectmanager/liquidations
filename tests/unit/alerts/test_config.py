"""Unit tests for alert configuration.

Tests for:
- Threshold validation
- Config loading and validation
- Severity level configuration
"""

from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from src.liquidationheatmap.alerts.config import (
    ThresholdConfig,
    load_alert_config,
)


class TestThresholdValidation:
    """Tests for threshold configuration validation."""

    def test_threshold_distance_must_be_positive(self) -> None:
        """Threshold distance must be positive."""
        with pytest.raises(ValueError, match="distance_pct must be > 0"):
            ThresholdConfig(
                distance_pct=Decimal("-1.0"),
                min_density=Decimal("1000000"),
            )

    def test_threshold_distance_cannot_be_zero(self) -> None:
        """Threshold distance cannot be zero."""
        with pytest.raises(ValueError, match="distance_pct must be > 0"):
            ThresholdConfig(
                distance_pct=Decimal("0"),
                min_density=Decimal("1000000"),
            )

    def test_threshold_distance_cannot_exceed_100(self) -> None:
        """Threshold distance cannot exceed 100%."""
        with pytest.raises(ValueError, match="distance_pct must be > 0 and <= 100"):
            ThresholdConfig(
                distance_pct=Decimal("101"),
                min_density=Decimal("1000000"),
            )

    def test_threshold_density_must_be_non_negative(self) -> None:
        """Threshold minimum density must be non-negative."""
        with pytest.raises(ValueError, match="min_density must be >= 0"):
            ThresholdConfig(
                distance_pct=Decimal("1.0"),
                min_density=Decimal("-1000000"),
            )

    def test_valid_threshold_config(self) -> None:
        """Valid threshold config should be created."""
        config = ThresholdConfig(
            distance_pct=Decimal("1.0"),
            min_density=Decimal("10000000"),
        )
        assert config.distance_pct == Decimal("1.0")
        assert config.min_density == Decimal("10000000")


class TestAlertConfigValidation:
    """Tests for alert configuration validation."""

    def test_load_config_with_valid_thresholds(self) -> None:
        """Valid config should load successfully."""
        config_yaml = """
liquidation_alerts:
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
    price_endpoint: https://api.binance.com/api/v3/ticker/price
    heatmap_endpoint: http://localhost:8000/liquidations/heatmap-timeseries
    symbol: BTCUSDT
  channels:
    discord:
      enabled: true
      webhook_url: https://discord.com/api/webhooks/test
"""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_yaml)
            f.flush()

            config = load_alert_config(Path(f.name))

        assert config.data_sources.symbol == "BTCUSDT"
        assert "critical" in config.thresholds
        assert config.thresholds["critical"].distance_pct == Decimal("1.0")

    def test_config_requires_at_least_one_threshold(self) -> None:
        """Config must have at least one threshold level."""
        config_yaml = """
liquidation_alerts:
  thresholds: {}
  cooldown:
    per_zone_minutes: 60
    max_daily_alerts: 10
  data_sources:
    price_endpoint: https://api.binance.com/api/v3/ticker/price
    heatmap_endpoint: http://localhost:8000/liquidations/heatmap-timeseries
    symbol: BTCUSDT
  channels:
    discord:
      enabled: true
"""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_yaml)
            f.flush()

            with pytest.raises(ValueError, match="threshold"):
                load_alert_config(Path(f.name))

    def test_critical_threshold_stricter_than_warning(self) -> None:
        """Critical threshold distance should be less than warning."""
        config_yaml = """
liquidation_alerts:
  thresholds:
    critical:
      distance_pct: 5.0
      min_density: 10000000
    warning:
      distance_pct: 3.0
      min_density: 5000000
    info:
      distance_pct: 7.0
      min_density: 1000000
  cooldown:
    per_zone_minutes: 60
    max_daily_alerts: 10
  data_sources:
    price_endpoint: https://api.binance.com/api/v3/ticker/price
    heatmap_endpoint: http://localhost:8000/api
    symbol: BTCUSDT
  channels:
    discord:
      enabled: true
"""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_yaml)
            f.flush()

            # Should raise about inverted thresholds
            with pytest.raises(ValueError, match="critical.*warning"):
                load_alert_config(Path(f.name))


class TestSeverityLevelOrdering:
    """Tests for severity level ordering validation."""

    def test_severity_levels_ordered_by_strictness(self) -> None:
        """Severity levels should be ordered: critical < warning < info."""
        config_yaml = """
liquidation_alerts:
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
    price_endpoint: https://api.binance.com/api/v3/ticker/price
    heatmap_endpoint: http://localhost:8000/api
    symbol: BTCUSDT
  channels:
    discord:
      enabled: true
"""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_yaml)
            f.flush()

            config = load_alert_config(Path(f.name))

        # Verify critical < warning < info
        assert (
            config.thresholds["critical"].distance_pct < config.thresholds["warning"].distance_pct
        )
        assert config.thresholds["warning"].distance_pct < config.thresholds["info"].distance_pct
