"""
Position margin model for audit trail and calculations.

Tracks margin calculations for positions with full audit trail for compliance
and debugging.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from src.config.precision import ensure_decimal


@dataclass
class PositionMargin:
    """
    Record of margin calculation for a specific position.

    Provides audit trail for:
    - Which tier configuration was used
    - Exact calculation parameters
    - Timestamp for compliance
    - Calculation results

    Attributes:
        id: Unique identifier for this calculation
        symbol: Trading pair symbol (e.g., "BTCUSDT")
        notional: Position notional value in USD
        margin_required: Calculated maintenance margin
        tier_number: Tier that was applied
        margin_rate: Margin rate used from tier
        maintenance_amount: MA offset used from tier
        configuration_version: Version of tier configuration used
        leverage: Leverage multiplier (if applicable)
        entry_price: Position entry price (if applicable)
        position_size: Position size in base currency (if applicable)
        liquidation_price: Calculated liquidation price (if applicable)
        side: Position side "long" or "short" (if applicable)
        calculated_at: Timestamp of calculation
    """

    symbol: str
    notional: Decimal
    margin_required: Decimal
    tier_number: int
    margin_rate: Decimal
    maintenance_amount: Decimal
    configuration_version: str
    calculated_at: datetime
    id: UUID = None
    leverage: Optional[Decimal] = None
    entry_price: Optional[Decimal] = None
    position_size: Optional[Decimal] = None
    liquidation_price: Optional[Decimal] = None
    side: Optional[str] = None

    def __post_init__(self):
        """Initialize with UUID and ensure Decimal types."""
        if self.id is None:
            self.id = uuid4()

        # Ensure all numeric fields are Decimal
        self.notional = ensure_decimal(self.notional)
        self.margin_required = ensure_decimal(self.margin_required)
        self.margin_rate = ensure_decimal(self.margin_rate)
        self.maintenance_amount = ensure_decimal(self.maintenance_amount)

        if self.leverage is not None:
            self.leverage = ensure_decimal(self.leverage)
        if self.entry_price is not None:
            self.entry_price = ensure_decimal(self.entry_price)
        if self.position_size is not None:
            self.position_size = ensure_decimal(self.position_size)
        if self.liquidation_price is not None:
            self.liquidation_price = ensure_decimal(self.liquidation_price)

    @classmethod
    def from_calculation(
        cls,
        symbol: str,
        notional: Decimal,
        margin_required: Decimal,
        tier_number: int,
        margin_rate: Decimal,
        maintenance_amount: Decimal,
        configuration_version: str,
        leverage: Optional[Decimal] = None,
        entry_price: Optional[Decimal] = None,
        position_size: Optional[Decimal] = None,
        liquidation_price: Optional[Decimal] = None,
        side: Optional[str] = None,
    ) -> "PositionMargin":
        """
        Create PositionMargin record from calculation results.

        Args:
            symbol: Trading pair symbol
            notional: Position notional value
            margin_required: Calculated maintenance margin
            tier_number: Tier that was applied
            margin_rate: Margin rate from tier
            maintenance_amount: MA offset from tier
            configuration_version: Config version used
            leverage: Leverage multiplier (optional)
            entry_price: Entry price (optional)
            position_size: Position size (optional)
            liquidation_price: Liquidation price (optional)
            side: Position side (optional)

        Returns:
            PositionMargin record with current timestamp

        Example:
            >>> record = PositionMargin.from_calculation(
            ...     symbol="BTCUSDT",
            ...     notional=Decimal("100000"),
            ...     margin_required=Decimal("750"),
            ...     tier_number=2,
            ...     margin_rate=Decimal("0.010"),
            ...     maintenance_amount=Decimal("250"),
            ...     configuration_version="binance-2025-v1",
            ...     leverage=Decimal("10"),
            ...     entry_price=Decimal("50000"),
            ...     position_size=Decimal("2"),
            ...     liquidation_price=Decimal("45500"),
            ...     side="long"
            ... )
        """
        return cls(
            symbol=symbol,
            notional=notional,
            margin_required=margin_required,
            tier_number=tier_number,
            margin_rate=margin_rate,
            maintenance_amount=maintenance_amount,
            configuration_version=configuration_version,
            calculated_at=datetime.utcnow(),
            leverage=leverage,
            entry_price=entry_price,
            position_size=position_size,
            liquidation_price=liquidation_price,
            side=side,
        )

    def to_dict(self) -> dict:
        """
        Convert to dictionary for serialization.

        Returns:
            Dictionary with all fields, Decimals as strings

        Example:
            >>> record.to_dict()
            {
                'id': '...',
                'symbol': 'BTCUSDT',
                'notional': '100000',
                'margin_required': '750',
                ...
            }
        """
        return {
            "id": str(self.id),
            "symbol": self.symbol,
            "notional": str(self.notional),
            "margin_required": str(self.margin_required),
            "tier_number": self.tier_number,
            "margin_rate": str(self.margin_rate),
            "maintenance_amount": str(self.maintenance_amount),
            "configuration_version": self.configuration_version,
            "calculated_at": self.calculated_at.isoformat(),
            "leverage": str(self.leverage) if self.leverage is not None else None,
            "entry_price": str(self.entry_price) if self.entry_price is not None else None,
            "position_size": str(self.position_size) if self.position_size is not None else None,
            "liquidation_price": (
                str(self.liquidation_price) if self.liquidation_price is not None else None
            ),
            "side": self.side,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PositionMargin":
        """
        Create PositionMargin from dictionary.

        Args:
            data: Dictionary with position margin data

        Returns:
            PositionMargin instance

        Example:
            >>> data = {
            ...     'symbol': 'BTCUSDT',
            ...     'notional': '100000',
            ...     'margin_required': '750',
            ...     ...
            ... }
            >>> record = PositionMargin.from_dict(data)
        """
        return cls(
            id=UUID(data["id"]) if "id" in data else None,
            symbol=data["symbol"],
            notional=Decimal(data["notional"]),
            margin_required=Decimal(data["margin_required"]),
            tier_number=data["tier_number"],
            margin_rate=Decimal(data["margin_rate"]),
            maintenance_amount=Decimal(data["maintenance_amount"]),
            configuration_version=data["configuration_version"],
            calculated_at=datetime.fromisoformat(data["calculated_at"]),
            leverage=Decimal(data["leverage"]) if data.get("leverage") else None,
            entry_price=Decimal(data["entry_price"]) if data.get("entry_price") else None,
            position_size=Decimal(data["position_size"]) if data.get("position_size") else None,
            liquidation_price=(
                Decimal(data["liquidation_price"]) if data.get("liquidation_price") else None
            ),
            side=data.get("side"),
        )

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"PositionMargin("
            f"symbol={self.symbol}, "
            f"notional=${self.notional}, "
            f"margin=${self.margin_required}, "
            f"tier={self.tier_number}, "
            f"version={self.configuration_version}"
            f")"
        )
