"""
Integration tests for Binance funding rate API.
Feature: LIQHEAT-005
Task: T016-T018, T033 - Test Binance API integration
TDD: Red phase
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.models.funding.funding_rate import FundingRate

# These imports will fail initially (TDD Red phase)
from src.services.funding.funding_fetcher import FundingFetcher, FundingFetchError


class TestFundingFetcher:
    """Test suite for Binance funding rate API integration."""

    @pytest.mark.asyncio
    async def test_fetch_current_funding_rate(self):
        """Test fetching current funding rate from Binance."""
        # Arrange
        fetcher = FundingFetcher(cache_ttl=300)

        # Mock the HTTP response
        mock_response = {
            "symbol": "BTCUSDT",
            "fundingRate": "0.00030000",
            "fundingTime": 1735689600000,
            "markPrice": "95432.12345678",
        }

        with patch.object(fetcher._client, "get", new_callable=AsyncMock) as mock_get:
            mock_response_obj = AsyncMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.status_code = 200
            mock_get.return_value = mock_response_obj

            # Act
            funding = await fetcher.get_funding_rate("BTCUSDT")

            # Assert
            assert isinstance(funding, FundingRate)
            assert funding.symbol == "BTCUSDT"
            assert funding.rate == Decimal("0.0003")
            assert funding.source == "binance"
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_with_cache_hit(self):
        """Test that cached values are returned without API call."""
        # Arrange
        fetcher = FundingFetcher(cache_ttl=300)

        mock_response = {
            "symbol": "BTCUSDT",
            "fundingRate": "0.00030000",
            "fundingTime": 1735689600000,
        }

        with patch.object(fetcher._client, "get", new_callable=AsyncMock) as mock_get:
            mock_response_obj = AsyncMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.status_code = 200
            mock_get.return_value = mock_response_obj

            # Act - First call should hit API
            funding1 = await fetcher.get_funding_rate("BTCUSDT")

            # Act - Second call should use cache
            funding2 = await fetcher.get_funding_rate("BTCUSDT")

            # Assert
            assert funding1 == funding2
            mock_get.assert_called_once()  # Only one API call

    @pytest.mark.asyncio
    async def test_fetch_with_retry_on_rate_limit(self):
        """Test retry logic on rate limit (429) response."""
        # Arrange
        fetcher = FundingFetcher(cache_ttl=300, max_retries=3)

        mock_response_fail = httpx.Response(
            status_code=429, json={"code": -1003, "msg": "Too many requests"}
        )

        mock_response_success = {
            "symbol": "BTCUSDT",
            "fundingRate": "0.00030000",
            "fundingTime": 1735689600000,
        }

        with patch.object(fetcher._client, "get", new_callable=AsyncMock) as mock_get:
            # First call fails with 429, second succeeds
            success_response = AsyncMock()
            success_response.json = AsyncMock(return_value=mock_response_success)
            success_response.status_code = 200

            mock_get.side_effect = [mock_response_fail, success_response]

            # Act
            funding = await fetcher.get_funding_rate("BTCUSDT")

            # Assert
            assert funding.symbol == "BTCUSDT"
            assert mock_get.call_count == 2  # Retried once

    @pytest.mark.asyncio
    async def test_fetch_error_handling(self):
        """Test error handling for API failures."""
        # Arrange
        fetcher = FundingFetcher(cache_ttl=300)

        with patch.object(fetcher._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.RequestError("Connection failed")

            # Act & Assert
            with pytest.raises(FundingFetchError, match="Connection failed"):
                await fetcher.get_funding_rate("BTCUSDT")

    @pytest.mark.asyncio
    async def test_fetch_invalid_symbol(self):
        """Test handling of invalid symbol."""
        # Arrange
        fetcher = FundingFetcher(cache_ttl=300)

        mock_response = {"code": -1121, "msg": "Invalid symbol"}

        with patch.object(fetcher._client, "get", new_callable=AsyncMock) as mock_get:
            mock_response_obj = AsyncMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.status_code = 400
            mock_get.return_value = mock_response_obj

            # Act & Assert
            with pytest.raises(FundingFetchError, match="Invalid symbol"):
                await fetcher.get_funding_rate("INVALID")

    @pytest.mark.asyncio
    async def test_get_cached_funding_fallback(self):
        """Test fallback to cached value when API unavailable."""
        # Arrange
        fetcher = FundingFetcher(cache_ttl=300)

        # First, populate cache
        mock_response = {
            "symbol": "BTCUSDT",
            "fundingRate": "0.00030000",
            "fundingTime": 1735689600000,
        }

        with patch.object(fetcher._client, "get", new_callable=AsyncMock) as mock_get:
            mock_response_obj = AsyncMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.status_code = 200
            mock_get.return_value = mock_response_obj

            # Populate cache
            await fetcher.get_funding_rate("BTCUSDT")

        # Now test fallback when API fails
        with patch.object(fetcher._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.RequestError("API down")

            # Act - Should return cached value
            cached = fetcher.get_cached_funding("BTCUSDT")

            # Assert
            assert cached is not None
            assert cached.symbol == "BTCUSDT"
            assert cached.rate == Decimal("0.0003")

    def test_sync_get_cached_funding(self):
        """Test synchronous cached funding retrieval."""
        # Arrange
        fetcher = FundingFetcher(cache_ttl=300)

        # Manually add to cache
        funding = FundingRate(
            symbol="BTCUSDT", rate=Decimal("0.0003"), funding_time=datetime.now(timezone.utc)
        )
        fetcher._cache.set("funding:BTCUSDT", funding)

        # Act
        cached = fetcher.get_cached_funding("BTCUSDT")

        # Assert
        assert cached == funding
