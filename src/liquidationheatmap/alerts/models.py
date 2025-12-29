"""Data models for the liquidation alert system.

This module defines the core data structures used throughout
the alert system, including zones, alerts, and cooldown state.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any


class AlertSeverity(Enum):
    """Alert severity levels."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class DeliveryStatus(Enum):
    """Alert delivery status."""

    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"  # Some channels failed
    FAILED = "failed"


@dataclass
class LiquidationZone:
    """A liquidation zone from heatmap data.

    Represents a price level where liquidations are concentrated.

    Attributes:
        price: Zone price level
        long_density: Long liquidation volume at this level in USD
        short_density: Short liquidation volume at this level in USD
    """

    price: Decimal
    long_density: Decimal
    short_density: Decimal

    @property
    def total_density(self) -> Decimal:
        """Total liquidation volume at this zone."""
        return self.long_density + self.short_density

    @property
    def dominant_side(self) -> str:
        """Returns 'long' or 'short' based on higher density."""
        return "long" if self.long_density > self.short_density else "short"


@dataclass
class ZoneProximity:
    """Zone with calculated distance from current price.

    Represents a liquidation zone with additional context about
    how close the current price is to the zone.

    Attributes:
        zone: The liquidation zone
        current_price: Current market price
        distance_pct: Absolute percentage distance from current price
        direction: Whether zone is "above" or "below" current price
    """

    zone: LiquidationZone
    current_price: Decimal
    distance_pct: Decimal
    direction: str  # "above" or "below"

    @property
    def zone_key(self) -> str:
        """Unique key for cooldown tracking.

        Uses price bucket (rounded to nearest 100) and dominant side
        to create a stable key for rate limiting.
        """
        bucket = int(self.zone.price / 100) * 100
        return f"{bucket}_{self.zone.dominant_side}"


@dataclass
class Alert:
    """An alert event with delivery tracking.

    Represents a liquidation zone alert that needs to be dispatched
    to notification channels.

    Attributes:
        id: Database primary key (assigned on insert)
        timestamp: When the alert was created
        symbol: Trading pair (e.g., BTCUSDT)
        current_price: Market price at alert time
        zone_price: Price of the liquidation zone
        zone_density: Total liquidation volume at the zone
        zone_side: Dominant side of the zone (long/short)
        distance_pct: Percentage distance from current price
        severity: Alert severity level
        channels_sent: List of channels the alert was sent to
        delivery_status: Current delivery status
        error_message: Error message if delivery failed
    """

    id: int | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    symbol: str = "BTCUSDT"
    current_price: Decimal = field(default_factory=lambda: Decimal("0"))
    zone_price: Decimal = field(default_factory=lambda: Decimal("0"))
    zone_density: Decimal = field(default_factory=lambda: Decimal("0"))
    zone_side: str = "long"
    distance_pct: Decimal = field(default_factory=lambda: Decimal("0"))
    severity: AlertSeverity = AlertSeverity.INFO
    message: str | None = None  # Optional custom message
    channels_sent: list[str] = field(default_factory=list)
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "current_price": str(self.current_price),
            "zone_price": str(self.zone_price),
            "zone_density": str(self.zone_density),
            "zone_side": self.zone_side,
            "distance_pct": str(self.distance_pct),
            "severity": self.severity.value,
            "message": self.message,
            "channels_sent": self.channels_sent,
            "delivery_status": self.delivery_status.value,
            "error_message": self.error_message,
        }

    @classmethod
    def from_zone_proximity(
        cls,
        proximity: ZoneProximity,
        severity: AlertSeverity,
        symbol: str = "BTCUSDT",
    ) -> "Alert":
        """Create an Alert from a ZoneProximity instance.

        Args:
            proximity: Zone proximity data
            severity: Alert severity level
            symbol: Trading pair symbol

        Returns:
            New Alert instance
        """
        return cls(
            symbol=symbol,
            current_price=proximity.current_price,
            zone_price=proximity.zone.price,
            zone_density=proximity.zone.total_density,
            zone_side=proximity.zone.dominant_side,
            distance_pct=proximity.distance_pct,
            severity=severity,
        )


@dataclass
class AlertCooldown:
    """Cooldown state for a specific zone.

    Tracks when the last alert was sent for a zone to enforce
    rate limiting.

    Attributes:
        zone_key: Unique identifier for the zone ({bucket}_{side})
        last_alert_time: Timestamp of last alert sent
        alert_count_today: Number of alerts sent today (UTC)
        last_reset_date: Date when daily counter was last reset
    """

    zone_key: str
    last_alert_time: datetime
    alert_count_today: int = 0
    last_reset_date: date = field(default_factory=lambda: datetime.now(timezone.utc).date())

    def is_on_cooldown(self, cooldown_minutes: int) -> bool:
        """Check if zone is still on cooldown.

        Args:
            cooldown_minutes: Cooldown period in minutes

        Returns:
            True if zone is on cooldown, False otherwise
        """
        now = datetime.now(timezone.utc)
        # Ensure last_alert_time is timezone-aware
        last_alert = self.last_alert_time
        if last_alert.tzinfo is None:
            last_alert = last_alert.replace(tzinfo=timezone.utc)
        return now - last_alert < timedelta(minutes=cooldown_minutes)

    def should_reset_daily_count(self) -> bool:
        """Check if daily counter should reset (new UTC day).

        Returns:
            True if a new UTC day has started since last reset
        """
        today = datetime.now(timezone.utc).date()
        return today > self.last_reset_date

    def reset_daily_count(self) -> None:
        """Reset the daily counter for a new UTC day."""
        self.alert_count_today = 0
        self.last_reset_date = datetime.now(timezone.utc).date()

    def record_alert(self) -> None:
        """Record that an alert was sent.

        Updates the last alert time and increments the daily counter.
        """
        self.last_alert_time = datetime.now(timezone.utc)
        self.alert_count_today += 1
