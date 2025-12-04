"""
Tests for moving_averages.py - Time-series smoothing algorithms.

Tests cover:
- Simple Moving Average (SMA)
- Exponential Moving Average (EMA)
- Weighted Moving Average (WMA)
- Window size handling
- Alpha parameter
"""

from datetime import datetime, timedelta

from src.validation.trends.moving_averages import MovingAverages, get_moving_averages


class TestMovingAverages:
    """Test MovingAverages functionality."""

    def test_simple_moving_average_with_window_3(self):
        """SMA should calculate correct average with window size 3."""
        # Arrange
        ma = MovingAverages()

        start = datetime.utcnow()
        data = [
            (start + timedelta(days=i), float(10 * (i + 1)))  # 10, 20, 30, 40, 50
            for i in range(5)
        ]

        # Act
        sma = ma.simple_moving_average(data, window_size=3)

        # Assert
        # First SMA point: (10 + 20 + 30) / 3 = 20
        # Second SMA point: (20 + 30 + 40) / 3 = 30
        # Third SMA point: (30 + 40 + 50) / 3 = 40
        assert len(sma) == 3  # 5 points - 3 window + 1
        assert abs(sma[0][1] - 20.0) < 0.01
        assert abs(sma[1][1] - 30.0) < 0.01
        assert abs(sma[2][1] - 40.0) < 0.01

    def test_exponential_moving_average_with_alpha_03(self):
        """EMA should calculate correctly with alpha = 0.3."""
        # Arrange
        ma = MovingAverages()

        start = datetime.utcnow()
        data = [
            (start + timedelta(days=i), 100.0)  # Constant value
            for i in range(5)
        ]

        # Act
        ema = ma.exponential_moving_average(data, alpha=0.3)

        # Assert
        # With constant values, EMA should converge to that value
        assert len(ema) == 5
        for _, val in ema:
            assert abs(val - 100.0) < 0.01  # Should all be ~100

    def test_exponential_moving_average_smooths_volatility(self):
        """EMA should smooth out volatility."""
        # Arrange
        ma = MovingAverages()

        start = datetime.utcnow()
        # Alternating high-low values
        data = [(start + timedelta(days=i), 100.0 if i % 2 == 0 else 50.0) for i in range(10)]

        # Act
        ema = ma.exponential_moving_average(data, alpha=0.3)

        # Assert
        # EMA should be smoother than raw data
        assert len(ema) == 10
        # Later values should stabilize around midpoint
        assert 60.0 < ema[-1][1] < 90.0

    def test_weighted_moving_average_gives_more_weight_to_recent(self):
        """WMA should weight recent values more heavily."""
        # Arrange
        ma = MovingAverages()

        start = datetime.utcnow()
        # Increasing values: 10, 20, 30, 40, 50
        data = [(start + timedelta(days=i), 10.0 * (i + 1)) for i in range(5)]

        # Act
        wma = ma.weighted_moving_average(data, window_size=3)

        # Assert
        # For window [10, 20, 30]: weights [1, 2, 3]
        # WMA = (10*1 + 20*2 + 30*3) / (1+2+3) = 140 / 6 = 23.33
        assert len(wma) == 3
        assert abs(wma[0][1] - 23.33) < 0.1

    def test_calculate_all_averages_returns_all_three_types(self):
        """calculate_all_averages should return SMA, EMA, and WMA."""
        # Arrange
        ma = MovingAverages()

        start = datetime.utcnow()
        data = [(start + timedelta(days=i), 80.0 + i * 2.0) for i in range(10)]

        # Act
        result = ma.calculate_all_averages(
            data_points=data,
            window_size=5,
            alpha=0.3,
        )

        # Assert
        assert "sma" in result
        assert "ema" in result
        assert "wma" in result
        assert "window_size" in result
        assert "alpha" in result
        assert result["window_size"] == 5
        assert result["alpha"] == 0.3

    def test_empty_data_returns_empty_averages(self):
        """Empty data should return empty averages."""
        # Arrange
        ma = MovingAverages()

        # Act
        sma = ma.simple_moving_average([], window_size=3)
        ema = ma.exponential_moving_average([], alpha=0.3)
        wma = ma.weighted_moving_average([], window_size=3)

        # Assert
        assert sma == []
        assert ema == []
        assert wma == []

    def test_get_moving_averages_returns_singleton(self):
        """get_moving_averages should return same instance."""
        # Act
        ma1 = get_moving_averages()
        ma2 = get_moving_averages()

        # Assert
        assert ma1 is ma2


class TestMovingAverageEdgeCases:
    """Test edge cases for moving averages."""

    def test_window_size_larger_than_data(self):
        """Window size larger than data should return empty SMA."""
        # Arrange
        ma = MovingAverages()

        data = [
            (datetime.utcnow(), 100.0),
            (datetime.utcnow() + timedelta(days=1), 110.0),
        ]

        # Act
        sma = ma.simple_moving_average(data, window_size=10)

        # Assert
        assert sma == []  # Not enough data for window

    def test_alpha_value_extremes(self):
        """Alpha = 1.0 should follow most recent value closely."""
        # Arrange
        ma = MovingAverages()

        start = datetime.utcnow()
        data = [
            (start, 50.0),
            (start + timedelta(days=1), 100.0),  # Big jump
        ]

        # Act
        ema = ma.exponential_moving_average(data, alpha=1.0)

        # Assert
        # With alpha=1.0, should track recent value exactly
        assert abs(ema[-1][1] - 100.0) < 0.01
