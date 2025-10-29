"""Tests for Funding Rate Adjusted liquidation model."""

from decimal import Decimal

from src.liquidationheatmap.models.funding_adjusted import FundingAdjustedModel


class TestFundingAdjustedModel:
    """Tests for FundingAdjustedModel with funding rate adjustments."""

    def test_positive_funding_increases_long_liquidation_risk(self):
        """Test that positive funding rate pushes long liquidation higher.

        Positive funding = longs pay shorts → more pressure on longs.
        Long liquidation should be slightly higher (closer to entry).
        """
        model = FundingAdjustedModel()

        current_price = Decimal("67000.00")
        open_interest = Decimal("40000.00")
        positive_funding = Decimal("0.0001")  # 0.01% funding

        liquidations = model.calculate_liquidations(
            current_price=current_price,
            open_interest=open_interest,
            symbol="BTCUSDT",
            leverage_tiers=[10],
            funding_rate=positive_funding,
        )

        # Get long liquidation with funding adjustment
        long_10x = [liq for liq in liquidations if liq.leverage_tier == "10x" and liq.side == "long"][0]

        # Standard Binance model for comparison (no funding)
        from src.liquidationheatmap.models.binance_standard import BinanceStandardModel
        standard_model = BinanceStandardModel()
        standard_liq = standard_model.calculate_liquidations(
            current_price, open_interest, leverage_tiers=[10]
        )[0]

        # Positive funding → long liquidation should be higher (more risky)
        assert long_10x.price_level > standard_liq.price_level
