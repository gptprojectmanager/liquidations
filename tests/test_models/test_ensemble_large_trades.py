"""Test that EnsembleModel accepts large_trades parameter."""

from decimal import Decimal

from src.liquidationheatmap.models.ensemble import EnsembleModel


class TestEnsembleLargeTradesParam:
    """Test EnsembleModel compatibility with large_trades parameter."""

    def test_ensemble_accepts_large_trades_parameter(self):
        """Test that EnsembleModel accepts large_trades parameter for API compatibility.

        This is required because the API passes large_trades to all models,
        so EnsembleModel must accept it even if it delegates to sub-models.
        """
        model = EnsembleModel()

        # Should not raise TypeError
        result = model.calculate_liquidations(
            current_price=Decimal("114000"),
            open_interest=Decimal("1000000000"),
            symbol="BTCUSDT",
            large_trades=None,  # API passes this parameter
        )

        assert isinstance(result, list)
