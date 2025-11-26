"""
Tier configuration cache with TTL and invalidation support.

Provides:
- In-memory caching with configurable TTL
- Thread-safe operations
- Manual invalidation for updates
- Automatic expiry
"""

import logging
import time
from threading import Lock
from typing import Dict, Optional

from src.models.tier_config import TierConfiguration
from src.services.tier_loader import TierLoader

logger = logging.getLogger(__name__)


class CacheEntry:
    """Single cache entry with TTL."""

    def __init__(self, config: TierConfiguration, ttl_seconds: int):
        """
        Create cache entry.

        Args:
            config: Tier configuration to cache
            ttl_seconds: Time-to-live in seconds
        """
        self.config = config
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        age_seconds = time.time() - self.created_at
        return age_seconds > self.ttl_seconds

    def age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return time.time() - self.created_at


class TierCache:
    """
    Thread-safe cache for tier configurations with TTL.

    Features:
    - Configurable TTL (default: 5 minutes)
    - Thread-safe read/write operations
    - Manual invalidation support
    - Automatic lazy expiry on access
    - Cache statistics
    """

    def __init__(
        self,
        loader: Optional[TierLoader] = None,
        ttl_seconds: int = 300,  # 5 minutes default
    ):
        """
        Initialize tier cache.

        Args:
            loader: TierLoader instance (creates default if None)
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.loader = loader or TierLoader()
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._invalidations = 0

        logger.info(f"TierCache initialized with TTL={ttl_seconds}s")

    def get(self, symbol: str) -> Optional[TierConfiguration]:
        """
        Get tier configuration from cache or load if missing/expired.

        Args:
            symbol: Trading pair symbol

        Returns:
            TierConfiguration if found, None if error loading

        Example:
            >>> cache = TierCache()
            >>> config = cache.get("BTCUSDT")
        """
        with self._lock:
            # Check if in cache
            if symbol in self._cache:
                entry = self._cache[symbol]

                # Check if expired
                if entry.is_expired():
                    logger.info(
                        f"Cache entry expired for {symbol} "
                        f"(age: {entry.age_seconds():.1f}s, TTL: {self.ttl_seconds}s)"
                    )
                    del self._cache[symbol]
                    self._misses += 1
                else:
                    # Valid cache hit
                    self._hits += 1
                    logger.debug(f"Cache hit for {symbol} (age: {entry.age_seconds():.1f}s)")
                    return entry.config

            # Cache miss - load from loader
            self._misses += 1

        # Load outside lock to avoid blocking
        try:
            config = self.loader.load_for_symbol(symbol)
        except FileNotFoundError:
            logger.warning(f"No configuration found for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Failed to load configuration for {symbol}: {e}")
            return None

        # Store in cache
        with self._lock:
            entry = CacheEntry(config, self.ttl_seconds)
            self._cache[symbol] = entry
            logger.info(f"Cached configuration for {symbol}")

        return config

    def get_or_default(self, symbol: str) -> TierConfiguration:
        """
        Get configuration or return Binance default if not found.

        Args:
            symbol: Trading pair symbol

        Returns:
            TierConfiguration (never None)

        Example:
            >>> cache = TierCache()
            >>> config = cache.get_or_default("UNKNOWN")  # Returns Binance default
        """
        config = self.get(symbol)

        if config is None:
            logger.warning(f"No configuration for {symbol}, using Binance default")
            config = TierLoader.load_binance_default()
            # Update symbol to match request
            config.symbol = symbol
            # Also update symbol on all tiers
            for tier in config.tiers:
                tier.symbol = symbol

            # Cache the default configuration
            with self._lock:
                entry = CacheEntry(config, self.ttl_seconds)
                self._cache[symbol] = entry
                logger.info(f"Cached default configuration for {symbol}")

        return config

    def invalidate(self, symbol: str) -> bool:
        """
        Invalidate cached configuration for symbol.

        Used when tier configuration is updated.

        Args:
            symbol: Trading pair symbol to invalidate

        Returns:
            True if entry was invalidated, False if not in cache

        Example:
            >>> cache.invalidate("BTCUSDT")
            True
        """
        with self._lock:
            if symbol in self._cache:
                del self._cache[symbol]
                self._invalidations += 1
                logger.info(f"Invalidated cache for {symbol}")
                return True

        logger.debug(f"No cache entry to invalidate for {symbol}")
        return False

    def invalidate_all(self):
        """
        Invalidate all cached configurations.

        Used for system-wide tier updates or configuration reloads.

        Example:
            >>> cache.invalidate_all()
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._invalidations += count
            logger.info(f"Invalidated all cache entries ({count} entries)")

    def preload(self, symbol: str) -> bool:
        """
        Preload configuration into cache.

        Useful for warming up cache on startup.

        Args:
            symbol: Trading pair symbol to preload

        Returns:
            True if preloaded successfully, False otherwise

        Example:
            >>> cache.preload("BTCUSDT")
            True
        """
        config = self.get(symbol)
        return config is not None

    def preload_all(self) -> int:
        """
        Preload all available configurations.

        Returns:
            Number of configurations preloaded

        Example:
            >>> count = cache.preload_all()
            >>> print(f"Preloaded {count} configurations")
        """
        configs = self.loader.load_all()

        with self._lock:
            for symbol, config in configs.items():
                entry = CacheEntry(config, self.ttl_seconds)
                self._cache[symbol] = entry

        logger.info(f"Preloaded {len(configs)} configurations into cache")
        return len(configs)

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache performance metrics

        Example:
            >>> stats = cache.get_stats()
            >>> print(f"Hit rate: {stats['hit_rate']:.1%}")
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

            return {
                "hits": self._hits,
                "misses": self._misses,
                "invalidations": self._invalidations,
                "total_requests": total_requests,
                "hit_rate": hit_rate,
                "cached_symbols": list(self._cache.keys()),
                "cache_size": len(self._cache),
                "ttl_seconds": self.ttl_seconds,
            }

    def clear_stats(self):
        """Reset cache statistics counters."""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._invalidations = 0
            logger.info("Cache statistics cleared")

    def __contains__(self, symbol: str) -> bool:
        """Check if symbol is in cache (not expired)."""
        with self._lock:
            if symbol not in self._cache:
                return False

            entry = self._cache[symbol]
            if entry.is_expired():
                del self._cache[symbol]
                return False

            return True

    def __len__(self) -> int:
        """Get number of valid (non-expired) cache entries."""
        with self._lock:
            # Remove expired entries
            expired = [symbol for symbol, entry in self._cache.items() if entry.is_expired()]
            for symbol in expired:
                del self._cache[symbol]

            return len(self._cache)


# Global cache instance
_global_cache: Optional[TierCache] = None
_cache_lock = Lock()


def get_global_cache(ttl_seconds: int = 300) -> TierCache:
    """
    Get or create global tier cache instance.

    Args:
        ttl_seconds: TTL for cache entries (only used on first call)

    Returns:
        Global TierCache instance

    Example:
        >>> cache = get_global_cache()
        >>> config = cache.get("BTCUSDT")
    """
    global _global_cache

    with _cache_lock:
        if _global_cache is None:
            _global_cache = TierCache(ttl_seconds=ttl_seconds)
            logger.info("Created global tier cache")

        return _global_cache


def invalidate_global_cache(symbol: Optional[str] = None):
    """
    Invalidate global cache (all or specific symbol).

    Args:
        symbol: Symbol to invalidate (None = invalidate all)

    Example:
        >>> invalidate_global_cache("BTCUSDT")  # Invalidate one
        >>> invalidate_global_cache()  # Invalidate all
    """
    cache = get_global_cache()

    if symbol is None:
        cache.invalidate_all()
    else:
        cache.invalidate(symbol)
