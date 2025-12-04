"""
TTL cache manager for funding rate data.
Feature: LIQHEAT-005
Task: T014-T015 - Implement TTL cache wrapper with cachetools
"""

import threading
from typing import Any, Dict, Optional

from cachetools import TTLCache


class CacheManager:
    """
    Thread-safe cache manager with TTL support.

    Uses cachetools TTLCache for automatic expiration of cached items
    after a specified time-to-live (TTL) period.
    """

    def __init__(self, ttl_seconds: int = 300, max_size: int = 128):
        """
        Initialize cache manager.

        Args:
            ttl_seconds: Time-to-live for cached items in seconds (default: 5 minutes)
            max_size: Maximum number of items in cache (default: 128)
        """
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache = TTLCache(maxsize=max_size, ttl=ttl_seconds)
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get item from cache.

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default if not found/expired
        """
        with self._lock:
            try:
                value = self._cache[key]
                self._hits += 1
                return value
            except KeyError:
                self._misses += 1
                return default

    def set(self, key: str, value: Any) -> None:
        """
        Set item in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            self._cache[key] = value

    def has(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists and not expired
        """
        with self._lock:
            return key in self._cache

    def delete(self, key: str) -> bool:
        """
        Delete item from cache.

        Args:
            key: Cache key

        Returns:
            True if item was deleted, False if not found
        """
        with self._lock:
            try:
                del self._cache[key]
                return True
            except KeyError:
                return False

    def clear(self) -> None:
        """Clear all items from cache."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats (hits, misses, size, hit_rate)
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0

            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "hit_rate": hit_rate,
            }

    def size(self) -> int:
        """
        Get current cache size.

        Returns:
            Number of items in cache
        """
        with self._lock:
            return len(self._cache)


# Global cache instances for different purposes
_funding_cache: Optional[CacheManager] = None
_adjustment_cache: Optional[CacheManager] = None


def get_funding_cache(ttl_seconds: int = 300) -> CacheManager:
    """
    Get global funding rate cache instance.

    Args:
        ttl_seconds: TTL for cached items (default: 5 minutes)

    Returns:
        Global funding cache
    """
    global _funding_cache
    if _funding_cache is None:
        _funding_cache = CacheManager(ttl_seconds=ttl_seconds, max_size=100)
    return _funding_cache


def get_adjustment_cache(ttl_seconds: int = 60) -> CacheManager:
    """
    Get global adjustment cache instance.

    Args:
        ttl_seconds: TTL for cached items (default: 1 minute)

    Returns:
        Global adjustment cache
    """
    global _adjustment_cache
    if _adjustment_cache is None:
        _adjustment_cache = CacheManager(ttl_seconds=ttl_seconds, max_size=50)
    return _adjustment_cache


def clear_all_caches() -> None:
    """Clear all global caches."""
    global _funding_cache, _adjustment_cache

    if _funding_cache:
        _funding_cache.clear()

    if _adjustment_cache:
        _adjustment_cache.clear()
