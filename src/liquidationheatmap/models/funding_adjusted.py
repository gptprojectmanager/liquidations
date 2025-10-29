"""Funding Rate Adjusted liquidation model."""

from decimal import Decimal
from typing import List

from .base import LiquidationLevel
from .binance_standard import BinanceStandardModel


class FundingAdjustedModel(BinanceStandardModel):
    """Extend BinanceStandardModel with funding rate pressure adjustments.

    Positive funding (longs pay shorts) → increases long liquidation risk
    Negative funding (shorts pay longs) → increases short liquidation risk

    Adjustment factor: 10x multiplier on funding rate impact
    """

    FUNDING_ADJUSTMENT_FACTOR = Decimal("10")

    @property
    def model_name(self) -> str:
        """Model identifier."""
        return "funding_adjusted"

    def calculate_liquidations(
        self,
        current_price: Decimal,
        open_interest: Decimal,
        symbol: str = "BTCUSDT",
        leverage_tiers: List[int] = None,
        funding_rate: Decimal = Decimal("0"),
    ) -> List[LiquidationLevel]:
        """Calculate liquidations with funding rate adjustments.

        Args:
            current_price: Current market price
            open_interest: Total Open Interest in USDT
            symbol: Trading pair
            leverage_tiers: Leverage values
            funding_rate: Current funding rate (e.g., 0.0001 for 0.01%)

        Returns:
            Adjusted liquidation levels
        """
        # Get base liquidations from parent (BinanceStandardModel)
        base_liquidations = super().calculate_liquidations(
            current_price, open_interest, symbol, leverage_tiers
        )

        # Apply funding rate adjustment
        adjusted = []
        for liq in base_liquidations:
            adjustment = funding_rate * self.FUNDING_ADJUSTMENT_FACTOR

            if liq.side == "long":
                # Positive funding → longs more risky → higher liquidation price
                adjusted_price = liq.price_level * (Decimal("1") + adjustment)
            else:  # short
                # Negative funding → shorts more risky → lower liquidation price
                adjusted_price = liq.price_level * (Decimal("1") - adjustment)

            adjusted.append(
                LiquidationLevel(
                    timestamp=liq.timestamp,
                    symbol=liq.symbol,
                    price_level=adjusted_price,
                    liquidation_volume=liq.liquidation_volume,
                    leverage_tier=liq.leverage_tier,
                    side=liq.side,
                    confidence=self.confidence_score(),  # Lower confidence
                )
            )

        return adjusted

    def confidence_score(self) -> Decimal:
        """Lower confidence than standard model (experimental)."""
        return Decimal("0.75")
