"""
Tests for FastAPI liquidation endpoints.

Following TDD approach.
"""

import pytest
from fastapi.testclient import TestClient


# Import will fail initially - this is expected (TDD RED)
@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    from src.api.main import app

    return TestClient(app)


class TestLiquidationsEndpoint:
    """Test suite for /liquidations/levels endpoint."""

    def test_get_liquidation_levels_default_leverages(self, client):
        """
        Test GET /liquidations/levels with default leverage levels.

        Should return liquidation data for default leverages [5, 10, 25, 50, 100, 125]
        """
        response = client.get("/liquidations/levels?entry_price=50000")

        assert response.status_code == 200

        data = response.json()
        assert "long_liquidations" in data
        assert "short_liquidations" in data

        # Default leverages should be 6 values
        assert len(data["long_liquidations"]) == 6
        assert len(data["short_liquidations"]) == 6

        # Check first long liquidation structure
        long_5x = data["long_liquidations"][0]
        assert long_5x["leverage"] == 5
        assert long_5x["position_type"] == "long"
        assert "liq_price" in long_5x
        assert "distance_percent" in long_5x
        assert "risk_level" in long_5x
