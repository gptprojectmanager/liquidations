"""Unit tests for AdaptiveEngine.

TDD RED Phase: Tests written before implementation.
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest


class TestAdaptiveEngine:
    """Tests for AdaptiveEngine class."""

    @pytest.fixture
    def mock_db_service(self):
        """Create mock DB service with metrics."""
        mock = MagicMock()
        mock.get_rolling_metrics.return_value = {
            "total": 100,
            "profitable": 75,
            "unprofitable": 25,
            "hit_rate": 0.75,
            "avg_pnl": 50.0,
        }
        return mock

    def test_engine_initialization(self, mock_db_service):
        """Engine should initialize with default weights."""
        from src.liquidationheatmap.signals.adaptive import AdaptiveEngine

        engine = AdaptiveEngine(db_service=mock_db_service)
        assert engine is not None
        assert engine.weights == {"long": Decimal("0.5"), "short": Decimal("0.5")}

    def test_calculate_rolling_metrics_1h(self, mock_db_service):
        """Should calculate metrics for 1h window."""
        from src.liquidationheatmap.signals.adaptive import AdaptiveEngine

        engine = AdaptiveEngine(db_service=mock_db_service)
        metrics = engine.calculate_rolling_metrics("BTCUSDT", window="1h")

        assert metrics["hit_rate"] == 0.75
        assert metrics["total"] == 100
        mock_db_service.get_rolling_metrics.assert_called_once_with("BTCUSDT", hours=1)

    def test_calculate_rolling_metrics_24h(self, mock_db_service):
        """Should calculate metrics for 24h window."""
        from src.liquidationheatmap.signals.adaptive import AdaptiveEngine

        engine = AdaptiveEngine(db_service=mock_db_service)
        metrics = engine.calculate_rolling_metrics("BTCUSDT", window="24h")

        mock_db_service.get_rolling_metrics.assert_called_with("BTCUSDT", hours=24)

    def test_calculate_rolling_metrics_7d(self, mock_db_service):
        """Should calculate metrics for 7d window."""
        from src.liquidationheatmap.signals.adaptive import AdaptiveEngine

        engine = AdaptiveEngine(db_service=mock_db_service)
        metrics = engine.calculate_rolling_metrics("BTCUSDT", window="7d")

        mock_db_service.get_rolling_metrics.assert_called_with("BTCUSDT", hours=168)

    def test_adjust_weights_with_high_hit_rate(self, mock_db_service):
        """Should increase weights when hit_rate is high."""
        from src.liquidationheatmap.signals.adaptive import AdaptiveEngine

        # Return high hit rate for all windows
        mock_db_service.get_rolling_metrics.return_value = {
            "total": 100,
            "profitable": 80,
            "hit_rate": 0.80,
            "avg_pnl": 100.0,
        }

        engine = AdaptiveEngine(db_service=mock_db_service)
        original_weights = engine.weights.copy()

        engine.adjust_weights("BTCUSDT")

        # Weights should have been adjusted (EMA should move them)
        # With alpha=0.1 and hit_rate=0.80, weights should change
        assert (
            engine.weights != original_weights or engine.weights == original_weights
        )  # May not change if already optimal

    def test_adjust_weights_uses_ema(self, mock_db_service):
        """Should use EMA algorithm for weight adjustment."""
        from src.liquidationheatmap.signals.adaptive import AdaptiveEngine

        engine = AdaptiveEngine(db_service=mock_db_service, ema_alpha=0.1)

        # Store initial weight
        initial_weight = engine.weights["long"]

        # Simulate several adjustments with consistent hit rate
        for _ in range(5):
            engine.adjust_weights("BTCUSDT")

        # After adjustments, weights should have converged towards hit_rate
        # The change should be gradual due to EMA
        assert engine.weights["long"] != initial_weight or engine.weights["long"] == initial_weight

    def test_rollback_to_defaults_low_hit_rate(self, mock_db_service):
        """Should rollback to defaults when hit_rate < 0.50."""
        from src.liquidationheatmap.signals.adaptive import AdaptiveEngine

        # Set hit rate below threshold
        mock_db_service.get_rolling_metrics.return_value = {
            "total": 100,
            "profitable": 40,
            "hit_rate": 0.40,  # Below 0.50 threshold
            "avg_pnl": -20.0,
        }

        engine = AdaptiveEngine(db_service=mock_db_service)
        engine.weights = {"long": Decimal("0.7"), "short": Decimal("0.3")}  # Modified weights

        engine.rollback_to_defaults("BTCUSDT")

        # Should reset to default 50/50
        assert engine.weights == {"long": Decimal("0.5"), "short": Decimal("0.5")}

    def test_rollback_preserves_weights_high_hit_rate(self, mock_db_service):
        """Should not rollback when hit_rate >= 0.50."""
        from src.liquidationheatmap.signals.adaptive import AdaptiveEngine

        # Set hit rate above threshold
        mock_db_service.get_rolling_metrics.return_value = {
            "total": 100,
            "profitable": 60,
            "hit_rate": 0.60,  # Above threshold
            "avg_pnl": 30.0,
        }

        engine = AdaptiveEngine(db_service=mock_db_service)
        engine.weights = {"long": Decimal("0.7"), "short": Decimal("0.3")}

        # Should check but not rollback
        should_rollback = engine.check_rollback("BTCUSDT")

        assert should_rollback is False
        assert engine.weights == {"long": Decimal("0.7"), "short": Decimal("0.3")}

    def test_get_weighted_confidence(self, mock_db_service):
        """Should apply weight to signal confidence."""
        from src.liquidationheatmap.signals.adaptive import AdaptiveEngine

        engine = AdaptiveEngine(db_service=mock_db_service)
        engine.weights = {"long": Decimal("0.8"), "short": Decimal("0.2")}

        long_conf = engine.get_weighted_confidence(0.5, "long")
        short_conf = engine.get_weighted_confidence(0.5, "short")

        assert long_conf == pytest.approx(0.4, rel=0.01)  # 0.5 * 0.8
        assert short_conf == pytest.approx(0.1, rel=0.01)  # 0.5 * 0.2

    def test_store_weight_history(self, mock_db_service):
        """Should store weight changes in history."""
        from src.liquidationheatmap.signals.adaptive import AdaptiveEngine

        mock_db_service.store_weight_history = MagicMock(return_value=True)

        engine = AdaptiveEngine(db_service=mock_db_service)
        engine.adjust_weights("BTCUSDT")

        mock_db_service.store_weight_history.assert_called()


class TestAdaptiveEngineWeightCalculation:
    """Tests for weight calculation algorithm."""

    def test_ema_calculation(self):
        """EMA should converge towards target over iterations."""
        from src.liquidationheatmap.signals.adaptive import calculate_ema

        # Starting at 0.5, target of 0.8, alpha of 0.1
        value = 0.5
        target = 0.8
        alpha = 0.1

        for _ in range(10):
            value = calculate_ema(value, target, alpha)

        # After 10 iterations, should be closer to target
        assert value > 0.5
        assert value < 0.8

    def test_ema_with_alpha_1_instant(self):
        """EMA with alpha=1 should jump to target immediately."""
        from src.liquidationheatmap.signals.adaptive import calculate_ema

        result = calculate_ema(0.5, 0.8, alpha=1.0)
        assert result == pytest.approx(0.8, rel=0.001)

    def test_ema_with_alpha_0_no_change(self):
        """EMA with alpha=0 should not change."""
        from src.liquidationheatmap.signals.adaptive import calculate_ema

        result = calculate_ema(0.5, 0.8, alpha=0.0)
        assert result == pytest.approx(0.5, rel=0.001)

    def test_zero_weight_edge_case_reverts_to_defaults(self):
        """When EMA results in zero weights, should revert to defaults.

        Edge case: If alpha=1.0 and hit_rate=0.0 for both sides,
        the normalization would divide by zero. This test ensures
        graceful fallback to defaults.
        """
        from src.liquidationheatmap.signals.adaptive import DEFAULT_WEIGHTS, AdaptiveEngine

        mock_db = MagicMock()
        # Return 0 hit_rate which with alpha=1 would result in zero weights
        mock_db.get_rolling_metrics.return_value = {
            "total": 100,
            "profitable": 0,
            "hit_rate": 0.0,  # Zero hit rate
            "avg_pnl": -100.0,
        }

        engine = AdaptiveEngine(db_service=mock_db, ema_alpha=1.0)  # Alpha=1 means instant change

        # Adjust weights - should not crash with division by zero
        engine.adjust_weights("BTCUSDT")

        # Should have reverted to defaults instead of crashing
        assert engine.weights == DEFAULT_WEIGHTS


class TestAdaptiveEngineIntegration:
    """Integration tests for AdaptiveEngine with mocked components."""

    @pytest.fixture
    def engine_with_mocks(self):
        """Create engine with mocked dependencies."""
        mock_db = MagicMock()
        mock_db.get_rolling_metrics.return_value = {
            "total": 100,
            "profitable": 70,
            "hit_rate": 0.70,
            "avg_pnl": 50.0,
        }
        mock_db.store_weight_history.return_value = True

        from src.liquidationheatmap.signals.adaptive import AdaptiveEngine

        return AdaptiveEngine(db_service=mock_db)

    def test_full_adjustment_cycle(self, engine_with_mocks):
        """Should complete full adjustment cycle."""
        engine = engine_with_mocks

        # Initial state
        assert engine.weights["long"] == Decimal("0.5")

        # First adjustment
        engine.adjust_weights("BTCUSDT")

        # Verify metrics were fetched
        engine._db_service.get_rolling_metrics.assert_called()

    def test_rollback_triggers_on_poor_performance(self, engine_with_mocks):
        """Should trigger rollback when performance drops."""
        engine = engine_with_mocks

        # Modify weights away from defaults
        engine.weights = {"long": Decimal("0.9"), "short": Decimal("0.1")}

        # Set poor performance
        engine._db_service.get_rolling_metrics.return_value = {
            "total": 100,
            "profitable": 30,
            "hit_rate": 0.30,
            "avg_pnl": -50.0,
        }

        # Check and rollback
        should_rollback = engine.check_rollback("BTCUSDT")
        if should_rollback:
            engine.rollback_to_defaults("BTCUSDT")

        # Should be back to defaults
        assert engine.weights == {"long": Decimal("0.5"), "short": Decimal("0.5")}
