"""Exchange Aggregator service.

Multiplexes liquidation streams from multiple exchanges into a single iterator.
Implements graceful degradation and automatic reconnection.
"""

import asyncio
import logging
from typing import AsyncIterator, Optional

from src.exchanges.base import ExchangeAdapter, ExchangeHealth, NormalizedLiquidation
from src.exchanges.binance import BinanceAdapter
from src.exchanges.bybit import BybitAdapter
from src.exchanges.hyperliquid import HyperliquidAdapter

logger = logging.getLogger(__name__)


class ExchangeAggregator:
    """Aggregates liquidation data from multiple exchanges."""

    SUPPORTED_EXCHANGES: dict[str, type[ExchangeAdapter]] = {
        "binance": BinanceAdapter,
        "hyperliquid": HyperliquidAdapter,
        "bybit": BybitAdapter,
    }

    # Reconnection settings
    MAX_RETRIES = 3
    BACKOFF_SECONDS = [1, 2, 4]  # Exponential backoff

    def __init__(self, exchanges: Optional[list[str]] = None):
        """Initialize aggregator.

        Args:
            exchanges: List of exchange names to aggregate (default: all)
        """
        self.exchanges = exchanges or list(self.SUPPORTED_EXCHANGES.keys())
        self.adapters: dict[str, ExchangeAdapter] = {}

        # Initialize adapters
        for exchange in self.exchanges:
            if exchange in self.SUPPORTED_EXCHANGES:
                self.adapters[exchange] = self.SUPPORTED_EXCHANGES[exchange]()
            else:
                logger.warning(f"Unknown exchange: {exchange}")

    async def connect_all(self) -> None:
        """Connect to all exchanges in parallel."""
        tasks = []
        exchange_names = []

        for exchange, adapter in self.adapters.items():
            tasks.append(adapter.connect())
            exchange_names.append(exchange)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for exchange, result in zip(exchange_names, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to connect to {exchange}: {result}")

    async def disconnect_all(self) -> None:
        """Disconnect from all exchanges."""
        tasks = [adapter.disconnect() for adapter in self.adapters.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stream_aggregated(
        self, symbol: str = "BTCUSDT"
    ) -> AsyncIterator[NormalizedLiquidation]:
        """Stream liquidations from all exchanges (multiplexed).

        Uses asyncio.Queue to merge streams from multiple adapters.
        """
        queue: asyncio.Queue[NormalizedLiquidation] = asyncio.Queue(maxsize=1000)

        async def pump(adapter: ExchangeAdapter) -> None:
            """Pump liquidations from adapter into queue."""
            retry_count = 0

            while retry_count < self.MAX_RETRIES:
                try:
                    async for liq in adapter.stream_liquidations(symbol):
                        await queue.put(liq)
                        retry_count = 0  # Reset on success
                except NotImplementedError:
                    # Adapter not implemented (e.g., Bybit)
                    logger.info(f"{adapter.exchange_name} not implemented, skipping")
                    return
                except Exception as e:
                    retry_count += 1
                    if retry_count < self.MAX_RETRIES:
                        backoff = self.BACKOFF_SECONDS[retry_count - 1]
                        logger.warning(
                            f"{adapter.exchange_name} stream error "
                            f"(retry {retry_count}/{self.MAX_RETRIES}): {e}"
                        )
                        await asyncio.sleep(backoff)
                    else:
                        logger.error(
                            f"{adapter.exchange_name} stream failed "
                            f"after {self.MAX_RETRIES} retries: {e}"
                        )
                        return

        # Start all pumps in background
        tasks = [asyncio.create_task(pump(adapter)) for adapter in self.adapters.values()]

        try:
            while True:
                try:
                    liq = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield liq
                except asyncio.TimeoutError:
                    logger.warning("No liquidations received for 30s")
                    # Continue waiting, don't break
        finally:
            # Cancel pump tasks
            for task in tasks:
                task.cancel()

    async def health_check_all(self) -> dict[str, ExchangeHealth]:
        """Check health of all exchanges."""
        tasks = {}
        for exchange, adapter in self.adapters.items():
            tasks[exchange] = adapter.health_check()

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        health_results = {}
        for exchange, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Health check failed for {exchange}: {result}")
                health_results[exchange] = None
            else:
                health_results[exchange] = result

        return health_results

    def get_active_exchanges(self) -> list[str]:
        """Return list of successfully connected exchanges."""
        return [
            exchange
            for exchange, adapter in self.adapters.items()
            if hasattr(adapter, "_is_connected") and adapter._is_connected
        ]
