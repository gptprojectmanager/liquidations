"""Tests for Binance exchange adapter.

TDD RED Phase: These tests should FAIL until implementation is complete.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exchanges.base import ExchangeHealth, NormalizedLiquidation


class TestBinanceAdapter:
    """Tests for BinanceAdapter class."""

    def test_exchange_name(self):
        """T013: BinanceAdapter.exchange_name returns 'binance'."""
        from src.exchanges.binance import BinanceAdapter

        adapter = BinanceAdapter()
        assert adapter.exchange_name == "binance"

    @pytest.mark.asyncio
    async def test_connect_creates_session(self):
        """T013: BinanceAdapter.connect() creates aiohttp session."""
        from src.exchanges.binance import BinanceAdapter

        adapter = BinanceAdapter()
        assert adapter._session is None
        assert adapter._is_connected is False

        await adapter.connect()

        assert adapter._session is not None
        assert adapter._is_connected is True

        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect_closes_session(self):
        """BinanceAdapter.disconnect() closes session cleanly."""
        from src.exchanges.binance import BinanceAdapter

        adapter = BinanceAdapter()
        await adapter.connect()
        assert adapter._is_connected is True

        await adapter.disconnect()

        assert adapter._is_connected is False
        assert adapter._session is None

    def test_normalize_symbol_passthrough(self):
        """T014: BinanceAdapter.normalize_symbol() returns symbol unchanged."""
        from src.exchanges.binance import BinanceAdapter

        adapter = BinanceAdapter()

        # Binance already uses standard format
        assert adapter.normalize_symbol("BTCUSDT") == "BTCUSDT"
        assert adapter.normalize_symbol("ETHUSDT") == "ETHUSDT"

    @pytest.mark.asyncio
    async def test_health_check_when_connected(self):
        """BinanceAdapter.health_check() returns health when connected."""
        from src.exchanges.binance import BinanceAdapter

        adapter = BinanceAdapter()

        # Create mock session manually to avoid real network calls
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        # Setup async context manager properly
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_session.get.return_value = mock_cm

        adapter._session = mock_session
        adapter._is_connected = True

        health = await adapter.health_check()

        assert isinstance(health, ExchangeHealth)
        assert health.exchange == "binance"
        assert health.is_connected is True

        adapter._is_connected = False

    @pytest.mark.asyncio
    async def test_health_check_when_disconnected(self):
        """BinanceAdapter.health_check() handles disconnected state."""
        from src.exchanges.binance import BinanceAdapter

        adapter = BinanceAdapter()
        # Don't connect - should still return health (disconnected)

        health = await adapter.health_check()

        assert isinstance(health, ExchangeHealth)
        assert health.exchange == "binance"
        assert health.is_connected is False

    @pytest.mark.asyncio
    async def test_stream_liquidations_yields_normalized_events(self):
        """BinanceAdapter.stream_liquidations() yields NormalizedLiquidation."""
        from src.exchanges.binance import BinanceAdapter

        adapter = BinanceAdapter()

        # Mock response data
        mock_data = [
            {
                "orderId": 12345,
                "symbol": "BTCUSDT",
                "price": "95000.0",
                "origQty": "0.5",
                "side": "SELL",  # SELL = long liquidation
                "time": 1703865600000,  # Unix ms
            }
        ]

        with patch.object(adapter, "_session") as mock_session:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value=mock_data)
            mock_response.raise_for_status = MagicMock()
            mock_session.get.return_value.__aenter__.return_value = mock_response

            adapter._is_connected = True
            adapter._session = mock_session

            # Get first liquidation from stream (then break)
            count = 0
            async for liq in adapter.stream_liquidations("BTCUSDT"):
                assert isinstance(liq, NormalizedLiquidation)
                assert liq.exchange == "binance"
                assert liq.symbol == "BTCUSDT"
                assert liq.price == 95000.0
                assert liq.side == "long"  # SELL -> long liquidated
                count += 1
                break  # Stop after first

            assert count == 1

    @pytest.mark.asyncio
    async def test_fetch_historical_returns_empty(self):
        """BinanceAdapter.fetch_historical() returns empty list (uses DuckDB)."""
        from src.exchanges.binance import BinanceAdapter

        adapter = BinanceAdapter()
        result = await adapter.fetch_historical(
            "BTCUSDT",
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        )

        assert result == []
