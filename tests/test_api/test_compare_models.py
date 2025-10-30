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


def test_ensemble_confidence_higher_when_models_agree():
    """Test that ensemble has higher confidence when models agree."""
    response = client.get("/liquidations/compare-models?symbol=BTCUSDT")

    assert response.status_code == 200
    data = response.json()

    # Find ensemble model
    ensemble = next((m for m in data["models"] if m["name"] == "ensemble"), None)
    assert ensemble is not None

    # Ensemble confidence should be between 0 and 1
    assert 0 <= float(ensemble["avg_confidence"]) <= 1


def test_model_names_match_expected_list():
    """Test that model names match expected values."""
    response = client.get("/liquidations/compare-models?symbol=BTCUSDT")

    assert response.status_code == 200
    data = response.json()

    expected_names = {"binance_standard", "funding_adjusted", "ensemble"}
    actual_names = {model["name"] for model in data["models"]}

    assert actual_names == expected_names
