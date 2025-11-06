"""
Binance liquidation price calculation model.

Implements Binance futures liquidation formula with maintenance margin.
"""


class BinanceLiquidationModel:
    """Calculate liquidation prices for Binance futures positions."""

    def calculate_liquidation_price(
        self, entry_price, leverage, position_type, maintenance_margin_rate=0.004
    ):
        """
        Calculate liquidation price using Binance formula.

        Formula:
        - Long:  liq_price = entry_price * (1 - 1/leverage + mmr/leverage)
        - Short: liq_price = entry_price * (1 + 1/leverage - mmr/leverage)

        Args:
            entry_price: Entry price of the position
            leverage: Leverage multiplier (e.g., 10 for 10x)
            position_type: "long" or "short"
            maintenance_margin_rate: Maintenance margin rate (default 0.004 = 0.4%)

        Returns:
            Dictionary with liquidation details
        """
        # Calculate liquidation price based on position type
        liq_price = entry_price * (1 - 1 / leverage + maintenance_margin_rate / leverage)

        return {"liq_price": liq_price, "leverage": leverage, "position_type": position_type}
