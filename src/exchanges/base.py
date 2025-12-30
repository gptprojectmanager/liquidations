"""Base interfaces for exchange adapters.

This module defines:
- NormalizedLiquidation: Unified liquidation event schema
- ExchangeHealth: Connection health metrics
- ExchangeAdapter: Abstract base class for exchange-specific adapters
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import AsyncIterator, Optional

from pydantic.dataclasses import dataclass


@dataclass
class NormalizedLiquidation:
    """Normalized liquidation event across all exchanges.

    Uses Pydantic dataclass for automatic validation of exchange data.

    Attributes:
        exchange: Exchange identifier ("binance", "hyperliquid", "bybit")
        symbol: Normalized symbol (e.g., "BTCUSDT")
        price: Liquidation price in quote currency
        quantity: Position size in base asset
        value_usd: Notional value (price * quantity)
        side: Position side ("long" or "short")
        timestamp: Event timestamp (UTC)
        raw_data: Original exchange response for debugging
        liquidation_type: Type of liquidation ("forced", "adl", "isolated", "cross")
        leverage: Position leverage if available
        is_validated: True after Pydantic schema parse succeeds
        confidence: Quality score (1.0=complete, 0.9=missing timestamp, 0.8=inferred)
    """

    # Required fields
    exchange: str
    symbol: str
    price: float
    quantity: float
    value_usd: float
    side: str
    timestamp: datetime

    # Optional metadata
    raw_data: Optional[dict] = None
    liquidation_type: Optional[str] = None
    leverage: Optional[float] = None

    # Validation flags
    is_validated: bool = False
    confidence: float = 1.0


@dataclass
class ExchangeHealth:
    """Health status of exchange connection.

    Attributes:
        exchange: Exchange identifier
        is_connected: Current connection status
        last_heartbeat: Last successful message/ping
        message_count: Messages received in last 60s
        error_count: Errors in last 60s
        uptime_percent: Last 24h uptime (0.0-100.0)
    """

    exchange: str
    is_connected: bool
    last_heartbeat: datetime
    message_count: int
    error_count: int
    uptime_percent: float


class ExchangeAdapter(ABC):
    """Abstract base class for exchange-specific adapters.

    Each exchange adapter must implement these methods to provide
    a unified interface for liquidation data streaming.
    """

    @property
    @abstractmethod
    def exchange_name(self) -> str:
        """Return exchange identifier (lowercase)."""
        pass

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to exchange (WebSocket or REST)."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close connection."""
        pass

    @abstractmethod
    async def stream_liquidations(
        self, symbol: str = "BTCUSDT"
    ) -> AsyncIterator[NormalizedLiquidation]:
        """Stream real-time liquidation events.

        Args:
            symbol: Trading pair symbol (default: BTCUSDT)

        Yields:
            NormalizedLiquidation: Normalized liquidation events

        Raises:
            ConnectionError: If exchange connection fails
            ValidationError: If data doesn't match schema
        """
        pass

    @abstractmethod
    async def fetch_historical(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> list[NormalizedLiquidation]:
        """Fetch historical liquidations (if available).

        Args:
            symbol: Trading pair symbol
            start_time: Start of time range
            end_time: End of time range

        Returns:
            Empty list if exchange doesn't support historical data.
        """
        pass

    @abstractmethod
    async def health_check(self) -> ExchangeHealth:
        """Check adapter health status."""
        pass

    @abstractmethod
    def normalize_symbol(self, exchange_symbol: str) -> str:
        """Convert exchange-specific symbol to standard format.

        Examples:
            - Binance: "BTCUSDT" -> "BTCUSDT"
            - Hyperliquid: "BTC" -> "BTCUSDT"
            - OKX: "BTC-USDT-SWAP" -> "BTCUSDT"
        """
        pass
