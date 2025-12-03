"""Cluster caching with TTL for performance optimization.

Caches clustering results to avoid recomputation for identical requests.
"""

import hashlib
import time
from typing import Any, Dict, Optional

from src.clustering.models import ClusterParameters


class ClusterCache:
    """In-memory cache for clustering results with TTL.

    Thread-safe simple cache implementation using dict.
    For production, consider Redis or similar distributed cache.
    """

    def __init__(self, ttl_seconds: int = 300):
        """Initialize cache.

        Args:
            ttl_seconds: Time-to-live for cached entries (default 5 minutes)
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}

    def generate_key(self, symbol: str, timeframe_minutes: int, params: ClusterParameters) -> str:
        """Generate unique cache key from clustering parameters.

        Args:
            symbol: Trading pair symbol
            timeframe_minutes: Data timeframe in minutes
            params: Clustering parameters

        Returns:
            Unique cache key string
        """
        # Create hash from parameters
        params_str = (
            f"{params.epsilon:.4f}_{params.min_samples}_{params.auto_tune}_{params.distance_metric}"
        )
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]

        return f"{symbol}_{timeframe_minutes}_{params_hash}"

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if exists and not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            return None

        entry = self._cache[key]
        expiry_time = entry["expires_at"]

        # Check if expired
        if time.time() > expiry_time:
            del self._cache[key]
            return None

        return entry["value"]

    def set(self, key: str, value: Any) -> None:
        """Set cache entry with TTL.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = {"value": value, "expires_at": time.time() + self.ttl_seconds}

    def invalidate(self, key: str) -> None:
        """Invalidate (delete) cache entry.

        Args:
            key: Cache key to invalidate
        """
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    def size(self) -> int:
        """Get number of cached entries.

        Returns:
            Number of entries in cache
        """
        return len(self._cache)
