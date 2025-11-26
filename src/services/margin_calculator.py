"""
Margin calculator service for tiered margin calculations.

Provides the main calculation interface using TierConfiguration.
"""

from decimal import Decimal

from src.config.precision import ensure_decimal
from src.models.tier_config import TierConfiguration


class MarginCalculator:
    """
    Service for calculating margin requirements using tiered rates.

    Attributes:
        config: TierConfiguration defining the tier structure
    """

    def __init__(self, config: TierConfiguration):
        """
        Initialize calculator with tier configuration.

        Args:
            config: TierConfiguration for symbol
        """
        self.config = config

    def calculate_margin(self, notional: Decimal) -> Decimal:
        """
        Calculate margin requirement for position.

        Args:
            notional: Position notional value in USD

        Returns:
            Required margin amount in USD

        Raises:
            ValueError: If notional is invalid or out of range
        """
        notional = ensure_decimal(notional)
        return self.config.calculate_margin(notional)

    def get_tier_for_position(self, notional: Decimal):
        """
        Get the tier that applies to a position.

        Args:
            notional: Position notional value

        Returns:
            MarginTier applicable to this position
        """
        notional = ensure_decimal(notional)
        return self.config.get_tier(notional)

    def calculate_liquidation_price(
        self, entry_price: Decimal, position_size: Decimal, leverage: Decimal, side: str
    ) -> Decimal:
        """
        Calculate liquidation price for leveraged position using tiered margins.

        Formula (adapted from Binance with tiered maintenance margin):
        - Long:  liq_price = entry_price * (1 - 1/leverage + margin_rate - MA/(notional))
        - Short: liq_price = entry_price * (1 + 1/leverage - margin_rate + MA/(notional))

        Where:
        - notional = entry_price * position_size
        - margin_rate = tier.margin_rate (maintenance margin rate for tier)
        - MA = tier.maintenance_amount (offset for continuity)

        Args:
            entry_price: Entry price of position
            position_size: Position size in base currency
            leverage: Leverage multiplier (e.g., 10 for 10x)
            side: Position side ("long" or "short")

        Returns:
            Liquidation price in quote currency

        Raises:
            ValueError: If leverage is zero, side is invalid, or position is invalid

        Example:
            >>> calc = MarginCalculator(binance_config)
            >>> calc.calculate_liquidation_price(
            ...     entry_price=Decimal("50000"),
            ...     position_size=Decimal("1"),
            ...     leverage=Decimal("10"),
            ...     side="long"
            ... )
            Decimal('45500.00')  # Tier 2: 0.01 rate, $250 MA
        """
        entry_price = ensure_decimal(entry_price)
        position_size = ensure_decimal(position_size)
        leverage = ensure_decimal(leverage)

        if leverage <= 0:
            raise ValueError(f"Leverage must be positive: {leverage}")

        if side not in ("long", "short"):
            raise ValueError(f"Side must be 'long' or 'short': {side}")

        # Calculate notional value
        notional = entry_price * position_size

        # Get tier for this notional
        tier = self.get_tier_for_position(notional)

        # Calculate maintenance margin rate and offset
        margin_rate = tier.margin_rate
        ma_offset = tier.maintenance_amount / notional

        # Leverage factor
        leverage_factor = Decimal("1") / leverage

        # Calculate liquidation price based on side
        if side == "long":
            # Long: liq_price = entry * (1 - 1/lev + MMR - MA/notional)
            liq_price = entry_price * (Decimal("1") - leverage_factor + margin_rate - ma_offset)
        else:  # short
            # Short: liq_price = entry * (1 + 1/lev - MMR + MA/notional)
            liq_price = entry_price * (Decimal("1") + leverage_factor - margin_rate + ma_offset)

        return liq_price

    def calculate_initial_margin(self, notional: Decimal, leverage: Decimal) -> Decimal:
        """
        Calculate initial margin required to open position.

        Formula: initial_margin = notional / leverage

        Args:
            notional: Position notional value
            leverage: Leverage multiplier

        Returns:
            Initial margin required

        Example:
            >>> calc.calculate_initial_margin(Decimal("100000"), Decimal("10"))
            Decimal('10000')  # 10% of notional for 10x leverage
        """
        notional = ensure_decimal(notional)
        leverage = ensure_decimal(leverage)

        if leverage <= 0:
            raise ValueError(f"Leverage must be positive: {leverage}")

        return notional / leverage

    def calculate_margin_ratio(self, notional: Decimal, wallet_balance: Decimal) -> Decimal:
        """
        Calculate margin ratio (maintenance margin / wallet balance).

        Used to determine liquidation risk. When margin ratio >= 100%, position is liquidated.

        Args:
            notional: Position notional value
            wallet_balance: Available wallet balance

        Returns:
            Margin ratio as decimal (e.g., 0.75 = 75%)

        Example:
            >>> calc.calculate_margin_ratio(Decimal("100000"), Decimal("3000"))
            Decimal('0.75')  # 75% margin ratio
        """
        notional = ensure_decimal(notional)
        wallet_balance = ensure_decimal(wallet_balance)

        if wallet_balance <= 0:
            raise ValueError("Wallet balance must be positive")

        maintenance_margin = self.calculate_margin(notional)
        return maintenance_margin / wallet_balance
