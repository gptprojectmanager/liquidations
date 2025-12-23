"""Integration tests for heatmap-timeseries API endpoint.

T037 - Tests for full API response matching openapi.yaml schema.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.liquidationheatmap.api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHeatmapTimeseriesAPIIntegration:
    """T037 - Integration tests for /liquidations/heatmap-timeseries endpoint."""

    def test_endpoint_returns_valid_json_structure(self, client):
        """Verify endpoint returns JSON matching openapi.yaml schema."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "interval": "15m",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify top-level structure per openapi.yaml
        assert "data" in data
        assert "meta" in data
        assert isinstance(data["data"], list)
        assert isinstance(data["meta"], dict)

    def test_meta_contains_required_fields(self, client):
        """Verify meta object contains all required fields per openapi.yaml."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "interval": "15m",
            },
        )

        assert response.status_code == 200
        meta = response.json()["meta"]

        # Required fields per openapi.yaml
        assert "symbol" in meta
        assert "start_time" in meta
        assert "end_time" in meta
        assert "interval" in meta
        assert "total_snapshots" in meta
        assert "price_range" in meta
        assert "total_long_volume" in meta
        assert "total_short_volume" in meta
        assert "total_consumed" in meta

        # Verify types
        assert meta["symbol"] == "BTCUSDT"
        assert meta["interval"] == "15m"
        assert isinstance(meta["total_snapshots"], int)
        assert isinstance(meta["price_range"], dict)
        assert "min" in meta["price_range"]
        assert "max" in meta["price_range"]

    def test_snapshot_contains_required_fields(self, client):
        """Verify each snapshot contains required fields per openapi.yaml."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "interval": "15m",
            },
        )

        assert response.status_code == 200
        data = response.json()["data"]

        # Check first snapshot if any exist
        if len(data) > 0:
            snapshot = data[0]

            # Required fields per HeatmapSnapshot schema
            assert "timestamp" in snapshot
            assert "levels" in snapshot
            assert "positions_created" in snapshot
            assert "positions_consumed" in snapshot

            # Verify types
            assert isinstance(snapshot["levels"], list)
            assert isinstance(snapshot["positions_created"], int)
            assert isinstance(snapshot["positions_consumed"], int)

    def test_level_contains_required_fields(self, client):
        """Verify each level contains required fields per openapi.yaml."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "interval": "15m",
            },
        )

        assert response.status_code == 200
        data = response.json()["data"]

        # Find a snapshot with levels
        for snapshot in data:
            if snapshot["levels"]:
                level = snapshot["levels"][0]

                # Required fields per HeatmapLevel schema
                assert "price" in level
                assert "long_density" in level
                assert "short_density" in level

                # Verify types
                assert isinstance(level["price"], (int, float))
                assert isinstance(level["long_density"], (int, float))
                assert isinstance(level["short_density"], (int, float))
                break

    def test_time_range_parameters_work(self, client):
        """Verify start_time and end_time parameters are respected."""
        # Request a specific time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=1)

        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "interval": "15m",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            },
        )

        assert response.status_code == 200
        meta = response.json()["meta"]

        # Verify time range is reflected in meta
        assert meta["start_time"] is not None
        assert meta["end_time"] is not None

    def test_different_intervals_work(self, client):
        """Verify all supported intervals work correctly."""
        intervals = ["5m", "15m", "1h", "4h"]

        for interval in intervals:
            response = client.get(
                "/liquidations/heatmap-timeseries",
                params={
                    "symbol": "BTCUSDT",
                    "interval": interval,
                },
            )

            assert response.status_code == 200, f"Failed for interval {interval}"
            meta = response.json()["meta"]
            assert meta["interval"] == interval

    def test_price_bin_size_parameter_works(self, client):
        """Verify price_bin_size parameter is accepted."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "interval": "15m",
                "price_bin_size": 200,
            },
        )

        assert response.status_code == 200

    def test_leverage_weights_parameter_works(self, client):
        """Verify leverage_weights parameter is accepted and parsed."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "interval": "15m",
                "leverage_weights": "5:20,10:35,25:25,50:15,100:5",
            },
        )

        assert response.status_code == 200

    def test_invalid_symbol_returns_400(self, client):
        """Verify invalid symbol returns 400 error."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "INVALID",
                "interval": "15m",
            },
        )

        assert response.status_code == 400
        assert "detail" in response.json()

    def test_invalid_leverage_weights_returns_400(self, client):
        """Verify invalid leverage_weights format returns 400."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "interval": "15m",
                "leverage_weights": "invalid:format",
            },
        )

        assert response.status_code == 400

    def test_snapshots_ordered_by_timestamp(self, client):
        """Verify snapshots are returned in chronological order."""
        response = client.get(
            "/liquidations/heatmap-timeseries",
            params={
                "symbol": "BTCUSDT",
                "interval": "15m",
            },
        )

        assert response.status_code == 200
        data = response.json()["data"]

        if len(data) > 1:
            timestamps = [s["timestamp"] for s in data]
            assert timestamps == sorted(timestamps), "Snapshots not in chronological order"
