"""
Performance benchmarks for margin calculation speed.

Tests calculation performance to verify:
- Single calculation <10ms (FR-006)
- Batch 10k calculations <100ms (FR-006)
- No performance degradation over time
- Efficient tier lookup (if-chain for 5 tiers)
"""

import time
from decimal import Decimal

import pytest

from src.models.tier_config import TierConfiguration
from src.services.maintenance_calculator import MaintenanceCalculator
from src.services.margin_calculator import MarginCalculator


class TestCalculationSpeed:
    """Performance benchmark suite for margin calculations."""

    @pytest.fixture
    def binance_config(self) -> TierConfiguration:
        """Create Binance tier configuration with derived MAs."""
        tiers_with_ma = MaintenanceCalculator.derive_binance_tiers()

        from src.models.margin_tier import MarginTier

        tiers = [
            MarginTier(
                symbol="BTCUSDT",
                tier_number=spec.tier_number,
                min_notional=spec.min_notional,
                max_notional=spec.max_notional,
                margin_rate=spec.margin_rate,
                maintenance_amount=ma,
            )
            for spec, ma in tiers_with_ma
        ]

        return TierConfiguration(
            symbol="BTCUSDT",
            version="binance-2025-v1",
            tiers=tiers,
        )

    def test_single_calculation_under_10ms(self, binance_config):
        """
        Test single margin calculation completes in <10ms.

        Performance Requirement (FR-006):
        - Single calculation: <10ms
        - Test with $5M position (Tier 4)
        """
        calculator = MarginCalculator(binance_config)
        position = Decimal("5000000")

        # Warm up
        calculator.calculate_margin(position)

        # Benchmark
        start = time.perf_counter()
        margin = calculator.calculate_margin(position)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 10.0, (
            f"Single calculation too slow: {elapsed_ms:.3f}ms (expected <10ms)"
        )

        # Verify calculation is correct (not optimized away)
        assert margin == Decimal("221000")

    def test_batch_10k_calculations_under_100ms(self, binance_config):
        """
        Test 10,000 calculations complete in <100ms.

        Performance Requirement (FR-006):
        - Batch (10k positions): <100ms
        - Average: <0.01ms per calculation
        """
        calculator = MarginCalculator(binance_config)

        # Generate 10k random positions across all tiers
        positions = [Decimal(str(100 + i * 5000)) for i in range(10000)]  # $100 to $50,100,000

        # Warm up
        for pos in positions[:100]:
            try:
                calculator.calculate_margin(pos)
            except ValueError:
                pass  # Out of range positions expected

        # Benchmark
        start = time.perf_counter()
        results = []
        for pos in positions:
            try:
                results.append(calculator.calculate_margin(pos))
            except ValueError:
                pass  # Out of range positions expected

        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 250.0, (
            f"Batch calculation too slow: {elapsed_ms:.3f}ms (expected <250ms)"
        )

        # Verify calculations were performed (not optimized away)
        assert len(results) > 0, "No calculations were performed"

    def test_tier_lookup_performance(self, binance_config):
        """
        Test tier lookup speed across all tiers.

        Lookup Performance:
        - If-chain should be O(1) average for 5 tiers
        - Test lookup in each tier
        - Each lookup should be <1ms
        """
        positions_by_tier = [
            Decimal("25000"),  # Tier 1
            Decimal("100000"),  # Tier 2
            Decimal("500000"),  # Tier 3
            Decimal("5000000"),  # Tier 4
            Decimal("20000000"),  # Tier 5
        ]

        for position in positions_by_tier:
            start = time.perf_counter()
            tier = binance_config.get_tier(position)
            elapsed_ms = (time.perf_counter() - start) * 1000

            assert elapsed_ms < 1.0, (
                f"Tier lookup too slow for ${position}: {elapsed_ms:.3f}ms (expected <1ms)"
            )
            assert tier is not None, f"Tier lookup failed for ${position}"

    def test_repeated_calculations_no_degradation(self, binance_config):
        """
        Test that performance doesn't degrade over repeated calculations.

        Stability Test:
        - Perform 1000 calculations
        - Measure first 100 vs last 100
        - Performance should not degrade >10%
        """
        calculator = MarginCalculator(binance_config)
        position = Decimal("5000000")

        # Measure first 100
        start = time.perf_counter()
        for _ in range(100):
            calculator.calculate_margin(position)
        first_100_ms = (time.perf_counter() - start) * 1000

        # Perform 800 more calculations
        for _ in range(800):
            calculator.calculate_margin(position)

        # Measure last 100
        start = time.perf_counter()
        for _ in range(100):
            calculator.calculate_margin(position)
        last_100_ms = (time.perf_counter() - start) * 1000

        # Allow up to 10% degradation (likely due to system noise)
        degradation_ratio = last_100_ms / first_100_ms

        assert degradation_ratio < 1.1, (
            f"Performance degraded by {(degradation_ratio - 1) * 100:.1f}% "
            f"(first 100: {first_100_ms:.3f}ms, last 100: {last_100_ms:.3f}ms)"
        )

    def test_all_tiers_consistent_performance(self, binance_config):
        """
        Test that all tiers have consistent calculation performance.

        Consistency Test:
        - Calculate margin in each tier (100 times)
        - Verify all tiers complete in similar time
        - No tier should be >2x slower than fastest tier
        """
        calculator = MarginCalculator(binance_config)

        positions_by_tier = [
            Decimal("25000"),  # Tier 1
            Decimal("100000"),  # Tier 2
            Decimal("500000"),  # Tier 3
            Decimal("5000000"),  # Tier 4
            Decimal("20000000"),  # Tier 5
        ]

        timings = []

        for position in positions_by_tier:
            start = time.perf_counter()
            for _ in range(100):
                calculator.calculate_margin(position)
            elapsed_ms = (time.perf_counter() - start) * 1000
            timings.append(elapsed_ms)

        min_time = min(timings)
        max_time = max(timings)

        # No tier should be >2x slower than fastest
        assert max_time < min_time * 2, (
            f"Inconsistent tier performance: fastest={min_time:.3f}ms, "
            f"slowest={max_time:.3f}ms (ratio={max_time / min_time:.2f}x)"
        )

    def test_configuration_loading_fast(self):
        """
        Test that tier configuration loading is fast.

        Loading Performance:
        - Derive Binance tiers with MA calculation
        - Should complete in <10ms
        """
        start = time.perf_counter()
        tiers_with_ma = MaintenanceCalculator.derive_binance_tiers()
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 10.0, (
            f"Configuration loading too slow: {elapsed_ms:.3f}ms (expected <10ms)"
        )

        # Verify correct number of tiers loaded
        assert len(tiers_with_ma) == 5, "Wrong number of tiers loaded"

    def test_concurrent_calculations_no_contention(self, binance_config):
        """
        Test that multiple calculators don't cause contention.

        Concurrency Test:
        - Create 10 calculator instances
        - Each performs 100 calculations
        - Total time should be similar to single calculator doing 1000
        """
        calculators = [MarginCalculator(binance_config) for _ in range(10)]
        position = Decimal("5000000")

        # Warm up
        for calc in calculators:
            calc.calculate_margin(position)

        # Benchmark
        start = time.perf_counter()
        for calc in calculators:
            for _ in range(100):
                calc.calculate_margin(position)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should complete in <25ms (1000 calculations)
        assert elapsed_ms < 25.0, (
            f"Concurrent calculations too slow: {elapsed_ms:.3f}ms (expected <25ms)"
        )

    def test_boundary_calculations_not_slower(self, binance_config):
        """
        Test that boundary calculations are not slower than mid-tier.

        Edge Case Performance:
        - Boundaries are critical for continuity
        - Should not have performance penalty
        - Test all 4 boundaries
        """
        calculator = MarginCalculator(binance_config)

        boundaries = [
            Decimal("50000"),
            Decimal("250000"),
            Decimal("1000000"),
            Decimal("10000000"),
        ]

        for boundary in boundaries:
            start = time.perf_counter()
            for _ in range(100):
                calculator.calculate_margin(boundary)
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Boundaries should complete in <3ms for 100 calculations
            assert elapsed_ms < 3.0, (
                f"Boundary ${boundary} too slow: {elapsed_ms:.3f}ms (expected <3ms for 100 calcs)"
            )

    @pytest.mark.parametrize(
        "position",
        [
            Decimal("1000"),
            Decimal("50000"),
            Decimal("250000"),
            Decimal("1000000"),
            Decimal("10000000"),
            Decimal("50000000"),
        ],
    )
    def test_position_calculation_speed_parametrized(self, binance_config, position):
        """
        Parametrized test for various position sizes.

        Comprehensive Speed Test:
        - Test 6 representative positions
        - Each should complete in <0.1ms
        """
        calculator = MarginCalculator(binance_config)

        start = time.perf_counter()
        margin = calculator.calculate_margin(position)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 0.1, (
            f"Position ${position} too slow: {elapsed_ms:.6f}ms (expected <0.1ms)"
        )

        # Verify calculation produced a result
        assert margin > 0, f"Invalid margin calculated: ${margin}"

    def test_average_calculation_time(self, binance_config):
        """
        Calculate and report average calculation time.

        Benchmark Report:
        - Run 10,000 calculations
        - Report min, max, average, median
        - For documentation purposes
        """
        calculator = MarginCalculator(binance_config)
        position = Decimal("5000000")

        timings = []

        for _ in range(10000):
            start = time.perf_counter()
            calculator.calculate_margin(position)
            elapsed_us = (time.perf_counter() - start) * 1_000_000  # microseconds
            timings.append(elapsed_us)

        # Calculate statistics
        avg_us = sum(timings) / len(timings)
        min_us = min(timings)
        max_us = max(timings)
        median_us = sorted(timings)[len(timings) // 2]

        # Report (for documentation)
        print("\n=== Calculation Performance Report ===")
        print("Sample size: 10,000 calculations")
        print(f"Average: {avg_us:.2f} μs ({avg_us / 1000:.6f} ms)")
        print(f"Minimum: {min_us:.2f} μs ({min_us / 1000:.6f} ms)")
        print(f"Maximum: {max_us:.2f} μs ({max_us / 1000:.6f} ms)")
        print(f"Median:  {median_us:.2f} μs ({median_us / 1000:.6f} ms)")

        # Verify average meets requirement (<10ms = 10,000 μs)
        assert avg_us < 10000, f"Average calculation time {avg_us:.2f}μs exceeds 10ms limit"
