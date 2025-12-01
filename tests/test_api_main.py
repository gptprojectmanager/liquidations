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
        assert first_long["leverage"] in ["5x", "10x", "25x", "50x", "100x"], (
            f"Invalid leverage value: {first_long['leverage']}"
        )

    # Check short liquidations have leverage field
    short_liqs = data["short_liquidations"]
    if len(short_liqs) > 0:
        first_short = short_liqs[0]
        assert "leverage" in first_short, (
            f"Short liquidation missing 'leverage' field. Keys: {first_short.keys()}"
        )
        assert first_short["leverage"] in ["5x", "10x", "25x", "50x", "100x"], (
            f"Invalid leverage value: {first_short['leverage']}"
        )


def test_api_uses_dynamic_binning_for_btc_range(client):
    """
    Test that /liquidations/levels uses dynamic binning instead of fixed $100.

    This test verifies the py-liquidation-map dynamic binning algorithm:
    - tick_degits = 2 - ceil(log10(price_range))
    - bin_size = 10^(-tick_degits)

    For actual BTC data with ~$24k price range ($102k-$126k):
    - Expected: $1000 bins (dynamic algorithm)
    - Old behavior: $100 bins (hardcoded)

    We verify this by checking the spacing between consecutive price levels
    is NOT the old hardcoded $100.
    """
    # Act
    response = client.get("/liquidations/levels?symbol=BTCUSDT&model=binance_standard&timeframe=1")

    # Assert
    assert response.status_code == 200
    data = response.json()

    # Get price levels from short liquidations (above current price)
    short_liqs = data["short_liquidations"]

    if len(short_liqs) >= 2:
        # Extract price levels and sort them
        price_levels = sorted([float(liq["price_level"]) for liq in short_liqs])

        # Calculate spacing between consecutive bins (should be consistent)
        spacings = [price_levels[i + 1] - price_levels[i] for i in range(len(price_levels) - 1)]

        # Get most common spacing (mode)
        from collections import Counter

        if spacings:
            spacing_counts = Counter(spacings)
            most_common_spacing = spacing_counts.most_common(1)[0][0]

            # Verify NOT using old hardcoded $100 bins
            # Actual data has ~$24k range, so dynamic binning gives $1000
            assert most_common_spacing != 100.0, (
                f"Still using hardcoded $100 bins. "
                f"Expected dynamic binning (got {most_common_spacing})"
            )

            # Verify bins are larger than $100 (appropriate for large range)
            assert most_common_spacing > 100.0, (
                f"Bin spacing {most_common_spacing} too small for ~$24k price range"
            )
