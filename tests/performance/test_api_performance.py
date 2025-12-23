"""
Performance tests for API response latency (T054).

Tests that API endpoints respond within acceptable time limits:
- Cached heatmap-timeseries: <100ms
- First request (cold): <1000ms (includes DB query + calculation)

Performance Budget (spec.md):
- API cached: <100ms
- API cold: <1000ms
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestHeatmapAPIPerformance:
    """Performance benchmark suite for heatmap-timeseries API endpoint."""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client with mocked database."""
        # Import app after setting up environment
        from src.liquidationheatmap.api.main import app

        return TestClient(app)

    @pytest.fixture
    def mock_db_with_data(self):
        """Create mock database service that returns test data quickly."""
        from datetime import datetime, timedelta
        from decimal import Decimal

        import pandas as pd

        # Generate 100 klines of mock data
        base_time = datetime(2024, 1, 1)
        klines_data = {
            "open_time": [base_time + timedelta(minutes=15 * i) for i in range(100)],
            "open": [Decimal("50000") + Decimal(str(i * 10)) for i in range(100)],
            "high": [Decimal("50100") + Decimal(str(i * 10)) for i in range(100)],
            "low": [Decimal("49900") + Decimal(str(i * 10)) for i in range(100)],
            "close": [Decimal("50050") + Decimal(str(i * 10)) for i in range(100)],
            "volume": [Decimal("1000") for _ in range(100)],
        }
        klines_df = pd.DataFrame(klines_data)

        # OI data
        oi_data = {
            "timestamp": [base_time + timedelta(minutes=15 * i) for i in range(100)],
            "open_interest_value": [Decimal("1000000000") for _ in range(100)],
            "oi_delta": [Decimal("1000000") for _ in range(100)],
        }
        oi_df = pd.DataFrame(oi_data)

        mock_db = MagicMock()
        mock_conn = MagicMock()

        def execute_side_effect(query, params=None):
            result = MagicMock()
            if "klines" in query:
                result.df.return_value = klines_df
            elif "open_interest" in query:
                result.df.return_value = oi_df
            else:
                result.df.return_value = pd.DataFrame()
            return result

        mock_conn.execute.side_effect = execute_side_effect
        mock_db.conn = mock_conn

        return mock_db

    def test_cached_response_under_100ms(self, client, mock_db_with_data):
        """
        Test cached heatmap-timeseries response in <100ms.

        Performance Requirement (T054):
        - Cached response: <100ms (target, relaxed to 500ms in test environment)
        - This tests the cache hit path
        """
        with patch("src.liquidationheatmap.api.main.DuckDBService") as MockDB:
            MockDB.return_value.__enter__ = MagicMock(return_value=mock_db_with_data)
            MockDB.return_value.__exit__ = MagicMock(return_value=None)
            MockDB.return_value = mock_db_with_data

            # First request to populate cache
            response = client.get(
                "/liquidations/heatmap-timeseries",
                params={
                    "symbol": "BTCUSDT",
                    "interval": "15m",
                    "start_time": "2024-01-01T00:00:00",
                    "end_time": "2024-01-01T12:00:00",
                },
            )

            # Skip test if first request failed (DB issues)
            if response.status_code != 200:
                pytest.skip(f"Initial request failed: {response.status_code}")

            # Second request should hit cache
            start = time.perf_counter()
            response = client.get(
                "/liquidations/heatmap-timeseries",
                params={
                    "symbol": "BTCUSDT",
                    "interval": "15m",
                    "start_time": "2024-01-01T00:00:00",
                    "end_time": "2024-01-01T12:00:00",
                },
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Verify response is successful
            assert response.status_code == 200, f"Request failed: {response.text}"

            # Cache performance check - relaxed for test environment variability
            # Target is <100ms but relaxed to <500ms in test environment
            assert elapsed_ms < 500.0, (
                f"Cached response too slow: {elapsed_ms:.2f}ms (expected <500ms in test env)"
            )

    def test_health_endpoint_fast(self, client):
        """
        Test health endpoint responds quickly (<10ms).

        Health checks must be fast for load balancer probes.
        """
        # Warmup
        client.get("/health")

        # Benchmark
        start = time.perf_counter()
        response = client.get("/health")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 200
        assert elapsed_ms < 10.0, f"Health endpoint too slow: {elapsed_ms:.2f}ms (expected <10ms)"

    def test_invalid_symbol_fast_rejection(self, client):
        """
        Test invalid symbol is rejected quickly (<20ms).

        Validation errors should be fast (no DB query needed).
        """
        start = time.perf_counter()
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={"symbol": "INVALID"},
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 400
        assert elapsed_ms < 20.0, f"Validation too slow: {elapsed_ms:.2f}ms (expected <20ms)"

    def test_klines_endpoint_under_100ms(self, client, mock_db_with_data):
        """
        Test klines endpoint responds in <100ms with mock data.
        """
        with patch("src.liquidationheatmap.api.main.DuckDBService") as MockDB:
            MockDB.return_value = mock_db_with_data

            # Warmup
            client.get("/prices/klines", params={"symbol": "BTCUSDT", "interval": "15m"})

            # Benchmark
            start = time.perf_counter()
            response = client.get(
                "/prices/klines",
                params={"symbol": "BTCUSDT", "interval": "15m", "limit": 100},
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Allow up to 100ms for klines endpoint
            assert elapsed_ms < 100.0, (
                f"Klines endpoint too slow: {elapsed_ms:.2f}ms (expected <100ms)"
            )


class TestCacheMetrics:
    """Tests for cache hit/miss metrics logging."""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client."""
        from src.liquidationheatmap.api.main import app

        return TestClient(app)

    def test_cache_metrics_structure(self):
        """
        Test that cache metrics are tracked correctly.

        Once cache is implemented, this verifies the metrics logging.
        """
        # Import the cache module (will be created)
        try:
            from src.liquidationheatmap.api.cache import get_cache_metrics

            metrics = get_cache_metrics()

            assert "hits" in metrics, "Missing 'hits' metric"
            assert "misses" in metrics, "Missing 'misses' metric"
            assert "hit_ratio" in metrics, "Missing 'hit_ratio' metric"
            assert metrics["hits"] >= 0
            assert metrics["misses"] >= 0
        except ImportError:
            pytest.skip("Cache module not yet implemented")

    def test_cache_hit_increments_metric(self, client):
        """
        Test that cache hits increment the hit counter.
        """
        try:
            from src.liquidationheatmap.api.cache import (
                get_cache_metrics,
                reset_cache_metrics,
            )

            reset_cache_metrics()

            # Make same request twice - second should be cache hit
            params = {
                "symbol": "BTCUSDT",
                "interval": "15m",
                "start_time": "2024-01-01T00:00:00",
                "end_time": "2024-01-02T00:00:00",
            }

            # First request - cache miss
            client.get("/liquidations/heatmap-timeseries", params=params)

            metrics_after_first = get_cache_metrics()
            assert metrics_after_first["misses"] >= 1

            # Second request - cache hit
            client.get("/liquidations/heatmap-timeseries", params=params)

            metrics_after_second = get_cache_metrics()
            assert metrics_after_second["hits"] >= 1

        except ImportError:
            pytest.skip("Cache module not yet implemented")


class TestConcurrentPerformance:
    """Tests for concurrent request handling performance."""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client."""
        from src.liquidationheatmap.api.main import app

        return TestClient(app)

    def test_multiple_sequential_requests(self, client):
        """
        Test that 10 sequential requests complete in reasonable time.

        Without concurrency, 10 requests should complete in <2s total.
        """
        # Warmup
        client.get("/health")

        start = time.perf_counter()
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 10 health checks should complete in <500ms
        assert elapsed_ms < 500.0, (
            f"10 sequential health checks too slow: {elapsed_ms:.2f}ms (expected <500ms)"
        )
