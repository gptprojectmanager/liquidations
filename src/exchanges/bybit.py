"""Bybit adapter - STUB due to liquidation topic removal.

ISSUE: Bybit removed the liquidation WebSocket topic.
WORKAROUND: None currently available.
STATUS: Lower priority - implement after Binance + Hyperliquid stable.
"""

import logging
from datetime import datetime, timezone
from typing import AsyncIterator

from src.exchanges.base import ExchangeAdapter, ExchangeHealth, NormalizedLiquidation

logger = logging.getLogger(__name__)


class BybitAdapter(ExchangeAdapter):
    """Bybit adapter (STUB - liquidation topic unavailable)."""

    def __init__(self):
        self._is_connected = False
        self._last_heartbeat = datetime.now(timezone.utc)

    @property
    def exchange_name(self) -> str:
        return "bybit"

    async def connect(self) -> None:
        """Raise NotImplementedError - liquidation topic removed."""
        raise NotImplementedError(
            "Bybit liquidation topic removed - awaiting alternative data source"
        )

    async def disconnect(self) -> None:
        """No-op for stub."""
        self._is_connected = False

    async def stream_liquidations(
        self, symbol: str = "BTCUSDT"
    ) -> AsyncIterator[NormalizedLiquidation]:
        """Raise NotImplementedError - liquidation topic removed."""
        raise NotImplementedError("Bybit liquidation topic removed")
        yield  # Make this a generator

    async def fetch_historical(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> list[NormalizedLiquidation]:
        """Return empty list - historical API untested."""
        return []

    async def health_check(self) -> ExchangeHealth:
        """Return disconnected health status."""
        return ExchangeHealth(
            exchange="bybit",
            is_connected=False,
            last_heartbeat=self._last_heartbeat,
            message_count=0,
            error_count=0,
            uptime_percent=0.0,
        )

    def normalize_symbol(self, exchange_symbol: str) -> str:
        """Bybit uses same format as Binance."""
        return exchange_symbol
