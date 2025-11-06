"""
Tests for Binance liquidation calculation model.

Following TDD approach - tests written first, ONE at a time.
"""

from src.models.liquidation import BinanceLiquidationModel


class TestBinanceLiquidationModel:
    """Test suite for Binance liquidation formula implementation."""

    def test_long_liquidation_10x_no_maintenance_margin(self):
        """
        Test long position liquidation at 10x leverage with zero maintenance margin.

        Formula: liq_price = entry_price * (1 - 1/leverage)
        Expected: 100 * (1 - 1/10) = 100 * 0.9 = 90.0
        """
        model = BinanceLiquidationModel()

        result = model.calculate_liquidation_price(
            entry_price=100.0, leverage=10, position_type="long", maintenance_margin_rate=0.0
        )

        assert result["liq_price"] == 90.0
        assert result["leverage"] == 10
        assert result["position_type"] == "long"
