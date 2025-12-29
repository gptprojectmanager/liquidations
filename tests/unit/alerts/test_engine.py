"""Unit tests for the alert evaluation engine.

Tests for:
- Distance calculation between current price and liquidation zones
- Threshold evaluation for triggering alerts
- Zone fetching from heatmap API
- Price fetching from Binance API
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from src.liquidationheatmap.alerts.models import (
    AlertSeverity,
    LiquidationZone,
    ZoneProximity,
)


class TestDistanceCalculation:
    """Tests for calculate_zone_proximity function."""

    def test_distance_calculation_above(self) -> None:
        """Zone above current price should have correct distance and direction."""
        from src.liquidationheatmap.alerts.engine import calculate_zone_proximity

        zone = LiquidationZone(
            price=Decimal("100000"),
            long_density=Decimal("5000000"),
            short_density=Decimal("10000000"),
        )
        current_price = Decimal("95000")

        proximity = calculate_zone_proximity(zone, current_price)

        # Distance: abs(100000 - 95000) / 95000 * 100 = 5.26%
        assert proximity.distance_pct == pytest.approx(Decimal("5.26"), rel=0.01)
        assert proximity.direction == "above"
        assert proximity.zone == zone
        assert proximity.current_price == current_price

    def test_distance_calculation_below(self) -> None:
        """Zone below current price should have correct distance and direction."""
        from src.liquidationheatmap.alerts.engine import calculate_zone_proximity

        zone = LiquidationZone(
            price=Decimal("90000"),
            long_density=Decimal("15000000"),
            short_density=Decimal("5000000"),
        )
        current_price = Decimal("95000")

        proximity = calculate_zone_proximity(zone, current_price)

        # Distance: abs(90000 - 95000) / 95000 * 100 = 5.26%
        assert proximity.distance_pct == pytest.approx(Decimal("5.26"), rel=0.01)
        assert proximity.direction == "below"

    def test_distance_calculation_at_zone(self) -> None:
        """When price is at zone, distance should be 0."""
        from src.liquidationheatmap.alerts.engine import calculate_zone_proximity

        zone = LiquidationZone(
            price=Decimal("95000"),
            long_density=Decimal("5000000"),
            short_density=Decimal("10000000"),
        )
        current_price = Decimal("95000")

        proximity = calculate_zone_proximity(zone, current_price)

        assert proximity.distance_pct == Decimal("0")

    def test_distance_calculation_precision(self) -> None:
        """Distance should be calculated with proper precision."""
        from src.liquidationheatmap.alerts.engine import calculate_zone_proximity

        zone = LiquidationZone(
            price=Decimal("94050"),
            long_density=Decimal("5000000"),
            short_density=Decimal("10000000"),
        )
        current_price = Decimal("94000")

        proximity = calculate_zone_proximity(zone, current_price)

        # Distance: abs(94050 - 94000) / 94000 * 100 = 0.0532%
        # Rounded to 2 decimal places = 0.05
        assert proximity.distance_pct == Decimal("0.05")


class TestThresholdEvaluation:
    """Tests for threshold evaluation logic."""

    def test_critical_threshold_triggered(self) -> None:
        """Alert should be CRITICAL when distance < 1%."""
        from src.liquidationheatmap.alerts.config import ThresholdConfig
        from src.liquidationheatmap.alerts.engine import evaluate_threshold

        thresholds = {
            "critical": ThresholdConfig(
                distance_pct=Decimal("1.0"),
                min_density=Decimal("10000000"),
            ),
            "warning": ThresholdConfig(
                distance_pct=Decimal("3.0"),
                min_density=Decimal("5000000"),
            ),
            "info": ThresholdConfig(
                distance_pct=Decimal("5.0"),
                min_density=Decimal("1000000"),
            ),
        }

        zone = LiquidationZone(
            price=Decimal("94500"),
            long_density=Decimal("5000000"),
            short_density=Decimal("15000000"),  # Total > 10M
        )
        proximity = ZoneProximity(
            zone=zone,
            current_price=Decimal("94000"),
            distance_pct=Decimal("0.53"),  # < 1%
            direction="above",
        )

        severity = evaluate_threshold(proximity, thresholds)

        assert severity == AlertSeverity.CRITICAL

    def test_warning_threshold_triggered(self) -> None:
        """Alert should be WARNING when 1% < distance < 3%."""
        from src.liquidationheatmap.alerts.config import ThresholdConfig
        from src.liquidationheatmap.alerts.engine import evaluate_threshold

        thresholds = {
            "critical": ThresholdConfig(
                distance_pct=Decimal("1.0"),
                min_density=Decimal("10000000"),
            ),
            "warning": ThresholdConfig(
                distance_pct=Decimal("3.0"),
                min_density=Decimal("5000000"),
            ),
            "info": ThresholdConfig(
                distance_pct=Decimal("5.0"),
                min_density=Decimal("1000000"),
            ),
        }

        zone = LiquidationZone(
            price=Decimal("96000"),
            long_density=Decimal("3000000"),
            short_density=Decimal("4000000"),  # Total = 7M > 5M
        )
        proximity = ZoneProximity(
            zone=zone,
            current_price=Decimal("94000"),
            distance_pct=Decimal("2.1"),  # Between 1% and 3%
            direction="above",
        )

        severity = evaluate_threshold(proximity, thresholds)

        assert severity == AlertSeverity.WARNING

    def test_info_threshold_triggered(self) -> None:
        """Alert should be INFO when 3% < distance < 5%."""
        from src.liquidationheatmap.alerts.config import ThresholdConfig
        from src.liquidationheatmap.alerts.engine import evaluate_threshold

        thresholds = {
            "critical": ThresholdConfig(
                distance_pct=Decimal("1.0"),
                min_density=Decimal("10000000"),
            ),
            "warning": ThresholdConfig(
                distance_pct=Decimal("3.0"),
                min_density=Decimal("5000000"),
            ),
            "info": ThresholdConfig(
                distance_pct=Decimal("5.0"),
                min_density=Decimal("1000000"),
            ),
        }

        zone = LiquidationZone(
            price=Decimal("98000"),
            long_density=Decimal("500000"),
            short_density=Decimal("1500000"),  # Total = 2M > 1M
        )
        proximity = ZoneProximity(
            zone=zone,
            current_price=Decimal("94000"),
            distance_pct=Decimal("4.2"),  # Between 3% and 5%
            direction="above",
        )

        severity = evaluate_threshold(proximity, thresholds)

        assert severity == AlertSeverity.INFO

    def test_no_threshold_triggered(self) -> None:
        """No alert when distance > highest threshold."""
        from src.liquidationheatmap.alerts.config import ThresholdConfig
        from src.liquidationheatmap.alerts.engine import evaluate_threshold

        thresholds = {
            "critical": ThresholdConfig(
                distance_pct=Decimal("1.0"),
                min_density=Decimal("10000000"),
            ),
            "warning": ThresholdConfig(
                distance_pct=Decimal("3.0"),
                min_density=Decimal("5000000"),
            ),
            "info": ThresholdConfig(
                distance_pct=Decimal("5.0"),
                min_density=Decimal("1000000"),
            ),
        }

        zone = LiquidationZone(
            price=Decimal("100000"),
            long_density=Decimal("500000"),
            short_density=Decimal("1500000"),
        )
        proximity = ZoneProximity(
            zone=zone,
            current_price=Decimal("94000"),
            distance_pct=Decimal("6.4"),  # > 5%
            direction="above",
        )

        severity = evaluate_threshold(proximity, thresholds)

        assert severity is None

    def test_density_filter_applied(self) -> None:
        """Alert should not trigger if density is below threshold."""
        from src.liquidationheatmap.alerts.config import ThresholdConfig
        from src.liquidationheatmap.alerts.engine import evaluate_threshold

        thresholds = {
            "critical": ThresholdConfig(
                distance_pct=Decimal("1.0"),
                min_density=Decimal("10000000"),  # Requires 10M
            ),
            "warning": ThresholdConfig(
                distance_pct=Decimal("3.0"),
                min_density=Decimal("5000000"),
            ),
            "info": ThresholdConfig(
                distance_pct=Decimal("5.0"),
                min_density=Decimal("1000000"),
            ),
        }

        zone = LiquidationZone(
            price=Decimal("94500"),
            long_density=Decimal("2000000"),
            short_density=Decimal("3000000"),  # Total = 5M < 10M for critical
        )
        proximity = ZoneProximity(
            zone=zone,
            current_price=Decimal("94000"),
            distance_pct=Decimal("0.53"),  # Would be critical by distance
            direction="above",
        )

        severity = evaluate_threshold(proximity, thresholds)

        # Falls through to WARNING because density > 5M
        assert severity == AlertSeverity.WARNING


class TestZoneFetcher:
    """Tests for ZoneFetcher class."""

    @pytest.mark.asyncio
    async def test_zone_fetcher_parses_response(self) -> None:
        """Zone fetcher should parse API response correctly."""
        from unittest.mock import MagicMock

        from src.liquidationheatmap.alerts.engine import ZoneFetcher

        mock_response_data = {
            "data": [
                {
                    "timestamp": "2025-12-28T14:00:00",
                    "levels": [
                        {
                            "price": 94000.0,
                            "long_density": 5000000.0,
                            "short_density": 10000000.0,
                        },
                        {
                            "price": 96000.0,
                            "long_density": 8000000.0,
                            "short_density": 2000000.0,
                        },
                    ],
                }
            ],
            "meta": {"symbol": "BTCUSDT"},
        }

        # Use MagicMock for sync methods (json() is sync in httpx)
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        # Mock the async context manager
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("src.liquidationheatmap.alerts.engine.httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            fetcher = ZoneFetcher("http://localhost:8000/liquidations/heatmap-timeseries")
            zones = await fetcher.fetch_zones("BTCUSDT")

        assert len(zones) == 2
        assert zones[0].price == Decimal("94000")
        assert zones[0].long_density == Decimal("5000000")
        assert zones[0].short_density == Decimal("10000000")
        assert zones[1].price == Decimal("96000")

    @pytest.mark.asyncio
    async def test_zone_fetcher_handles_empty_response(self) -> None:
        """Zone fetcher should handle empty response gracefully."""
        from unittest.mock import MagicMock

        from src.liquidationheatmap.alerts.engine import ZoneFetcher

        mock_response_data = {"data": [], "meta": {"symbol": "BTCUSDT"}}

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("src.liquidationheatmap.alerts.engine.httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            fetcher = ZoneFetcher("http://localhost:8000/api")
            zones = await fetcher.fetch_zones("BTCUSDT")

        assert len(zones) == 0

    @pytest.mark.asyncio
    async def test_zone_fetcher_handles_api_error(self) -> None:
        """Zone fetcher should raise error on API failure."""
        from src.liquidationheatmap.alerts.engine import ZoneFetcher, ZoneFetchError

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection failed")

        with patch("src.liquidationheatmap.alerts.engine.httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            fetcher = ZoneFetcher("http://localhost:8000/api")
            with pytest.raises(ZoneFetchError):
                await fetcher.fetch_zones("BTCUSDT")


class TestPriceFetcher:
    """Tests for PriceFetcher class."""

    @pytest.mark.asyncio
    async def test_price_fetcher_parses_binance_response(self) -> None:
        """Price fetcher should parse Binance API response correctly."""
        from unittest.mock import MagicMock

        from src.liquidationheatmap.alerts.engine import PriceFetcher

        mock_response_data = {"symbol": "BTCUSDT", "price": "94523.45"}

        # Use MagicMock for sync methods, response.json() is sync in httpx
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("src.liquidationheatmap.alerts.engine.httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            fetcher = PriceFetcher("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
            price = await fetcher.fetch_price("BTCUSDT")

        assert price == Decimal("94523.45")

    @pytest.mark.asyncio
    async def test_price_fetcher_handles_api_error(self) -> None:
        """Price fetcher should raise error on API failure."""
        from src.liquidationheatmap.alerts.engine import PriceFetcher, PriceFetchError

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection failed")

        with patch("src.liquidationheatmap.alerts.engine.httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            fetcher = PriceFetcher("https://api.binance.com/api/v3/ticker/price")
            with pytest.raises(PriceFetchError):
                await fetcher.fetch_price("BTCUSDT")

    @pytest.mark.asyncio
    async def test_price_fetcher_validates_response(self) -> None:
        """Price fetcher should validate response format."""
        from unittest.mock import MagicMock

        from src.liquidationheatmap.alerts.engine import PriceFetcher, PriceFetchError

        mock_response_data = {"symbol": "BTCUSDT"}  # Missing 'price' field

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("src.liquidationheatmap.alerts.engine.httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            fetcher = PriceFetcher("https://api.binance.com/api/v3/ticker/price")
            with pytest.raises(PriceFetchError, match="price"):
                await fetcher.fetch_price("BTCUSDT")
