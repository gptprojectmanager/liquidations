"""
TierConfiguration model for managing collections of margin tiers.

Ensures mathematical continuity across all tier boundaries and provides
efficient tier lookup functionality.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from src.config.precision import ensure_decimal, validate_continuity
from src.models.margin_tier import MarginTier


@dataclass
class TierConfiguration:
    """
    Complete tier configuration for a trading symbol.

    Manages a collection of MarginTier objects and ensures:
    - Tiers are sorted by min_notional
    - No gaps between tiers
    - Mathematical continuity at all boundaries
    - At least one tier exists

    Attributes:
        symbol: Trading symbol (e.g., "BTCUSDT")
        version: Configuration version string
        tiers: List of MarginTier objects (sorted by min_notional)
        last_updated: Timestamp of last update
        source: Configuration source ("binance", "manual", etc.)
        is_active: Whether this configuration is currently active
    """

    symbol: str
    version: str
    tiers: List[MarginTier]
    last_updated: Optional[datetime] = None
    source: str = "manual"
    is_active: bool = True

    def __post_init__(self):
        """Initialize and validate configuration."""
        if self.last_updated is None:
            self.last_updated = datetime.utcnow()

        # Validate and prepare configuration
        self._validate_configuration()

    def _validate_configuration(self):
        """
        Validate tier configuration completeness and continuity.

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.tiers:
            raise ValueError("Configuration must have at least one tier")

        # Sort tiers by min_notional
        self.tiers.sort(key=lambda t: t.min_notional)

        # Validate all tiers belong to same symbol
        for tier in self.tiers:
            if tier.symbol != self.symbol:
                raise ValueError(
                    f"Tier symbol {tier.symbol} doesn't match configuration symbol {self.symbol}"
                )

        # Check for gaps between tiers
        for i in range(len(self.tiers) - 1):
            if self.tiers[i].max_notional != self.tiers[i + 1].min_notional:
                raise ValueError(
                    f"Gap between tier {i} and {i + 1}: "
                    f"tier {i} ends at ${self.tiers[i].max_notional}, "
                    f"tier {i + 1} starts at ${self.tiers[i + 1].min_notional}"
                )

        # Validate continuity at all boundaries
        for i in range(len(self.tiers) - 1):
            if not self._check_continuity(self.tiers[i], self.tiers[i + 1]):
                boundary = self.tiers[i].max_notional
                margin1 = self._calculate_at_boundary(self.tiers[i], boundary)
                margin2 = self._calculate_at_boundary(self.tiers[i + 1], boundary)
                raise ValueError(
                    f"Discontinuity at tier {i}/{i + 1} boundary (${boundary}): "
                    f"margin jumps from ${margin1} to ${margin2}"
                )

    def _check_continuity(self, tier1: MarginTier, tier2: MarginTier) -> bool:
        """
        Check mathematical continuity at tier boundary.

        Args:
            tier1: Lower tier
            tier2: Upper tier

        Returns:
            True if continuous within threshold
        """
        boundary = tier1.max_notional
        margin1 = self._calculate_at_boundary(tier1, boundary)
        margin2 = self._calculate_at_boundary(tier2, boundary)

        return validate_continuity(margin1, margin2)

    def _calculate_at_boundary(self, tier: MarginTier, boundary: Decimal) -> Decimal:
        """
        Calculate margin at exact boundary value.

        Uses the formula directly to avoid range check issues.

        Args:
            tier: Tier to calculate for
            boundary: Boundary notional value

        Returns:
            Margin at boundary
        """
        return boundary * tier.margin_rate - tier.maintenance_amount

    def get_tier(self, notional: Decimal) -> MarginTier:
        """
        Get appropriate tier for notional value using if-chain lookup.

        Uses simple if-chain (not binary search) for optimal performance
        with small number of tiers (typically 5).

        Args:
            notional: Position notional value

        Returns:
            MarginTier applicable for this notional

        Raises:
            ValueError: If no tier found for notional
        """
        notional = ensure_decimal(notional)

        # If-chain lookup for 5 tiers (most common case)
        # This is faster than binary search for small N
        for tier in self.tiers:
            if tier.contains(notional):
                return tier

        # Handle edge case: value above max tier
        if notional > self.tiers[-1].max_notional:
            return self.tiers[-1]

        # Handle edge case: value below min tier
        if notional <= self.tiers[0].min_notional:
            raise ValueError(
                f"Notional ${notional} below minimum tier threshold (${self.tiers[0].min_notional})"
            )

        raise ValueError(f"No tier found for notional ${notional}")

    def calculate_margin(self, notional: Decimal) -> Decimal:
        """
        Calculate margin for given notional value.

        Convenience method that finds appropriate tier and calculates margin.

        Args:
            notional: Position notional value

        Returns:
            Required margin amount
        """
        tier = self.get_tier(notional)
        return tier.calculate_margin(notional)

    def get_tier_at_boundary(self, boundary: Decimal) -> tuple[MarginTier, MarginTier]:
        """
        Get both tiers at a boundary for validation.

        Args:
            boundary: Boundary notional value

        Returns:
            Tuple of (lower_tier, upper_tier)

        Raises:
            ValueError: If boundary doesn't match any tier boundary
        """
        boundary = ensure_decimal(boundary)

        for i in range(len(self.tiers) - 1):
            if self.tiers[i].max_notional == boundary:
                return (self.tiers[i], self.tiers[i + 1])

        raise ValueError(f"${boundary} is not a tier boundary")

    def validate_continuity_at_all_boundaries(self) -> dict:
        """
        Validate continuity at all tier boundaries.

        Returns:
            Dictionary with boundary values as keys and continuity status
        """
        results = {}

        for i in range(len(self.tiers) - 1):
            boundary = self.tiers[i].max_notional
            is_continuous = self._check_continuity(self.tiers[i], self.tiers[i + 1])
            margin1 = self._calculate_at_boundary(self.tiers[i], boundary)
            margin2 = self._calculate_at_boundary(self.tiers[i + 1], boundary)
            difference = abs(margin1 - margin2)

            results[str(boundary)] = {
                "continuous": is_continuous,
                "margin_left": str(margin1),
                "margin_right": str(margin2),
                "difference": str(difference),
            }

        return results

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"TierConfiguration(symbol={self.symbol}, "
            f"version={self.version}, "
            f"tiers={len(self.tiers)}, "
            f"active={self.is_active})"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "version": self.version,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "source": self.source,
            "is_active": self.is_active,
            "tiers": [tier.to_dict() for tier in self.tiers],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TierConfiguration":
        """Create instance from dictionary."""
        return cls(
            symbol=data["symbol"],
            version=data["version"],
            tiers=[MarginTier.from_dict(t) for t in data["tiers"]],
            last_updated=(
                datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else None
            ),
            source=data.get("source", "manual"),
            is_active=data.get("is_active", True),
        )
