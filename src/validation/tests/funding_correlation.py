"""
Funding rate correlation validation test.

Tests whether estimated long/short position ratios correlate with
funding rates over a 30-day window (FR-001).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import numpy as np
from scipy import stats

from src.models.validation_test import ValidationTest
from src.validation.constants import (
    FUNDING_CORRELATION_MIN_ACCEPTABLE,
    FUNDING_CORRELATION_P_VALUE_MAX,
)
from src.validation.exceptions import InsufficientDataError
from src.validation.logger import logger


class FundingCorrelationTest:
    """
    Funding rate correlation validation test.

    Calculates Pearson correlation between estimated long/short ratios
    and funding rates to validate model accuracy.
    """

    def __init__(self, run_id: str):
        """
        Initialize funding correlation test.

        Args:
            run_id: Parent validation run ID
        """
        self.run_id = run_id
        self.test_type = "funding_correlation"
        self.weight = Decimal("0.40")  # 40% weight in overall score
        self.test_id = str(uuid.uuid4())

    def calculate_correlation(
        self, long_short_ratios: np.ndarray, funding_rates: np.ndarray
    ) -> tuple[float, float]:
        """
        Calculate Pearson correlation coefficient.

        Args:
            long_short_ratios: Array of estimated long/short ratios
            funding_rates: Array of funding rates

        Returns:
            Tuple of (correlation_coefficient, p_value)

        Raises:
            InsufficientDataError: If arrays are empty or too small
        """
        if len(long_short_ratios) == 0 or len(funding_rates) == 0:
            raise InsufficientDataError("Cannot calculate correlation with empty arrays")

        if len(long_short_ratios) < 3 or len(funding_rates) < 3:
            raise InsufficientDataError("Need at least 3 data points for correlation")

        if len(long_short_ratios) != len(funding_rates):
            raise ValueError("Arrays must be same length")

        # Calculate Pearson correlation
        correlation, p_value = stats.pearsonr(long_short_ratios, funding_rates)

        logger.debug(
            f"Calculated correlation: {correlation:.4f}, p-value: {p_value:.6f} "
            f"(n={len(long_short_ratios)})"
        )

        return correlation, p_value

    def score_from_correlation(self, correlation: Decimal, p_value: Decimal) -> dict:
        """
        Calculate test score from correlation coefficient.

        Args:
            correlation: Correlation coefficient (-1 to 1)
            p_value: Statistical significance p-value

        Returns:
            Dict with passed, score, diagnostics
        """
        # Check statistical significance first
        if p_value >= FUNDING_CORRELATION_P_VALUE_MAX:
            # Not statistically significant - fail regardless of correlation
            return {
                "passed": False,
                "score": Decimal("0.0"),
                "diagnostics": {
                    "correlation": float(correlation),
                    "p_value": float(p_value),
                    "reason": "Not statistically significant (p >= 0.05)",
                },
            }

        # Convert correlation to absolute value for scoring
        # (negative correlation still indicates relationship)
        abs_correlation = abs(correlation)

        # Score scales from correlation:
        # 1.0 -> 100 points
        # 0.7 -> 70 points (threshold)
        # 0.0 -> 0 points
        score = Decimal(str(abs_correlation)) * Decimal("100")

        # Test passes if correlation >= threshold AND statistically significant
        passed = abs_correlation >= float(FUNDING_CORRELATION_MIN_ACCEPTABLE)

        diagnostics = {
            "correlation": float(correlation),
            "abs_correlation": float(abs_correlation),
            "p_value": float(p_value),
            "threshold": float(FUNDING_CORRELATION_MIN_ACCEPTABLE),
        }

        return {"passed": passed, "score": score, "diagnostics": diagnostics}

    def execute(
        self,
        long_short_ratios: Optional[np.ndarray] = None,
        funding_rates: Optional[np.ndarray] = None,
    ) -> ValidationTest:
        """
        Execute funding correlation test.

        Args:
            long_short_ratios: Estimated ratios (optional, will fetch if None)
            funding_rates: Funding rates (optional, will fetch if None)

        Returns:
            ValidationTest result object
        """
        executed_at = datetime.utcnow()
        start_time = datetime.utcnow()

        try:
            # If data not provided, would fetch from data_fetcher here
            # For now, require data to be passed in
            if long_short_ratios is None or funding_rates is None:
                raise InsufficientDataError("Data must be provided for this test")

            # Calculate correlation
            correlation, p_value = self.calculate_correlation(long_short_ratios, funding_rates)

            # Score the result
            result = self.score_from_correlation(Decimal(str(correlation)), Decimal(str(p_value)))

            # Calculate duration
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Create ValidationTest result
            test_result = ValidationTest(
                test_id=self.test_id,
                run_id=self.run_id,
                test_type=self.test_type,
                test_name="Funding Rate Correlation Test",
                passed=result["passed"],
                score=result["score"],
                weight=self.weight,
                primary_metric=Decimal(str(correlation)),
                secondary_metric=Decimal(str(p_value)),
                diagnostics=result["diagnostics"],
                executed_at=executed_at,
                duration_ms=duration_ms,
            )

            logger.info(
                f"Funding correlation test completed: "
                f"correlation={correlation:.4f}, passed={result['passed']}, "
                f"score={result['score']:.1f}"
            )

            return test_result

        except Exception as e:
            # Calculate duration even on error
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Create failed test result
            test_result = ValidationTest(
                test_id=self.test_id,
                run_id=self.run_id,
                test_type=self.test_type,
                test_name="Funding Rate Correlation Test",
                passed=False,
                score=Decimal("0.0"),
                weight=self.weight,
                error_message=str(e),
                executed_at=executed_at,
                duration_ms=duration_ms,
            )

            logger.error(f"Funding correlation test failed: {e}")

            return test_result
