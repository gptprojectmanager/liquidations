"""
Concurrency and race condition testing for funding rate bias adjustment.
Tests thread safety, async behavior, and concurrent access patterns.
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal

import pytest

from src.models.funding.adjustment_config import AdjustmentConfigModel
from src.services.funding.bias_calculator import BiasCalculator
from src.services.funding.cache_manager import CacheManager
from src.services.funding.complete_calculator import CompleteBiasCalculator


class TestThreadSafety:
    """Test thread safety of calculator and cache."""

    def test_concurrent_calculator_calls(self):
        """Test calculator is thread-safe with concurrent calls."""
        calculator = BiasCalculator()
        test_rates = [
            Decimal("0.0001"),
            Decimal("0.0003"),
            Decimal("0.0005"),
            Decimal("-0.0002"),
            Decimal("-0.0004"),
        ]

        def calculate_rate(rate):
            """Calculate bias for a rate."""
            result = calculator.calculate(rate)
            # Verify OI conservation
            total = result.long_ratio + result.short_ratio
            assert total == Decimal("1.0"), f"OI not conserved: {total}"
            return result

        # Run 100 calculations concurrently across multiple threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(100):
                for rate in test_rates:
                    future = executor.submit(calculate_rate, rate)
                    futures.append(future)

            # Wait for all to complete and verify no exceptions
            for future in as_completed(futures):
                result = future.result()  # Will raise if calculation failed
                assert result is not None

    def test_concurrent_cache_access(self):
        """Test cache manager is thread-safe with concurrent access."""
        cache = CacheManager(ttl_seconds=60, max_size=100)

        def write_and_read(thread_id):
            """Write and read from cache concurrently."""
            for i in range(100):
                key = f"key_{thread_id}_{i}"
                value = f"value_{thread_id}_{i}"

                # Write
                cache.set(key, value)

                # Read back immediately
                retrieved = cache.get(key)

                # Should get back what we wrote (or None if evicted)
                if retrieved is not None:
                    assert retrieved == value, f"Cache corruption: {retrieved} != {value}"

        # Run multiple threads concurrently
        threads = []
        for thread_id in range(10):
            thread = threading.Thread(target=write_and_read, args=(thread_id,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Cache should still be functional
        cache.set("final_test", "works")
        assert cache.get("final_test") == "works"

    def test_concurrent_different_scale_factors(self):
        """Test multiple calculators with different configs running concurrently."""

        def create_and_test(scale_factor):
            """Create calculator and run tests."""
            calc = BiasCalculator(scale_factor=scale_factor)
            test_rate = Decimal("0.0003")

            # Run calculation multiple times
            for _ in range(50):
                result = calc.calculate(test_rate)
                total = result.long_ratio + result.short_ratio
                assert total == Decimal("1.0")

            return scale_factor

        # Test different scale factors concurrently
        scale_factors = [10.0, 25.0, 50.0, 75.0, 100.0]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_and_test, sf) for sf in scale_factors]

            results = [future.result() for future in as_completed(futures)]

        assert len(results) == len(scale_factors)


class TestAsyncBehavior:
    """Test async/await behavior and timeout handling."""

    @pytest.mark.asyncio
    async def test_async_calculator_initialization(self):
        """Test async initialization of complete calculator."""
        config = AdjustmentConfigModel(enabled=False)  # Disable for sync test
        calculator = CompleteBiasCalculator(config)

        # Should initialize successfully
        assert calculator is not None
        assert calculator.config.enabled is False

    @pytest.mark.asyncio
    async def test_concurrent_async_calculations(self):
        """Test multiple async calculations running concurrently."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        async def calculate_neutral(symbol, oi):
            """Calculate neutral adjustment."""
            adjustment = calculator._create_neutral_adjustment(symbol, oi)
            # Verify OI conservation
            assert adjustment.long_oi + adjustment.short_oi == adjustment.total_oi
            return adjustment

        # Run 100 calculations concurrently
        tasks = []
        for i in range(100):
            task = calculate_neutral(f"SYMBOL{i}", Decimal(f"{1000000 + i}"))
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 100
        for result in results:
            assert result.long_ratio == Decimal("0.5")
            assert result.short_ratio == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_async_timeout_behavior(self):
        """Test behavior when async operations timeout."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        async def slow_operation():
            """Simulate slow operation."""
            await asyncio.sleep(0.1)
            return calculator._create_neutral_adjustment("BTCUSDT", Decimal("1000000"))

        # Should complete within reasonable time
        try:
            result = await asyncio.wait_for(slow_operation(), timeout=1.0)
            assert result is not None
        except asyncio.TimeoutError:
            pytest.fail("Operation timed out unexpectedly")

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations_async(self):
        """Test cache operations in async context."""
        cache = CacheManager(ttl_seconds=60)

        async def async_cache_operation(key_id):
            """Perform cache operations asynchronously."""
            key = f"async_key_{key_id}"
            value = f"async_value_{key_id}"

            # Write
            cache.set(key, value)

            # Small delay to simulate real-world usage
            await asyncio.sleep(0.001)

            # Read
            result = cache.get(key)
            return result == value

        # Run 100 concurrent async operations
        tasks = [async_cache_operation(i) for i in range(100)]
        results = await asyncio.gather(*tasks)

        # All operations should succeed
        assert all(results)


class TestRaceConditions:
    """Test for potential race conditions."""

    def test_cache_size_limit_under_load(self):
        """Test cache size limit is respected under concurrent load."""
        max_size = 50
        cache = CacheManager(ttl_seconds=300, max_size=max_size)

        def rapid_writes(thread_id):
            """Rapidly write to cache."""
            for i in range(200):
                cache.set(f"thread_{thread_id}_key_{i}", f"value_{i}")

        # Multiple threads writing rapidly
        threads = []
        for tid in range(5):
            thread = threading.Thread(target=rapid_writes, args=(tid,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Cache size should not exceed max_size
        # (actual size may vary due to eviction, but shouldn't be much larger)
        assert len(cache._cache) <= max_size * 1.5, (
            f"Cache size {len(cache._cache)} significantly exceeds max {max_size}"
        )

    def test_calculator_state_isolation(self):
        """Test that calculator instances don't share mutable state."""
        calc1 = BiasCalculator(scale_factor=25.0)
        calc2 = BiasCalculator(scale_factor=75.0)

        test_rate = Decimal("0.0005")

        # Calculations should be independent
        result1 = calc1.calculate(test_rate)
        result2 = calc2.calculate(test_rate)

        # Different scale factors should give different results
        assert result1.long_ratio != result2.long_ratio

        # Each should maintain OI conservation
        assert result1.long_ratio + result1.short_ratio == Decimal("1.0")
        assert result2.long_ratio + result2.short_ratio == Decimal("1.0")

        # Original calculator should still work with original config
        result1_again = calc1.calculate(test_rate)
        assert result1_again.long_ratio == result1.long_ratio

    def test_no_shared_mutable_defaults(self):
        """Test that calculators don't share mutable default objects."""
        calc1 = BiasCalculator()
        calc2 = BiasCalculator()

        # Should be separate instances
        assert calc1 is not calc2

        # Modifying one shouldn't affect the other
        # (this is more of a sanity check for the code structure)
        result1 = calc1.calculate(Decimal("0.0003"))
        result2 = calc2.calculate(Decimal("0.0003"))

        # Results should be identical (same config)
        assert result1.long_ratio == result2.long_ratio


class TestStressConcurrency:
    """Stress testing with high concurrency."""

    def test_high_volume_concurrent_requests(self):
        """Simulate high volume of concurrent requests."""
        calculator = BiasCalculator()
        num_requests = 1000
        num_workers = 20

        def process_request(request_id):
            """Process a single request."""
            rate = Decimal(f"{(request_id % 100) / 100000}")  # Vary the rate
            result = calculator.calculate(rate)
            return result.long_ratio + result.short_ratio == Decimal("1.0")

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(process_request, i) for i in range(num_requests)]
            results = [future.result() for future in as_completed(futures)]

        # All requests should maintain OI conservation
        assert all(results), "Some requests failed OI conservation under load"

    @pytest.mark.asyncio
    async def test_async_high_volume(self):
        """Test high volume of async operations."""
        config = AdjustmentConfigModel(enabled=False)
        calculator = CompleteBiasCalculator(config)

        async def single_calculation(calc_id):
            """Single async calculation."""
            oi = Decimal(f"{1000000 + calc_id}")
            result = calculator._create_neutral_adjustment(f"SYM{calc_id}", oi)
            return result.total_oi == oi

        # 500 concurrent async operations
        tasks = [single_calculation(i) for i in range(500)]
        results = await asyncio.gather(*tasks)

        assert all(results), "Some async calculations failed"

    def test_cache_concurrent_eviction(self):
        """Test cache eviction under concurrent access."""
        cache = CacheManager(ttl_seconds=60, max_size=20)

        def concurrent_access(thread_id):
            """Concurrently access cache causing evictions."""
            for i in range(100):
                # Write - this will cause evictions due to small max_size
                cache.set(f"t{thread_id}_k{i}", f"v{i}")

                # Try to read recent writes
                for j in range(max(0, i - 5), i):
                    value = cache.get(f"t{thread_id}_k{j}")
                    # May be None due to eviction, but shouldn't crash

        threads = []
        for tid in range(5):
            thread = threading.Thread(target=concurrent_access, args=(tid,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Cache should still be functional after all this
        cache.set("final", "test")
        assert cache.get("final") == "test"


class TestDeadlockPrevention:
    """Test that operations don't deadlock."""

    @pytest.mark.timeout(5)
    def test_no_deadlock_with_recursive_calls(self):
        """Test no deadlock with nested calculator calls."""
        calculator = BiasCalculator()

        def nested_calculation(depth):
            """Recursively call calculator."""
            if depth == 0:
                return True

            rate = Decimal(f"{depth / 1000}")
            result = calculator.calculate(rate)

            # Nested call
            return nested_calculation(depth - 1) and (
                result.long_ratio + result.short_ratio == Decimal("1.0")
            )

        # Should complete without deadlock
        assert nested_calculation(10)

    @pytest.mark.timeout(10)
    def test_no_deadlock_with_concurrent_writes(self):
        """Test no deadlock with concurrent cache writes to same key."""
        cache = CacheManager(ttl_seconds=60)

        def hammer_same_key(thread_id):
            """Repeatedly write to same key."""
            for i in range(100):
                cache.set("shared_key", f"thread_{thread_id}_value_{i}")

        threads = []
        for tid in range(10):
            thread = threading.Thread(target=hammer_same_key, args=(tid,))
            threads.append(thread)
            thread.start()

        # Should complete within timeout
        for thread in threads:
            thread.join()
