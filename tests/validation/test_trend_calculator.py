"""
Tests for trend_calculator.py - Linear regression and trend analysis.

Tests cover:
- Slope calculation
- Trend direction determination
- Change percentage calculation
- Multi-metric trend analysis
"""

from datetime import datetime, timedelta

from src.validation.trends.trend_calculator import (
    TrendCalculator,
    TrendDirection,
    get_trend_calculator,
)


class TestTrendCalculator:
    """Test TrendCalculator functionality."""

    def test_calculate_score_trend_with_improving_scores(self):
        """Trend should be IMPROVING when scores increase."""
        # Arrange
        calculator = TrendCalculator(min_data_points=3)

        start = datetime.utcnow() - timedelta(days=10)
        scores = [
            (start + timedelta(days=i), 70.0 + i * 2.0)  # Scores: 70, 72, 74, 76, 78
            for i in range(5)
        ]

        # Act
        trend = calculator.calculate_score_trend(scores)

        # Assert
        assert trend["direction"] == TrendDirection.IMPROVING
        assert trend["slope"] > 0

    def test_calculate_score_trend_with_degrading_scores(self):
        """Trend should be DEGRADING when scores decrease."""
        # Arrange
        calculator = TrendCalculator(min_data_points=3)

        start = datetime.utcnow() - timedelta(days=10)
        scores = [
            (start + timedelta(days=i), 90.0 - i * 3.0)  # Scores: 90, 87, 84, 81, 78
            for i in range(5)
        ]

        # Act
        trend = calculator.calculate_score_trend(scores)

        # Assert
        assert trend["direction"] == TrendDirection.DEGRADING
        assert trend["slope"] < 0

    def test_calculate_score_trend_with_stable_scores(self):
        """Trend should be STABLE when scores don't change significantly."""
        # Arrange
        calculator = TrendCalculator()

        start = datetime.utcnow() - timedelta(days=10)
        scores = [
            (start + timedelta(days=i), 85.0 + (i % 2) * 0.5)  # Scores oscillate slightly around 85
            for i in range(10)
        ]

        # Act
        trend = calculator.calculate_score_trend(scores)

        # Assert
        assert trend["direction"] == TrendDirection.STABLE

    def test_calculate_score_trend_with_insufficient_data(self):
        """Trend should be INSUFFICIENT_DATA with too few points."""
        # Arrange
        calculator = TrendCalculator(min_data_points=5)

        scores = [
            (datetime.utcnow(), 80.0),
            (datetime.utcnow() + timedelta(days=1), 82.0),
        ]  # Only 2 points

        # Act
        trend = calculator.calculate_score_trend(scores)

        # Assert
        assert trend["direction"] == TrendDirection.INSUFFICIENT_DATA

    def test_slope_calculation_accuracy(self):
        """Slope should be calculated accurately."""
        # Arrange
        calculator = TrendCalculator()

        start = datetime.utcnow()
        # Perfect linear increase: 2 points per day
        scores = [(start + timedelta(days=i), 50.0 + i * 2.0) for i in range(10)]

        # Act
        trend = calculator.calculate_score_trend(scores)

        # Assert
        # Slope should be approximately 2.0 (2 points per day)
        assert abs(trend["slope"] - 2.0) < 0.1  # Allow small numerical error

    def test_change_percent_calculation(self):
        """Change percent should be calculated correctly."""
        # Arrange
        calculator = TrendCalculator(min_data_points=2)

        start = datetime.utcnow()
        scores = [
            (start, 80.0),
            (start + timedelta(days=1), 90.0),
            (start + timedelta(days=2), 100.0),
        ]

        # Act
        trend = calculator.calculate_score_trend(scores)

        # Assert
        # (100 - 80) / 80 * 100 = 25%
        assert abs(trend["change_percent"] - 25.0) < 0.1

    def test_trend_includes_first_and_last_scores(self):
        """Trend should include first and last scores."""
        # Arrange
        calculator = TrendCalculator(min_data_points=2)

        scores = [
            (datetime.utcnow(), 70.0),
            (datetime.utcnow() + timedelta(days=5), 90.0),
        ]

        # Act
        trend = calculator.calculate_score_trend(scores)

        # Assert
        assert trend["first_score"] == 70.0
        assert trend["last_score"] == 90.0

    def test_get_trend_calculator_returns_singleton(self):
        """get_trend_calculator should return same instance."""
        # Act
        calc1 = get_trend_calculator()
        calc2 = get_trend_calculator()

        # Assert
        assert calc1 is calc2


class TestTrendDirection:
    """Test TrendDirection enum."""

    def test_trend_direction_values(self):
        """TrendDirection should have expected values."""
        # Assert
        assert TrendDirection.IMPROVING == "improving"
        assert TrendDirection.STABLE == "stable"
        assert TrendDirection.DEGRADING == "degrading"
        assert TrendDirection.INSUFFICIENT_DATA == "insufficient_data"
