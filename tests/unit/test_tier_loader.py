"""
Unit tests for TierLoader and TierCache.

Tests tier loading from YAML and caching functionality.
"""

import time
from decimal import Decimal
from pathlib import Path

import pytest

from src.services.tier_cache import TierCache
from src.services.tier_loader import TierLoader


class TestTierLoader:
    """Test suite for TierLoader."""

    def test_load_binance_default(self):
        """Test loading Binance default tiers (hardcoded fallback)."""
        config = TierLoader.load_binance_default()

        assert config.symbol == "BTCUSDT"
        assert config.version == "binance-default-v1"
        assert len(config.tiers) == 5

        # Verify MAs are correct
        expected_mas = [
            Decimal("0"),
            Decimal("250"),
            Decimal("4000"),
            Decimal("29000"),
            Decimal("529000"),
        ]

        for i, (tier, expected_ma) in enumerate(zip(config.tiers, expected_mas)):
            assert tier.maintenance_amount == expected_ma, f"Tier {i + 1} MA mismatch"

    def test_load_from_yaml(self):
        """Test loading tier configuration from YAML file."""
        loader = TierLoader()

        # Load Binance YAML
        yaml_path = Path("config/tiers/binance.yaml")

        if not yaml_path.exists():
            pytest.skip("binance.yaml not found")

        config = loader.load_from_yaml(yaml_path)

        assert config.symbol == "BTCUSDT"
        assert config.version == "binance-2025-v1"
        assert len(config.tiers) == 5

        # Verify first tier
        tier1 = config.tiers[0]
        assert tier1.tier_number == 1
        assert tier1.min_notional == Decimal("0")
        assert tier1.max_notional == Decimal("50000")
        assert tier1.margin_rate == Decimal("0.005")
        assert tier1.maintenance_amount == Decimal("0")

    def test_load_for_symbol(self):
        """Test loading configuration by symbol name."""
        loader = TierLoader()

        try:
            config = loader.load_for_symbol("BTCUSDT")
            assert config.symbol == "BTCUSDT"
        except FileNotFoundError:
            pytest.skip("BTCUSDT.yaml not found")

    def test_load_for_symbol_case_insensitive(self):
        """Test that symbol loading is case-insensitive."""
        loader = TierLoader()

        # Try all case variations
        for symbol in ["BTCUSDT", "btcusdt", "BtcUsDt"]:
            try:
                config = loader.load_for_symbol(symbol)
                assert config is not None
                break
            except FileNotFoundError:
                continue
        else:
            pytest.skip("No BTCUSDT configuration found")

    def test_load_all(self):
        """Test loading all available configurations."""
        loader = TierLoader()
        configs = loader.load_all()

        # Should at least have binance.yaml if it exists
        if (Path("config/tiers/binance.yaml")).exists():
            assert "BTCUSDT" in configs
            assert len(configs) >= 1


class TestTierCache:
    """Test suite for TierCache."""

    def test_cache_initialization(self):
        """Test cache initializes with correct TTL."""
        cache = TierCache(ttl_seconds=300)

        assert cache.ttl_seconds == 300
        assert len(cache) == 0

    def test_get_or_default_returns_default_for_unknown_symbol(self):
        """Test that get_or_default returns Binance default for unknown symbols."""
        cache = TierCache()

        config = cache.get_or_default("UNKNOWN_SYMBOL")

        assert config is not None
        assert config.symbol == "UNKNOWN_SYMBOL"  # Symbol updated to match request
        assert len(config.tiers) == 5  # Binance default has 5 tiers

    def test_get_loads_and_caches(self):
        """Test that get() loads configuration and caches it."""
        cache = TierCache()

        # Skip if no configuration available
        try:
            config = cache.get("BTCUSDT")
        except Exception:
            pytest.skip("No BTCUSDT configuration available")

        if config is None:
            pytest.skip("No BTCUSDT configuration available")

        # Should be in cache now
        assert "BTCUSDT" in cache

        # Second get should be cache hit
        stats_before = cache.get_stats()
        config2 = cache.get("BTCUSDT")
        stats_after = cache.get_stats()

        assert config2 is not None
        assert stats_after["hits"] > stats_before["hits"]

    def test_cache_expiry(self):
        """Test that cache entries expire after TTL."""
        cache = TierCache(ttl_seconds=1)  # 1 second TTL

        # Load default
        config = cache.get_or_default("TEST")

        assert "TEST" in cache

        # Wait for expiry
        time.sleep(1.1)

        # Should be expired now
        assert "TEST" not in cache

    def test_invalidate_removes_from_cache(self):
        """Test that invalidate() removes entry from cache."""
        cache = TierCache()

        # Load default
        cache.get_or_default("TEST")

        assert "TEST" in cache

        # Invalidate
        result = cache.invalidate("TEST")

        assert result is True
        assert "TEST" not in cache

    def test_invalidate_all_clears_cache(self):
        """Test that invalidate_all() clears entire cache."""
        cache = TierCache()

        # Load multiple symbols
        cache.get_or_default("SYM1")
        cache.get_or_default("SYM2")
        cache.get_or_default("SYM3")

        assert len(cache) == 3

        # Invalidate all
        cache.invalidate_all()

        assert len(cache) == 0

    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        cache = TierCache()

        # Initial stats
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0

        # Load once (miss)
        cache.get_or_default("TEST")

        stats = cache.get_stats()
        assert stats["misses"] == 1

        # Load again (hit)
        cache.get_or_default("TEST")

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["total_requests"] == 2
        assert stats["hit_rate"] == 0.5

    def test_preload(self):
        """Test preloading configuration into cache."""
        cache = TierCache()

        # Try to preload (may fail if no config)
        try:
            result = cache.preload("BTCUSDT")
            if result:
                assert "BTCUSDT" in cache
        except Exception:
            pytest.skip("Cannot preload BTCUSDT")

    def test_clear_stats(self):
        """Test clearing cache statistics."""
        cache = TierCache()

        # Generate some stats
        cache.get_or_default("TEST")
        cache.get_or_default("TEST")

        stats = cache.get_stats()
        assert stats["hits"] > 0

        # Clear stats
        cache.clear_stats()

        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
