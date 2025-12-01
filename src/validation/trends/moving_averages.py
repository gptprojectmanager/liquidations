"""
Moving average calculations for validation metrics.

Smooths time-series data using various moving average techniques.
"""

from datetime import datetime
from typing import List, Tuple

from src.validation.logger import logger


class MovingAverages:
    """
    Calculates moving averages for validation metrics.

    Provides smoothing for trend visualization and analysis.
    """

    def __init__(self):
        """Initialize moving averages calculator."""
        logger.info("MovingAverages initialized")

    def simple_moving_average(
        self,
        data_points: List[Tuple[datetime, float]],
        window_size: int = 7,
    ) -> List[Tuple[datetime, float]]:
        """
        Calculate simple moving average (SMA).

        Args:
            data_points: List of (timestamp, value) tuples
            window_size: Number of points in moving window

        Returns:
            List of (timestamp, sma_value) tuples
        """
        if len(data_points) < window_size:
            logger.warning(f"Insufficient data for SMA: {len(data_points)} < {window_size}")
            return []

        # Sort by timestamp
        sorted_data = sorted(data_points, key=lambda x: x[0])

        sma_values = []

        for i in range(window_size - 1, len(sorted_data)):
            # Get window
            window = sorted_data[i - window_size + 1 : i + 1]

            # Calculate average
            avg = sum(val for _, val in window) / len(window)

            # Use timestamp of last point in window
            sma_values.append((sorted_data[i][0], avg))

        logger.info(
            f"SMA calculated: {len(sma_values)} points from {len(data_points)} "
            f"(window={window_size})"
        )

        return sma_values

    def exponential_moving_average(
        self,
        data_points: List[Tuple[datetime, float]],
        alpha: float = 0.3,
    ) -> List[Tuple[datetime, float]]:
        """
        Calculate exponential moving average (EMA).

        Args:
            data_points: List of (timestamp, value) tuples
            alpha: Smoothing factor (0-1), higher = more weight on recent values

        Returns:
            List of (timestamp, ema_value) tuples
        """
        if not data_points:
            logger.warning("No data points for EMA")
            return []

        if not 0 < alpha <= 1:
            logger.warning(f"Invalid alpha {alpha}, using 0.3")
            alpha = 0.3

        # Sort by timestamp
        sorted_data = sorted(data_points, key=lambda x: x[0])

        ema_values = []

        # Initialize with first value
        ema = sorted_data[0][1]
        ema_values.append((sorted_data[0][0], ema))

        # Calculate EMA for remaining points
        for ts, val in sorted_data[1:]:
            ema = alpha * val + (1 - alpha) * ema
            ema_values.append((ts, ema))

        logger.info(f"EMA calculated: {len(ema_values)} points (alpha={alpha:.2f})")

        return ema_values

    def weighted_moving_average(
        self,
        data_points: List[Tuple[datetime, float]],
        window_size: int = 7,
    ) -> List[Tuple[datetime, float]]:
        """
        Calculate weighted moving average (WMA).

        More recent values have higher weight.

        Args:
            data_points: List of (timestamp, value) tuples
            window_size: Number of points in moving window

        Returns:
            List of (timestamp, wma_value) tuples
        """
        if len(data_points) < window_size:
            logger.warning(f"Insufficient data for WMA: {len(data_points)} < {window_size}")
            return []

        # Sort by timestamp
        sorted_data = sorted(data_points, key=lambda x: x[0])

        wma_values = []

        # Calculate weights (linear: 1, 2, 3, ..., window_size)
        weights = list(range(1, window_size + 1))
        weight_sum = sum(weights)

        for i in range(window_size - 1, len(sorted_data)):
            # Get window
            window = sorted_data[i - window_size + 1 : i + 1]

            # Calculate weighted average
            weighted_sum = sum(val * weight for (_, val), weight in zip(window, weights))
            wma = weighted_sum / weight_sum

            # Use timestamp of last point in window
            wma_values.append((sorted_data[i][0], wma))

        logger.info(
            f"WMA calculated: {len(wma_values)} points from {len(data_points)} "
            f"(window={window_size})"
        )

        return wma_values

    def calculate_all_averages(
        self,
        data_points: List[Tuple[datetime, float]],
        window_size: int = 7,
        alpha: float = 0.3,
    ) -> dict:
        """
        Calculate all moving average types.

        Args:
            data_points: List of (timestamp, value) tuples
            window_size: Window size for SMA and WMA
            alpha: Smoothing factor for EMA

        Returns:
            Dict with all moving averages
        """
        logger.info(
            f"Calculating all averages for {len(data_points)} points "
            f"(window={window_size}, alpha={alpha})"
        )

        sma = self.simple_moving_average(data_points, window_size)
        ema = self.exponential_moving_average(data_points, alpha)
        wma = self.weighted_moving_average(data_points, window_size)

        return {
            "sma": sma,
            "ema": ema,
            "wma": wma,
            "window_size": window_size,
            "alpha": alpha,
        }

    def smooth_scores(
        self,
        runs: List,
        method: str = "sma",
        window_size: int = 7,
        alpha: float = 0.3,
    ) -> List[Tuple[datetime, float]]:
        """
        Smooth validation run scores using specified method.

        Args:
            runs: List of ValidationRun instances
            method: 'sma', 'ema', or 'wma'
            window_size: Window size for SMA/WMA
            alpha: Smoothing factor for EMA

        Returns:
            List of smoothed (timestamp, score) tuples
        """
        # Extract scores
        data_points = [
            (run.started_at, float(run.overall_score)) for run in runs if run.overall_score
        ]

        logger.info(f"Smoothing {len(data_points)} scores using {method.upper()}")

        if method == "sma":
            return self.simple_moving_average(data_points, window_size)
        elif method == "ema":
            return self.exponential_moving_average(data_points, alpha)
        elif method == "wma":
            return self.weighted_moving_average(data_points, window_size)
        else:
            logger.warning(f"Unknown method {method}, using SMA")
            return self.simple_moving_average(data_points, window_size)


# Global averages instance
_global_averages = None


def get_moving_averages() -> MovingAverages:
    """
    Get global moving averages instance (singleton).

    Returns:
        MovingAverages instance
    """
    global _global_averages

    if _global_averages is None:
        _global_averages = MovingAverages()

    return _global_averages
