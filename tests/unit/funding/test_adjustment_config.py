"""
Unit tests for configuration loader.
Feature: LIQHEAT-005
Task: T008 - Test configuration loader
TDD: Red phase
"""

import pytest

from src.models.funding.adjustment_config import AdjustmentConfigModel

# These imports will fail initially (TDD Red phase)
from src.services.funding.adjustment_config import load_config


class TestConfigurationLoader:
    """Test suite for configuration loading and validation."""

    def test_load_valid_config_file(self, tmp_path):
        """Test loading a valid configuration file."""
        # Arrange
        config_content = """
bias_adjustment:
  enabled: true
  symbol: "BTCUSDT"
  sensitivity: 50.0
  max_adjustment: 0.20
  outlier_cap: 0.10
  cache_ttl_seconds: 300
  extreme_alert_threshold: 0.05
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        # Act
        config = load_config(str(config_file))

        # Assert
        assert isinstance(config, AdjustmentConfigModel)
        assert config.enabled is True
        assert config.symbol == "BTCUSDT"
        assert config.sensitivity == 50.0
        assert config.max_adjustment == 0.20
        assert config.outlier_cap == 0.10
        assert config.cache_ttl_seconds == 300
        assert config.extreme_alert_threshold == 0.05

    def test_load_default_config(self):
        """Test loading default configuration from project config directory."""
        # Act
        config = load_config()  # Should load from config/bias_settings.yaml

        # Assert
        assert isinstance(config, AdjustmentConfigModel)
        assert config.symbol == "BTCUSDT"  # From our created config
        assert 10.0 <= config.sensitivity <= 100.0
        assert 0.10 <= config.max_adjustment <= 0.30

    def test_config_validation_sensitivity_range(self, tmp_path):
        """Test that sensitivity must be within valid range."""
        # Arrange - Invalid sensitivity (too low)
        config_content = """
bias_adjustment:
  enabled: true
  symbol: "BTCUSDT"
  sensitivity: 5.0
  max_adjustment: 0.20
"""
        config_file = tmp_path / "invalid_config.yaml"
        config_file.write_text(config_content)

        # Act & Assert
        with pytest.raises(ValueError, match="Input should be greater than or equal to 10"):
            load_config(str(config_file))

    def test_config_validation_max_adjustment_range(self, tmp_path):
        """Test that max_adjustment must be within valid range."""
        # Arrange - Invalid max_adjustment (too high)
        config_content = """
bias_adjustment:
  enabled: true
  symbol: "BTCUSDT"
  sensitivity: 50.0
  max_adjustment: 0.50
"""
        config_file = tmp_path / "invalid_config.yaml"
        config_file.write_text(config_content)

        # Act & Assert
        with pytest.raises(ValueError, match="Input should be less than or equal to 0.3"):
            load_config(str(config_file))

    def test_config_disabled_feature(self, tmp_path):
        """Test handling of disabled feature configuration."""
        # Arrange
        config_content = """
bias_adjustment:
  enabled: false
  symbol: "BTCUSDT"
"""
        config_file = tmp_path / "disabled_config.yaml"
        config_file.write_text(config_content)

        # Act
        config = load_config(str(config_file))

        # Assert
        assert config.enabled is False
        # Should still have defaults for other fields
        assert config.sensitivity == 50.0  # default
        assert config.max_adjustment == 0.20  # default

    def test_missing_config_file(self):
        """Test handling of missing configuration file."""
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent_config.yaml")

    def test_invalid_yaml_format(self, tmp_path):
        """Test handling of invalid YAML format."""
        # Arrange
        config_content = "invalid: yaml: content: {["
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text(config_content)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid YAML"):
            load_config(str(config_file))

    def test_config_smoothing_settings(self, tmp_path):
        """Test loading smoothing configuration."""
        # Arrange
        config_content = """
bias_adjustment:
  enabled: true
  symbol: "BTCUSDT"
  sensitivity: 50.0
  max_adjustment: 0.20
  smoothing:
    enabled: true
    periods: 3
    weights: [0.5, 0.3, 0.2]
"""
        config_file = tmp_path / "smoothing_config.yaml"
        config_file.write_text(config_content)

        # Act
        config = load_config(str(config_file))

        # Assert
        assert config.smoothing_enabled is True
        assert config.smoothing_periods == 3
        assert config.smoothing_weights == [0.5, 0.3, 0.2]
        assert sum(config.smoothing_weights) == pytest.approx(1.0)
