"""
MarginTier data model with mathematical continuity guarantees.

This module implements the core MarginTier dataclass with Decimal precision
to ensure accurate margin calculations and continuity at tier boundaries.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from src.config.precision import ONE, ZERO, ensure_decimal


@dataclass
class MarginTier:
    """
    Single margin tier with maintenance amount for continuity.

    The margin calculation uses the formula:
        margin = notional * margin_rate - maintenance_amount

    This ensures mathematical continuity at tier boundaries through
    proper calculation of maintenance amounts.

    Invariants:
    - min_notional < max_notional
    - 0 < margin_rate <= 1
    - maintenance_amount >= 0
    - Continuous at boundaries (validated externally in TierConfiguration)

    Attributes:
        id: Unique identifier for this tier
        symbol: Trading symbol (e.g., "BTCUSDT")
        tier_number: Tier level (1, 2, 3, etc.)
        min_notional: Minimum position size for this tier (inclusive)
        max_notional: Maximum position size for this tier (exclusive)
        margin_rate: Margin rate as decimal (e.g., 0.005 for 0.5%)
        maintenance_amount: Maintenance amount offset for continuity
    """

    symbol: str
    tier_number: int
    min_notional: Decimal
    max_notional: Decimal
    margin_rate: Decimal
    maintenance_amount: Decimal
    id: Optional[UUID] = None

    def __post_init__(self):
        """Validate and convert fields to proper types."""
        # Generate ID if not provided
        if self.id is None:
            self.id = uuid4()

        # Convert to Decimal with proper precision
        self.min_notional = ensure_decimal(self.min_notional)
        self.max_notional = ensure_decimal(self.max_notional)
        self.margin_rate = ensure_decimal(self.margin_rate)
        self.maintenance_amount = ensure_decimal(self.maintenance_amount)

        # Validate invariants
        self._validate()

    def _validate(self):
        """Validate tier invariants."""
        if self.min_notional >= self.max_notional:
            raise ValueError(
                f"Invalid tier range: min_notional ({self.min_notional}) "
                f"must be < max_notional ({self.max_notional})"
            )

        if self.margin_rate <= ZERO or self.margin_rate > ONE:
            raise ValueError(f"Invalid margin rate: {self.margin_rate} (must be > 0 and <= 1)")

        if self.maintenance_amount < ZERO:
            raise ValueError(
                f"Invalid maintenance amount: {self.maintenance_amount} (must be >= 0)"
            )

        if self.tier_number < 1:
            raise ValueError(f"Invalid tier number: {self.tier_number} (must be >= 1)")

    def calculate_margin(self, notional: Decimal) -> Decimal:
        """
        Calculate margin for position within this tier.

        Formula: margin = notional * margin_rate - maintenance_amount

        Args:
            notional: Position notional value in USD

        Returns:
            Required margin amount in USD

        Raises:
            ValueError: If notional is outside tier range
        """
        notional = ensure_decimal(notional)

        # Check if notional is within tier range
        # Note: max_notional is exclusive, min_notional is inclusive
        if notional <= self.min_notional or notional > self.max_notional:
            raise ValueError(
                f"Notional {notional} outside tier range ({self.min_notional}, {self.max_notional}]"
            )

        # Calculate margin with maintenance amount offset
        margin = notional * self.margin_rate - self.maintenance_amount

        # Ensure margin is never negative (defensive check)
        if margin < ZERO:
            raise ValueError(
                f"Calculated negative margin ${margin} for notional ${notional} "
                f"(rate={self.margin_rate}, MA={self.maintenance_amount})"
            )

        return margin

    def contains(self, notional: Decimal) -> bool:
        """
        Check if notional value falls within this tier.

        Args:
            notional: Position notional value

        Returns:
            True if notional is in tier range (min, max]
        """
        notional = ensure_decimal(notional)
        return self.min_notional < notional <= self.max_notional

    def effective_rate(self, notional: Decimal) -> Decimal:
        """
        Calculate effective margin rate at given notional.

        The effective rate accounts for the maintenance amount:
            effective_rate = (margin / notional)
                          = margin_rate - (maintenance_amount / notional)

        Args:
            notional: Position notional value

        Returns:
            Effective margin rate as decimal
        """
        notional = ensure_decimal(notional)
        margin = self.calculate_margin(notional)
        return margin / notional

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"MarginTier(tier={self.tier_number}, "
            f"symbol={self.symbol}, "
            f"range=${self.min_notional:,.2f}-${self.max_notional:,.2f}, "
            f"rate={self.margin_rate:.4f}, "
            f"MA=${self.maintenance_amount:,.2f})"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "symbol": self.symbol,
            "tier_number": self.tier_number,
            "min_notional": str(self.min_notional),
            "max_notional": str(self.max_notional),
            "margin_rate": str(self.margin_rate),
            "maintenance_amount": str(self.maintenance_amount),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MarginTier":
        """Create instance from dictionary."""
        return cls(
            id=UUID(data["id"]) if "id" in data else None,
            symbol=data["symbol"],
            tier_number=data["tier_number"],
            min_notional=Decimal(data["min_notional"]),
            max_notional=Decimal(data["max_notional"]),
            margin_rate=Decimal(data["margin_rate"]),
            maintenance_amount=Decimal(data["maintenance_amount"]),
        )
