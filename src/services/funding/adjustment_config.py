"""
Configuration loader for bias adjustment settings.
Feature: LIQHEAT-005
Task: T008 - Create configuration loader
"""

from pathlib import Path
from typing import Optional

import yaml

from src.models.funding.adjustment_config import AdjustmentConfigModel


def load_config(config_path: Optional[str] = None) -> AdjustmentConfigModel:
    """
    Load and validate bias adjustment configuration from YAML file.

    Args:
        config_path: Path to configuration file. If None, loads from
                    config/bias_settings.yaml

    Returns:
        Validated AdjustmentConfigModel

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid or YAML is malformed
    """
    # Default to project config directory
    if config_path is None:
        config_path = "config/bias_settings.yaml"

    path = Path(config_path)

    # Check file exists
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    # Load YAML
    try:
        with open(path, "r") as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format in {config_path}: {e}")

    if raw_config is None:
        raise ValueError(f"Empty configuration file: {config_path}")

    # Extract bias_adjustment section
    if "bias_adjustment" not in raw_config:
        raise ValueError(f"Missing 'bias_adjustment' section in {config_path}")

    bias_config = raw_config["bias_adjustment"]

    # Handle smoothing configuration if present
    if "smoothing" in bias_config:
        smoothing = bias_config.pop("smoothing")
        bias_config["smoothing_enabled"] = smoothing.get("enabled", False)
        bias_config["smoothing_periods"] = smoothing.get("periods", 3)
        bias_config["smoothing_weights"] = smoothing.get("weights")

    # Create and validate model
    try:
        config = AdjustmentConfigModel(**bias_config)
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}")

    return config


def save_config(config: AdjustmentConfigModel, config_path: str) -> None:
    """
    Save configuration to YAML file.

    Args:
        config: Configuration to save
        config_path: Path to save to
    """
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict
    config_dict = config.model_dump()

    # Restructure smoothing for YAML format
    if config_dict.get("smoothing_enabled"):
        smoothing = {
            "enabled": config_dict.pop("smoothing_enabled"),
            "periods": config_dict.pop("smoothing_periods"),
            "weights": config_dict.pop("smoothing_weights"),
        }
        config_dict["smoothing"] = smoothing
    else:
        # Remove smoothing fields if disabled
        config_dict.pop("smoothing_enabled", None)
        config_dict.pop("smoothing_periods", None)
        config_dict.pop("smoothing_weights", None)

    # Wrap in bias_adjustment section
    output = {"bias_adjustment": config_dict}

    # Write YAML
    with open(path, "w") as f:
        yaml.safe_dump(output, f, default_flow_style=False, sort_keys=False)


def get_default_config() -> AdjustmentConfigModel:
    """
    Get default configuration with standard values.

    Returns:
        Default AdjustmentConfigModel
    """
    return AdjustmentConfigModel()


# Global config instance (lazy loaded)
_global_config: Optional[AdjustmentConfigModel] = None


def get_config() -> AdjustmentConfigModel:
    """
    Get the global configuration instance.

    Loads from default path on first call.

    Returns:
        Global configuration
    """
    global _global_config
    if _global_config is None:
        _global_config = load_config()
    return _global_config


def reload_config(config_path: Optional[str] = None) -> AdjustmentConfigModel:
    """
    Reload configuration from file.

    Args:
        config_path: Optional path to config file

    Returns:
        Reloaded configuration
    """
    global _global_config
    _global_config = load_config(config_path)
    return _global_config
