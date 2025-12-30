"""Exchange adapters for multi-exchange liquidation data aggregation.

This module provides:
- NormalizedLiquidation: Unified liquidation event schema
- ExchangeHealth: Connection health metrics
- ExchangeAdapter: Abstract base class for exchange-specific adapters
- ExchangeAggregator: Multi-exchange stream multiplexer
"""

from src.exchanges.aggregator import ExchangeAggregator
from src.exchanges.base import (
    ExchangeAdapter,
    ExchangeHealth,
    NormalizedLiquidation,
)
from src.exchanges.binance import BinanceAdapter
from src.exchanges.bybit import BybitAdapter
from src.exchanges.hyperliquid import HyperliquidAdapter

__all__ = [
    "NormalizedLiquidation",
    "ExchangeHealth",
    "ExchangeAdapter",
    "ExchangeAggregator",
    "BinanceAdapter",
    "HyperliquidAdapter",
    "BybitAdapter",
]
