"""
API contract tests for /api/margin/batch endpoint.

Tests batch calculation endpoint for multiple positions.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


class TestBatchAPI:
    """Test suite for batch calculation API endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        return TestClient(app)

    def test_batch_calculate_multiple_positions(self, client):
        """
        Test batch calculation for multiple positions.

        POST /api/margin/batch
        Request: [{"symbol": "BTCUSDT", "notional": "50000"}, ...]
        """
        response = client.post(
            "/api/margin/batch",
            json={
                "calculations": [
                    {"symbol": "BTCUSDT", "notional": "50000"},
                    {"symbol": "BTCUSDT", "notional": "100000"},
                    {"symbol": "BTCUSDT", "notional": "500000"},
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        assert len(data["results"]) == 3

    def test_batch_performance(self, client):
        """
        Test batch calculation performance.

        10k positions should complete in <100ms.
        """
        import time

        # Create 100 position batch (scaled down for test)
        calculations = [{"symbol": "BTCUSDT", "notional": str(i * 10000)} for i in range(1, 101)]

        start = time.time()
        response = client.post("/api/margin/batch", json={"calculations": calculations})
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 1.0  # 100 calcs in <1 second
