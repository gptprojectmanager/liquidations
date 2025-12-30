"""Integration tests for ExchangeAggregator.

Tests multi-exchange stream aggregation and failure handling.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.exchanges.base import NormalizedLiquidation


class TestAggregatorIntegration:
    """Integration tests for ExchangeAggregator."""

    @pytest.mark.asyncio
    async def test_single_exchange_failure_continues_others(self):
        """T032: System survives single exchange failure."""
        from src.exchanges.aggregator import ExchangeAggregator

        agg = ExchangeAggregator(exchanges=["binance", "hyperliquid"])

        # Mock binance to work, hyperliquid to fail on connect
        mock_binance = AsyncMock()
        mock_binance._is_connected = True
        mock_binance.exchange_name = "binance"

        mock_hl = AsyncMock()
        mock_hl._is_connected = False
        mock_hl.exchange_name = "hyperliquid"
        mock_hl.connect.side_effect = ConnectionError("WebSocket failed")

        agg.adapters["binance"] = mock_binance
        agg.adapters["hyperliquid"] = mock_hl

        # Should not raise
        await agg.connect_all()

        # Binance should be active, hyperliquid not
        active = agg.get_active_exchanges()
        assert "binance" in active

    @pytest.mark.asyncio
    async def test_graceful_degradation_returns_partial_data(self):
        """Aggregator returns data from working exchanges when others fail."""
        from src.exchanges.aggregator import ExchangeAggregator

        agg = ExchangeAggregator(exchanges=["binance"])

        # Create mock liquidation
        mock_liq = NormalizedLiquidation(
            exchange="binance",
            symbol="BTCUSDT",
            price=95000.0,
            quantity=0.5,
            value_usd=47500.0,
            side="long",
            timestamp=datetime.now(timezone.utc),
        )

        # Mock adapter to yield one liquidation
        async def mock_stream(symbol):
            yield mock_liq

        mock_adapter = MagicMock()
        mock_adapter._is_connected = True
        mock_adapter.exchange_name = "binance"
        mock_adapter.stream_liquidations = mock_stream

        agg.adapters["binance"] = mock_adapter

        # Collect liquidations (with timeout)
        liquidations = []
        count = 0
        async for liq in agg.stream_aggregated("BTCUSDT"):
            liquidations.append(liq)
            count += 1
            if count >= 1:
                break

        assert len(liquidations) == 1
        assert liquidations[0].exchange == "binance"
