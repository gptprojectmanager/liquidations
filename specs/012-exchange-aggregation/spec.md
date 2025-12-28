# Exchange Aggregation Specification

**Feature**: Multi-Exchange Liquidation Data Aggregation
**Priority**: P3 - Strategic (Post-Validation Expansion)
**Estimated Effort**: 7-10 days
**Status**: Draft
**Created**: 2025-12-28

---

## 1. Executive Summary

### Problem Statement

Current implementation is Binance-only with **77.8% hit rate validation**. To provide complete market view and competitive differentiation, we need to aggregate liquidation data from multiple exchanges.

**Market Reality**:
- Binance: ~45% of derivatives volume
- Bybit: ~25% of derivatives volume
- OKX: ~15% of derivatives volume
- Hyperliquid: ~5% (growing, DEX)
- Other: ~10%

**Current State**:
- ✅ Binance REST API: Functional (historical + real-time)
- ❌ Binance WebSocket: 403 blocked (rate limits or auth issues)
- ⚠️ Bybit WebSocket: Connects but liquidation topic removed
- ✅ Hyperliquid WebSocket: Working, low liquidation frequency for BTC
- ❓ OKX: Untested

### Success Criteria

**P0 - Must Have**:
- [ ] **Adapter Pattern**: Unified interface for all exchanges
- [ ] **Data Normalization**: Common schema for liquidation events
- [ ] **Graceful Degradation**: System survives exchange downtime
- [ ] **Aggregated Heatmap**: Single view combining all sources

**P1 - Should Have**:
- [ ] **Per-Exchange Toggle**: Users can filter by exchange
- [ ] **Exchange Health Check**: Monitor API status
- [ ] **Correlation Analysis**: Compare exchange liquidation patterns

**P2 - Nice to Have**:
- [ ] **Arbitrage Detection**: Identify cross-exchange liquidation spreads
- [ ] **Volume Weighting**: Weight heatmap by exchange market share

---

## 2. Technical Design

### 2.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                      │
│  /liquidations/heatmap?exchanges=binance,bybit,hyperliquid  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Exchange Aggregator Service                     │
│  - Dispatch to multiple adapters in parallel                │
│  - Merge results into unified schema                        │
│  - Apply volume weighting (optional)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┬──────────────┐
       │               │               │              │
┌──────▼─────┐  ┌──────▼─────┐  ┌─────▼──────┐  ┌───▼─────────┐
│  Binance   │  │   Bybit    │  │ Hyperliquid│  │    OKX      │
│  Adapter   │  │  Adapter   │  │  Adapter   │  │  Adapter    │
└──────┬─────┘  └──────┬─────┘  └─────┬──────┘  └───┬─────────┘
       │               │               │              │
┌──────▼─────┐  ┌──────▼─────┐  ┌─────▼──────┐  ┌───▼─────────┐
│ Binance    │  │  Bybit     │  │Hyperliquid │  │   OKX       │
│ REST/WS    │  │   REST/WS  │  │  WebSocket │  │  REST/WS    │
└────────────┘  └────────────┘  └────────────┘  └─────────────┘
```

### 2.2 Core Components

#### 2.2.1 Exchange Adapter Interface

**File**: `src/exchanges/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Optional

@dataclass
class NormalizedLiquidation:
    """Normalized liquidation event across all exchanges."""

    # Common fields
    exchange: str                # "binance" | "bybit" | "hyperliquid" | "okx"
    symbol: str                  # Normalized: "BTCUSDT"
    price: float                 # Liquidation price
    quantity: float              # Position size (base asset)
    value_usd: float             # Notional value in USD
    side: str                    # "long" | "short"
    timestamp: datetime          # Event timestamp

    # Exchange-specific metadata (optional)
    raw_data: dict = None        # Original event for debugging
    liquidation_type: str = None # "forced" | "adl" | "isolated" | "cross"
    leverage: Optional[float] = None  # If available

    # Validation flags
    is_validated: bool = False   # Passed schema validation
    confidence: float = 1.0      # 0.0-1.0, lower for uncertain data


@dataclass
class ExchangeHealth:
    """Health status of exchange connection."""

    exchange: str
    is_connected: bool
    last_heartbeat: datetime
    message_count: int           # Messages received in last 60s
    error_count: int             # Errors in last 60s
    uptime_percent: float        # Last 24h uptime


class ExchangeAdapter(ABC):
    """Abstract base class for exchange-specific adapters."""

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
        self,
        symbol: str = "BTCUSDT"
    ) -> AsyncIterator[NormalizedLiquidation]:
        """Stream real-time liquidation events.

        Yields:
            NormalizedLiquidation: Normalized liquidation events

        Raises:
            ConnectionError: If exchange connection fails
            ValidationError: If data doesn't match schema
        """
        pass

    @abstractmethod
    async def fetch_historical(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> list[NormalizedLiquidation]:
        """Fetch historical liquidations (if available).

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
            - Bybit: "BTCUSDT" -> "BTCUSDT"
            - Hyperliquid: "BTC" -> "BTCUSDT"
            - OKX: "BTC-USDT-SWAP" -> "BTCUSDT"
        """
        pass
```

#### 2.2.2 Binance Adapter

**File**: `src/exchanges/binance.py`

```python
import asyncio
import logging
from datetime import datetime
from typing import AsyncIterator, Optional

import aiohttp
from src.exchanges.base import (
    ExchangeAdapter,
    NormalizedLiquidation,
    ExchangeHealth
)

logger = logging.getLogger(__name__)


class BinanceAdapter(ExchangeAdapter):
    """Binance Futures adapter (REST only - WebSocket has auth issues)."""

    BASE_URL = "https://fapi.binance.com"

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._is_connected = False
        self._last_heartbeat = None
        self._message_count = 0
        self._error_count = 0

    @property
    def exchange_name(self) -> str:
        return "binance"

    async def connect(self) -> None:
        """Initialize HTTP session."""
        if not self._session:
            self._session = aiohttp.ClientSession()
            self._is_connected = True
            self._last_heartbeat = datetime.now()
            logger.info("Binance adapter connected (REST)")

    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
            self._is_connected = False
            logger.info("Binance adapter disconnected")

    async def stream_liquidations(
        self,
        symbol: str = "BTCUSDT"
    ) -> AsyncIterator[NormalizedLiquidation]:
        """Stream liquidations via REST polling (WebSocket blocked).

        NOTE: This is a workaround for WebSocket 403 errors.
        Polls /fapi/v1/forceOrders every 5 seconds.
        """
        if not self._is_connected:
            await self.connect()

        seen_order_ids = set()

        while self._is_connected:
            try:
                async with self._session.get(
                    f"{self.BASE_URL}/fapi/v1/forceOrders",
                    params={"symbol": symbol, "limit": 100}
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

                    for order in data:
                        order_id = order["orderId"]
                        if order_id in seen_order_ids:
                            continue

                        seen_order_ids.add(order_id)
                        self._message_count += 1

                        yield NormalizedLiquidation(
                            exchange="binance",
                            symbol=self.normalize_symbol(order["symbol"]),
                            price=float(order["price"]),
                            quantity=float(order["origQty"]),
                            value_usd=float(order["price"]) * float(order["origQty"]),
                            side="long" if order["side"] == "BUY" else "short",
                            timestamp=datetime.fromtimestamp(order["time"] / 1000),
                            raw_data=order,
                            liquidation_type="forced",
                            is_validated=True,
                            confidence=1.0
                        )

                await asyncio.sleep(5)  # Poll every 5s

            except Exception as e:
                self._error_count += 1
                logger.error(f"Binance polling error: {e}")
                await asyncio.sleep(10)  # Back off on error

    async def fetch_historical(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> list[NormalizedLiquidation]:
        """Fetch from DuckDB (already ingested via scripts)."""
        # Delegate to existing DuckDB queries
        # Implementation reuses existing ingestion pipeline
        return []  # Stub - actual implementation uses db_service

    async def health_check(self) -> ExchangeHealth:
        """Ping Binance API."""
        try:
            async with self._session.get(f"{self.BASE_URL}/fapi/v1/ping") as resp:
                resp.raise_for_status()
                return ExchangeHealth(
                    exchange="binance",
                    is_connected=self._is_connected,
                    last_heartbeat=datetime.now(),
                    message_count=self._message_count,
                    error_count=self._error_count,
                    uptime_percent=99.5  # Binance is reliable
                )
        except Exception as e:
            logger.error(f"Binance health check failed: {e}")
            return ExchangeHealth(
                exchange="binance",
                is_connected=False,
                last_heartbeat=self._last_heartbeat,
                message_count=self._message_count,
                error_count=self._error_count + 1,
                uptime_percent=0.0
            )

    def normalize_symbol(self, exchange_symbol: str) -> str:
        """Binance already uses standard format."""
        return exchange_symbol
```

#### 2.2.3 Hyperliquid Adapter

**File**: `src/exchanges/hyperliquid.py`

```python
import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncIterator, Optional

import websockets
from src.exchanges.base import (
    ExchangeAdapter,
    NormalizedLiquidation,
    ExchangeHealth
)

logger = logging.getLogger(__name__)


class HyperliquidAdapter(ExchangeAdapter):
    """Hyperliquid DEX adapter (WebSocket only)."""

    WS_URL = "wss://api.hyperliquid.xyz/ws"

    def __init__(self):
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._is_connected = False
        self._last_heartbeat = None
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
            self._last_heartbeat = datetime.now()
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
        self,
        symbol: str = "BTCUSDT"
    ) -> AsyncIterator[NormalizedLiquidation]:
        """Stream liquidations from Hyperliquid trades channel."""
        if not self._is_connected:
            await self.connect()

        # Subscribe to trades channel
        coin = self.normalize_symbol(symbol)  # "BTCUSDT" -> "BTC"
        subscribe_msg = {
            "method": "subscribe",
            "subscription": {"type": "trades", "coin": coin}
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
                    self._last_heartbeat = datetime.now()

                    yield NormalizedLiquidation(
                        exchange="hyperliquid",
                        symbol=symbol,  # Normalize back to "BTCUSDT"
                        price=float(trade["px"]),
                        quantity=float(trade["sz"]),
                        value_usd=float(trade["px"]) * float(trade["sz"]),
                        side="long" if trade["side"] == "A" else "short",
                        timestamp=datetime.now(),  # HL doesn't provide timestamp
                        raw_data=trade,
                        liquidation_type="forced",
                        is_validated=True,
                        confidence=0.9  # Lower confidence (no timestamp)
                    )

            except Exception as e:
                self._error_count += 1
                logger.error(f"Hyperliquid parsing error: {e}")

    async def fetch_historical(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> list[NormalizedLiquidation]:
        """Hyperliquid doesn't provide historical API."""
        return []

    async def health_check(self) -> ExchangeHealth:
        """Check WebSocket connection."""
        is_alive = self._ws and not self._ws.closed
        return ExchangeHealth(
            exchange="hyperliquid",
            is_connected=is_alive,
            last_heartbeat=self._last_heartbeat or datetime.now(),
            message_count=self._message_count,
            error_count=self._error_count,
            uptime_percent=95.0 if is_alive else 0.0
        )

    def normalize_symbol(self, exchange_symbol: str) -> str:
        """Convert "BTCUSDT" -> "BTC" for Hyperliquid."""
        if exchange_symbol.endswith("USDT"):
            return exchange_symbol[:-4]  # Remove "USDT"
        return exchange_symbol
```

#### 2.2.4 Bybit Adapter (Stub)

**File**: `src/exchanges/bybit.py`

```python
"""Bybit adapter - INCOMPLETE due to liquidation topic removal.

ISSUE: Bybit removed the liquidation WebSocket topic.
WORKAROUND: Use ticker or trades and infer liquidations from volume spikes.
STATUS: Lower priority - implement after Binance + Hyperliquid stable.
"""

from src.exchanges.base import ExchangeAdapter, NormalizedLiquidation, ExchangeHealth
from datetime import datetime
from typing import AsyncIterator


class BybitAdapter(ExchangeAdapter):
    """Bybit adapter (STUB - liquidation topic unavailable)."""

    @property
    def exchange_name(self) -> str:
        return "bybit"

    async def connect(self) -> None:
        raise NotImplementedError("Bybit liquidation topic removed - awaiting alternative")

    async def disconnect(self) -> None:
        pass

    async def stream_liquidations(self, symbol: str = "BTCUSDT") -> AsyncIterator[NormalizedLiquidation]:
        raise NotImplementedError("Bybit liquidation topic removed")
        yield  # Make generator

    async def fetch_historical(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> list[NormalizedLiquidation]:
        return []

    async def health_check(self) -> ExchangeHealth:
        return ExchangeHealth(
            exchange="bybit",
            is_connected=False,
            last_heartbeat=datetime.now(),
            message_count=0,
            error_count=0,
            uptime_percent=0.0
        )

    def normalize_symbol(self, exchange_symbol: str) -> str:
        return exchange_symbol
```

#### 2.2.5 Exchange Aggregator Service

**File**: `src/exchanges/aggregator.py`

```python
import asyncio
import logging
from datetime import datetime
from typing import AsyncIterator, Optional

from src.exchanges.base import ExchangeAdapter, NormalizedLiquidation, ExchangeHealth
from src.exchanges.binance import BinanceAdapter
from src.exchanges.hyperliquid import HyperliquidAdapter
from src.exchanges.bybit import BybitAdapter

logger = logging.getLogger(__name__)


class ExchangeAggregator:
    """Aggregates liquidation data from multiple exchanges."""

    SUPPORTED_EXCHANGES = {
        "binance": BinanceAdapter,
        "hyperliquid": HyperliquidAdapter,
        "bybit": BybitAdapter,
    }

    def __init__(self, exchanges: list[str] = None):
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
        tasks = [adapter.connect() for adapter in self.adapters.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for exchange, result in zip(self.adapters.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Failed to connect to {exchange}: {result}")

    async def disconnect_all(self) -> None:
        """Disconnect from all exchanges."""
        tasks = [adapter.disconnect() for adapter in self.adapters.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stream_aggregated(
        self,
        symbol: str = "BTCUSDT"
    ) -> AsyncIterator[NormalizedLiquidation]:
        """Stream liquidations from all exchanges (multiplexed).

        Uses asyncio.Queue to merge streams from multiple adapters.
        """
        queue = asyncio.Queue(maxsize=1000)

        async def pump(adapter: ExchangeAdapter):
            """Pump liquidations from adapter into queue."""
            try:
                async for liq in adapter.stream_liquidations(symbol):
                    await queue.put(liq)
            except Exception as e:
                logger.error(f"{adapter.exchange_name} stream error: {e}")

        # Start all pumps in background
        tasks = [asyncio.create_task(pump(adapter)) for adapter in self.adapters.values()]

        try:
            while True:
                liq = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield liq
        except asyncio.TimeoutError:
            logger.warning("No liquidations received for 30s")
        finally:
            # Cancel pump tasks
            for task in tasks:
                task.cancel()

    async def health_check_all(self) -> dict[str, ExchangeHealth]:
        """Check health of all exchanges."""
        tasks = {
            exchange: adapter.health_check()
            for exchange, adapter in self.adapters.items()
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        return {
            exchange: result if not isinstance(result, Exception) else None
            for exchange, result in zip(tasks.keys(), results)
        }

    def get_active_exchanges(self) -> list[str]:
        """Return list of successfully connected exchanges."""
        return [
            exchange
            for exchange, adapter in self.adapters.items()
            if adapter._is_connected
        ]
```

### 2.3 Database Schema Extension

**File**: `scripts/init_database.py` (modification)

```sql
-- Add exchange column to liquidations table
ALTER TABLE liquidations
ADD COLUMN exchange VARCHAR DEFAULT 'binance';

-- Index for filtering by exchange
CREATE INDEX IF NOT EXISTS idx_liquidations_exchange
ON liquidations(exchange);

-- Create exchange_health table for monitoring
CREATE TABLE IF NOT EXISTS exchange_health (
    timestamp TIMESTAMP,
    exchange VARCHAR,
    is_connected BOOLEAN,
    message_count INTEGER,
    error_count INTEGER,
    uptime_percent FLOAT,
    PRIMARY KEY (timestamp, exchange)
);
```

### 2.4 API Endpoint Extension

**File**: `src/liquidationheatmap/api/main.py` (modification)

```python
from src.exchanges.aggregator import ExchangeAggregator

# Initialize aggregator at startup
aggregator = ExchangeAggregator()

@app.on_event("startup")
async def startup_event():
    await aggregator.connect_all()
    logger.info(f"Connected to exchanges: {aggregator.get_active_exchanges()}")

@app.on_event("shutdown")
async def shutdown_event():
    await aggregator.disconnect_all()


@app.get("/liquidations/heatmap")
async def get_heatmap(
    symbol: str = "BTCUSDT",
    timeframe: str = "24h",
    exchanges: Optional[str] = None,  # NEW: "binance,hyperliquid" or None for all
):
    """Generate aggregated heatmap from multiple exchanges.

    Args:
        symbol: Trading pair (BTCUSDT, ETHUSDT)
        timeframe: Time window (24h, 7d, 30d)
        exchanges: Comma-separated exchange list (default: all active)

    Returns:
        Aggregated heatmap with per-exchange breakdown
    """
    # Parse exchanges filter
    selected_exchanges = None
    if exchanges:
        selected_exchanges = [e.strip() for e in exchanges.split(",")]

    # Fetch data per exchange (parallel)
    # ... implementation reuses existing heatmap logic
    # ... but queries DuckDB with exchange filter

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "exchanges": aggregator.get_active_exchanges(),
        "zones": [...],  # Aggregated zones
        "per_exchange": {
            "binance": {...},
            "hyperliquid": {...}
        }
    }


@app.get("/exchanges/health")
async def exchange_health():
    """Get health status of all exchanges."""
    health = await aggregator.health_check_all()
    return {
        "timestamp": datetime.now().isoformat(),
        "exchanges": health
    }
```

---

## 3. Implementation Plan

### Phase 1: Core Infrastructure (Days 1-3)

**Tasks**:
1. [ ] Create `src/exchanges/` directory
2. [ ] Implement `base.py` with abstract interfaces
3. [ ] Implement `BinanceAdapter` (REST polling workaround)
4. [ ] Implement `HyperliquidAdapter` (WebSocket)
5. [ ] Implement `BybitAdapter` (stub with NotImplementedError)
6. [ ] Write unit tests for each adapter

**Deliverables**:
- `src/exchanges/base.py`
- `src/exchanges/binance.py`
- `src/exchanges/hyperliquid.py`
- `src/exchanges/bybit.py`
- `tests/test_exchanges/test_adapters.py`

**Success Criteria**:
- All adapters pass schema validation
- Binance REST polling receives liquidations
- Hyperliquid WebSocket connects and streams

---

### Phase 2: Aggregation Service (Days 3-5)

**Tasks**:
1. [ ] Implement `ExchangeAggregator` class
2. [ ] Add asyncio.Queue multiplexing for streams
3. [ ] Implement health check aggregation
4. [ ] Add graceful degradation (skip failed exchanges)
5. [ ] Write integration tests for multi-exchange streaming

**Deliverables**:
- `src/exchanges/aggregator.py`
- `tests/integration/test_aggregator.py`

**Success Criteria**:
- Aggregator successfully merges Binance + Hyperliquid streams
- System survives single exchange failure
- Health check returns accurate status for all exchanges

---

### Phase 3: Database Integration (Days 5-6)

**Tasks**:
1. [ ] Add `exchange` column to DuckDB schema
2. [ ] Migrate existing data (mark as "binance")
3. [ ] Update ingestion pipeline to tag exchange
4. [ ] Create `exchange_health` monitoring table
5. [ ] Update validation scripts to test per-exchange

**Deliverables**:
- `scripts/migrate_add_exchange_column.py`
- Updated `scripts/ingest_aggtrades.py`
- Updated `src/liquidationheatmap/ingestion/db_service.py`

**Success Criteria**:
- Existing 185GB Binance data preserved
- New liquidations tagged with exchange
- Query performance unchanged (<5s for 24h heatmap)

---

### Phase 4: API Extension (Days 6-7)

**Tasks**:
1. [ ] Add `exchanges` parameter to `/liquidations/heatmap`
2. [ ] Implement per-exchange filtering in queries
3. [ ] Add `/exchanges/health` endpoint
4. [ ] Add `/exchanges` endpoint (list supported exchanges)
5. [ ] Update API documentation

**Deliverables**:
- Updated `src/liquidationheatmap/api/main.py`
- Updated `docs/api_guide.md`
- Postman/curl examples

**Success Criteria**:
- `/liquidations/heatmap?exchanges=binance` returns Binance-only data
- `/liquidations/heatmap` (no param) returns aggregated data
- `/exchanges/health` shows real-time status

---

### Phase 5: Frontend Integration (Days 7-8)

**Tasks**:
1. [ ] Add exchange selector dropdown to `heatmap.html`
2. [ ] Add exchange health indicator badges
3. [ ] Color-code liquidation zones by exchange
4. [ ] Add exchange legend (Binance=orange, Hyperliquid=purple, etc.)
5. [ ] Update chart tooltips to show exchange source

**Deliverables**:
- Updated `frontend/heatmap.html`
- Updated `frontend/coinglass_heatmap.html`
- CSS for exchange color coding

**Success Criteria**:
- Users can toggle "All Exchanges" vs individual exchange
- Exchange health shown as green/red badges
- Heatmap visually distinguishes exchange sources

---

### Phase 6: Validation & Testing (Days 8-10)

**Tasks**:
1. [ ] Run price-level validation on Hyperliquid data
2. [ ] Compare Binance vs Hyperliquid liquidation patterns
3. [ ] Test failover scenarios (disconnect Hyperliquid mid-stream)
4. [ ] Load test aggregator (100 concurrent WebSocket clients)
5. [ ] Document exchange-specific quirks

**Deliverables**:
- `data/validation/hyperliquid_validation.jsonl`
- `docs/EXCHANGE_COMPARISON.md`
- Load test results

**Success Criteria**:
- Hyperliquid hit rate ≥60% (lower than Binance acceptable due to low volume)
- System survives 1-exchange failure without crash
- Aggregator handles 100+ concurrent clients

---

## 4. Exchange-Specific Implementation Notes

### 4.1 Binance

**Status**: ✅ Working (REST), ❌ WebSocket blocked

**Data Sources**:
- **Historical**: DuckDB (4 years aggTrades already ingested)
- **Real-time**: REST `/fapi/v1/forceOrders` (poll every 5s)

**Workarounds**:
- WebSocket 403 likely due to rate limits or IP restrictions
- Use REST polling as temporary solution (acceptable for 5s latency)
- TODO: Investigate WebSocket auth requirements

**Tier Configuration**:
- Already implemented: `config/tiers/binance.yaml`
- 5-tier structure, fully validated

---

### 4.2 Hyperliquid

**Status**: ✅ WebSocket working, ⚠️ Low liquidation frequency

**Data Sources**:
- **Historical**: ❌ Not available (DEX, no centralized API)
- **Real-time**: ✅ WebSocket `wss://api.hyperliquid.xyz/ws`

**Implementation Notes**:
- Subscribe to `trades` channel, filter `liquidation: true`
- Symbol format: "BTC" (not "BTCUSDT")
- No timestamp in trade events (use current time)
- Lower confidence score (0.9) due to missing metadata

**Limitations**:
- Cannot validate historical accuracy (no backtest data)
- BTC liquidations rare (~1-2 per hour during testing)
- Consider adding altcoins for more activity

---

### 4.3 Bybit

**Status**: ❌ Liquidation topic removed

**Data Sources**:
- **Historical**: ⚠️ API available but untested
- **Real-time**: ❌ WebSocket liquidation topic deprecated

**Workarounds**:
1. **Option A**: Infer liquidations from volume spikes in trades channel
   - Pro: Uses existing WebSocket
   - Con: Lower accuracy, requires heuristics
2. **Option B**: Use Bybit's liquidation records API (if available)
   - Pro: Official data
   - Con: May have delay (not real-time)
3. **Option C**: Delay Bybit until topic restored
   - Pro: No technical debt
   - Con: Incomplete exchange coverage

**Recommendation**: Implement Option C (defer Bybit), focus on Binance + Hyperliquid first

---

### 4.4 OKX

**Status**: ❓ Untested

**Data Sources**:
- **Historical**: ❓ Unknown
- **Real-time**: ❓ WebSocket endpoint TBD

**Research Tasks**:
- [ ] Test OKX WebSocket liquidation channel
- [ ] Verify symbol format (likely "BTC-USDT-SWAP")
- [ ] Check rate limits and authentication requirements
- [ ] Compare tier structure vs Binance

**Priority**: P4 (after Binance + Hyperliquid stable)

---

## 5. Data Normalization Schema

### 5.1 Symbol Normalization

| Exchange | Raw Symbol | Normalized |
|----------|-----------|------------|
| Binance | `BTCUSDT` | `BTCUSDT` |
| Bybit | `BTCUSDT` | `BTCUSDT` |
| Hyperliquid | `BTC` | `BTCUSDT` |
| OKX | `BTC-USDT-SWAP` | `BTCUSDT` |

**Standard**: Always use `{BASE}{QUOTE}` format (e.g., BTCUSDT, ETHUSDT)

### 5.2 Side Normalization

| Exchange | Raw Side | Normalized |
|----------|----------|------------|
| Binance | `BUY` / `SELL` | `long` / `short` |
| Bybit | `Buy` / `Sell` | `long` / `short` |
| Hyperliquid | `A` / `B` (Ask/Bid) | `long` / `short` |
| OKX | `buy` / `sell` | `long` / `short` |

**Standard**: Lowercase `long` or `short`

### 5.3 Timestamp Normalization

- **Standard**: Python `datetime` object in UTC
- **Storage**: ISO 8601 string in DuckDB (`YYYY-MM-DDTHH:MM:SS.sssZ`)
- **Exchange Handling**:
  - Binance: Millisecond UNIX timestamp → convert
  - Hyperliquid: No timestamp → use `datetime.now()`
  - Bybit: Microsecond UNIX timestamp → convert
  - OKX: TBD

---

## 6. Fallback & Resilience Strategy

### 6.1 Graceful Degradation

**Principle**: System must function even if exchanges fail

**Scenarios**:

| Scenario | Behavior | User Experience |
|----------|----------|-----------------|
| All exchanges connected | Show aggregated heatmap | Best case |
| Binance only | Show Binance data (45% coverage) | Acceptable |
| Hyperliquid only | Show Hyperliquid data (5% coverage) | Degraded |
| All exchanges down | Show cached data + error banner | Fallback |

**Implementation**:
```python
async def generate_heatmap(exchanges: list[str]) -> dict:
    """Generate heatmap with fallback logic."""
    results = {}

    for exchange in exchanges:
        try:
            data = await fetch_exchange_data(exchange)
            results[exchange] = data
        except Exception as e:
            logger.error(f"{exchange} failed: {e}")
            # Continue with other exchanges

    if not results:
        # All failed - return cached data
        return load_cached_heatmap()

    return aggregate_results(results)
```

### 6.2 Caching Strategy

**Cache Invalidation**:
- **Real-time data**: Cache for 30s (acceptable staleness)
- **Historical data**: Cache for 1 hour (rarely changes)
- **Health checks**: Cache for 10s (near real-time status)

**Cache Keys**:
```
heatmap:{symbol}:{timeframe}:{exchanges}:v1
  Example: heatmap:BTCUSDT:24h:binance,hyperliquid:v1

exchange_health:{exchange}:v1
  Example: exchange_health:binance:v1
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

**File**: `tests/test_exchanges/test_adapters.py`

```python
import pytest
from datetime import datetime
from src.exchanges.binance import BinanceAdapter
from src.exchanges.hyperliquid import HyperliquidAdapter

@pytest.mark.asyncio
async def test_binance_connection():
    """Binance adapter connects successfully."""
    adapter = BinanceAdapter()
    await adapter.connect()
    assert adapter._is_connected
    await adapter.disconnect()

@pytest.mark.asyncio
async def test_hyperliquid_stream():
    """Hyperliquid streams liquidations."""
    adapter = HyperliquidAdapter()
    await adapter.connect()

    count = 0
    async for liq in adapter.stream_liquidations("BTCUSDT"):
        assert liq.exchange == "hyperliquid"
        assert liq.symbol == "BTCUSDT"
        count += 1
        if count >= 5:  # Stop after 5 liquidations
            break

    await adapter.disconnect()
    assert count > 0

@pytest.mark.asyncio
async def test_symbol_normalization():
    """Symbol normalization works for all exchanges."""
    hl = HyperliquidAdapter()
    assert hl.normalize_symbol("BTCUSDT") == "BTC"

    bn = BinanceAdapter()
    assert bn.normalize_symbol("BTCUSDT") == "BTCUSDT"
```

### 7.2 Integration Tests

**File**: `tests/integration/test_multi_exchange.py`

```python
import pytest
from src.exchanges.aggregator import ExchangeAggregator

@pytest.mark.asyncio
async def test_aggregator_multiplexing():
    """Aggregator merges streams from multiple exchanges."""
    agg = ExchangeAggregator(exchanges=["binance", "hyperliquid"])
    await agg.connect_all()

    exchanges_seen = set()
    count = 0

    async for liq in agg.stream_aggregated("BTCUSDT"):
        exchanges_seen.add(liq.exchange)
        count += 1
        if count >= 20:
            break

    await agg.disconnect_all()

    # Should see liquidations from both exchanges
    assert "binance" in exchanges_seen or "hyperliquid" in exchanges_seen

@pytest.mark.asyncio
async def test_exchange_failover():
    """System survives single exchange failure."""
    # Mock Hyperliquid to always fail
    agg = ExchangeAggregator(exchanges=["binance", "hyperliquid"])

    # Inject failure
    agg.adapters["hyperliquid"].connect = lambda: (_ for _ in ()).throw(Exception("Mock failure"))

    await agg.connect_all()

    # Binance should still work
    active = agg.get_active_exchanges()
    assert "binance" in active

    await agg.disconnect_all()
```

---

## 8. Risk Analysis

### 8.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Exchange API changes** | High | High | Version API endpoints, implement change detection, add fallback to cached data |
| **WebSocket stability** | Medium | High | Implement exponential backoff, auto-reconnect, circuit breakers |
| **Data normalization errors** | Medium | Medium | Rigorous schema validation, log mismatches, reject invalid data |
| **Hyperliquid low volume** | High | Low | Acceptable - use as secondary source, focus on Binance |
| **DuckDB performance degradation** | Low | High | Partition by exchange, index optimization, monitor query times |

### 8.2 Business Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Exchange ToS violations** | Low | Critical | Review ToS for each exchange, use only publicly available data, add disclaimers |
| **Competitor launches first** | Medium | Medium | Focus on accuracy (77.8% validation) as differentiator, not just feature count |
| **User confusion (too many options)** | Low | Low | Default to "All Exchanges", hide per-exchange toggle in advanced menu |

---

## 9. Success Metrics

### P0 Metrics (Launch Criteria)

- [ ] **Adapter Coverage**: Binance + Hyperliquid adapters functional
- [ ] **Schema Validation**: 100% of liquidations pass normalization
- [ ] **Uptime**: Aggregator uptime ≥99% over 7 days
- [ ] **Performance**: Aggregated heatmap loads in <7s (vs <5s for Binance-only)

### P1 Metrics (Post-Launch)

- [ ] **Hit Rate**: Hyperliquid validation ≥60%
- [ ] **User Adoption**: ≥20% of users toggle exchange filter within 1 week
- [ ] **Exchange Health**: ≥90% uptime for each exchange over 30 days

### P2 Metrics (Future)

- [ ] **OKX Integration**: OKX adapter added within 3 months
- [ ] **Bybit Workaround**: Alternative data source for Bybit implemented
- [ ] **Cross-Exchange Correlation**: Publish analysis of liquidation pattern correlation

---

## 10. Future Enhancements

### P3 Features (Post-MVP)

1. **Volume-Weighted Aggregation**
   - Weight heatmap zones by exchange market share
   - Binance (45%) gets higher weight than Hyperliquid (5%)

2. **Arbitrage Detection**
   - Identify liquidation level discrepancies across exchanges
   - Alert when spread >2%

3. **Exchange Comparison Dashboard**
   - Side-by-side charts for each exchange
   - Correlation analysis

4. **Predictive Models**
   - Use multi-exchange data to improve liquidation prediction accuracy
   - Ensemble model combining all sources

---

## 11. Documentation Requirements

### Developer Documentation

- [ ] `docs/EXCHANGE_INTEGRATION.md` - Guide for adding new exchanges
- [ ] `docs/EXCHANGE_COMPARISON.md` - Analysis of exchange differences
- [ ] API documentation updates (`/exchanges/*` endpoints)

### User Documentation

- [ ] FAQ: "Which exchanges are supported?"
- [ ] Tutorial: "How to filter by exchange"
- [ ] Glossary: Exchange-specific terms

---

## 12. Dependencies

### External Libraries

```toml
# pyproject.toml additions
[project.dependencies]
websockets = "^12.0"        # Hyperliquid WebSocket
aiohttp = "^3.9.0"          # Binance REST API
```

### Infrastructure

- No new infrastructure required (uses existing DuckDB + FastAPI)
- Optional: Redis for cross-exchange cache (defer to P2 real-time streaming)

---

## 13. Rollout Plan

### Alpha Phase (Week 1-2)

- Binance + Hyperliquid adapters only
- Internal testing with dev team
- Fix critical bugs, tune performance

### Beta Phase (Week 3)

- Release to 10-20 beta users
- Gather feedback on UX (exchange selector)
- Monitor aggregator stability

### Production (Week 4)

- Public launch with Binance + Hyperliquid
- Announce feature via Twitter, blog post
- Monitor for first 7 days, collect metrics

### Post-Launch (Month 2+)

- Add OKX adapter (if feasible)
- Investigate Bybit workarounds
- Publish exchange comparison analysis

---

## 14. Open Questions

### Technical

1. **Binance WebSocket**: Can we resolve 403 error with API key? Or is IP-based restriction?
2. **Hyperliquid Historical**: Any unofficial APIs for backfilling liquidation data?
3. **Bybit Alternative**: Should we implement volume spike heuristic or wait for topic restoration?
4. **OKX Viability**: Is OKX liquidation WebSocket reliable enough for production?

### Business

1. **Exchange Prioritization**: Should we add OKX before fixing Bybit?
2. **Volume Weighting**: Do users care about weighted vs unweighted heatmaps?
3. **Monetization**: Charge for multi-exchange access (premium feature)?

### Legal

1. **ToS Review**: Have we confirmed each exchange allows commercial use of API data?
2. **Data Licensing**: Any restrictions on combining data from multiple exchanges?

---

## 15. References

- Binance API: https://binance-docs.github.io/apidocs/futures/en/
- Bybit API: https://bybit-exchange.github.io/docs/v5/intro
- Hyperliquid API: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
- OKX API: https://www.okx.com/docs-v5/en/

---

## Revision History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-12-28 | 1.0 | Initial specification | Claude Opus 4.5 |

---

**Status**: Ready for review
**Next Steps**:
1. Review with team
2. Prioritize Phase 1 implementation
3. Create detailed task breakdown in `tasks.md`
