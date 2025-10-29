"""Tests for FastAPI main application."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    from src.liquidationheatmap.api.main import app
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_200(self, client):
        """Test that health check returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_status_ok(self, client):
        """Test that health check returns status ok."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"


class TestLiquidationsEndpoint:
    """Tests for /liquidations/levels endpoint."""

    def test_liquidations_returns_200_with_valid_params(self, client):
        """Test that liquidations endpoint returns 200 with valid params."""
        response = client.get("/liquidations/levels?symbol=BTCUSDT&model=binance_standard")
        assert response.status_code == 200

    def test_liquidations_returns_long_and_short_levels(self, client):
        """Test that liquidations returns both long and short levels."""
        response = client.get("/liquidations/levels?symbol=BTCUSDT&model=binance_standard")
        data = response.json()

        assert "long_liquidations" in data
        assert "short_liquidations" in data
        assert isinstance(data["long_liquidations"], list)
        assert isinstance(data["short_liquidations"], list)

    def test_liquidations_with_ensemble_model(self, client):
        """Test that ensemble model parameter works."""
        response = client.get("/liquidations/levels?symbol=BTCUSDT&model=ensemble")
        assert response.status_code == 200
