"""
TDD RED: Tests for funding rate correlation validation test.

Tests that estimated long/short ratios correlate with funding rates.
"""

from decimal import Decimal

import numpy as np
import pytest

from src.validation.tests.funding_correlation import FundingCorrelationTest


class TestFundingCorrelation:
    """Test suite for funding rate correlation validation."""

    @pytest.fixture
    def test_instance(self):
        """Create test instance."""
        return FundingCorrelationTest(run_id="test-run-001")

    def test_funding_correlation_initialization(self, test_instance):
        """
        Test FundingCorrelationTest initialization.

        GIVEN no parameters
        WHEN creating FundingCorrelationTest
        THEN instance should be created with correct defaults
        """
        assert test_instance.run_id == "test-run-001"
        assert test_instance.test_type == "funding_correlation"
        assert test_instance.weight == Decimal("0.40")

    def test_calculate_correlation_with_perfect_correlation(self, test_instance):
        """
        Test correlation calculation with perfect positive correlation.

        GIVEN perfectly correlated data
        WHEN calculating Pearson correlation
        THEN should return correlation ~1.0 and p-value ~0.0
        """
        # Perfect positive correlation
        long_short_ratios = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        funding_rates = np.array([0.01, 0.02, 0.03, 0.04, 0.05])

        correlation, p_value = test_instance.calculate_correlation(long_short_ratios, funding_rates)

        assert correlation > 0.99  # Near perfect correlation
        assert p_value < 0.05  # Statistically significant

    def test_calculate_correlation_with_negative_correlation(self, test_instance):
        """
        Test correlation calculation with negative correlation.

        GIVEN negatively correlated data
        WHEN calculating correlation
        THEN should return negative correlation coefficient
        """
        # Negative correlation
        long_short_ratios = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        funding_rates = np.array([0.05, 0.04, 0.03, 0.02, 0.01])

        correlation, p_value = test_instance.calculate_correlation(long_short_ratios, funding_rates)

        assert correlation < -0.99  # Strong negative correlation
        assert p_value < 0.05

    def test_execute_with_sufficient_correlation(self, test_instance):
        """
        Test test execution with good correlation.

        GIVEN correlation above threshold (>0.70)
        WHEN executing test
        THEN test should pass with appropriate score
        """
        # Mock data fetcher would return data here
        # For now, test the scoring logic directly

        # Simulate correlation of 0.85 (good)
        result = test_instance.score_from_correlation(
            correlation=Decimal("0.85"), p_value=Decimal("0.001")
        )

        assert result["passed"] is True
        assert result["score"] > Decimal("80.0")  # Good correlation = high score

    def test_execute_with_insufficient_correlation(self, test_instance):
        """
        Test test execution with poor correlation.

        GIVEN correlation below threshold (<0.70)
        WHEN executing test
        THEN test should fail with low score
        """
        # Simulate correlation of 0.50 (poor)
        result = test_instance.score_from_correlation(
            correlation=Decimal("0.50"), p_value=Decimal("0.05")
        )

        assert result["passed"] is False
        assert result["score"] < Decimal("70.0")  # Poor correlation = low score

    def test_execute_with_statistically_insignificant_result(self, test_instance):
        """
        Test execution with high p-value (not statistically significant).

        GIVEN p-value >= 0.05
        WHEN executing test
        THEN test should fail or score heavily penalized
        """
        # High correlation but not statistically significant
        result = test_instance.score_from_correlation(
            correlation=Decimal("0.80"),
            p_value=Decimal("0.10"),  # Not significant
        )

        assert result["passed"] is False  # Fails due to p-value
        assert "p_value" in result["diagnostics"]

    def test_insufficient_data_handling(self, test_instance):
        """
        Test handling of insufficient data.

        GIVEN less than minimum required data points
        WHEN executing test
        THEN should raise InsufficientDataError
        """
        from src.validation.exceptions import InsufficientDataError

        # Empty arrays
        long_short_ratios = np.array([])
        funding_rates = np.array([])

        with pytest.raises(InsufficientDataError):
            test_instance.calculate_correlation(long_short_ratios, funding_rates)

    def test_score_calculation_scales_correctly(self, test_instance):
        """
        Test that score scales linearly from correlation.

        GIVEN various correlation values
        WHEN calculating scores
        THEN scores should scale appropriately
        """
        # Test multiple correlation values
        test_cases = [
            (Decimal("1.00"), Decimal("0.001"), 100),  # Perfect -> 100
            (Decimal("0.90"), Decimal("0.01"), 90),  # 0.9 -> ~90
            (Decimal("0.70"), Decimal("0.02"), 70),  # Threshold -> ~70
            (Decimal("0.50"), Decimal("0.03"), 50),  # Below threshold -> ~50
        ]

        for correlation, p_value, expected_score in test_cases:
            result = test_instance.score_from_correlation(correlation, p_value)
            # Allow ±10 points tolerance
            assert abs(result["score"] - expected_score) <= 10
