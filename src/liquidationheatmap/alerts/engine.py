"""Alert evaluation engine.

This module provides the core logic for:
- Fetching current price from Binance
- Fetching liquidation zones from heatmap API
- Calculating distance between price and zones
- Evaluating thresholds to determine alert severity
"""

import logging
from decimal import Decimal
from typing import Any

import httpx

from .config import ThresholdConfig
from .models import AlertSeverity, LiquidationZone, ZoneProximity

logger = logging.getLogger(__name__)


class PriceFetchError(Exception):
    """Error fetching price from exchange API."""

    pass


class ZoneFetchError(Exception):
    """Error fetching zones from heatmap API."""

    pass


def calculate_zone_proximity(
    zone: LiquidationZone,
    current_price: Decimal,
) -> ZoneProximity:
    """Calculate the proximity of a zone to the current price.

    Args:
        zone: The liquidation zone
        current_price: Current market price

    Returns:
        ZoneProximity with distance and direction calculated
    """
    if current_price == Decimal("0"):
        raise ValueError("current_price cannot be zero")

    distance = abs(zone.price - current_price)
    distance_pct = (distance / current_price) * Decimal("100")

    # Round to 2 decimal places for consistency
    distance_pct = distance_pct.quantize(Decimal("0.01"))

    direction = "above" if zone.price > current_price else "below"

    return ZoneProximity(
        zone=zone,
        current_price=current_price,
        distance_pct=distance_pct,
        direction=direction,
    )


def evaluate_threshold(
    proximity: ZoneProximity,
    thresholds: dict[str, ThresholdConfig],
) -> AlertSeverity | None:
    """Evaluate if a zone proximity triggers an alert.

    Checks thresholds in order of severity (critical, warning, info)
    and returns the highest severity that matches both distance and
    density requirements.

    Args:
        proximity: Zone proximity to evaluate
        thresholds: Dict of severity level -> ThresholdConfig

    Returns:
        AlertSeverity if threshold is triggered, None otherwise
    """
    total_density = proximity.zone.total_density

    # Check thresholds in order of severity (highest first)
    severity_order = [
        ("critical", AlertSeverity.CRITICAL),
        ("warning", AlertSeverity.WARNING),
        ("info", AlertSeverity.INFO),
    ]

    for level_name, severity in severity_order:
        if level_name not in thresholds:
            continue

        threshold = thresholds[level_name]

        # Check both distance and density requirements
        if (
            proximity.distance_pct <= threshold.distance_pct
            and total_density >= threshold.min_density
        ):
            logger.debug(
                f"Threshold {level_name} triggered: "
                f"distance={proximity.distance_pct}% <= {threshold.distance_pct}%, "
                f"density={total_density} >= {threshold.min_density}"
            )
            return severity

    return None


class PriceFetcher:
    """Fetches current price from Binance API."""

    def __init__(self, endpoint: str, timeout: float = 10.0):
        """Initialize the price fetcher.

        Args:
            endpoint: Binance price API endpoint
            timeout: Request timeout in seconds
        """
        self.endpoint = endpoint
        self.timeout = timeout

    async def fetch_price(self, symbol: str) -> Decimal:
        """Fetch current price for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)

        Returns:
            Current price as Decimal

        Raises:
            PriceFetchError: If API call fails or response is invalid
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Build URL with symbol if not already included
                url = self.endpoint
                if "symbol=" not in url:
                    separator = "&" if "?" in url else "?"
                    url = f"{url}{separator}symbol={symbol}"

                logger.debug(f"Fetching price from {url}")
                response = await client.get(url)
                response.raise_for_status()

                data = response.json()

                if "price" not in data:
                    raise PriceFetchError(f"Invalid response: missing 'price' field. Got: {data}")

                price = Decimal(str(data["price"]))
                logger.info(f"Fetched price for {symbol}: {price}")
                return price

        except httpx.HTTPError as e:
            raise PriceFetchError(f"HTTP error fetching price: {e}") from e
        except Exception as e:
            if isinstance(e, PriceFetchError):
                raise
            raise PriceFetchError(f"Error fetching price: {e}") from e


class ZoneFetcher:
    """Fetches liquidation zones from heatmap API."""

    def __init__(self, endpoint: str, timeout: float = 30.0):
        """Initialize the zone fetcher.

        Args:
            endpoint: Heatmap timeseries API endpoint
            timeout: Request timeout in seconds
        """
        self.endpoint = endpoint
        self.timeout = timeout

    async def fetch_zones(self, symbol: str) -> list[LiquidationZone]:
        """Fetch liquidation zones for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)

        Returns:
            List of LiquidationZone objects

        Raises:
            ZoneFetchError: If API call fails or response is invalid
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Build URL with symbol
                url = self.endpoint
                if "?" in url:
                    url = f"{url}&symbol={symbol}"
                else:
                    url = f"{url}?symbol={symbol}"

                logger.debug(f"Fetching zones from {url}")
                response = await client.get(url)
                response.raise_for_status()

                data = response.json()
                return self._parse_zones(data)

        except httpx.HTTPError as e:
            raise ZoneFetchError(f"HTTP error fetching zones: {e}") from e
        except Exception as e:
            if isinstance(e, ZoneFetchError):
                raise
            raise ZoneFetchError(f"Error fetching zones: {e}") from e

    def _parse_zones(self, data: dict[str, Any]) -> list[LiquidationZone]:
        """Parse zones from API response.

        Args:
            data: API response data

        Returns:
            List of LiquidationZone objects
        """
        zones = []

        # Get the latest snapshot (last item in data array)
        snapshots = data.get("data", [])
        if not snapshots:
            logger.warning("No zone data in response")
            return zones

        latest = snapshots[-1]
        levels = latest.get("levels", [])

        for level in levels:
            zone = LiquidationZone(
                price=Decimal(str(level["price"])),
                long_density=Decimal(str(level.get("long_density", 0))),
                short_density=Decimal(str(level.get("short_density", 0))),
            )
            zones.append(zone)

        logger.info(f"Parsed {len(zones)} zones from API")
        return zones


class AlertEvaluationEngine:
    """Main engine for evaluating liquidation zone alerts.

    Coordinates price fetching, zone fetching, and threshold evaluation
    to generate alerts.
    """

    def __init__(
        self,
        price_fetcher: PriceFetcher,
        zone_fetcher: ZoneFetcher,
        thresholds: dict[str, ThresholdConfig],
        symbol: str = "BTCUSDT",
    ):
        """Initialize the alert evaluation engine.

        Args:
            price_fetcher: PriceFetcher instance
            zone_fetcher: ZoneFetcher instance
            thresholds: Alert thresholds by severity level
            symbol: Trading pair symbol
        """
        self.price_fetcher = price_fetcher
        self.zone_fetcher = zone_fetcher
        self.thresholds = thresholds
        self.symbol = symbol

    async def evaluate(self) -> list[tuple[ZoneProximity, AlertSeverity]]:
        """Evaluate all zones and return those triggering alerts.

        Returns:
            List of (ZoneProximity, AlertSeverity) tuples for zones
            that trigger alerts, sorted by severity (critical first)
        """
        # Fetch current price
        current_price = await self.price_fetcher.fetch_price(self.symbol)
        logger.info(f"Current price for {self.symbol}: {current_price}")

        # Fetch liquidation zones
        zones = await self.zone_fetcher.fetch_zones(self.symbol)
        logger.info(f"Fetched {len(zones)} zones")

        # Evaluate each zone
        alerts: list[tuple[ZoneProximity, AlertSeverity]] = []

        for zone in zones:
            proximity = calculate_zone_proximity(zone, current_price)
            severity = evaluate_threshold(proximity, self.thresholds)

            if severity is not None:
                alerts.append((proximity, severity))
                logger.info(
                    f"Alert triggered: {severity.value} at {zone.price} "
                    f"({proximity.distance_pct}% away)"
                )

        # Sort by severity (critical first) then by distance
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.WARNING: 1,
            AlertSeverity.INFO: 2,
        }
        alerts.sort(key=lambda x: (severity_order[x[1]], x[0].distance_pct))

        return alerts
