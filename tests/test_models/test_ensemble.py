"""Tests for Ensemble liquidation model."""

from decimal import Decimal

from src.liquidationheatmap.models.ensemble import EnsembleModel


class TestEnsembleModel:
    """Tests for EnsembleModel weighted aggregation."""

    def test_ensemble_weights_sum_to_one(self):
        """Test that model weights sum to 1.0 (100%)."""
        model = EnsembleModel()

        weights = model.get_weights()
        total = sum(weights.values())

        assert total == Decimal("1.0")

    def test_ensemble_combines_multiple_models(self):
        """Test that ensemble aggregates predictions from multiple models."""
        model = EnsembleModel()

        current_price = Decimal("67000.00")
        open_interest = Decimal("40000.00")

        liquidations = model.calculate_liquidations(
            current_price=current_price,
            open_interest=open_interest,
            leverage_tiers=[10],
        )

        # Should have liquidations for both long and short
        long_liqs = [liq for liq in liquidations if liq.side == "long"]
        short_liqs = [liq for liq in liquidations if liq.side == "short"]

        assert len(long_liqs) > 0
        assert len(short_liqs) > 0
