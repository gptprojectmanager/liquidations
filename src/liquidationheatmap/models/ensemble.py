"""Ensemble liquidation model - weighted average of multiple models."""

from decimal import Decimal
from typing import Dict, List

from .base import AbstractLiquidationModel, LiquidationLevel
from .binance_standard import BinanceStandardModel
from .funding_adjusted import FundingAdjustedModel


class EnsembleModel(AbstractLiquidationModel):
    """Combine multiple liquidation models with weighted average.

    Default weights:
    - BinanceStandardModel: 50% (most reliable)
    - FundingAdjustedModel: 30% (experimental)
    - py_liquidation_map: 20% (external library, optional)

    Aggregates predictions by $100 price buckets.
    Confidence decreases when models disagree by >5%.
    """

    DEFAULT_WEIGHTS = {
        "binance_standard": Decimal("0.50"),
        "funding_adjusted": Decimal("0.30"),
        "py_liquidation_map": Decimal("0.20"),
    }

    PRICE_BUCKET_SIZE = Decimal("100")  # $100 increments
    DISAGREEMENT_THRESHOLD = Decimal("0.05")  # 5%

    def __init__(self):
        """Initialize ensemble with available models."""
        self.models = {
            "binance_standard": BinanceStandardModel(),
            "funding_adjusted": FundingAdjustedModel(),
            # py_liquidation_map: not implemented yet, fallback to adjusted weights
        }

        # Adjust weights if models are missing
        self.weights = self._adjust_weights()

    @property
    def model_name(self) -> str:
        """Model identifier."""
        return "ensemble"

    def get_weights(self) -> Dict[str, Decimal]:
        """Return current model weights."""
        return self.weights.copy()

    def calculate_liquidations(
        self,
        current_price: Decimal,
        open_interest: Decimal,
        symbol: str = "BTCUSDT",
        leverage_tiers: List[int] = None,
        funding_rate: Decimal = Decimal("0"),
    ) -> List[LiquidationLevel]:
        """Calculate ensemble liquidations from weighted models.

        Args:
            current_price: Current market price
            open_interest: Total Open Interest
            symbol: Trading pair
            leverage_tiers: Leverage tiers
            funding_rate: Current funding rate (for FundingAdjustedModel)

        Returns:
            Aggregated liquidation levels
        """
        if leverage_tiers is None:
            leverage_tiers = [5, 10, 25, 50, 100]

        # Collect predictions from all models
        all_predictions = []

        for model_name, model in self.models.items():
            if model_name == "funding_adjusted":
                preds = model.calculate_liquidations(
                    current_price, open_interest, symbol, leverage_tiers, funding_rate
                )
            else:
                preds = model.calculate_liquidations(
                    current_price, open_interest, symbol, leverage_tiers
                )
            all_predictions.append((model_name, preds))

        # Aggregate predictions by leverage tier and side
        aggregated = self._aggregate_predictions(all_predictions)

        return aggregated

    def confidence_score(self) -> Decimal:
        """Base confidence for ensemble (adjusted per prediction based on agreement)."""
        return Decimal("0.85")

    def _adjust_weights(self) -> Dict[str, Decimal]:
        """Adjust weights to sum to 1.0 when models are missing."""
        available = {k: v for k, v in self.DEFAULT_WEIGHTS.items() if k in self.models}

        if not available:
            return {}

        # Normalize to sum to 1.0
        total = sum(available.values())
        return {k: v / total for k, v in available.items()}

    def _aggregate_predictions(self, predictions: List[tuple]) -> List[LiquidationLevel]:
        """Aggregate predictions from multiple models using weighted average.

        Groups by leverage_tier + side, then calculates weighted average price.
        """
        # Group predictions by (leverage_tier, side)
        grouped = {}

        for model_name, preds in predictions:
            weight = self.weights.get(model_name, Decimal("0"))

            for pred in preds:
                key = (pred.leverage_tier, pred.side)

                if key not in grouped:
                    grouped[key] = {
                        "prices": [],
                        "volumes": [],
                        "symbol": pred.symbol,
                        "timestamp": pred.timestamp,
                    }

                grouped[key]["prices"].append((weight, pred.price_level))
                grouped[key]["volumes"].append((weight, pred.liquidation_volume))

        # Calculate weighted averages
        result = []
        for (leverage_tier, side), data in grouped.items():
            # Weighted average price
            weighted_price = sum(w * p for w, p in data["prices"])

            # Weighted average volume
            weighted_volume = sum(w * v for w, v in data["volumes"])

            # Check model agreement (coefficient of variation)
            prices = [p for _, p in data["prices"]]
            avg_price = sum(prices) / len(prices)
            disagreement = (
                max(abs(p - avg_price) / avg_price for p in prices)
                if avg_price > 0
                else Decimal("0")
            )

            # Lower confidence if models disagree significantly
            confidence = self.confidence_score()
            if disagreement > self.DISAGREEMENT_THRESHOLD:
                confidence = Decimal("0.70")

            result.append(
                LiquidationLevel(
                    timestamp=data["timestamp"],
                    symbol=data["symbol"],
                    price_level=weighted_price,
                    liquidation_volume=weighted_volume,
                    leverage_tier=leverage_tier,
                    side=side,
                    confidence=confidence,
                )
            )

        return result
