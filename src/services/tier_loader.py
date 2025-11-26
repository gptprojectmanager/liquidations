"""
Tier configuration loader from YAML files.

Loads tier configurations from YAML files and creates TierConfiguration instances
with derived maintenance amounts.
"""

import logging
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional

import yaml

from src.models.margin_tier import MarginTier
from src.models.tier_config import TierConfiguration
from src.services.maintenance_calculator import MaintenanceCalculator, TierSpec

logger = logging.getLogger(__name__)


class TierLoader:
    """
    Loader for tier configurations from YAML files.

    Supports:
    - Loading from YAML with automatic MA derivation
    - Symbol-specific configurations
    - Validation and error handling
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize tier loader.

        Args:
            config_dir: Directory containing tier YAML files
                       Defaults to config/tiers/ in repository root
        """
        if config_dir is None:
            # Default to config/tiers in repository root
            repo_root = Path(__file__).parent.parent.parent
            config_dir = repo_root / "config" / "tiers"

        self.config_dir = Path(config_dir)
        logger.info(f"TierLoader initialized with config_dir: {self.config_dir}")

    def load_from_yaml(self, yaml_path: Path) -> TierConfiguration:
        """
        Load tier configuration from YAML file.

        YAML Format:
        ```yaml
        symbol: BTCUSDT
        version: binance-2025-v1
        tiers:
          - tier_number: 1
            min_notional: 0
            max_notional: 50000
            margin_rate: 0.005
          - tier_number: 2
            min_notional: 50000
            max_notional: 250000
            margin_rate: 0.010
        ```

        Args:
            yaml_path: Path to YAML configuration file

        Returns:
            TierConfiguration with derived maintenance amounts

        Raises:
            FileNotFoundError: If YAML file doesn't exist
            ValueError: If YAML is invalid or missing required fields
            yaml.YAMLError: If YAML parsing fails

        Example:
            >>> loader = TierLoader()
            >>> config = loader.load_from_yaml(Path("config/tiers/binance.yaml"))
            >>> config.symbol
            'BTCUSDT'
        """
        yaml_path = Path(yaml_path)

        if not yaml_path.exists():
            raise FileNotFoundError(f"Tier configuration not found: {yaml_path}")

        logger.info(f"Loading tier configuration from {yaml_path}")

        with open(yaml_path, "r") as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise yaml.YAMLError(f"Failed to parse YAML: {e}")

        # Validate required fields
        if not data:
            raise ValueError(f"Empty YAML file: {yaml_path}")

        if "symbol" not in data:
            raise ValueError("Missing required field: symbol")

        if "version" not in data:
            raise ValueError("Missing required field: version")

        if "tiers" not in data or not data["tiers"]:
            raise ValueError("Missing or empty tiers list")

        symbol = data["symbol"]
        version = data["version"]
        tier_specs_raw = data["tiers"]

        # Convert to TierSpec objects
        tier_specs = []
        for tier_data in tier_specs_raw:
            try:
                spec = TierSpec(
                    tier_number=tier_data["tier_number"],
                    min_notional=Decimal(str(tier_data["min_notional"])),
                    max_notional=Decimal(str(tier_data["max_notional"])),
                    margin_rate=Decimal(str(tier_data["margin_rate"])),
                )
                tier_specs.append(spec)
            except KeyError as e:
                raise ValueError(f"Missing required tier field: {e}")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid tier data: {e}")

        # Derive maintenance amounts
        tiers_with_ma = MaintenanceCalculator.calculate_maintenance_amount(tier_specs)

        # Create MarginTier objects
        margin_tiers = [
            MarginTier(
                symbol=symbol,
                tier_number=spec.tier_number,
                min_notional=spec.min_notional,
                max_notional=spec.max_notional,
                margin_rate=spec.margin_rate,
                maintenance_amount=ma,
            )
            for spec, ma in tiers_with_ma
        ]

        # Create and return TierConfiguration
        config = TierConfiguration(
            symbol=symbol,
            version=version,
            tiers=margin_tiers,
        )

        logger.info(f"Loaded {len(margin_tiers)} tiers for {symbol} (version: {version})")

        return config

    def load_for_symbol(self, symbol: str) -> TierConfiguration:
        """
        Load tier configuration for specific symbol.

        Looks for {symbol}.yaml in config directory (case-insensitive).

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")

        Returns:
            TierConfiguration for the symbol

        Raises:
            FileNotFoundError: If configuration file not found

        Example:
            >>> loader = TierLoader()
            >>> config = loader.load_for_symbol("BTCUSDT")
        """
        # Try exact match first
        yaml_path = self.config_dir / f"{symbol}.yaml"

        if not yaml_path.exists():
            # Try lowercase
            yaml_path = self.config_dir / f"{symbol.lower()}.yaml"

        if not yaml_path.exists():
            # Try uppercase
            yaml_path = self.config_dir / f"{symbol.upper()}.yaml"

        if not yaml_path.exists():
            raise FileNotFoundError(
                f"No tier configuration found for symbol: {symbol} (searched in {self.config_dir})"
            )

        return self.load_from_yaml(yaml_path)

    def load_all(self) -> Dict[str, TierConfiguration]:
        """
        Load all tier configurations from config directory.

        Returns:
            Dictionary mapping symbol to TierConfiguration

        Example:
            >>> loader = TierLoader()
            >>> configs = loader.load_all()
            >>> configs.keys()
            dict_keys(['BTCUSDT', 'ETHUSDT'])
        """
        if not self.config_dir.exists():
            logger.warning(f"Config directory does not exist: {self.config_dir}")
            return {}

        configs = {}

        for yaml_file in self.config_dir.glob("*.yaml"):
            try:
                config = self.load_from_yaml(yaml_file)
                configs[config.symbol] = config
                logger.info(f"Loaded configuration for {config.symbol}")
            except Exception as e:
                logger.error(f"Failed to load {yaml_file}: {e}")
                # Continue loading other files

        logger.info(f"Loaded {len(configs)} tier configurations")
        return configs

    @staticmethod
    def load_binance_default() -> TierConfiguration:
        """
        Load default Binance tier configuration (hardcoded fallback).

        Returns Binance's standard 5-tier structure with derived MAs.
        Useful when YAML files are not available.

        Returns:
            TierConfiguration with Binance defaults

        Example:
            >>> config = TierLoader.load_binance_default()
            >>> len(config.tiers)
            5
        """
        tiers_with_ma = MaintenanceCalculator.derive_binance_tiers()

        margin_tiers = [
            MarginTier(
                symbol="BTCUSDT",  # Default symbol
                tier_number=spec.tier_number,
                min_notional=spec.min_notional,
                max_notional=spec.max_notional,
                margin_rate=spec.margin_rate,
                maintenance_amount=ma,
            )
            for spec, ma in tiers_with_ma
        ]

        return TierConfiguration(
            symbol="BTCUSDT",
            version="binance-default-v1",
            tiers=margin_tiers,
        )
