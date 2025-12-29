"""Tests for Bybit exchange adapter (stub).

TDD RED Phase: Tests for stub that raises NotImplementedError.
"""

from datetime import datetime, timezone

import pytest


class TestBybitAdapter:
    """Tests for BybitAdapter stub class."""

    def test_exchange_name(self):
        """T017: BybitAdapter.exchange_name returns 'bybit'."""
        from src.exchanges.bybit import BybitAdapter

        adapter = BybitAdapter()
        assert adapter.exchange_name == "bybit"

    @pytest.mark.asyncio
    async def test_connect_raises_not_implemented(self):
        """T017: BybitAdapter.connect() raises NotImplementedError."""
        from src.exchanges.bybit import BybitAdapter

        adapter = BybitAdapter()

        with pytest.raises(NotImplementedError) as exc_info:
            await adapter.connect()

        assert "liquidation topic removed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_stream_liquidations_raises_not_implemented(self):
        """BybitAdapter.stream_liquidations() raises NotImplementedError."""
        from src.exchanges.bybit import BybitAdapter

        adapter = BybitAdapter()

        with pytest.raises(NotImplementedError):
            async for _ in adapter.stream_liquidations("BTCUSDT"):
                pass

    @pytest.mark.asyncio
    async def test_fetch_historical_returns_empty(self):
        """BybitAdapter.fetch_historical() returns empty list."""
        from src.exchanges.bybit import BybitAdapter

        adapter = BybitAdapter()

        result = await adapter.fetch_historical(
            "BTCUSDT",
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        )

        assert result == []

    def test_normalize_symbol_passthrough(self):
        """BybitAdapter.normalize_symbol() returns symbol unchanged."""
        from src.exchanges.bybit import BybitAdapter

        adapter = BybitAdapter()

        # Bybit uses same format as Binance
        assert adapter.normalize_symbol("BTCUSDT") == "BTCUSDT"
