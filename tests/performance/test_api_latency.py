"""
Performance tests for API response latency.

Tests that API endpoints respond within acceptable time limits.
"""

import time

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


class TestAPILatency:
    """Test suite for API response time performance."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        return TestClient(app)

    def test_calculate_endpoint_latency(self, client):
        """
        Test /calculate endpoint latency.

        Should respond in <100ms for single calculation.
        """
        # Warmup
        client.post("/api/margin/calculate", json={"symbol": "BTCUSDT", "notional": "50000"})

        # Measure
        start = time.time()
        response = client.post(
            "/api/margin/calculate", json={"symbol": "BTCUSDT", "notional": "50000"}
        )
        duration = (time.time() - start) * 1000  # Convert to ms

        assert response.status_code == 200
        assert duration < 100  # <100ms

    def test_tiers_endpoint_latency(self, client):
        """Test /tiers endpoint latency."""
        # Warmup
        client.get("/api/margin/tiers/BTCUSDT")

        # Measure
        start = time.time()
        response = client.get("/api/margin/tiers/BTCUSDT")
        duration = (time.time() - start) * 1000

        assert response.status_code == 200
        assert duration < 50  # <50ms (faster, just retrieval)

    def test_batch_endpoint_latency(self, client):
        """
        Test batch endpoint latency.

        10 calculations should complete in <100ms.
        """
        calculations = [{"symbol": "BTCUSDT", "notional": str(i * 10000)} for i in range(1, 11)]

        # Warmup
        client.post("/api/margin/batch", json={"calculations": calculations})

        # Measure
        start = time.time()
        response = client.post("/api/margin/batch", json={"calculations": calculations})
        duration = (time.time() - start) * 1000

        assert response.status_code == 200
        assert duration < 100  # 10 calcs in <100ms
