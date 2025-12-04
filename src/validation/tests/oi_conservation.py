"""
Open Interest conservation validation test.

Verifies that total estimated positions equal actual open interest
within acceptable error tolerance (FR-002).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import numpy as np

from src.models.validation_test import ValidationTest
from src.validation.constants import OI_CONSERVATION_ERROR_MAX
from src.validation.exceptions import InsufficientDataError
from src.validation.logger import logger


class OIConservationTest:
    """
    Open Interest conservation validation test.

    Ensures sum of estimated long/short positions equals actual OI,
    validating calculation correctness.
    """

    def __init__(self, run_id: str):
        """
        Initialize OI conservation test.

        Args:
            run_id: Parent validation run ID
        """
        self.run_id = run_id
        self.test_type = "oi_conservation"
        self.weight = Decimal("0.35")  # 35% weight
        self.test_id = str(uuid.uuid4())

    def calculate_error(self, estimated_positions: np.ndarray, actual_oi: np.ndarray) -> Decimal:
        """
        Calculate conservation error percentage.

        Args:
            estimated_positions: Sum of estimated long+short positions
            actual_oi: Actual open interest values

        Returns:
            Error percentage (0-100)

        Raises:
            InsufficientDataError: If arrays empty or mismatched
        """
        if len(estimated_positions) == 0 or len(actual_oi) == 0:
            raise InsufficientDataError("Cannot calculate error with empty arrays")

        if len(estimated_positions) != len(actual_oi):
            raise ValueError("Arrays must be same length")

        # Calculate absolute percentage error for each point
        errors = np.abs((estimated_positions - actual_oi) / actual_oi) * 100

        # Use mean absolute percentage error (MAPE)
        mean_error = Decimal(str(np.mean(errors)))

        logger.debug(
            f"Calculated OI conservation error: {mean_error:.4f}% (n={len(estimated_positions)})"
        )

        return mean_error

    def score_from_error(self, error_pct: Decimal) -> dict:
        """
        Calculate test score from conservation error.

        Args:
            error_pct: Error percentage

        Returns:
            Dict with passed, score, diagnostics
        """
        # Convert to decimal for threshold comparison
        threshold = OI_CONSERVATION_ERROR_MAX * Decimal("100")  # Convert 0.01 to 1%

        # Score inversely proportional to error:
        # 0% error -> 100 points
        # 1% error -> 90 points (threshold)
        # 5% error -> 50 points
        # 10% error -> 0 points
        if error_pct <= 10:
            score = Decimal("100") - (error_pct * Decimal("10"))
        else:
            score = Decimal("0")

        # Test passes if error below threshold
        passed = error_pct <= threshold

        diagnostics = {
            "error_percentage": float(error_pct),
            "threshold_percentage": float(threshold),
            "conservation_quality": "excellent"
            if error_pct < 0.5
            else "good"
            if error_pct < 1
            else "poor",
        }

        return {"passed": passed, "score": max(score, Decimal("0")), "diagnostics": diagnostics}

    def execute(
        self,
        estimated_positions: Optional[np.ndarray] = None,
        actual_oi: Optional[np.ndarray] = None,
    ) -> ValidationTest:
        """
        Execute OI conservation test.

        Args:
            estimated_positions: Sum of long+short estimates
            actual_oi: Actual OI values

        Returns:
            ValidationTest result object
        """
        executed_at = datetime.utcnow()
        start_time = datetime.utcnow()

        try:
            # Require data to be provided
            if estimated_positions is None or actual_oi is None:
                raise InsufficientDataError("Data must be provided for this test")

            # Calculate error
            error_pct = self.calculate_error(estimated_positions, actual_oi)

            # Score the result
            result = self.score_from_error(error_pct)

            # Calculate duration
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Create ValidationTest result
            test_result = ValidationTest(
                test_id=self.test_id,
                run_id=self.run_id,
                test_type=self.test_type,
                test_name="Open Interest Conservation Test",
                passed=result["passed"],
                score=result["score"],
                weight=self.weight,
                primary_metric=error_pct,
                diagnostics=result["diagnostics"],
                executed_at=executed_at,
                duration_ms=duration_ms,
            )

            logger.info(
                f"OI conservation test completed: "
                f"error={error_pct:.2f}%, passed={result['passed']}, "
                f"score={result['score']:.1f}"
            )

            return test_result

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            test_result = ValidationTest(
                test_id=self.test_id,
                run_id=self.run_id,
                test_type=self.test_type,
                test_name="Open Interest Conservation Test",
                passed=False,
                score=Decimal("0.0"),
                weight=self.weight,
                error_message=str(e),
                executed_at=executed_at,
                duration_ms=duration_ms,
            )

            logger.error(f"OI conservation test failed: {e}")

            return test_result
