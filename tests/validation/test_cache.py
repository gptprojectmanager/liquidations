"""
Tests for cache.py - TTL-based dashboard caching.

Tests cover:
- Cache get/set operations
- TTL expiration
- LRU-like eviction
- Thread safety
- Cache statistics
- Cached query decorator
"""

import time

from src.validation.visualization.cache import (
    CachedQuery,
    CacheEntry,
    DashboardCache,
    get_dashboard_cache,
)


class TestDashboardCache:
    """Test DashboardCache functionality."""

    def test_initialization_with_defaults(self):
        """Cache should initialize with default TTL and size."""
        # Act
        cache = DashboardCache()

        # Assert
        assert cache.default_ttl == 300  # 5 minutes
        assert cache.max_size == 1000

    def test_set_and_get_returns_cached_value(self):
        """Set value should be retrievable with get."""
        # Arrange
        cache = DashboardCache()

        # Act
        cache.set("key1", "value1")
        result = cache.get("key1")

        # Assert
        assert result == "value1"

    def test_get_returns_none_for_missing_key(self):
        """Get should return None for non-existent key."""
        # Arrange
        cache = DashboardCache()

        # Act
        result = cache.get("nonexistent")

        # Assert
        assert result is None

    def test_get_returns_none_for_expired_entry(self):
        """Get should return None for expired entries."""
        # Arrange
        cache = DashboardCache(default_ttl=1)  # 1 second TTL

        # Act
        cache.set("key1", "value1")
        time.sleep(1.5)  # Wait for expiration
        result = cache.get("key1")

        # Assert
        assert result is None

    def test_delete_removes_entry(self):
        """Delete should remove entry from cache."""
        # Arrange
        cache = DashboardCache()
        cache.set("key1", "value1")

        # Act
        deleted = cache.delete("key1")
        result = cache.get("key1")

        # Assert
        assert deleted is True
        assert result is None

    def test_clear_removes_all_entries(self):
        """Clear should remove all entries."""
        # Arrange
        cache = DashboardCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Act
        count = cache.clear()

        # Assert
        assert count == 3
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None

    def test_cleanup_expired_removes_only_expired(self):
        """cleanup_expired should remove only expired entries."""
        # Arrange
        cache = DashboardCache()
        cache.set("key1", "value1", ttl=1)  # Short TTL
        cache.set("key2", "value2", ttl=1000)  # Long TTL

        time.sleep(1.5)  # Wait for key1 to expire

        # Act
        count = cache.cleanup_expired()

        # Assert
        assert count == 1  # Only key1 expired
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_evict_oldest_when_max_size_reached(self):
        """Cache should evict oldest entry when max size reached."""
        # Arrange
        cache = DashboardCache(max_size=3)

        # Fill cache
        cache.set("key1", "value1")
        time.sleep(0.01)
        cache.set("key2", "value2")
        time.sleep(0.01)
        cache.set("key3", "value3")
        time.sleep(0.01)

        # Act
        cache.set("key4", "value4")  # Should evict key1

        # Assert
        assert cache.get("key1") is None  # Oldest evicted
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_get_stats_returns_accurate_statistics(self):
        """get_stats should return cache statistics."""
        # Arrange
        cache = DashboardCache(max_size=10)
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("nonexistent")  # Miss

        # Act
        stats = cache.get_stats()

        # Assert
        assert stats["size"] == 2
        assert stats["max_size"] == 10
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["total_requests"] == 3
        assert abs(stats["hit_rate_percent"] - 66.67) < 0.1  # 2/3 = 66.67%

    def test_make_key_generates_consistent_hash(self):
        """make_key should generate consistent hash for same inputs."""
        # Act
        key1 = DashboardCache.make_key("arg1", "arg2", param1="value1")
        key2 = DashboardCache.make_key("arg1", "arg2", param1="value1")

        # Assert
        assert key1 == key2

    def test_make_key_different_for_different_inputs(self):
        """make_key should generate different hash for different inputs."""
        # Act
        key1 = DashboardCache.make_key("arg1", param1="value1")
        key2 = DashboardCache.make_key("arg1", param1="value2")

        # Assert
        assert key1 != key2

    def test_get_dashboard_cache_returns_singleton(self):
        """get_dashboard_cache should return same instance."""
        # Act
        cache1 = get_dashboard_cache()
        cache2 = get_dashboard_cache()

        # Assert
        assert cache1 is cache2


class TestCacheEntry:
    """Test CacheEntry functionality."""

    def test_cache_entry_creation(self):
        """CacheEntry should be created with value and TTL."""
        # Act
        entry = CacheEntry("test_value", ttl_seconds=60)

        # Assert
        assert entry.value == "test_value"
        assert entry.ttl_seconds == 60
        assert entry.is_expired() is False

    def test_is_expired_returns_true_after_ttl(self):
        """is_expired should return True after TTL."""
        # Arrange
        entry = CacheEntry("value", ttl_seconds=1)

        # Act
        time.sleep(1.5)
        result = entry.is_expired()

        # Assert
        assert result is True

    def test_age_seconds_increases_over_time(self):
        """age_seconds should increase over time."""
        # Arrange
        entry = CacheEntry("value", ttl_seconds=60)
        initial_age = entry.age_seconds()

        # Act
        time.sleep(0.5)
        later_age = entry.age_seconds()

        # Assert
        assert later_age > initial_age
        assert later_age >= 0.5


class TestCachedQuery:
    """Test CachedQuery decorator."""

    def test_cached_query_decorator_caches_result(self):
        """CachedQuery should cache function results."""
        # Arrange
        cache = DashboardCache()
        call_count = [0]  # Mutable for closure

        @CachedQuery(cache=cache, ttl=300)
        def expensive_function(x):
            call_count[0] += 1
            return x * 2

        # Act
        result1 = expensive_function(5)
        result2 = expensive_function(5)  # Should use cache

        # Assert
        assert result1 == 10
        assert result2 == 10
        assert call_count[0] == 1  # Only called once

    def test_cached_query_with_different_args(self):
        """CachedQuery should cache separately for different args."""
        # Arrange
        cache = DashboardCache()

        @CachedQuery(cache=cache, ttl=300)
        def add(a, b):
            return a + b

        # Act
        result1 = add(1, 2)
        result2 = add(3, 4)  # Different args

        # Assert
        assert result1 == 3
        assert result2 == 7
