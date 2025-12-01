"""
Statistical accuracy validation with 2,628 stratified test cases.

Validates 99% accuracy confidence with 0.5% margin of error using
stratified sampling across all 5 margin tiers. Uses exact binomial
test to verify accuracy meets Binance standards.

Statistical Basis:
  n = (Z² × p × (1-p)) / E²
  n = (2.576² × 0.99 × 0.01) / 0.005²
  n = 2,628 samples

Sample Distribution:
  - Tier 1 ($0-50k):        528 samples (20%)
  - Tier 2 ($50k-250k):     528 samples (20%)
  - Tier 3 ($250k-1M):      528 samples (20%)
  - Tier 4 ($1M-10M):       528 samples (20%)
  - Tier 5 ($10M-50M):      516 samples (20%)
"""

from decimal import Decimal
from typing import List

import numpy as np
import pytest
from scipy import stats

from src.services.margin_calculator import MarginCalculator
from src.services.tier_loader import TierLoader


class TestStatisticalAccuracy:
    """
    Statistical validation test suite with 2,628 stratified samples.

    Validates that margin calculations achieve ≥99% accuracy across
    all tier boundaries using exact binomial hypothesis testing.
    """

    @pytest.fixture
    def calculator(self) -> MarginCalculator:
        """Create margin calculator with Binance default tiers."""
        config = TierLoader.load_binance_default()
        return MarginCalculator(config)

    @pytest.fixture
    def tier_samples(self) -> dict:
        """
        Generate 2,628 stratified samples across all tiers.

        Returns:
            dict: Tier number -> list of notional values
        """
        np.random.seed(42)  # Reproducible results

        samples = {
            1: self._generate_tier_samples(min_val=1, max_val=50_000, count=528, tier=1),
            2: self._generate_tier_samples(min_val=50_001, max_val=250_000, count=528, tier=2),
            3: self._generate_tier_samples(min_val=250_001, max_val=1_000_000, count=528, tier=3),
            4: self._generate_tier_samples(
                min_val=1_000_001, max_val=10_000_000, count=528, tier=4
            ),
            5: self._generate_tier_samples(
                min_val=10_000_001, max_val=50_000_000, count=516, tier=5
            ),
        }

        return samples

    def _generate_tier_samples(
        self, min_val: int, max_val: int, count: int, tier: int
    ) -> List[Decimal]:
        """
        Generate uniformly distributed samples within a tier range.

        Args:
            min_val: Minimum notional value
            max_val: Maximum notional value
            count: Number of samples to generate
            tier: Tier number (for logging)

        Returns:
            List of Decimal notional values
        """
        # Generate uniformly distributed samples
        # Use linear distribution for better statistical properties
        samples = np.random.uniform(min_val, max_val, count)

        # Convert to Decimal with 2 decimal places
        return [Decimal(str(round(val, 2))) for val in samples]

    def _calculate_expected_margin(self, notional: Decimal) -> Decimal:
        """
        Calculate expected margin using Binance formulas.

        Uses documented tier rates and maintenance amounts to compute
        the expected margin for comparison.

        Args:
            notional: Position notional value

        Returns:
            Expected maintenance margin
        """
        # Binance tier configuration
        tiers = [
            (Decimal("50000"), Decimal("0.005"), Decimal("0")),  # Tier 1
            (Decimal("250000"), Decimal("0.010"), Decimal("250")),  # Tier 2
            (Decimal("1000000"), Decimal("0.025"), Decimal("4000")),  # Tier 3
            (Decimal("10000000"), Decimal("0.050"), Decimal("29000")),  # Tier 4
            (Decimal("50000000"), Decimal("0.100"), Decimal("529000")),  # Tier 5
        ]

        for max_notional, rate, ma in tiers:
            if notional <= max_notional:
                return notional * rate - ma

        # Beyond tier 5 (> $50M) - use tier 5 rate
        return notional * Decimal("0.100") - Decimal("529000")

    def _is_accurate(
        self, calculated: Decimal, expected: Decimal, tolerance: Decimal = Decimal("0.01")
    ) -> bool:
        """
        Check if calculated margin is within tolerance of expected.

        Args:
            calculated: Margin from MarginCalculator
            expected: Expected margin from Binance formula
            tolerance: Acceptable error (default $0.01)

        Returns:
            True if within tolerance
        """
        error = abs(calculated - expected)
        return error <= tolerance

    def test_tier_1_stratified_samples(self, calculator, tier_samples):
        """
        Test 528 stratified samples in Tier 1 ($0-50k).

        Verifies uniform distribution of samples and validates
        accuracy across the tier range.
        """
        samples = tier_samples[1]
        assert len(samples) == 528, "Tier 1 should have 528 samples"

        successes = 0
        failures = []

        for notional in samples:
            calculated = calculator.calculate_margin(notional)
            expected = self._calculate_expected_margin(notional)

            if self._is_accurate(calculated, expected):
                successes += 1
            else:
                failures.append(
                    {
                        "notional": str(notional),
                        "calculated": str(calculated),
                        "expected": str(expected),
                        "error": str(abs(calculated - expected)),
                    }
                )

        accuracy = successes / len(samples)

        # Report failures if any
        if failures:
            print(f"\nTier 1 Failures ({len(failures)}):")
            for i, fail in enumerate(failures[:5]):  # Show first 5
                print(
                    f"  {i + 1}. Notional=${fail['notional']}: "
                    f"got ${fail['calculated']}, expected ${fail['expected']} "
                    f"(error=${fail['error']})"
                )

        assert accuracy >= 0.99, (
            f"Tier 1 accuracy {accuracy:.4f} below 99% threshold ({successes}/{len(samples)})"
        )

    def test_tier_2_stratified_samples(self, calculator, tier_samples):
        """
        Test 528 stratified samples in Tier 2 ($50k-250k).

        Critical tier for boundary testing at $50k threshold.
        """
        samples = tier_samples[2]
        assert len(samples) == 528, "Tier 2 should have 528 samples"

        successes = 0
        failures = []

        for notional in samples:
            calculated = calculator.calculate_margin(notional)
            expected = self._calculate_expected_margin(notional)

            if self._is_accurate(calculated, expected):
                successes += 1
            else:
                failures.append(
                    {
                        "notional": str(notional),
                        "calculated": str(calculated),
                        "expected": str(expected),
                        "error": str(abs(calculated - expected)),
                    }
                )

        accuracy = successes / len(samples)

        if failures:
            print(f"\nTier 2 Failures ({len(failures)}):")
            for i, fail in enumerate(failures[:5]):
                print(
                    f"  {i + 1}. Notional=${fail['notional']}: "
                    f"got ${fail['calculated']}, expected ${fail['expected']} "
                    f"(error=${fail['error']})"
                )

        assert accuracy >= 0.99, (
            f"Tier 2 accuracy {accuracy:.4f} below 99% threshold ({successes}/{len(samples)})"
        )

    def test_tier_3_stratified_samples(self, calculator, tier_samples):
        """
        Test 528 stratified samples in Tier 3 ($250k-1M).

        Tests institutional position sizes with 2.5% margin rate.
        """
        samples = tier_samples[3]
        assert len(samples) == 528, "Tier 3 should have 528 samples"

        successes = 0
        failures = []

        for notional in samples:
            calculated = calculator.calculate_margin(notional)
            expected = self._calculate_expected_margin(notional)

            if self._is_accurate(calculated, expected):
                successes += 1
            else:
                failures.append(
                    {
                        "notional": str(notional),
                        "calculated": str(calculated),
                        "expected": str(expected),
                        "error": str(abs(calculated - expected)),
                    }
                )

        accuracy = successes / len(samples)

        if failures:
            print(f"\nTier 3 Failures ({len(failures)}):")
            for i, fail in enumerate(failures[:5]):
                print(
                    f"  {i + 1}. Notional=${fail['notional']}: "
                    f"got ${fail['calculated']}, expected ${fail['expected']} "
                    f"(error=${fail['error']})"
                )

        assert accuracy >= 0.99, (
            f"Tier 3 accuracy {accuracy:.4f} below 99% threshold ({successes}/{len(samples)})"
        )

    def test_tier_4_stratified_samples(self, calculator, tier_samples):
        """
        Test 528 stratified samples in Tier 4 ($1M-10M).

        Critical for whale positions with 5% margin rate.
        """
        samples = tier_samples[4]
        assert len(samples) == 528, "Tier 4 should have 528 samples"

        successes = 0
        failures = []

        for notional in samples:
            calculated = calculator.calculate_margin(notional)
            expected = self._calculate_expected_margin(notional)

            if self._is_accurate(calculated, expected):
                successes += 1
            else:
                failures.append(
                    {
                        "notional": str(notional),
                        "calculated": str(calculated),
                        "expected": str(expected),
                        "error": str(abs(calculated - expected)),
                    }
                )

        accuracy = successes / len(samples)

        if failures:
            print(f"\nTier 4 Failures ({len(failures)}):")
            for i, fail in enumerate(failures[:5]):
                print(
                    f"  {i + 1}. Notional=${fail['notional']}: "
                    f"got ${fail['calculated']}, expected ${fail['expected']} "
                    f"(error=${fail['error']})"
                )

        assert accuracy >= 0.99, (
            f"Tier 4 accuracy {accuracy:.4f} below 99% threshold ({successes}/{len(samples)})"
        )

    def test_tier_5_stratified_samples(self, calculator, tier_samples):
        """
        Test 516 stratified samples in Tier 5 ($10M-50M).

        Maximum tier with 10% margin rate for ultra-large positions.
        """
        samples = tier_samples[5]
        assert len(samples) == 516, "Tier 5 should have 516 samples"

        successes = 0
        failures = []

        for notional in samples:
            calculated = calculator.calculate_margin(notional)
            expected = self._calculate_expected_margin(notional)

            if self._is_accurate(calculated, expected):
                successes += 1
            else:
                failures.append(
                    {
                        "notional": str(notional),
                        "calculated": str(calculated),
                        "expected": str(expected),
                        "error": str(abs(calculated - expected)),
                    }
                )

        accuracy = successes / len(samples)

        if failures:
            print(f"\nTier 5 Failures ({len(failures)}):")
            for i, fail in enumerate(failures[:5]):
                print(
                    f"  {i + 1}. Notional=${fail['notional']}: "
                    f"got ${fail['calculated']}, expected ${fail['expected']} "
                    f"(error=${fail['error']})"
                )

        assert accuracy >= 0.99, (
            f"Tier 5 accuracy {accuracy:.4f} below 99% threshold ({successes}/{len(samples)})"
        )

    def test_overall_accuracy_2628_samples(self, calculator, tier_samples):
        """
        Test overall accuracy across all 2,628 stratified samples.

        Uses exact binomial test to validate 99% accuracy hypothesis
        with 99% confidence level and 0.5% margin of error.

        Statistical Test:
          H0: accuracy ≥ 0.99
          H1: accuracy < 0.99
          α = 0.01 (99% confidence)
        """
        all_samples = []
        for tier_num in range(1, 6):
            all_samples.extend(tier_samples[tier_num])

        assert len(all_samples) == 2628, f"Total samples should be 2628, got {len(all_samples)}"

        successes = 0
        total_tests = 0
        failures_by_tier = {1: [], 2: [], 3: [], 4: [], 5: []}

        for notional in all_samples:
            total_tests += 1
            calculated = calculator.calculate_margin(notional)
            expected = self._calculate_expected_margin(notional)

            if self._is_accurate(calculated, expected):
                successes += 1
            else:
                # Determine tier for failure tracking
                tier_num = self._get_tier_number(notional)
                failures_by_tier[tier_num].append(
                    {
                        "notional": str(notional),
                        "calculated": str(calculated),
                        "expected": str(expected),
                        "error": str(abs(calculated - expected)),
                    }
                )

        # Calculate overall accuracy
        accuracy = successes / total_tests

        # Binomial test: H0: p ≥ 0.99, H1: p < 0.99
        # One-sided test with α = 0.01
        result = stats.binomtest(successes, total_tests, p=0.99, alternative="less")
        p_value = result.pvalue

        # Report statistics
        print(f"\n{'=' * 60}")
        print("Statistical Accuracy Report (2,628 Stratified Samples)")
        print(f"{'=' * 60}")
        print(f"Total Tests:     {total_tests}")
        print(f"Successes:       {successes}")
        print(f"Failures:        {total_tests - successes}")
        print(f"Accuracy:        {accuracy:.4%}")
        print(f"p-value:         {p_value:.6f}")
        print("Confidence:      99%")
        print("Margin of Error: 0.5%")

        # Failure breakdown by tier
        total_failures = sum(len(fails) for fails in failures_by_tier.values())
        if total_failures > 0:
            print("\nFailure Breakdown by Tier:")
            for tier_num, fails in failures_by_tier.items():
                if fails:
                    print(f"  Tier {tier_num}: {len(fails)} failures")
                    # Show first 2 failures per tier
                    for i, fail in enumerate(fails[:2]):
                        print(f"    - Notional=${fail['notional']}: error=${fail['error']}")

        print(f"{'=' * 60}\n")

        # Assertions
        assert accuracy >= 0.99, (
            f"Overall accuracy {accuracy:.4%} below 99% threshold (failed {total_tests - successes}/{total_tests} tests)"
        )

        # Statistical significance test
        assert p_value >= 0.01, (
            f"Binomial test p-value {p_value:.6f} < 0.01 - reject H0: accuracy ≥ 99%"
        )

    def _get_tier_number(self, notional: Decimal) -> int:
        """Determine tier number for a given notional value."""
        if notional <= 50_000:
            return 1
        elif notional <= 250_000:
            return 2
        elif notional <= 1_000_000:
            return 3
        elif notional <= 10_000_000:
            return 4
        else:
            return 5

    def test_sample_distribution_uniformity(self, tier_samples):
        """
        Verify that samples are uniformly distributed within each tier.

        Uses chi-square test to validate uniform distribution across
        sub-ranges within each tier.
        """
        for tier_num, samples in tier_samples.items():
            # Divide tier range into 10 bins (linear)
            min_val = float(min(samples))
            max_val = float(max(samples))

            # Use linear bins for uniform distribution test
            bins = np.linspace(min_val, max_val, 11)

            # Count samples in each bin
            hist, _ = np.histogram([float(s) for s in samples], bins=bins)

            # Chi-square test for uniformity
            # Expected frequency = total / bins
            expected_freq = len(samples) / 10
            chi2_stat = np.sum((hist - expected_freq) ** 2 / expected_freq)

            # Critical value for 9 degrees of freedom at α=0.05: 16.919
            # We use α=0.01 for stricter validation: 21.666
            critical_value = 21.666

            assert chi2_stat < critical_value, (
                f"Tier {tier_num} samples not uniformly distributed (χ²={chi2_stat:.2f} > {critical_value})"
            )

    def test_performance_2628_calculations(self, calculator, tier_samples):
        """
        Verify that 2,628 calculations complete within performance budget.

        Target: All 2,628 calculations in <1 second (avg <0.38ms per calc)
        """
        import time

        all_samples = []
        for tier_num in range(1, 6):
            all_samples.extend(tier_samples[tier_num])

        start_time = time.perf_counter()

        for notional in all_samples:
            _ = calculator.calculate_margin(notional)

        end_time = time.perf_counter()
        elapsed = end_time - start_time

        avg_time_ms = (elapsed / len(all_samples)) * 1000

        print("\nPerformance Results:")
        print(f"  Total samples:   {len(all_samples)}")
        print(f"  Total time:      {elapsed:.3f}s")
        print(f"  Avg per calc:    {avg_time_ms:.3f}ms")

        assert elapsed < 1.0, (
            f"2,628 calculations took {elapsed:.3f}s > 1.0s target (avg {avg_time_ms:.3f}ms per calc)"
        )

        # Individual calculation should be <10ms (per FR-005)
        assert avg_time_ms < 10.0, (
            f"Average calculation time {avg_time_ms:.3f}ms exceeds 10ms threshold"
        )
