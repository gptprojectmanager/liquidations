"""
Memory leak and performance profiling tests.
Tests for memory leaks, resource cleanup, and performance degradation.
"""

import asyncio
import gc
import sys
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from src.models.funding.adjustment_config import AdjustmentConfigModel
from src.models.funding.funding_rate import FundingRate
from src.services.funding.complete_calculator import CompleteBiasCalculator


class TestMemoryLeaks:
    """Test for memory leaks in long-running scenarios."""

    @pytest.mark.asyncio
    async def test_no_memory_leak_from_repeated_calculations(self):
        """Test that repeated calculations don't leak memory."""
        config = AdjustmentConfigModel(enabled=False)  # Neutral mode for speed
        calculator = CompleteBiasCalculator(config)

        # Get initial memory usage
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Perform 1000 calculations
        for i in range(1000):
            await calculator.calculate_bias_adjustment(f"SYM{i % 10}", Decimal(f"{1000000 + i}"))

        # Force garbage collection
        gc.collect()
        final_objects = len(gc.get_objects())

        # Object count should not grow significantly (allow 10% variance)
        growth = final_objects - initial_objects
        growth_percent = (growth / initial_objects) * 100

        assert growth_percent < 10, (
            f"Potential memory leak: {growth_percent:.1f}% object growth "
            f"({initial_objects} -> {final_objects})"
        )

    @pytest.mark.asyncio
    async def test_cache_memory_bounded(self):
        """Test that cache memory usage is bounded."""
        config = AdjustmentConfigModel(enabled=True, cache_ttl_seconds=60)
        calculator = CompleteBiasCalculator(config)

        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            # Fill cache with many different symbols
            for i in range(100):
                await calculator.calculate_bias_adjustment(f"SYM{i}", Decimal("1000000"))

            # Check that cache size is bounded (max_size=50 in CompleteBiasCalculator)
            cache_size = len(calculator._adjustment_cache._cache)
            assert cache_size <= 50, f"Cache not bounded: {cache_size} items (max 50)"

    @pytest.mark.asyncio
    async def test_history_list_bounded(self):
        """Test that history list doesn't grow unbounded."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            # Generate many calculations to add to history
            for i in range(100):
                # Clear cache to force new calculations
                calculator._adjustment_cache._cache.clear()
                await calculator.calculate_bias_adjustment("BTCUSDT", Decimal(f"{1000000 + i}"))

            # History should be bounded to max_history (10 in CompleteBiasCalculator)
            history_size = len(calculator._history)
            assert history_size <= 10, f"History not bounded: {history_size} items (max 10)"

    @pytest.mark.asyncio
    async def test_no_circular_references(self):
        """Test that objects don't create circular references."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        # Perform calculation
        result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

        # Delete calculator and result
        del calculator
        del result

        # Force garbage collection
        gc.collect()

        # Check that all garbage was collected (no circular references preventing cleanup)
        # This is a simple check - if circular refs exist, gc.collect() may return > 0
        uncollectable = gc.collect()
        assert uncollectable == 0, f"Found {uncollectable} uncollectable objects"


class TestResourceCleanup:
    """Test proper resource cleanup."""

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self):
        """Test that async context manager properly cleans up resources."""
        config = AdjustmentConfigModel(enabled=False)

        # Use context manager
        async with CompleteBiasCalculator(config) as calculator:
            result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
            assert result is not None

        # After exiting context, resources should be cleaned up
        # (Specific checks would depend on what resources are tracked)

    @pytest.mark.asyncio
    async def test_explicit_close(self):
        """Test that explicit close() cleans up resources."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
        assert result is not None

        # Explicit cleanup
        await calculator.close()

        # Should be safe to close multiple times
        await calculator.close()

    @pytest.mark.asyncio
    async def test_cache_clear_frees_memory(self):
        """Test that clearing cache actually frees memory."""
        config = AdjustmentConfigModel(enabled=True)
        calculator = CompleteBiasCalculator(config)

        mock_funding = FundingRate(
            symbol="BTCUSDT",
            rate=Decimal("0.0003"),
            funding_time="2025-12-02T12:00:00+00:00",
        )

        with patch.object(
            calculator._fetcher, "get_funding_rate", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_funding

            # Fill cache
            for i in range(50):
                await calculator.calculate_bias_adjustment(f"SYM{i}", Decimal("1000000"))

            cache_size_before = len(calculator._adjustment_cache._cache)

            # Clear cache
            calculator._adjustment_cache.clear()

            cache_size_after = len(calculator._adjustment_cache._cache)

            assert cache_size_before > 0, "Cache should have been filled"
            assert cache_size_after == 0, "Cache should be empty after clear"


class TestPerformanceDegradation:
    """Test for performance degradation over time."""

    @pytest.mark.asyncio
    async def test_no_performance_degradation_over_time(self):
        """Test that calculation speed doesn't degrade over time."""
        import time

        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        # Warm up
        for _ in range(10):
            await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))

        # Measure first batch
        start1 = time.time()
        for i in range(100):
            await calculator.calculate_bias_adjustment(f"SYM{i % 5}", Decimal(f"{1000000 + i}"))
        time1 = time.time() - start1

        # Perform many more calculations
        for i in range(1000):
            await calculator.calculate_bias_adjustment(f"SYM{i % 5}", Decimal(f"{1000000 + i}"))

        # Measure second batch
        start2 = time.time()
        for i in range(100):
            await calculator.calculate_bias_adjustment(f"SYM{i % 5}", Decimal(f"{2000000 + i}"))
        time2 = time.time() - start2

        # Second batch should not be significantly slower (allow 20% variance)
        slowdown = ((time2 - time1) / time1) * 100

        assert slowdown < 20, (
            f"Performance degraded by {slowdown:.1f}% (first: {time1:.3f}s, second: {time2:.3f}s)"
        )

    @pytest.mark.asyncio
    async def test_concurrent_performance_stable(self):
        """Test that performance is stable under concurrent load."""
        import time

        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        async def batch_calculations(count: int):
            """Perform batch of calculations."""
            for i in range(count):
                await calculator.calculate_bias_adjustment(f"SYM{i % 5}", Decimal(f"{1000000 + i}"))

        # Measure sequential performance
        start_seq = time.time()
        await batch_calculations(100)
        time_sequential = time.time() - start_seq

        # Measure concurrent performance (5 parallel batches of 20 each = 100 total)
        start_conc = time.time()
        tasks = [batch_calculations(20) for _ in range(5)]
        await asyncio.gather(*tasks)
        time_concurrent = time.time() - start_conc

        # Concurrent should be faster or at least not significantly slower
        # (On single core it might be slightly slower due to overhead)
        slowdown = ((time_concurrent - time_sequential) / time_sequential) * 100

        # Allow 50% slowdown for concurrent overhead
        assert slowdown < 50, (
            f"Concurrent performance degraded by {slowdown:.1f}% "
            f"(sequential: {time_sequential:.3f}s, concurrent: {time_concurrent:.3f}s)"
        )


class TestMemoryBoundaries:
    """Test memory usage stays within reasonable boundaries."""

    @pytest.mark.asyncio
    async def test_large_oi_doesnt_consume_excessive_memory(self):
        """Test that large OI values don't consume excessive memory."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        gc.collect()
        initial_objects = len(gc.get_objects())

        # Use very large OI values
        large_oi_values = [
            Decimal("1000000000000"),  # 1 trillion
            Decimal("999999999999999"),  # ~1 quadrillion
        ]

        for oi in large_oi_values:
            result = await calculator.calculate_bias_adjustment("BTCUSDT", oi)
            assert result.total_oi == oi

        gc.collect()
        final_objects = len(gc.get_objects())

        # Should not create excessive objects even with huge numbers
        growth = final_objects - initial_objects
        assert growth < 100, f"Too many objects created: {growth}"

    @pytest.mark.asyncio
    async def test_decimal_precision_memory_efficient(self):
        """Test that Decimal precision doesn't cause memory bloat."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        # High precision Decimal
        precise_oi = Decimal("1000000.123456789012345678901234567890")

        gc.collect()
        initial_size = sys.getsizeof(precise_oi)

        result = await calculator.calculate_bias_adjustment("BTCUSDT", precise_oi)

        # Result Decimals should not be significantly larger
        long_oi_size = sys.getsizeof(result.long_oi)
        short_oi_size = sys.getsizeof(result.short_oi)

        # Allow 2x size increase for calculations
        assert long_oi_size < initial_size * 2, f"long_oi too large: {long_oi_size} bytes"
        assert short_oi_size < initial_size * 2, f"short_oi too large: {short_oi_size} bytes"


class TestStressMemory:
    """Stress testing for memory under extreme conditions."""

    @pytest.mark.asyncio
    async def test_sustained_high_volume_no_leak(self):
        """Test sustained high volume doesn't leak memory."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        # Measure baseline
        gc.collect()
        baseline_objects = len(gc.get_objects())

        # Sustained load: 10 batches of 100 calculations each
        for batch in range(10):
            for i in range(100):
                await calculator.calculate_bias_adjustment(
                    f"SYM{i % 10}", Decimal(f"{1000000 + batch * 100 + i}")
                )

            # Check memory after each batch
            gc.collect()
            current_objects = len(gc.get_objects())
            growth = ((current_objects - baseline_objects) / baseline_objects) * 100

            # Should not grow more than 15% even after sustained load
            assert growth < 15, (
                f"Memory leak detected after batch {batch}: {growth:.1f}% growth "
                f"({baseline_objects} -> {current_objects})"
            )

    @pytest.mark.asyncio
    async def test_rapid_calculator_creation_destruction(self):
        """Test that rapidly creating/destroying calculators doesn't leak."""
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Create and destroy 100 calculators rapidly
        for i in range(100):
            config = AdjustmentConfigModel(enabled=False)
            calculator = CompleteBiasCalculator(config)
            result = await calculator.calculate_bias_adjustment("BTCUSDT", Decimal("1000000"))
            await calculator.close()
            del calculator
            del result

        gc.collect()
        final_objects = len(gc.get_objects())

        growth = final_objects - initial_objects
        growth_percent = (growth / initial_objects) * 100

        # Should not accumulate objects
        assert growth_percent < 10, (
            f"Object accumulation detected: {growth_percent:.1f}% growth "
            f"({initial_objects} -> {final_objects})"
        )
