"""
Cache layer for dashboard queries.

Provides caching to improve dashboard performance.
"""

import hashlib
import json
import threading
import time
from typing import Any, Dict, Optional

from src.validation.logger import logger


class CacheEntry:
    """Cache entry with TTL."""

    def __init__(self, value: Any, ttl_seconds: int):
        """
        Initialize cache entry.

        Args:
            value: Cached value
            ttl_seconds: Time to live in seconds
        """
        self.value = value
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        age = time.time() - self.created_at
        return age > self.ttl_seconds

    def age_seconds(self) -> float:
        """Get entry age in seconds."""
        return time.time() - self.created_at


class DashboardCache:
    """
    Cache for dashboard query results.

    Thread-safe in-memory cache with TTL support.
    """

    def __init__(
        self,
        default_ttl: int = 300,  # 5 minutes
        max_size: int = 1000,
    ):
        """
        Initialize dashboard cache.

        Args:
            default_ttl: Default time-to-live in seconds
            max_size: Maximum cache entries
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

        logger.info(f"DashboardCache initialized: ttl={default_ttl}s, max_size={max_size}")

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                logger.debug(f"Cache miss: {key}")
                return None

            if entry.is_expired():
                # Remove expired entry
                del self._cache[key]
                self._misses += 1
                logger.debug(f"Cache expired: {key} (age={entry.age_seconds():.1f}s)")
                return None

            self._hits += 1
            logger.debug(
                f"Cache hit: {key} (age={entry.age_seconds():.1f}s, ttl={entry.ttl_seconds}s)"
            )
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        if ttl is None:
            ttl = self.default_ttl

        with self._lock:
            # Check size limit
            if len(self._cache) >= self.max_size and key not in self._cache:
                # Remove oldest entry
                self._evict_oldest()

            entry = CacheEntry(value, ttl)
            self._cache[key] = entry

            logger.debug(f"Cache set: {key} (ttl={ttl}s)")

    def delete(self, key: str) -> bool:
        """
        Delete entry from cache.

        Args:
            key: Cache key

        Returns:
            True if entry was deleted
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache delete: {key}")
                return True
            return False

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0

            logger.info(f"Cache cleared: {count} entries removed")
            return count

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            expired_keys = [key for key, entry in self._cache.items() if entry.is_expired()]

            for key in expired_keys:
                del self._cache[key]

            logger.info(f"Cache cleanup: {len(expired_keys)} expired entries removed")
            return len(expired_keys)

    def get_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "total_requests": total_requests,
                "hit_rate_percent": hit_rate,
                "default_ttl": self.default_ttl,
            }

    def _evict_oldest(self) -> None:
        """Evict oldest cache entry (LRU-like)."""
        if not self._cache:
            return

        # Find oldest entry
        oldest_key = min(self._cache.items(), key=lambda x: x[1].created_at)[0]

        del self._cache[oldest_key]
        logger.debug(f"Cache eviction: {oldest_key}")

    @staticmethod
    def make_key(*args, **kwargs) -> str:
        """
        Generate cache key from arguments.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Cache key string
        """
        # Serialize arguments
        key_data = {
            "args": args,
            "kwargs": sorted(kwargs.items()),  # Sort for consistency
        }

        # Hash to create key
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()

        return key_hash


class CachedQuery:
    """
    Decorator for caching query results.

    Example:
        @CachedQuery(ttl=300)
        def expensive_query(model_name, days):
            # ... query logic
            return results
    """

    def __init__(self, cache: Optional[DashboardCache] = None, ttl: int = 300):
        """
        Initialize cached query decorator.

        Args:
            cache: DashboardCache instance (uses global if None)
            ttl: Cache TTL in seconds
        """
        self.cache = cache or get_dashboard_cache()
        self.ttl = ttl

    def __call__(self, func):
        """Decorate function with caching."""

        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = DashboardCache.make_key(func.__name__, *args, **kwargs)

            # Try to get from cache
            cached_value = self.cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Returning cached result for {func.__name__}")
                return cached_value

            # Execute function
            result = func(*args, **kwargs)

            # Cache result
            self.cache.set(cache_key, result, ttl=self.ttl)

            return result

        return wrapper


# Global cache instance
_global_cache: Optional[DashboardCache] = None
_cache_lock = threading.Lock()


def get_dashboard_cache() -> DashboardCache:
    """
    Get global dashboard cache instance (singleton).

    Returns:
        DashboardCache instance
    """
    global _global_cache

    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = DashboardCache(
                    default_ttl=300,  # 5 minutes
                    max_size=1000,
                )

    return _global_cache


def invalidate_cache() -> int:
    """
    Invalidate (clear) entire cache.

    Returns:
        Number of entries cleared
    """
    cache = get_dashboard_cache()
    return cache.clear()


def cleanup_cache() -> int:
    """
    Cleanup expired cache entries.

    Returns:
        Number of entries removed
    """
    cache = get_dashboard_cache()
    return cache.cleanup_expired()
