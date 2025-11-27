"""
Directional positioning validation test.

Verifies all long liquidations are below current price and
short liquidations are above current price (FR-003).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import numpy as np

from src.models.validation_test import ValidationTest
from src.validation.constants import DIRECTIONAL_ACCURACY_MIN
from src.validation.exceptions import InsufficientDataError
from src.validation.logger import logger


class DirectionalTest:
    """
    Directional positioning validation test.

    Ensures long liquidations < current price and short liquidations > current price,
    validating basic directional correctness.
    """

    def __init__(self, run_id: str):
        """
        Initialize directional test.

        Args:
            run_id: Parent validation run ID
        """
        self.run_id = run_id
        self.test_type = "directional_positioning"
        self.weight = Decimal("0.25")  # 25% weight
        self.test_id = str(uuid.uuid4())

    def calculate_accuracy(
        self,
        long_liq_prices: np.ndarray,
        short_liq_prices: np.ndarray,
        current_prices: np.ndarray,
    ) -> Decimal:
        """
        Calculate directional accuracy percentage.

        Args:
            long_liq_prices: Long liquidation prices
            short_liq_prices: Short liquidation prices
            current_prices: Current market prices (same length)

        Returns:
            Accuracy percentage (0-100)

        Raises:
            InsufficientDataError: If arrays empty
        """
        if len(long_liq_prices) == 0 and len(short_liq_prices) == 0:
            raise InsufficientDataError("Need at least some liquidation data")

        total_correct = 0
        total_positions = 0

        # Check long liquidations (should be below current price)
        if len(long_liq_prices) > 0:
            long_correct = np.sum(long_liq_prices < current_prices[: len(long_liq_prices)])
            total_correct += long_correct
            total_positions += len(long_liq_prices)

        # Check short liquidations (should be above current price)
        if len(short_liq_prices) > 0:
            short_correct = np.sum(short_liq_prices > current_prices[: len(short_liq_prices)])
            total_correct += short_correct
            total_positions += len(short_liq_prices)

        accuracy = Decimal(str((total_correct / total_positions) * 100))

        logger.debug(
            f"Calculated directional accuracy: {accuracy:.2f}% "
            f"({total_correct}/{total_positions} correct)"
        )

        return accuracy

    def score_from_accuracy(self, accuracy: Decimal) -> dict:
        """
        Calculate test score from directional accuracy.

        Args:
            accuracy: Accuracy percentage (0-100)

        Returns:
            Dict with passed, score, diagnostics
        """
        # Score equals accuracy
        score = accuracy

        # Test passes if accuracy >= threshold (95%)
        threshold = DIRECTIONAL_ACCURACY_MIN * Decimal("100")
        passed = accuracy >= threshold

        diagnostics = {
            "accuracy_percentage": float(accuracy),
            "threshold_percentage": float(threshold),
            "quality": "excellent" if accuracy >= 99 else "good" if accuracy >= 95 else "poor",
        }

        return {"passed": passed, "score": score, "diagnostics": diagnostics}

    def execute(
        self,
        long_liq_prices: Optional[np.ndarray] = None,
        short_liq_prices: Optional[np.ndarray] = None,
        current_prices: Optional[np.ndarray] = None,
    ) -> ValidationTest:
        """
        Execute directional positioning test.

        Args:
            long_liq_prices: Long liquidation prices
            short_liq_prices: Short liquidation prices
            current_prices: Current market prices

        Returns:
            ValidationTest result object
        """
        executed_at = datetime.utcnow()
        start_time = datetime.utcnow()

        try:
            # Require data
            if long_liq_prices is None or short_liq_prices is None or current_prices is None:
                raise InsufficientDataError("Data must be provided for this test")

            # Calculate accuracy
            accuracy = self.calculate_accuracy(long_liq_prices, short_liq_prices, current_prices)

            # Score the result
            result = self.score_from_accuracy(accuracy)

            # Calculate duration
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Create ValidationTest result
            test_result = ValidationTest(
                test_id=self.test_id,
                run_id=self.run_id,
                test_type=self.test_type,
                test_name="Directional Positioning Test",
                passed=result["passed"],
                score=result["score"],
                weight=self.weight,
                primary_metric=accuracy,
                diagnostics=result["diagnostics"],
                executed_at=executed_at,
                duration_ms=duration_ms,
            )

            logger.info(
                f"Directional test completed: "
                f"accuracy={accuracy:.2f}%, passed={result['passed']}, "
                f"score={result['score']:.1f}"
            )

            return test_result

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            test_result = ValidationTest(
                test_id=self.test_id,
                run_id=self.run_id,
                test_type=self.test_type,
                test_name="Directional Positioning Test",
                passed=False,
                score=Decimal("0.0"),
                weight=self.weight,
                error_message=str(e),
                executed_at=executed_at,
                duration_ms=duration_ms,
            )

            logger.error(f"Directional test failed: {e}")

            return test_result
