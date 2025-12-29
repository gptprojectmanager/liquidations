"""Hyperliquid DEX adapter using WebSocket.

Connects to wss://api.hyperliquid.xyz/ws and subscribes to trades channel,
filtering for liquidation events.
"""

import json
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

import websockets

from src.exchanges.base import ExchangeAdapter, ExchangeHealth, NormalizedLiquidation

logger = logging.getLogger(__name__)


class HyperliquidAdapter(ExchangeAdapter):
    """Hyperliquid DEX adapter (WebSocket only)."""

    WS_URL = "wss://api.hyperliquid.xyz/ws"

    def __init__(self):
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._is_connected = False
        self._last_heartbeat: Optional[datetime] = None
        self._message_count = 0
        self._error_count = 0

    @property
    def exchange_name(self) -> str:
        return "hyperliquid"

    async def connect(self) -> None:
        """Connect to Hyperliquid WebSocket."""
        try:
            self._ws = await websockets.connect(self.WS_URL)
            self._is_connected = True
            self._last_heartbeat = datetime.now(timezone.utc)
            logger.info("Hyperliquid adapter connected (WebSocket)")
        except Exception as e:
            logger.error(f"Hyperliquid connection failed: {e}")
            raise

    async def disconnect(self) -> None:
        """Close WebSocket."""
        if self._ws:
            await self._ws.close()
            self._ws = None
            self._is_connected = False
            logger.info("Hyperliquid adapter disconnected")

    async def stream_liquidations(
        self, symbol: str = "BTCUSDT"
    ) -> AsyncIterator[NormalizedLiquidation]:
        """Stream liquidations from Hyperliquid trades channel.

        Subscribes to trades, filters for liquidation: true events.
        """
        if not self._is_connected:
            await self.connect()

        # Subscribe to trades channel
        coin = self._denormalize_symbol(symbol)  # "BTCUSDT" -> "BTC"
        subscribe_msg = {
            "method": "subscribe",
            "subscription": {"type": "trades", "coin": coin},
        }
        await self._ws.send(json.dumps(subscribe_msg))

        async for message in self._ws:
            try:
                data = json.loads(message)

                if data.get("channel") != "trades":
                    continue

                for trade in data.get("data", []):
                    if not trade.get("liquidation"):
                        continue

                    self._message_count += 1
                    self._last_heartbeat = datetime.now(timezone.utc)

                    yield NormalizedLiquidation(
                        exchange="hyperliquid",
                        symbol=symbol,  # Keep as "BTCUSDT"
                        price=float(trade["px"]),
                        quantity=float(trade["sz"]),
                        value_usd=float(trade["px"]) * float(trade["sz"]),
                        side=self._normalize_side(trade["side"]),
                        timestamp=datetime.now(timezone.utc),  # HL doesn't provide timestamp
                        raw_data=trade,
                        liquidation_type="forced",
                        is_validated=True,
                        confidence=0.9,  # Lower confidence due to missing timestamp
                    )

            except json.JSONDecodeError as e:
                self._error_count += 1
                logger.error(f"Hyperliquid JSON parsing error: {e}")
            except Exception as e:
                self._error_count += 1
                logger.error(f"Hyperliquid stream error: {e}")

        # WebSocket loop exited (connection closed) - update state for consistency
        self._is_connected = False
        logger.warning("Hyperliquid WebSocket connection closed")

    def _normalize_side(self, side: str) -> str:
        """Convert Hyperliquid side to standard format.

        Hyperliquid uses:
        - A (Ask) = trade hit ask = forced buy = SHORT position liquidated
        - B (Bid) = trade hit bid = forced sell = LONG position liquidated
        """
        if side == "A":
            return "short"
        elif side == "B":
            return "long"
        return side.lower()

    def _denormalize_symbol(self, symbol: str) -> str:
        """Convert standard symbol to Hyperliquid format for subscription.

        "BTCUSDT" -> "BTC"
        """
        if symbol.endswith("USDT"):
            return symbol[:-4]
        return symbol

    async def fetch_historical(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> list[NormalizedLiquidation]:
        """Hyperliquid doesn't provide historical liquidation API."""
        return []

    async def health_check(self) -> ExchangeHealth:
        """Check WebSocket connection."""
        is_alive = self._ws is not None and not self._ws.closed if self._ws else False

        return ExchangeHealth(
            exchange="hyperliquid",
            is_connected=is_alive and self._is_connected,
            last_heartbeat=self._last_heartbeat or datetime.now(timezone.utc),
            message_count=self._message_count,
            error_count=self._error_count,
            uptime_percent=95.0 if is_alive else 0.0,
        )

    def normalize_symbol(self, exchange_symbol: str) -> str:
        """Convert Hyperliquid symbol to standard format.

        "BTC" -> "BTCUSDT"
        """
        if not exchange_symbol.endswith("USDT"):
            return f"{exchange_symbol}USDT"
        return exchange_symbol
