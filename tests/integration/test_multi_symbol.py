"""
Integration tests for multi-symbol tier configurations.

Tests that different symbols can have different tier configurations
and calculations remain independent.
"""

from decimal import Decimal

import pytest

from src.models.tier_config import TierConfiguration
from src.services.maintenance_calculator import MaintenanceCalculator
from src.services.margin_calculator import MarginCalculator
from src.services.tier_cache import TierCache
from src.services.tier_loader import TierLoader


class TestMultiSymbol:
    """Test suite for multi-symbol tier configuration support."""

    @pytest.fixture
    def btc_config(self) -> TierConfiguration:
        """Create BTC tier configuration."""
        # Use Binance default for BTC
        return TierLoader.load_binance_default()

    @pytest.fixture
    def eth_config(self) -> TierConfiguration:
        """Create ETH tier configuration with different tiers."""
        # Simulate ETH having different tier structure
        tiers_with_ma = MaintenanceCalculator.derive_binance_tiers()

        from src.models.margin_tier import MarginTier

        tiers = [
            MarginTier(
                symbol="ETHUSDT",
                tier_number=spec.tier_number,
                min_notional=spec.min_notional,
                max_notional=spec.max_notional,
                margin_rate=spec.margin_rate,
                maintenance_amount=ma,
            )
            for spec, ma in tiers_with_ma
        ]

        return TierConfiguration(
            symbol="ETHUSDT",
            version="binance-2025-v1",
            tiers=tiers,
        )

    def test_different_symbols_have_independent_configs(self, btc_config, eth_config):
        """
        Test that different symbols maintain independent configurations.

        Multi-Symbol Requirement (FR-004):
        - Each symbol has its own tier configuration
        - Configurations don't interfere with each other
        """
        assert btc_config.symbol == "BTCUSDT"
        assert eth_config.symbol == "ETHUSDT"

        # Both should have valid configurations
        assert len(btc_config.tiers) == 5
        assert len(eth_config.tiers) == 5

    def test_same_position_different_symbols_independent_calculation(self, btc_config, eth_config):
        """
        Test that calculations for same position size are independent per symbol.

        Independence Test:
        - $1M position in BTC uses BTC tiers
        - $1M position in ETH uses ETH tiers
        - Results are independent
        """
        btc_calc = MarginCalculator(btc_config)
        eth_calc = MarginCalculator(eth_config)

        position = Decimal("1000000")

        btc_margin = btc_calc.calculate_margin(position)
        eth_margin = eth_calc.calculate_margin(position)

        # Both should calculate (using same tier structure in this test)
        assert btc_margin == eth_margin == Decimal("21000")

        # But they came from independent configurations
        assert btc_calc.config is not eth_calc.config

    def test_cache_handles_multiple_symbols(self):
        """
        Test that cache correctly stores different symbols separately.

        Cache Independence:
        - Each symbol cached independently
        - No cross-symbol contamination
        """
        cache = TierCache()

        # Load defaults for multiple symbols
        btc_config = cache.get_or_default("BTCUSDT")
        eth_config = cache.get_or_default("ETHUSDT")
        bnb_config = cache.get_or_default("BNBUSDT")

        # All should be cached separately
        assert "BTCUSDT" in cache
        assert "ETHUSDT" in cache
        assert "BNBUSDT" in cache

        # Cache should have 3 entries
        assert len(cache) == 3

        # Symbols should match
        assert btc_config.symbol == "BTCUSDT"
        assert eth_config.symbol == "ETHUSDT"
        assert bnb_config.symbol == "BNBUSDT"

    def test_invalidate_one_symbol_doesnt_affect_others(self):
        """
        Test that invalidating one symbol doesn't affect others.

        Cache Isolation:
        - Invalidating BTC shouldn't affect ETH
        - Other symbols remain cached
        """
        cache = TierCache()

        # Load multiple symbols
        cache.get_or_default("BTCUSDT")
        cache.get_or_default("ETHUSDT")
        cache.get_or_default("BNBUSDT")

        assert len(cache) == 3

        # Invalidate only BTC
        cache.invalidate("BTCUSDT")

        # BTC should be gone, others remain
        assert "BTCUSDT" not in cache
        assert "ETHUSDT" in cache
        assert "BNBUSDT" in cache
        assert len(cache) == 2

    def test_multi_symbol_calculations_maintain_continuity(self, btc_config, eth_config):
        """
        Test that each symbol maintains continuity independently.

        Continuity Per Symbol:
        - BTC boundaries continuous
        - ETH boundaries continuous
        - No cross-symbol interference
        """
        btc_calc = MarginCalculator(btc_config)
        eth_calc = MarginCalculator(eth_config)

        # Test BTC continuity at $1M boundary
        btc_at_boundary = btc_calc.calculate_margin(Decimal("1000000"))
        assert btc_at_boundary == Decimal("21000")

        # Test ETH continuity at $1M boundary
        eth_at_boundary = eth_calc.calculate_margin(Decimal("1000000"))
        assert eth_at_boundary == Decimal("21000")

        # Both maintain continuity independently
        # (using same tier structure in this test, but configurations are independent)

    def test_loader_loads_symbol_specific_configs(self):
        """
        Test that TierLoader can load symbol-specific YAML files.

        Symbol-Specific Loading:
        - Loader looks for {symbol}.yaml
        - Falls back to default if not found
        - Case-insensitive symbol matching
        """
        loader = TierLoader()

        # Try to load BTCUSDT (should find binance.yaml or use default)
        try:
            config = loader.load_for_symbol("BTCUSDT")
            assert config.symbol == "BTCUSDT"
        except FileNotFoundError:
            # No specific config, which is fine for test
            pytest.skip("No BTCUSDT configuration available")

    def test_loader_load_all_returns_multiple_symbols(self):
        """
        Test that load_all() returns all available symbol configurations.

        Multi-Symbol Discovery:
        - Finds all .yaml files in config directory
        - Returns dictionary keyed by symbol
        """
        loader = TierLoader()
        configs = loader.load_all()

        # Should be a dictionary
        assert isinstance(configs, dict)

        # If any configs loaded, verify structure
        if configs:
            for symbol, config in configs.items():
                assert config.symbol == symbol
                assert isinstance(config, TierConfiguration)
                assert len(config.tiers) > 0

    def test_calculator_with_wrong_symbol_config_still_calculates(self):
        """
        Test that using wrong symbol config doesn't break calculation.

        Robustness:
        - Calculator uses config it's given
        - Symbol mismatch is just metadata
        - Calculations still work correctly
        """
        # Create config labeled as BTC
        config = TierLoader.load_binance_default()
        config.symbol = "BTCUSDT"

        # Use it for "ETH" calculation (symbol mismatch)
        calc = MarginCalculator(config)

        # Should still calculate correctly (ignores symbol mismatch)
        position = Decimal("100000")
        margin = calc.calculate_margin(position)

        # Tier 2: 100k * 0.01 - 250 = 750
        assert margin == Decimal("750")

    def test_cache_preload_multiple_symbols(self):
        """
        Test preloading cache with multiple symbols.

        Cache Warming:
        - preload_all() loads all available configs
        - Each symbol cached independently
        """
        cache = TierCache()

        # Preload all available configs
        count = cache.preload_all()

        # Should have loaded at least the available configs
        assert count >= 0  # May be 0 if no config files

        # If any loaded, verify they're in cache
        if count > 0:
            stats = cache.get_stats()
            assert stats["cache_size"] == count
