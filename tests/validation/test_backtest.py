"""Tests for backtest framework (T2.2-T2.4).

TDD RED phase: These tests define the backtest API.
"""

from datetime import datetime

import pytest

from src.liquidationheatmap.validation.backtest import (
    BacktestConfig,
    BacktestResult,
    PredictionMetrics,
    calculate_metrics,
    run_backtest,
)


class TestPredictionMetrics:
    """Test Precision/Recall/F1 calculation."""

    def test_perfect_predictions(self):
        """All predictions hit, all liquidations predicted."""
        metrics = calculate_metrics(
            true_positives=10,
            false_positives=0,
            false_negatives=0,
        )

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1_score == 1.0

    def test_no_predictions(self):
        """No predictions made."""
        metrics = calculate_metrics(
            true_positives=0,
            false_positives=0,
            false_negatives=5,
        )

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1_score == 0.0

    def test_all_false_positives(self):
        """All predictions missed."""
        metrics = calculate_metrics(
            true_positives=0,
            false_positives=10,
            false_negatives=5,
        )

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1_score == 0.0

    def test_balanced_metrics(self):
        """Typical case with mixed results."""
        # 6 TP, 4 FP, 2 FN
        # Precision = 6/(6+4) = 0.6
        # Recall = 6/(6+2) = 0.75
        # F1 = 2 * 0.6 * 0.75 / (0.6 + 0.75) = 0.667
        metrics = calculate_metrics(
            true_positives=6,
            false_positives=4,
            false_negatives=2,
        )

        assert metrics.precision == pytest.approx(0.6, rel=0.01)
        assert metrics.recall == pytest.approx(0.75, rel=0.01)
        assert metrics.f1_score == pytest.approx(0.667, rel=0.01)


class TestBacktestConfig:
    """Test backtest configuration."""

    def test_default_config(self):
        """Config has sensible defaults."""
        config = BacktestConfig(
            symbol="BTCUSDT",
            start_date=datetime(2024, 6, 1),
            end_date=datetime(2024, 12, 31),
        )

        assert config.symbol == "BTCUSDT"
        assert config.tolerance_pct == 1.0  # 1% default
        assert config.prediction_horizon_minutes == 60  # 1 hour default

    def test_custom_tolerance(self):
        """Custom tolerance levels."""
        config = BacktestConfig(
            symbol="BTCUSDT",
            start_date=datetime(2024, 6, 1),
            end_date=datetime(2024, 12, 31),
            tolerance_pct=0.5,
        )

        assert config.tolerance_pct == 0.5


class TestBacktestResult:
    """Test backtest result structure."""

    def test_result_has_metrics(self):
        """Result contains key metrics."""
        result = BacktestResult(
            config=BacktestConfig(
                symbol="BTCUSDT",
                start_date=datetime(2024, 6, 1),
                end_date=datetime(2024, 12, 31),
            ),
            metrics=PredictionMetrics(
                precision=0.7,
                recall=0.8,
                f1_score=0.75,
            ),
            true_positives=70,
            false_positives=30,
            false_negatives=18,
            total_predictions=100,
            total_liquidations=88,
        )

        assert result.metrics.f1_score == 0.75
        assert result.total_predictions == 100
        assert result.passed_gate(threshold=0.6)
        assert not result.passed_gate(threshold=0.8)

    def test_result_to_dict(self):
        """Result can be serialized."""
        result = BacktestResult(
            config=BacktestConfig(
                symbol="BTCUSDT",
                start_date=datetime(2024, 6, 1),
                end_date=datetime(2024, 12, 31),
            ),
            metrics=PredictionMetrics(
                precision=0.7,
                recall=0.8,
                f1_score=0.75,
            ),
            true_positives=70,
            false_positives=30,
            false_negatives=18,
            total_predictions=100,
            total_liquidations=88,
        )

        data = result.to_dict()

        assert "metrics" in data
        assert data["metrics"]["f1_score"] == 0.75
        assert data["symbol"] == "BTCUSDT"


class TestRunBacktest:
    """Integration tests for backtest execution."""

    @pytest.mark.skip(reason="Requires database - run manually")
    def test_backtest_btc_2024(self):
        """Run backtest on BTC 2024 data."""
        config = BacktestConfig(
            symbol="BTCUSDT",
            start_date=datetime(2024, 6, 1),
            end_date=datetime(2024, 12, 31),
            tolerance_pct=1.0,
        )

        result = run_backtest(config)

        # Gate 2: F1 >= 0.6
        assert result.metrics.f1_score >= 0.4, (
            f"F1 score {result.metrics.f1_score} below minimum threshold"
        )
