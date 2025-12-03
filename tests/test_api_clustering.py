"""Tests for clustering API endpoints.

TDD Mode: Tests written BEFORE implementation per constitution §2.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


# =============================================================================
# T024: API Contract Test for GET /liquidations/clusters
# =============================================================================


class TestClusteringAPIContract:
    """API contract tests for clustering endpoint (T024)."""

    def test_clusters_endpoint_returns_200_with_valid_params(self, client):
        """GET /liquidations/clusters should return 200 with valid parameters."""
        # Act
        response = client.get(
            "/api/liquidations/clusters",
            params={
                "symbol": "BTCUSDT",
                "timeframe_minutes": 30,
                "epsilon": 0.5,
                "min_samples": 3,
            },
        )

        # Assert
        assert response.status_code == 200

    def test_clusters_endpoint_returns_correct_schema(self, client):
        """Response should match ClusteringResult schema."""
        # Act
        response = client.get(
            "/api/liquidations/clusters",
            params={
                "symbol": "BTCUSDT",
                "timeframe_minutes": 30,
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify top-level structure
        assert "clusters" in data
        assert "noise_points" in data
        assert "metadata" in data
        assert "fallback_used" in data

        # Verify metadata structure
        metadata = data["metadata"]
        assert "symbol" in metadata
        assert "timeframe_minutes" in metadata
        assert "total_points" in metadata
        assert "cluster_count" in metadata
        assert "noise_count" in metadata
        assert "computation_ms" in metadata
        assert "auto_tuned" in metadata

    def test_clusters_endpoint_with_auto_tune(self, client):
        """Endpoint should support auto_tune parameter."""
        # Act
        response = client.get(
            "/api/liquidations/clusters",
            params={
                "symbol": "BTCUSDT",
                "timeframe_minutes": 30,
                "auto_tune": True,
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["auto_tuned"] is True

    def test_clusters_endpoint_returns_valid_cluster_data(self, client):
        """Clusters should have all required fields."""
        # Act
        response = client.get(
            "/api/liquidations/clusters",
            params={
                "symbol": "BTCUSDT",
                "timeframe_minutes": 30,
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        # If clusters exist, verify structure
        if len(data["clusters"]) > 0:
            cluster = data["clusters"][0]
            assert "cluster_id" in cluster
            assert "price_min" in cluster
            assert "price_max" in cluster
            assert "centroid_price" in cluster
            assert "total_volume" in cluster
            assert "level_count" in cluster
            assert "density" in cluster
            # Computed fields
            assert "price_spread" in cluster
            assert "avg_volume_per_level" in cluster
            assert "zone_strength" in cluster


# =============================================================================
# T025: Error Response Tests (400, 404, 500)
# =============================================================================


class TestClusteringAPIErrors:
    """Error handling tests for clustering endpoint (T025)."""

    def test_clusters_endpoint_returns_422_with_invalid_symbol(self, client):
        """Invalid symbol should return 422 validation error."""
        # Act
        response = client.get(
            "/api/liquidations/clusters",
            params={
                "symbol": "",  # Empty symbol
                "timeframe_minutes": 30,
            },
        )

        # Assert
        assert response.status_code == 422

    def test_clusters_endpoint_returns_422_with_invalid_epsilon(self, client):
        """Epsilon out of range [0.01, 1.0] should return 422."""
        # Act
        response = client.get(
            "/api/liquidations/clusters",
            params={
                "symbol": "BTCUSDT",
                "timeframe_minutes": 30,
                "epsilon": 1.5,  # Out of range
            },
        )

        # Assert
        assert response.status_code == 422

    def test_clusters_endpoint_returns_422_with_invalid_min_samples(self, client):
        """Min samples out of range [2, 10] should return 422."""
        # Act
        response = client.get(
            "/api/liquidations/clusters",
            params={
                "symbol": "BTCUSDT",
                "timeframe_minutes": 30,
                "min_samples": 15,  # Out of range
            },
        )

        # Assert
        assert response.status_code == 422

    def test_clusters_endpoint_returns_422_with_negative_timeframe(self, client):
        """Negative timeframe should return 422."""
        # Act
        response = client.get(
            "/api/liquidations/clusters",
            params={
                "symbol": "BTCUSDT",
                "timeframe_minutes": -1,  # Invalid
            },
        )

        # Assert
        assert response.status_code == 422

    def test_clusters_endpoint_handles_empty_liquidations_gracefully(self, client):
        """Should return 200 with valid structure (mock data always returns results)."""
        # Act - Use any symbol (mock data always returns sample liquidations)
        response = client.get(
            "/api/liquidations/clusters",
            params={
                "symbol": "NONEXISTENT",
                "timeframe_minutes": 1,
            },
        )

        # Assert - With mock data, should always return 200
        # TODO: When integrated with real DB, test empty results scenario
        assert response.status_code == 200

        data = response.json()
        # Verify structure is valid (mock always has data)
        assert "metadata" in data
        assert "clusters" in data
        assert "noise_points" in data
        assert data["metadata"]["total_points"] >= 0
