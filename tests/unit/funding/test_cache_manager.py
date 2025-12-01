"""
Unit tests for cache manager.
Feature: LIQHEAT-005
Task: T014-T015 - Test cache implementation
TDD: Red phase
"""

import time
from datetime import datetime, timezone
from decimal import Decimal

# These imports will fail initially (TDD Red phase)
from src.services.funding.cache_manager import CacheManager

from src.models.funding.funding_rate import FundingRate


class TestCacheManager:
    """Test suite for TTL cache implementation."""

    def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        # Arrange
        cache = CacheManager(ttl_seconds=5)
        key = "test_key"
        value = {"data": "test_value"}

        # Act
        cache.set(key, value)
        result = cache.get(key)

        # Assert
        assert result == value

    def test_cache_ttl_expiration(self):
        """Test that cached items expire after TTL."""
        # Arrange
        cache = CacheManager(ttl_seconds=1)  # 1 second TTL
        key = "expire_key"
        value = "test_value"

        # Act
        cache.set(key, value)
        time.sleep(1.1)  # Wait for expiration
        result = cache.get(key)

        # Assert
        assert result is None  # Should be expired

    def test_cache_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        # Arrange
        cache = CacheManager(ttl_seconds=60)

        # Act
        result = cache.get("nonexistent_key")

        # Assert
        assert result is None

    def test_cache_clear(self):
        """Test clearing the cache."""
        # Arrange
        cache = CacheManager(ttl_seconds=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Act
        cache.clear()

        # Assert
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_has_key(self):
        """Test checking if key exists in cache."""
        # Arrange
        cache = CacheManager(ttl_seconds=60)
        cache.set("existing_key", "value")

        # Act & Assert
        assert cache.has("existing_key") is True
        assert cache.has("nonexistent_key") is False

    def test_cache_delete_key(self):
        """Test deleting a specific key."""
        # Arrange
        cache = CacheManager(ttl_seconds=60)
        cache.set("key_to_delete", "value")

        # Act
        cache.delete("key_to_delete")

        # Assert
        assert cache.get("key_to_delete") is None

    def test_cache_funding_rate_objects(self):
        """Test caching FundingRate objects."""
        # Arrange
        cache = CacheManager(ttl_seconds=300)  # 5 minutes
        funding = FundingRate(
            symbol="BTCUSDT", rate=Decimal("0.0003"), funding_time=datetime.now(timezone.utc)
        )

        # Act
        cache.set("funding:BTCUSDT", funding)
        result = cache.get("funding:BTCUSDT")

        # Assert
        assert result == funding
        assert result.rate == Decimal("0.0003")

    def test_cache_get_with_default(self):
        """Test getting with a default value."""
        # Arrange
        cache = CacheManager(ttl_seconds=60)
        default = {"default": "value"}

        # Act
        result = cache.get("missing_key", default=default)

        # Assert
        assert result == default

    def test_cache_size_limit(self):
        """Test that cache respects size limits."""
        # Arrange
        cache = CacheManager(ttl_seconds=60, max_size=3)

        # Act - Add more items than max_size
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # Should evict oldest

        # Assert - First item should be evicted
        assert cache.get("key1") is None  # LRU eviction
        assert cache.get("key4") is not None

    def test_cache_stats(self):
        """Test getting cache statistics."""
        # Arrange
        cache = CacheManager(ttl_seconds=60)

        # Act
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        stats = cache.stats()

        # Assert
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate"] == 0.5
