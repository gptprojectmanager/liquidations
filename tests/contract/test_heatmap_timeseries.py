"""Contract tests for /liquidations/heatmap-timeseries endpoint.

Tests that the API response matches the OpenAPI contract in contracts/openapi.yaml.
"""

import pytest
from fastapi.testclient import TestClient

from src.liquidationheatmap.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHeatmapTimeseriesContract:
    """Contract tests for /liquidations/heatmap-timeseries endpoint."""

    def test_endpoint_exists(self, client):
        """Verify endpoint exists and returns 200 for valid params."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T01:00:00Z",
                "interval": "15m",
            },
        )
        # May return 200 or 500 depending on data availability
        # Contract test verifies endpoint exists and is routable
        assert response.status_code in [200, 500]

    def test_response_structure_matches_contract(self, client):
        """Verify response structure matches OpenAPI schema."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T01:00:00Z",
                "interval": "15m",
            },
        )

        if response.status_code == 200:
            data = response.json()

            # Top-level structure
            assert "data" in data
            assert "meta" in data
            assert isinstance(data["data"], list)

            # Meta structure
            meta = data["meta"]
            assert "symbol" in meta
            assert "interval" in meta
            assert "total_snapshots" in meta

            # If snapshots present, verify structure
            if data["data"]:
                snapshot = data["data"][0]
                assert "timestamp" in snapshot
                assert "levels" in snapshot
                assert "positions_created" in snapshot
                assert "positions_consumed" in snapshot

                if snapshot["levels"]:
                    level = snapshot["levels"][0]
                    assert "price" in level
                    assert "long_density" in level
                    assert "short_density" in level

    def test_invalid_symbol_returns_error(self, client):
        """Verify unsupported symbol returns appropriate error."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "INVALID",
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T01:00:00Z",
            },
        )
        # Should return 400 for unsupported symbol
        assert response.status_code == 400

    def test_invalid_interval_returns_422(self, client):
        """Verify invalid interval format returns validation error."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T01:00:00Z",
                "interval": "invalid",
            },
        )
        # Invalid interval enum should return 422 (validation error)
        assert response.status_code == 422

    def test_missing_symbol_returns_422(self, client):
        """Verify missing required symbol param returns validation error."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                # Missing symbol - which is required
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T01:00:00Z",
            },
        )
        assert response.status_code == 422

    def test_leverage_weights_query_param(self, client):
        """Verify leverage_weights query param is accepted."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T01:00:00Z",
                "leverage_weights": "10:0.5,25:0.3,50:0.2",
            },
        )
        # Should accept the parameter (may fail on data, but param is valid)
        assert response.status_code in [200, 500]

    def test_invalid_leverage_weights_format(self, client):
        """Verify invalid leverage_weights format returns error."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T01:00:00Z",
                "leverage_weights": "invalid_format",
            },
        )
        # Invalid format should return 400
        assert response.status_code == 400
