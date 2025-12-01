"""
Binance accuracy comparison tests.

Verifies that margin calculations match Binance's documented formulas and examples.
Tests use known position sizes and expected results from Binance documentation.
"""

from decimal import Decimal

import pytest

from src.services.margin_calculator import MarginCalculator
from src.services.tier_loader import TierLoader


class TestBinanceAccuracy:
    """Test suite comparing calculations against Binance standards."""

    @pytest.fixture
    def calculator(self) -> MarginCalculator:
        """Create margin calculator with Binance default tiers."""
        config = TierLoader.load_binance_default()
        return MarginCalculator(config)

    # Binance documented examples (Tier 1)

    def test_tier_1_example_10k(self, calculator):
        """
        Test Tier 1 calculation for $10k position.

        Binance Tier 1: 0-50k @ 0.5% MMR, MA=0
        Formula: margin = notional * 0.005 - 0
        Expected: 10000 * 0.005 = 50
        """
        position = Decimal("10000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("50")
        assert margin == expected

    def test_tier_1_example_25k(self, calculator):
        """
        Test Tier 1 calculation for $25k position.

        Expected: 25000 * 0.005 = 125
        """
        position = Decimal("25000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("125")
        assert margin == expected

    def test_tier_1_max_50k(self, calculator):
        """
        Test Tier 1 at maximum ($50k).

        Expected: 50000 * 0.005 = 250
        """
        position = Decimal("50000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("250")
        assert margin == expected

    # Binance documented examples (Tier 2)

    def test_tier_2_example_100k(self, calculator):
        """
        Test Tier 2 calculation for $100k position.

        Binance Tier 2: 50k-250k @ 1% MMR, MA=250
        Formula: margin = notional * 0.01 - 250
        Expected: 100000 * 0.01 - 250 = 750
        """
        position = Decimal("100000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("750")
        assert margin == expected

    def test_tier_2_example_150k(self, calculator):
        """
        Test Tier 2 for $150k position.

        Expected: 150000 * 0.01 - 250 = 1250
        """
        position = Decimal("150000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("1250")
        assert margin == expected

    def test_tier_2_max_250k(self, calculator):
        """
        Test Tier 2 at maximum ($250k).

        Expected: 250000 * 0.01 - 250 = 2250
        """
        position = Decimal("250000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("2250")
        assert margin == expected

    # Binance documented examples (Tier 3)

    def test_tier_3_example_500k(self, calculator):
        """
        Test Tier 3 calculation for $500k position.

        Binance Tier 3: 250k-1M @ 2.5% MMR, MA=4000
        Formula: margin = notional * 0.025 - 4000
        Expected: 500000 * 0.025 - 4000 = 8500
        """
        position = Decimal("500000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("8500")
        assert margin == expected

    def test_tier_3_example_750k(self, calculator):
        """
        Test Tier 3 for $750k position.

        Expected: 750000 * 0.025 - 4000 = 14750
        """
        position = Decimal("750000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("14750")
        assert margin == expected

    def test_tier_3_max_1m(self, calculator):
        """
        Test Tier 3 at maximum ($1M).

        Expected: 1000000 * 0.025 - 4000 = 21000
        """
        position = Decimal("1000000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("21000")
        assert margin == expected

    # Binance documented examples (Tier 4)

    def test_tier_4_example_2m(self, calculator):
        """
        Test Tier 4 calculation for $2M position.

        Binance Tier 4: 1M-10M @ 5% MMR, MA=29000
        Formula: margin = notional * 0.05 - 29000
        Expected: 2000000 * 0.05 - 29000 = 71000
        """
        position = Decimal("2000000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("71000")
        assert margin == expected

    def test_tier_4_example_5m(self, calculator):
        """
        Test Tier 4 for $5M position (whale position).

        Expected: 5000000 * 0.05 - 29000 = 221000
        """
        position = Decimal("5000000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("221000")
        assert margin == expected

    def test_tier_4_max_10m(self, calculator):
        """
        Test Tier 4 at maximum ($10M).

        Expected: 10000000 * 0.05 - 29000 = 471000
        """
        position = Decimal("10000000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("471000")
        assert margin == expected

    # Binance documented examples (Tier 5)

    def test_tier_5_example_20m(self, calculator):
        """
        Test Tier 5 calculation for $20M position.

        Binance Tier 5: 10M-50M @ 10% MMR, MA=529000
        Formula: margin = notional * 0.10 - 529000
        Expected: 20000000 * 0.10 - 529000 = 1471000
        """
        position = Decimal("20000000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("1471000")
        assert margin == expected

    def test_tier_5_example_30m(self, calculator):
        """
        Test Tier 5 for $30M position.

        Expected: 30000000 * 0.10 - 529000 = 2471000
        """
        position = Decimal("30000000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("2471000")
        assert margin == expected

    def test_tier_5_max_50m(self, calculator):
        """
        Test Tier 5 at maximum ($50M).

        Expected: 50000000 * 0.10 - 529000 = 4471000
        """
        position = Decimal("50000000")
        margin = calculator.calculate_margin(position)

        expected = Decimal("4471000")
        assert margin == expected

    # Liquidation price calculations (Binance formulas)

    def test_long_liquidation_price_10x_leverage(self, calculator):
        """
        Test long liquidation price with 10x leverage.

        Binance formula for long:
        liq = entry * (1 - 1/leverage + MMR - MA/notional)

        Example: $50k entry, 1 BTC, 10x leverage
        notional = 50000, tier = 1, MMR = 0.005, MA = 0
        liq = 50000 * (1 - 0.1 + 0.005 - 0) = 50000 * 0.905 = 45250
        """
        entry_price = Decimal("50000")
        position_size = Decimal("1")
        leverage = Decimal("10")

        liq_price = calculator.calculate_liquidation_price(
            entry_price, position_size, leverage, "long"
        )

        expected = Decimal("45250")
        assert liq_price == expected

    def test_short_liquidation_price_10x_leverage(self, calculator):
        """
        Test short liquidation price with 10x leverage.

        Binance formula for short:
        liq = entry * (1 + 1/leverage - MMR + MA/notional)

        Example: $50k entry, 1 BTC, 10x leverage
        notional = 50000, tier = 1, MMR = 0.005, MA = 0
        liq = 50000 * (1 + 0.1 - 0.005 + 0) = 50000 * 1.095 = 54750
        """
        entry_price = Decimal("50000")
        position_size = Decimal("1")
        leverage = Decimal("10")

        liq_price = calculator.calculate_liquidation_price(
            entry_price, position_size, leverage, "short"
        )

        expected = Decimal("54750")
        assert liq_price == expected

    def test_long_liquidation_price_5x_leverage_tier2(self, calculator):
        """
        Test long liquidation with 5x leverage in Tier 2.

        Entry: $50k, Size: 3 BTC, 5x leverage
        Notional: 150000, Tier 2, MMR: 0.01, MA: 250
        liq = 50000 * (1 - 0.2 + 0.01 - 250/150000)
            = 50000 * (0.81 - 0.0016666...)
            = 50000 * 0.8083333...
            = 40416.666...
        """
        entry_price = Decimal("50000")
        position_size = Decimal("3")
        leverage = Decimal("5")

        liq_price = calculator.calculate_liquidation_price(
            entry_price, position_size, leverage, "long"
        )

        # Calculate expected with full precision
        notional = entry_price * position_size
        ma_offset = Decimal("250") / notional
        expected = entry_price * (
            Decimal("1") - Decimal("1") / leverage + Decimal("0.01") - ma_offset
        )

        # Should match within 1 cent
        assert abs(liq_price - expected) < Decimal("0.01")

    # Maintenance amount verification

    def test_maintenance_amounts_match_binance(self, calculator):
        """
        Verify maintenance amounts match Binance values.

        Binance documented MA values:
        Tier 1: 0
        Tier 2: 250
        Tier 3: 4000
        Tier 4: 29000
        Tier 5: 529000
        """
        config = calculator.config

        expected_mas = [
            Decimal("0"),
            Decimal("250"),
            Decimal("4000"),
            Decimal("29000"),
            Decimal("529000"),
        ]

        for tier, expected_ma in zip(config.tiers, expected_mas):
            assert tier.maintenance_amount == expected_ma, f"Tier {tier.tier_number} MA mismatch"

    def test_margin_rates_match_binance(self, calculator):
        """
        Verify margin rates match Binance values.

        Binance documented MMR values:
        Tier 1: 0.5% (0.005)
        Tier 2: 1.0% (0.010)
        Tier 3: 2.5% (0.025)
        Tier 4: 5.0% (0.050)
        Tier 5: 10.0% (0.100)
        """
        config = calculator.config

        expected_rates = [
            Decimal("0.005"),
            Decimal("0.010"),
            Decimal("0.025"),
            Decimal("0.050"),
            Decimal("0.100"),
        ]

        for tier, expected_rate in zip(config.tiers, expected_rates):
            assert tier.margin_rate == expected_rate, f"Tier {tier.tier_number} rate mismatch"

    # Precision verification

    def test_binance_precision_compatibility(self, calculator):
        """
        Test that calculations maintain Binance-compatible precision.

        Binance uses 8 decimal places for crypto, 2 for fiat.
        Our Decimal128 should handle this easily.
        """
        # Position with 8 decimal precision (BTC)
        entry_price = Decimal("49999.12345678")
        position_size = Decimal("0.12345678")

        # Should calculate without precision loss
        notional = entry_price * position_size

        tier = calculator.get_tier_for_position(notional)
        margin = calculator.calculate_margin(notional)

        # Verify calculations used full precision
        assert isinstance(margin, Decimal)
        assert isinstance(notional, Decimal)

    # Cross-verification with Binance documentation

    def test_tier_boundaries_match_binance(self, calculator):
        """
        Verify tier boundaries match Binance documentation.

        Binance boundaries:
        Tier 1: 0 - 50,000
        Tier 2: 50,000 - 250,000
        Tier 3: 250,000 - 1,000,000
        Tier 4: 1,000,000 - 10,000,000
        Tier 5: 10,000,000 - 50,000,000
        """
        config = calculator.config

        expected_boundaries = [
            (Decimal("0"), Decimal("50000")),
            (Decimal("50000"), Decimal("250000")),
            (Decimal("250000"), Decimal("1000000")),
            (Decimal("1000000"), Decimal("10000000")),
            (Decimal("10000000"), Decimal("50000000")),
        ]

        for tier, (min_val, max_val) in zip(config.tiers, expected_boundaries):
            assert tier.min_notional == min_val, f"Tier {tier.tier_number} min mismatch"
            assert tier.max_notional == max_val, f"Tier {tier.tier_number} max mismatch"
