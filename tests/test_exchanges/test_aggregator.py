"""Tests for ExchangeAggregator service.

TDD: Tests for multi-exchange stream aggregation.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exchanges.base import ExchangeHealth


class TestExchangeAggregator:
    """Tests for ExchangeAggregator class."""

    def test_initialization_default_exchanges(self):
        """T029: ExchangeAggregator initializes with default exchanges."""
        from src.exchanges.aggregator import ExchangeAggregator

        agg = ExchangeAggregator()

        # Should have all supported exchanges
        assert "binance" in agg.exchanges
        assert "hyperliquid" in agg.exchanges
        assert "bybit" in agg.exchanges

    def test_initialization_custom_exchanges(self):
        """ExchangeAggregator accepts custom exchange list."""
        from src.exchanges.aggregator import ExchangeAggregator

        agg = ExchangeAggregator(exchanges=["binance", "hyperliquid"])

        assert agg.exchanges == ["binance", "hyperliquid"]
        assert len(agg.adapters) == 2

    def test_unknown_exchange_logged(self):
        """ExchangeAggregator logs warning for unknown exchanges."""
        from src.exchanges.aggregator import ExchangeAggregator

        with patch("src.exchanges.aggregator.logger") as mock_logger:
            agg = ExchangeAggregator(exchanges=["binance", "unknown_exchange"])

            mock_logger.warning.assert_called()
            assert "binance" in agg.adapters
            assert "unknown_exchange" not in agg.adapters

    @pytest.mark.asyncio
    async def test_connect_all_parallel(self):
        """T030: connect_all() connects to all exchanges in parallel."""
        from src.exchanges.aggregator import ExchangeAggregator

        agg = ExchangeAggregator(exchanges=["binance"])

        # Mock the binance adapter
        mock_adapter = AsyncMock()
        agg.adapters["binance"] = mock_adapter

        await agg.connect_all()

        mock_adapter.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_all_handles_failures(self):
        """connect_all() continues even if some exchanges fail."""
        from src.exchanges.aggregator import ExchangeAggregator

        agg = ExchangeAggregator(exchanges=["binance", "hyperliquid"])

        # Make binance succeed, hyperliquid fail
        mock_binance = AsyncMock()
        mock_hl = AsyncMock()
        mock_hl.connect.side_effect = ConnectionError("Mock failure")

        agg.adapters["binance"] = mock_binance
        agg.adapters["hyperliquid"] = mock_hl

        # Should not raise, just log the failure
        await agg.connect_all()

        mock_binance.connect.assert_called_once()
        mock_hl.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_all(self):
        """disconnect_all() disconnects from all exchanges."""
        from src.exchanges.aggregator import ExchangeAggregator

        agg = ExchangeAggregator(exchanges=["binance"])

        mock_adapter = AsyncMock()
        agg.adapters["binance"] = mock_adapter

        await agg.disconnect_all()

        mock_adapter.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        """T031: health_check_all() returns health for all exchanges."""
        from src.exchanges.aggregator import ExchangeAggregator

        agg = ExchangeAggregator(exchanges=["binance"])

        mock_health = ExchangeHealth(
            exchange="binance",
            is_connected=True,
            last_heartbeat=datetime.now(timezone.utc),
            message_count=100,
            error_count=0,
            uptime_percent=99.5,
        )
        mock_adapter = AsyncMock()
        mock_adapter.health_check.return_value = mock_health
        agg.adapters["binance"] = mock_adapter

        result = await agg.health_check_all()

        assert "binance" in result
        assert result["binance"].is_connected is True

    def test_get_active_exchanges(self):
        """get_active_exchanges() returns connected exchanges."""
        from src.exchanges.aggregator import ExchangeAggregator

        agg = ExchangeAggregator(exchanges=["binance", "hyperliquid"])

        # Mock connected state
        mock_binance = MagicMock()
        mock_binance._is_connected = True
        mock_hl = MagicMock()
        mock_hl._is_connected = False

        agg.adapters["binance"] = mock_binance
        agg.adapters["hyperliquid"] = mock_hl

        active = agg.get_active_exchanges()

        assert "binance" in active
        assert "hyperliquid" not in active

    def test_supported_exchanges_registry(self):
        """SUPPORTED_EXCHANGES contains all adapters."""
        from src.exchanges.aggregator import ExchangeAggregator

        assert "binance" in ExchangeAggregator.SUPPORTED_EXCHANGES
        assert "hyperliquid" in ExchangeAggregator.SUPPORTED_EXCHANGES
        assert "bybit" in ExchangeAggregator.SUPPORTED_EXCHANGES
