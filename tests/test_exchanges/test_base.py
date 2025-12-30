"""Tests for base exchange adapter interfaces.

TDD: These tests define the expected behavior of base classes.
"""

from datetime import datetime, timezone

import pytest

from src.exchanges.base import (
    ExchangeAdapter,
    ExchangeHealth,
    NormalizedLiquidation,
)


class TestNormalizedLiquidation:
    """Tests for NormalizedLiquidation dataclass."""

    def test_create_valid_liquidation(self):
        """T010: NormalizedLiquidation accepts valid data."""
        liq = NormalizedLiquidation(
            exchange="binance",
            symbol="BTCUSDT",
            price=95000.0,
            quantity=0.5,
            value_usd=47500.0,
            side="long",
            timestamp=datetime.now(timezone.utc),
        )

        assert liq.exchange == "binance"
        assert liq.symbol == "BTCUSDT"
        assert liq.price == 95000.0
        assert liq.quantity == 0.5
        assert liq.value_usd == 47500.0
        assert liq.side == "long"
        assert liq.is_validated is False
        assert liq.confidence == 1.0

    def test_liquidation_with_optional_fields(self):
        """NormalizedLiquidation accepts optional metadata."""
        liq = NormalizedLiquidation(
            exchange="hyperliquid",
            symbol="BTCUSDT",
            price=95000.0,
            quantity=0.5,
            value_usd=47500.0,
            side="short",
            timestamp=datetime.now(timezone.utc),
            raw_data={"px": "95000", "sz": "0.5"},
            liquidation_type="forced",
            leverage=10.0,
            is_validated=True,
            confidence=0.9,
        )

        assert liq.raw_data == {"px": "95000", "sz": "0.5"}
        assert liq.liquidation_type == "forced"
        assert liq.leverage == 10.0
        assert liq.is_validated is True
        assert liq.confidence == 0.9

    def test_liquidation_validates_required_fields(self):
        """T012: NormalizedLiquidation validates required fields via Pydantic."""
        from pydantic import ValidationError

        # Missing required fields should raise ValidationError
        with pytest.raises(ValidationError):
            NormalizedLiquidation(
                exchange="binance",
                # Missing symbol, price, quantity, value_usd, side, timestamp
            )

    def test_liquidation_type_coercion(self):
        """NormalizedLiquidation coerces types via Pydantic."""
        # String numbers should be coerced to float
        liq = NormalizedLiquidation(
            exchange="binance",
            symbol="BTCUSDT",
            price="95000.0",  # String instead of float
            quantity="0.5",
            value_usd="47500.0",
            side="long",
            timestamp=datetime.now(timezone.utc),
        )

        assert isinstance(liq.price, float)
        assert liq.price == 95000.0


class TestExchangeHealth:
    """Tests for ExchangeHealth dataclass."""

    def test_create_valid_health(self):
        """ExchangeHealth accepts valid data."""
        health = ExchangeHealth(
            exchange="binance",
            is_connected=True,
            last_heartbeat=datetime.now(timezone.utc),
            message_count=100,
            error_count=0,
            uptime_percent=99.5,
        )

        assert health.exchange == "binance"
        assert health.is_connected is True
        assert health.message_count == 100
        assert health.error_count == 0
        assert health.uptime_percent == 99.5


class TestExchangeAdapter:
    """Tests for ExchangeAdapter abstract base class."""

    def test_cannot_instantiate_abstract_adapter(self):
        """T011: ExchangeAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            ExchangeAdapter()

        assert "abstract" in str(exc_info.value).lower()

    def test_adapter_requires_all_methods(self):
        """ExchangeAdapter requires all abstract methods to be implemented."""

        # Incomplete implementation should fail
        class IncompleteAdapter(ExchangeAdapter):
            @property
            def exchange_name(self) -> str:
                return "incomplete"

            async def connect(self) -> None:
                pass

            # Missing: disconnect, stream_liquidations, fetch_historical,
            #          health_check, normalize_symbol

        with pytest.raises(TypeError):
            IncompleteAdapter()

    def test_concrete_adapter_can_be_instantiated(self):
        """Fully implemented adapter can be instantiated."""
        from typing import AsyncIterator

        class ConcreteAdapter(ExchangeAdapter):
            @property
            def exchange_name(self) -> str:
                return "test"

            async def connect(self) -> None:
                pass

            async def disconnect(self) -> None:
                pass

            async def stream_liquidations(
                self, symbol: str = "BTCUSDT"
            ) -> AsyncIterator[NormalizedLiquidation]:
                yield  # Empty generator

            async def fetch_historical(
                self, symbol: str, start_time: datetime, end_time: datetime
            ) -> list[NormalizedLiquidation]:
                return []

            async def health_check(self) -> ExchangeHealth:
                return ExchangeHealth(
                    exchange="test",
                    is_connected=True,
                    last_heartbeat=datetime.now(timezone.utc),
                    message_count=0,
                    error_count=0,
                    uptime_percent=100.0,
                )

            def normalize_symbol(self, exchange_symbol: str) -> str:
                return exchange_symbol

        adapter = ConcreteAdapter()
        assert adapter.exchange_name == "test"
