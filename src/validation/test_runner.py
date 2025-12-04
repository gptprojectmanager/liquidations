"""
Test runner and aggregator for validation suite.

Executes all validation tests and aggregates results.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

from src.models.validation_run import TriggerType, ValidationRun, ValidationStatus
from src.models.validation_test import ValidationTest
from src.validation.logger import logger
from src.validation.tests.directional_test import DirectionalTest
from src.validation.tests.funding_correlation import FundingCorrelationTest
from src.validation.tests.oi_conservation import OIConservationTest


class ValidationTestRunner:
    """
    Orchestrates execution of all validation tests.

    Runs funding correlation, OI conservation, and directional tests,
    aggregating results into overall score and grade.
    """

    def __init__(self, model_name: str, trigger_type: str = "manual", triggered_by: str = "system"):
        """
        Initialize test runner.

        Args:
            model_name: Name of model being validated
            trigger_type: 'manual' or 'scheduled'
            triggered_by: User ID or 'system'
        """
        self.model_name = model_name
        self.trigger_type = trigger_type
        self.triggered_by = triggered_by
        self.run_id = str(uuid.uuid4())

    def calculate_overall_score(self, tests: List[ValidationTest]) -> Decimal:
        """
        Calculate weighted overall score from individual tests.

        Args:
            tests: List of completed ValidationTest results

        Returns:
            Overall score (0-100)
        """
        if not tests:
            return Decimal("0.0")

        total_score = Decimal("0.0")

        for test in tests:
            # Weighted contribution = score * weight
            contribution = test.weighted_contribution()
            total_score += contribution

            logger.debug(
                f"Test {test.test_type}: score={test.score:.1f}, "
                f"weight={test.weight:.2f}, contribution={contribution:.1f}"
            )

        logger.info(f"Overall score calculated: {total_score:.2f}")
        return total_score

    def assign_grade(self, score: Decimal) -> str:
        """
        Assign letter grade based on score.

        Args:
            score: Overall score (0-100)

        Returns:
            Grade: 'A', 'B', 'C', or 'F'
        """
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        else:
            return "F"

    def run_all_tests(
        self,
        funding_data: dict = None,
        oi_data: dict = None,
        directional_data: dict = None,
    ) -> tuple[ValidationRun, List[ValidationTest]]:
        """
        Execute all validation tests.

        Args:
            funding_data: Dict with 'long_short_ratios' and 'funding_rates'
            oi_data: Dict with 'estimated_positions' and 'actual_oi'
            directional_data: Dict with 'long_liq_prices', 'short_liq_prices', 'current_prices'

        Returns:
            Tuple of (ValidationRun, List[ValidationTest])
        """
        started_at = datetime.utcnow()
        logger.info(f"Starting validation run: {self.run_id} for model {self.model_name}")

        # Create validation run
        data_end_date = datetime.utcnow().date()
        data_start_date = data_end_date - timedelta(days=30)

        run = ValidationRun(
            run_id=self.run_id,
            model_name=self.model_name,
            trigger_type=TriggerType(self.trigger_type),
            triggered_by=self.triggered_by,
            started_at=started_at,
            data_start_date=data_start_date,
            data_end_date=data_end_date,
            status=ValidationStatus.RUNNING,
        )

        tests: List[ValidationTest] = []

        try:
            # Execute Test 1: Funding Correlation
            logger.info("Executing funding correlation test...")
            funding_test = FundingCorrelationTest(self.run_id)
            if funding_data:
                test_result = funding_test.execute(
                    long_short_ratios=funding_data.get("long_short_ratios"),
                    funding_rates=funding_data.get("funding_rates"),
                )
                tests.append(test_result)

            # Execute Test 2: OI Conservation
            logger.info("Executing OI conservation test...")
            oi_test = OIConservationTest(self.run_id)
            if oi_data:
                test_result = oi_test.execute(
                    estimated_positions=oi_data.get("estimated_positions"),
                    actual_oi=oi_data.get("actual_oi"),
                )
                tests.append(test_result)

            # Execute Test 3: Directional Positioning
            logger.info("Executing directional positioning test...")
            directional_test = DirectionalTest(self.run_id)
            if directional_data:
                test_result = directional_test.execute(
                    long_liq_prices=directional_data.get("long_liq_prices"),
                    short_liq_prices=directional_data.get("short_liq_prices"),
                    current_prices=directional_data.get("current_prices"),
                )
                tests.append(test_result)

            # Calculate overall score
            overall_score = self.calculate_overall_score(tests)
            overall_grade = self.assign_grade(overall_score)

            # Update run with results
            completed_at = datetime.utcnow()
            duration_seconds = int((completed_at - started_at).total_seconds())

            run.completed_at = completed_at
            run.duration_seconds = duration_seconds
            run.overall_score = overall_score
            run.overall_grade = overall_grade
            run.status = ValidationStatus.COMPLETED
            run.data_completeness = Decimal("100.0")  # Placeholder

            logger.info(
                f"Validation run completed: grade={overall_grade}, "
                f"score={overall_score:.2f}, duration={duration_seconds}s"
            )

            return run, tests

        except Exception as e:
            logger.error(f"Validation run failed: {e}", exc_info=True)

            # Mark run as failed
            run.status = ValidationStatus.FAILED
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()

            return run, tests
