"""
Binance funding rate API client with caching and retry logic.
Feature: LIQHEAT-005
Tasks: T016-T018 - Implement Binance funding rate API client with retry and caching
"""

import asyncio
import logging
from typing import Optional

import httpx

from src.models.funding.funding_rate import FundingRate
from src.services.funding.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class FundingFetchError(Exception):
    """Exception raised when funding rate fetch fails."""

    pass


class FundingFetcher:
    """
    Fetches funding rates from Binance API with caching and retry logic.

    Implements:
    - T016: Binance funding rate API client
    - T017: Rate limiting with exponential backoff
    - T018: Funding rate caching logic
    """

    BASE_URL = "https://fapi.binance.com"
    FUNDING_ENDPOINT = "/fapi/v1/fundingRate"

    def __init__(
        self,
        cache_ttl: int = 300,
        max_retries: int = 3,
        timeout: int = 10,
        base_url: Optional[str] = None,
    ):
        """
        Initialize funding fetcher.

        Args:
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
            max_retries: Maximum retry attempts (default: 3)
            timeout: Request timeout in seconds (default: 10)
            base_url: Optional custom base URL for testing
        """
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries
        self.timeout = timeout
        self.base_url = base_url or self.BASE_URL

        # Initialize HTTP client
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(timeout))

        # Initialize cache
        self._cache = CacheManager(ttl_seconds=cache_ttl, max_size=100)

    async def get_funding_rate(self, symbol: str) -> FundingRate:
        """
        Get current funding rate for symbol.

        Args:
            symbol: Trading symbol (e.g., BTCUSDT)

        Returns:
            Current FundingRate

        Raises:
            FundingFetchError: If unable to fetch funding rate
        """
        # Check cache first
        cache_key = f"funding:{symbol}"
        cached = self._cache.get(cache_key)

        if cached is not None:
            logger.debug(f"Cache hit for {symbol}")
            return cached

        logger.debug(f"Cache miss for {symbol}, fetching from API")

        # Fetch from API with retry
        try:
            funding = await self._fetch_with_retry(symbol)

            # Cache the result
            self._cache.set(cache_key, funding)

            return funding

        except Exception as e:
            logger.error(f"Failed to fetch funding rate for {symbol}: {e}")

            # Try to return cached value even if expired
            cached = self.get_cached_funding(symbol)
            if cached:
                logger.warning(f"Returning stale cached value for {symbol}")
                return cached

            raise FundingFetchError(f"Failed to fetch funding rate: {str(e)}")

    async def _fetch_with_retry(self, symbol: str) -> FundingRate:
        """
        Fetch funding rate with exponential backoff retry.

        Args:
            symbol: Trading symbol

        Returns:
            FundingRate from API

        Raises:
            FundingFetchError: After all retries exhausted
        """
        last_error = None
        backoff = 1.0  # Initial backoff in seconds

        for attempt in range(self.max_retries):
            try:
                # Make API request
                response = await self._client.get(
                    self.FUNDING_ENDPOINT, params={"symbol": symbol, "limit": 1}
                )

                # Check for rate limiting
                if response.status_code == 429:
                    wait_time = min(backoff * (2**attempt), 60)  # Cap at 60s
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue

                # Check for client errors
                if response.status_code >= 400:
                    data = await response.json()
                    if "msg" in data:
                        raise FundingFetchError(data["msg"])
                    raise FundingFetchError(f"API error {response.status_code}")

                # Parse successful response
                data = await response.json()

                # Handle array response (limit=1 returns array)
                if isinstance(data, list):
                    if not data:
                        raise FundingFetchError(f"No funding rate data for {symbol}")
                    data = data[0]

                # Create FundingRate from response
                return FundingRate.from_binance(data)

            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"Request error on attempt {attempt + 1}: {e}")

                if attempt < self.max_retries - 1:
                    wait_time = min(backoff * (2**attempt), 60)
                    await asyncio.sleep(wait_time)
                    continue

        # All retries exhausted
        raise FundingFetchError(f"Max retries exceeded: {last_error}")

    def get_cached_funding(self, symbol: str) -> Optional[FundingRate]:
        """
        Get cached funding rate if available.

        Synchronous method for fallback scenarios.

        Args:
            symbol: Trading symbol

        Returns:
            Cached FundingRate or None
        """
        cache_key = f"funding:{symbol}"
        return self._cache.get(cache_key)

    async def close(self):
        """Close HTTP client connections."""
        await self._client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
