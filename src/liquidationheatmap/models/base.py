"""Abstract base class for liquidation calculation models."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List


@dataclass
class LiquidationLevel:
    """Single liquidation level calculated by a model."""

    timestamp: datetime
    symbol: str
    price_level: Decimal
    liquidation_volume: Decimal
    leverage_tier: str
    side: str
    confidence: Decimal


class AbstractLiquidationModel(ABC):
    """Abstract base class for liquidation calculation models."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model name identifier."""
        pass

    @abstractmethod
    def calculate_liquidations(
        self,
        current_price: Decimal,
        open_interest: Decimal,
        symbol: str = "BTCUSDT",
        leverage_tiers: List[int] = None,
    ) -> List[LiquidationLevel]:
        """Calculate liquidation levels."""
        pass

    @abstractmethod
    def confidence_score(self) -> Decimal:
        """Return model confidence score (0.0-1.0)."""
        pass
