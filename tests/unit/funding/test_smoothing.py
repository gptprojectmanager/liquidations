"""
Unit tests for historical smoothing functionality.
Feature: LIQHEAT-005
Task: T021 - Add historical smoothing support
TDD: Red phase
"""

from decimal import Decimal

import pytest

from src.models.funding.adjustment_config import AdjustmentConfigModel
from src.models.funding.bias_adjustment import BiasAdjustment

# These imports will fail initially (TDD Red phase)
from src.services.funding.smoothing import HistoricalSmoother


class TestHistoricalSmoother:
    """Test suite for historical smoothing."""

    def test_smooth_with_single_adjustment(self):
        """Test smoothing with only one historical adjustment (no smoothing)."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            smoothing_enabled=True,
            smoothing_periods=3,
        )
        smoother = HistoricalSmoother(config)

        current = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.55"),
            short_ratio=Decimal("0.45"),
            confidence=0.5,
        )

        # Act - With no history, should return current unchanged
        result = smoother.smooth_adjustment(current, history=[])

        # Assert
        assert result.long_ratio == current.long_ratio
        assert result.short_ratio == current.short_ratio

    def test_smooth_with_two_periods(self):
        """Test smoothing with two historical adjustments."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            smoothing_enabled=True,
            smoothing_periods=2,
            smoothing_weights=[0.6, 0.4],  # Current gets 60%, previous gets 40%
        )
        smoother = HistoricalSmoother(config)

        previous = BiasAdjustment(
            funding_input=Decimal("0.0002"),
            long_ratio=Decimal("0.52"),
            short_ratio=Decimal("0.48"),
            confidence=0.4,
        )

        current = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.55"),
            short_ratio=Decimal("0.45"),
            confidence=0.5,
        )

        # Act
        result = smoother.smooth_adjustment(current, history=[previous])

        # Assert
        # Expected: 0.55 * 0.6 + 0.52 * 0.4 = 0.33 + 0.208 = 0.538
        expected_long = Decimal("0.538")
        expected_short = Decimal("0.462")

        assert abs(result.long_ratio - expected_long) < Decimal("0.001")
        assert abs(result.short_ratio - expected_short) < Decimal("0.001")
        assert result.long_ratio + result.short_ratio == Decimal("1.0")  # OI conservation

    def test_smooth_with_three_periods(self):
        """Test smoothing with three historical adjustments."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            smoothing_enabled=True,
            smoothing_periods=3,
            smoothing_weights=[0.5, 0.3, 0.2],  # Weights for current, -1, -2
        )
        smoother = HistoricalSmoother(config)

        oldest = BiasAdjustment(
            funding_input=Decimal("0.0001"),
            long_ratio=Decimal("0.51"),
            short_ratio=Decimal("0.49"),
            confidence=0.3,
        )

        middle = BiasAdjustment(
            funding_input=Decimal("0.0002"),
            long_ratio=Decimal("0.52"),
            short_ratio=Decimal("0.48"),
            confidence=0.4,
        )

        current = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.55"),
            short_ratio=Decimal("0.45"),
            confidence=0.5,
        )

        # Act
        result = smoother.smooth_adjustment(current, history=[oldest, middle])

        # Assert
        # Expected: 0.55 * 0.5 + 0.52 * 0.3 + 0.51 * 0.2
        # = 0.275 + 0.156 + 0.102 = 0.533
        expected_long = Decimal("0.533")
        expected_short = Decimal("0.467")

        assert abs(result.long_ratio - expected_long) < Decimal("0.001")
        assert abs(result.short_ratio - expected_short) < Decimal("0.001")

    def test_smooth_when_disabled(self):
        """Test that no smoothing occurs when disabled."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            smoothing_enabled=False,  # Disabled
            smoothing_periods=3,
        )
        smoother = HistoricalSmoother(config)

        previous = BiasAdjustment(
            funding_input=Decimal("0.0002"),
            long_ratio=Decimal("0.52"),
            short_ratio=Decimal("0.48"),
            confidence=0.4,
        )

        current = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.55"),
            short_ratio=Decimal("0.45"),
            confidence=0.5,
        )

        # Act
        result = smoother.smooth_adjustment(current, history=[previous])

        # Assert - Should return current unchanged
        assert result.long_ratio == current.long_ratio
        assert result.short_ratio == current.short_ratio

    def test_smooth_with_insufficient_history(self):
        """Test smoothing with less history than requested periods."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            smoothing_enabled=True,
            smoothing_periods=5,  # Request 5 periods
            smoothing_weights=None,  # Auto-calculate
        )
        smoother = HistoricalSmoother(config)

        # Only 2 adjustments available
        previous = BiasAdjustment(
            funding_input=Decimal("0.0002"),
            long_ratio=Decimal("0.52"),
            short_ratio=Decimal("0.48"),
            confidence=0.4,
        )

        current = BiasAdjustment(
            funding_input=Decimal("0.0003"),
            long_ratio=Decimal("0.55"),
            short_ratio=Decimal("0.45"),
            confidence=0.5,
        )

        # Act
        result = smoother.smooth_adjustment(current, history=[previous])

        # Assert - Should use what's available (2 periods)
        assert result.long_ratio != current.long_ratio  # Some smoothing applied
        assert result.long_ratio < current.long_ratio  # Pulled toward lower historical value
        assert result.long_ratio > previous.long_ratio  # But still higher than old value

    def test_smooth_preserves_oi_conservation(self):
        """Test that smoothing always preserves OI conservation."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            smoothing_enabled=True,
            smoothing_periods=3,
        )
        smoother = HistoricalSmoother(config)

        # Create adjustments with varying ratios
        adjustments = []
        for i in range(3):
            adj = BiasAdjustment(
                funding_input=Decimal(str(0.0001 * (i + 1))),
                long_ratio=Decimal(str(0.51 + 0.03 * i)),
                short_ratio=Decimal(str(0.49 - 0.03 * i)),
                confidence=0.3 + 0.1 * i,
            )
            adjustments.append(adj)

        # Act
        result = smoother.smooth_adjustment(adjustments[-1], history=adjustments[:-1])

        # Assert - Must maintain OI conservation
        total = result.long_ratio + result.short_ratio
        assert abs(total - Decimal("1.0")) < Decimal("1e-10")

    def test_smooth_with_extreme_values(self):
        """Test smoothing helps dampen extreme swings."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            smoothing_enabled=True,
            smoothing_periods=3,
            smoothing_weights=[0.4, 0.35, 0.25],  # More weight on history
        )
        smoother = HistoricalSmoother(config)

        # Stable history
        stable1 = BiasAdjustment(
            funding_input=Decimal("0.0001"),
            long_ratio=Decimal("0.50"),
            short_ratio=Decimal("0.50"),
            confidence=0.3,
        )

        stable2 = BiasAdjustment(
            funding_input=Decimal("0.0001"),
            long_ratio=Decimal("0.51"),
            short_ratio=Decimal("0.49"),
            confidence=0.3,
        )

        # Extreme current value
        extreme = BiasAdjustment(
            funding_input=Decimal("0.01"),
            long_ratio=Decimal("0.70"),  # Extreme jump
            short_ratio=Decimal("0.30"),
            confidence=0.9,
        )

        # Act
        result = smoother.smooth_adjustment(extreme, history=[stable1, stable2])

        # Assert - Should be dampened
        assert result.long_ratio < extreme.long_ratio  # Pulled back from extreme
        assert result.long_ratio > Decimal("0.55")  # But still moved from stable

    def test_auto_calculate_weights(self):
        """Test automatic weight calculation."""
        # Arrange
        config = AdjustmentConfigModel(
            enabled=True,
            symbol="BTCUSDT",
            smoothing_enabled=True,
            smoothing_periods=3,
            smoothing_weights=None,  # Auto-calculate
        )
        smoother = HistoricalSmoother(config)

        # Act
        weights = smoother.get_weights()

        # Assert
        assert len(weights) == 3
        assert sum(weights) == pytest.approx(1.0)
        # Should be decreasing (more weight on recent)
        assert weights[0] > weights[1] > weights[2]
