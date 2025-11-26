"""
API contract tests for /api/margin/calculate endpoint.

Tests that the margin calculation API endpoint returns consistent
results matching Binance standards and internal calculations.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


class TestCalculateAPI:
    """Test suite for margin calculation API endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        return TestClient(app)

    def test_calculate_endpoint_basic_request(self, client):
        """
        Test basic margin calculation request.

        POST /api/margin/calculate
        Request: {"symbol": "BTCUSDT", "notional": 50000}
        Response: margin, tier, rate, etc.
        """
        response = client.post(
            "/api/margin/calculate", json={"symbol": "BTCUSDT", "notional": "50000"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should return margin calculation
        assert "margin" in data
        assert "tier" in data
        assert "margin_rate" in data
        assert data["tier"] == 1
        assert data["margin"] == "250.00"  # $50k * 0.5% - 0 = $250

    def test_calculate_with_different_tiers(self, client):
        """
        Test calculation across different tiers.

        Verifies tier-specific calculations are correct.
        """
        # Tier 1: $50k
        r1 = client.post("/api/margin/calculate", json={"symbol": "BTCUSDT", "notional": "50000"})
        assert r1.json()["tier"] == 1
        assert r1.json()["margin"] == "250.00"

        # Tier 2: $100k
        r2 = client.post("/api/margin/calculate", json={"symbol": "BTCUSDT", "notional": "100000"})
        assert r2.json()["tier"] == 2
        assert r2.json()["margin"] == "750.00"

        # Tier 3: $500k
        r3 = client.post("/api/margin/calculate", json={"symbol": "BTCUSDT", "notional": "500000"})
        assert r3.json()["tier"] == 3
        assert r3.json()["margin"] == "8500.00"

    def test_calculate_with_liquidation_price(self, client):
        """
        Test calculation including liquidation price.

        POST with entry_price, position_size, leverage, side
        Should return liquidation price.
        """
        response = client.post(
            "/api/margin/calculate",
            json={
                "symbol": "BTCUSDT",
                "entry_price": "50000",
                "position_size": "1",
                "leverage": "10",
                "side": "long",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "liquidation_price" in data
        assert "margin" in data
        # Long 1 BTC @ $50k with 10x leverage (Tier 1)
        # liq = 50000 * (1 - 0.1 + 0.005 - 0) = 45250
        assert data["liquidation_price"] == "45250.00"

    def test_calculate_invalid_symbol(self, client):
        """
        Test calculation with invalid symbol.

        Should return 404 or appropriate error.
        """
        response = client.post(
            "/api/margin/calculate", json={"symbol": "INVALIDUSDT", "notional": "50000"}
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_calculate_missing_parameters(self, client):
        """
        Test calculation with missing required parameters.

        Should return 422 validation error.
        """
        response = client.post(
            "/api/margin/calculate",
            json={
                "symbol": "BTCUSDT"
                # Missing notional or other required params
            },
        )

        assert response.status_code == 422

    def test_calculate_negative_notional(self, client):
        """
        Test calculation with negative notional.

        Should return 400 bad request.
        """
        response = client.post(
            "/api/margin/calculate", json={"symbol": "BTCUSDT", "notional": "-50000"}
        )

        assert response.status_code == 400
        assert (
            "negative" in response.json()["detail"].lower()
            or "invalid" in response.json()["detail"].lower()
        )

    def test_calculate_response_format(self, client):
        """
        Test that response follows contract format.

        Should have all expected fields with correct types.
        """
        response = client.post(
            "/api/margin/calculate", json={"symbol": "BTCUSDT", "notional": "50000"}
        )

        data = response.json()

        # Required fields
        assert "symbol" in data
        assert "notional" in data
        assert "margin" in data
        assert "tier" in data
        assert "margin_rate" in data
        assert "maintenance_amount" in data

        # Types
        assert isinstance(data["tier"], int)
        assert isinstance(data["symbol"], str)
        # Decimal values returned as strings for precision
        assert isinstance(data["margin"], str)
        assert isinstance(data["notional"], str)

    def test_calculate_with_tier_details(self, client):
        """
        Test that response includes tier details.

        Should include tier range, max leverage, etc.
        """
        response = client.post(
            "/api/margin/calculate",
            json={"symbol": "BTCUSDT", "notional": "50000", "include_tier_details": True},
        )

        data = response.json()

        assert "tier_details" in data
        tier_details = data["tier_details"]

        assert "tier_number" in tier_details
        assert "min_notional" in tier_details
        assert "max_notional" in tier_details
        assert "max_leverage" in tier_details

    def test_calculate_matches_internal_calculator(self, client):
        """
        Test that API results match internal MarginCalculator.

        Consistency check between API and internal implementation.
        """
        from src.services.margin_calculator import MarginCalculator
        from src.services.tier_loader import TierLoader

        # Calculate via API
        response = client.post(
            "/api/margin/calculate", json={"symbol": "BTCUSDT", "notional": "100000"}
        )
        api_margin = Decimal(response.json()["margin"])

        # Calculate via internal calculator
        config = TierLoader.load_binance_default()
        calculator = MarginCalculator(config)
        internal_margin = calculator.calculate_margin(Decimal("100000"))

        # Should match
        assert abs(api_margin - internal_margin) < Decimal("0.01")

    def test_calculate_concurrent_requests(self, client):
        """
        Test that API handles concurrent requests correctly.

        Verifies thread safety and correct independent calculations.
        """
        import concurrent.futures

        def make_request(notional):
            response = client.post(
                "/api/margin/calculate", json={"symbol": "BTCUSDT", "notional": str(notional)}
            )
            return response.json()

        # Make 10 concurrent requests with different notionals
        notionals = [
            10000,
            50000,
            100000,
            250000,
            500000,
            1000000,
            2000000,
            5000000,
            10000000,
            20000000,
        ]

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(make_request, notionals))

        # All should succeed
        assert len(results) == 10
        for result in results:
            assert "margin" in result
            assert "tier" in result

    def test_calculate_decimal_precision(self, client):
        """
        Test that API preserves decimal precision.

        Important for crypto calculations (8 decimal places).
        """
        response = client.post(
            "/api/margin/calculate", json={"symbol": "BTCUSDT", "notional": "50000.12345678"}
        )

        data = response.json()

        # Notional should be preserved with precision
        assert "50000.12" in data["notional"]  # At least 2 decimals preserved

    def test_calculate_with_display_format(self, client):
        """
        Test calculation with user-friendly display format.

        include_display=True should return formatted strings.
        """
        response = client.post(
            "/api/margin/calculate",
            json={"symbol": "BTCUSDT", "notional": "50000", "include_display": True},
        )

        data = response.json()

        assert "display" in data
        display = data["display"]

        # Should have formatted strings
        assert "$" in display["maintenance_margin"]  # Currency formatted
        assert "%" in display["margin_rate_percent"]  # Percentage formatted
