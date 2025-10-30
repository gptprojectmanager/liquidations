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


class TestLiquidationsWithRealData:
    """Tests for liquidations endpoint with real DuckDB data."""

    def test_liquidations_uses_real_open_interest_from_db(self, client):
        """Test that API fetches real Open Interest from DuckDB, not hardcoded mock."""
        response = client.get("/liquidations/levels?symbol=BTCUSDT&model=binance_standard")
        data = response.json()

        # With real data from sample CSV, current_price should match DB
        # and long_liquidations volumes should be calculated from real OI
        assert response.status_code == 200
        assert "current_price" in data

        # Check that we got real liquidations (not empty)
        assert len(data["long_liquidations"]) > 0
        assert len(data["short_liquidations"]) > 0

        # Verify volumes are calculated (not zero/mock)
        first_long = data["long_liquidations"][0]
        assert float(first_long["volume"]) > 0

    def test_levels_returns_longs_below_price_shorts_above(self, client):
        """Test that long liquidations are below current price, shorts above."""
        response = client.get("/liquidations/levels?symbol=BTCUSDT&model=binance_standard")
        data = response.json()

        current_price = float(data["current_price"])

        # All long liquidations should be BELOW current price
        for liq in data["long_liquidations"]:
            liq_price = float(liq["price_level"])
            assert liq_price < current_price, f"Long liq {liq_price} should be < {current_price}"

        # All short liquidations should be ABOVE current price
        for liq in data["short_liquidations"]:
            liq_price = float(liq["price_level"])
            assert liq_price > current_price, f"Short liq {liq_price} should be > {current_price}"

    def test_liquidations_include_leverage_tiers(self, client):
        """Test that liquidations include multiple leverage tiers."""
        response = client.get("/liquidations/levels?symbol=BTCUSDT&model=binance_standard")
        data = response.json()

        # Collect all leverage tiers
        leverage_tiers = set()
        for liq in data["long_liquidations"] + data["short_liquidations"]:
            leverage_tiers.add(liq["leverage"])

        # Should have multiple leverage tiers (5x, 10x, 25x, 50x, 100x)
        assert len(leverage_tiers) >= 3, (
            f"Expected ≥3 leverage tiers, got {len(leverage_tiers)}: {leverage_tiers}"
        )

    def test_invalid_symbol_returns_error(self, client):
        """Test that invalid symbol parameter returns error or empty response."""
        response = client.get("/liquidations/levels?symbol=INVALID&model=binance_standard")

        # API may return 200 with empty data or error status
        # Both are acceptable - just verify it doesn't crash
        assert response.status_code in [200, 400, 404], f"Unexpected status: {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            # If 200, should have structure (may be empty)
            assert "long_liquidations" in data
            assert "short_liquidations" in data


class TestHistoricalLiquidationsEndpoint:
    """Tests for /liquidations/history endpoint (T047)."""

    def test_history_returns_200_with_valid_params(self, client):
        """Test that history endpoint returns 200 with valid params."""
        response = client.get("/liquidations/history?symbol=BTCUSDT")
        assert response.status_code == 200

    def test_history_returns_list_of_records(self, client):
        """Test that history returns list of liquidation records from DB."""
        response = client.get("/liquidations/history?symbol=BTCUSDT")
        data = response.json()

        assert isinstance(data, list)
        # Should have at least some historical data from liquidation_history table
        assert len(data) > 0


class TestFrontendStaticFiles:
    """Tests for frontend static file serving."""

    def test_frontend_liquidation_map_html_is_served(self, client):
        """Test that frontend/liquidation_map.html is accessible via HTTP."""
        response = client.get("/frontend/liquidation_map.html")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
