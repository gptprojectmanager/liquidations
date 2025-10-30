"""
Tests for API endpoints in main.py.

Focus: Verify API response structure includes leverage tier information.
"""

import pytest
from fastapi.testclient import TestClient

from src.liquidationheatmap.api.main import app


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


def test_liquidation_levels_response_includes_leverage_field(client):
    """
    Test that /liquidations/levels API response includes 'leverage' field.

    This test SHOULD FAIL initially because the current implementation
    aggregates liquidations without preserving leverage tier.

    Expected behavior:
    - Each liquidation in long_liquidations should have 'leverage' field
    - Each liquidation in short_liquidations should have 'leverage' field
    - Leverage values should be one of: '10x', '25x', '50x', '100x'
    """
    # Act
    response = client.get("/liquidations/levels?symbol=BTCUSDT&model=binance_standard&timeframe=1")

    # Assert
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()

    # Verify structure
    assert "long_liquidations" in data, "Response missing long_liquidations"
    assert "short_liquidations" in data, "Response missing short_liquidations"

    # Check long liquidations have leverage field
    long_liqs = data["long_liquidations"]
    if len(long_liqs) > 0:
        first_long = long_liqs[0]
        assert "leverage" in first_long, (
            f"Long liquidation missing 'leverage' field. Keys: {first_long.keys()}"
        )
        assert first_long["leverage"] in ["10x", "25x", "50x", "100x"], (
            f"Invalid leverage value: {first_long['leverage']}"
        )

    # Check short liquidations have leverage field
    short_liqs = data["short_liquidations"]
    if len(short_liqs) > 0:
        first_short = short_liqs[0]
        assert "leverage" in first_short, (
            f"Short liquidation missing 'leverage' field. Keys: {first_short.keys()}"
        )
        assert first_short["leverage"] in ["10x", "25x", "50x", "100x"], (
            f"Invalid leverage value: {first_short['leverage']}"
        )
