"""
Integration tests for whale position margin calculations.

Tests large position sizes ($5M-$50M) to verify:
- Correct tier selection
- Accurate margin calculation with MA offset
- Decimal precision at scale
- Cross-tier accuracy
"""

from decimal import Decimal

import pytest

from src.config.precision import ZERO
from src.models.tier_config import TierConfiguration
from src.services.maintenance_calculator import MaintenanceCalculator
from src.services.margin_calculator import MarginCalculator


class TestWhalePositions:
    """Test suite for large position margin calculations."""

    @pytest.fixture
    def binance_config(self) -> TierConfiguration:
        """Create Binance tier configuration with derived MAs."""
        tiers_with_ma = MaintenanceCalculator.derive_binance_tiers()

        from src.models.margin_tier import MarginTier

        tiers = [
            MarginTier(
                symbol="BTCUSDT",
                tier_number=spec.tier_number,
                min_notional=spec.min_notional,
                max_notional=spec.max_notional,
                margin_rate=spec.margin_rate,
                maintenance_amount=ma,
            )
            for spec, ma in tiers_with_ma
        ]

        return TierConfiguration(
            symbol="BTCUSDT",
            version="binance-2025-v1",
            tiers=tiers,
        )

    def test_5m_position_tier_4_accuracy(self, binance_config):
        """
        Test $5M position lands in Tier 4 with correct margin.

        User Story 1 Acceptance Criteria:
        - Position: $5,000,000
        - Expected Tier: 4 ($1M-$10M @ 5.0%)
        - Expected MA: $29,000
        - Expected Margin: $5,000,000 * 0.05 - $29,000 = $221,000
        """
        calculator = MarginCalculator(binance_config)
        position_size = Decimal("5000000")

        # Calculate margin
        margin = calculator.calculate_margin(position_size)

        # Expected calculation
        expected_margin = Decimal("221000")  # 5M * 0.05 - 29k

        # Verify exact match (no precision loss)
        assert margin == expected_margin, (
            f"Whale position margin incorrect: got ${margin}, expected ${expected_margin}"
        )

        # Verify tier selection
        tier = binance_config.get_tier(position_size)
        assert tier.tier_number == 4, f"Wrong tier: got {tier.tier_number}, expected 4"
        assert tier.margin_rate == Decimal("0.050"), "Wrong margin rate for Tier 4"
        assert tier.maintenance_amount == Decimal("29000"), "Wrong MA for Tier 4"

    def test_10m_position_tier_4_upper_boundary(self, binance_config):
        """
        Test $10M position (Tier 4 upper boundary).

        Boundary Conditions:
        - Position: $10,000,000 (exactly at Tier 4 → Tier 5 boundary)
        - Expected Margin: $10M * 0.05 - $29,000 = $471,000
        - Should equal Tier 5 margin at same notional: $10M * 0.10 - $529,000 = $471,000
        """
        calculator = MarginCalculator(binance_config)
        boundary = Decimal("10000000")

        margin_tier4 = calculator.calculate_margin(boundary)
        expected_margin = Decimal("471000")

        assert margin_tier4 == expected_margin, (
            f"Tier 4 upper boundary incorrect: got ${margin_tier4}, expected ${expected_margin}"
        )

    def test_20m_position_tier_5_accuracy(self, binance_config):
        """
        Test $20M position in Tier 5 (highest tier).

        Large Position Test:
        - Position: $20,000,000
        - Expected Tier: 5 ($10M-$50M @ 10.0%)
        - Expected MA: $529,000
        - Expected Margin: $20M * 0.10 - $529,000 = $1,471,000
        """
        calculator = MarginCalculator(binance_config)
        position_size = Decimal("20000000")

        margin = calculator.calculate_margin(position_size)
        expected_margin = Decimal("1471000")

        assert margin == expected_margin, (
            f"Tier 5 large position incorrect: got ${margin}, expected ${expected_margin}"
        )

        # Verify tier
        tier = binance_config.get_tier(position_size)
        assert tier.tier_number == 5, f"Wrong tier: got {tier.tier_number}, expected 5"
        assert tier.margin_rate == Decimal("0.100"), "Wrong margin rate for Tier 5"

    def test_50m_position_tier_5_maximum(self, binance_config):
        """
        Test $50M position (maximum supported).

        Maximum Position Test:
        - Position: $50,000,000 (Tier 5 upper limit)
        - Expected Margin: $50M * 0.10 - $529,000 = $4,471,000
        """
        calculator = MarginCalculator(binance_config)
        max_position = Decimal("50000000")

        margin = calculator.calculate_margin(max_position)
        expected_margin = Decimal("4471000")

        assert margin == expected_margin, (
            f"Maximum position margin incorrect: got ${margin}, expected ${expected_margin}"
        )

    def test_whale_positions_sequential(self, binance_config):
        """
        Test multiple whale positions in sequence to verify consistency.

        Sequential Test:
        - $2M, $5M, $8M, $15M, $30M
        - All should calculate correctly without state leakage
        """
        calculator = MarginCalculator(binance_config)

        test_cases = [
            (Decimal("2000000"), Decimal("71000")),  # Tier 4: 2M * 0.05 - 29k
            (Decimal("5000000"), Decimal("221000")),  # Tier 4: 5M * 0.05 - 29k
            (Decimal("8000000"), Decimal("371000")),  # Tier 4: 8M * 0.05 - 29k
            (Decimal("15000000"), Decimal("971000")),  # Tier 5: 15M * 0.10 - 529k
            (Decimal("30000000"), Decimal("2471000")),  # Tier 5: 30M * 0.10 - 529k
        ]

        for position, expected_margin in test_cases:
            margin = calculator.calculate_margin(position)
            assert margin == expected_margin, (
                f"Position ${position} failed: got ${margin}, expected ${expected_margin}"
            )

    def test_whale_position_never_negative(self, binance_config):
        """
        Property: Whale positions must never produce negative margin.

        Tests positions from $1M to $50M to ensure MA offset never over-corrects.
        """
        calculator = MarginCalculator(binance_config)

        # Test every $1M increment from $1M to $50M
        for millions in range(1, 51):
            position = Decimal(str(millions * 1_000_000))
            margin = calculator.calculate_margin(position)

            assert margin > ZERO, f"Negative margin at ${position}: margin=${margin}"

    def test_whale_position_exceeds_tier_5_maximum(self, binance_config):
        """
        Test that positions exceeding $50M raise appropriate error.

        Error Handling:
        - Position: $60M (exceeds Tier 5 max)
        - Should raise ValueError with clear message
        """
        calculator = MarginCalculator(binance_config)
        over_max = Decimal("60000000")

        with pytest.raises(ValueError, match="outside tier range"):
            calculator.calculate_margin(over_max)
