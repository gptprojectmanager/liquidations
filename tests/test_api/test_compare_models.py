"""Tests for /liquidations/compare-models endpoint (T040 - TDD RED)."""

from fastapi.testclient import TestClient

from src.liquidationheatmap.api.main import app

client = TestClient(app)


def test_compare_returns_all_three_models():
    """Test that compare-models endpoint returns all 3 models.

    Expected models:
    - binance_standard
    - funding_adjusted
    - ensemble
    """
    response = client.get("/liquidations/compare-models?symbol=BTCUSDT")

    assert response.status_code == 200
    data = response.json()

    assert "models" in data
    assert len(data["models"]) == 3

    model_names = [model["name"] for model in data["models"]]
    assert "binance_standard" in model_names
    assert "funding_adjusted" in model_names
    assert "ensemble" in model_names
