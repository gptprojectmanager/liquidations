"""
API contract tests for /api/margin/tiers/{symbol} endpoint.

Tests tier information retrieval endpoint.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


class TestTiersAPI:
    """Test suite for tiers information API endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        return TestClient(app)

    def test_get_tiers_basic(self, client):
        """
        Test basic tier retrieval.

        GET /api/margin/tiers/BTCUSDT
        Should return all tiers for symbol.
        """
        response = client.get("/api/margin/tiers/BTCUSDT")

        assert response.status_code == 200
        data = response.json()

        assert "symbol" in data
        assert "tiers" in data
        assert data["symbol"] == "BTCUSDT"
        assert len(data["tiers"]) == 5  # Binance has 5 tiers

    def test_get_tiers_structure(self, client):
        """
        Test tier data structure.

        Each tier should have required fields.
        """
        response = client.get("/api/margin/tiers/BTCUSDT")
        tiers = response.json()["tiers"]

        for tier in tiers:
            assert "tier_number" in tier
            assert "min_notional" in tier
            assert "max_notional" in tier
            assert "margin_rate" in tier
            assert "maintenance_amount" in tier
            assert "max_leverage" in tier

    def test_get_tiers_invalid_symbol(self, client):
        """Test tier retrieval with invalid symbol."""
        response = client.get("/api/margin/tiers/INVALIDUSDT")

        assert response.status_code == 404

    def test_get_tiers_with_comparison(self, client):
        """
        Test tier retrieval with comparison table.

        GET /api/margin/tiers/BTCUSDT?format=comparison
        """
        response = client.get("/api/margin/tiers/BTCUSDT?format=comparison")

        assert response.status_code == 200
        data = response.json()

        assert "comparison_table" in data
