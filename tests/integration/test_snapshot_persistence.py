"""Integration tests for snapshot persistence.

T028 - Tests for saving and loading snapshots from DuckDB.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.liquidationheatmap.ingestion.db_service import DuckDBService
from src.liquidationheatmap.models.position import HeatmapSnapshot


@pytest.fixture
def db_service():
    """Create a DuckDB service connection for testing."""
    db = DuckDBService()
    db.ensure_snapshot_tables()
    yield db
    db.close()


class TestSnapshotPersistence:
    """T028 - Integration tests for snapshot persistence."""

    def test_save_and_load_snapshot(self, db_service):
        """Verify snapshot can be saved and loaded correctly."""
        # Create a test snapshot
        test_time = datetime(2025, 12, 1, 12, 0, 0)
        snapshot = HeatmapSnapshot(
            timestamp=test_time,
            symbol="BTCUSDT",
        )

        # Add some cells
        cell1 = snapshot.get_cell(Decimal("95000"))
        cell1.long_density = Decimal("1000000")
        cell1.short_density = Decimal("0")

        cell2 = snapshot.get_cell(Decimal("100000"))
        cell2.long_density = Decimal("0")
        cell2.short_density = Decimal("2000000")

        # Save the snapshot
        db_service.save_snapshot(snapshot)

        # Load the snapshots
        loaded = db_service.load_snapshots(
            symbol="BTCUSDT",
            start_time=test_time - timedelta(hours=1),
            end_time=test_time + timedelta(hours=1),
        )

        # Verify loaded data
        assert len(loaded) == 1
        assert loaded[0]["symbol"] == "BTCUSDT"
        assert len(loaded[0]["cells"]) == 2  # Two cells saved

        # Cleanup
        db_service.conn.execute(
            "DELETE FROM liquidation_snapshots WHERE symbol = 'BTCUSDT' AND timestamp = ?",
            [test_time],
        )

    def test_save_multiple_snapshots(self, db_service):
        """Verify multiple snapshots can be saved and loaded in order."""
        base_time = datetime(2025, 12, 1, 12, 0, 0)

        # Create and save 3 snapshots
        for i in range(3):
            snapshot = HeatmapSnapshot(
                timestamp=base_time + timedelta(minutes=15 * i),
                symbol="BTCUSDT",
            )
            cell = snapshot.get_cell(Decimal("95000"))
            cell.long_density = Decimal(str(1000000 * (i + 1)))
            db_service.save_snapshot(snapshot)

        # Load all snapshots
        loaded = db_service.load_snapshots(
            symbol="BTCUSDT",
            start_time=base_time - timedelta(hours=1),
            end_time=base_time + timedelta(hours=1),
        )

        # Verify order and count
        assert len(loaded) == 3

        # Verify timestamps are in order
        timestamps = [snap["timestamp"] for snap in loaded]
        assert timestamps == sorted(timestamps)

        # Cleanup
        db_service.conn.execute(
            "DELETE FROM liquidation_snapshots WHERE symbol = 'BTCUSDT' AND timestamp >= ? AND timestamp <= ?",
            [base_time - timedelta(hours=1), base_time + timedelta(hours=1)],
        )

    def test_load_empty_range_returns_empty_list(self, db_service):
        """Verify empty time range returns empty list."""
        # Load from a time range with no data
        loaded = db_service.load_snapshots(
            symbol="BTCUSDT",
            start_time=datetime(2020, 1, 1),
            end_time=datetime(2020, 1, 2),
        )

        assert loaded == []

    def test_load_wrong_symbol_returns_empty_list(self, db_service):
        """Verify loading with wrong symbol returns empty list."""
        # Save a snapshot for BTCUSDT
        test_time = datetime(2025, 12, 1, 12, 0, 0)
        snapshot = HeatmapSnapshot(
            timestamp=test_time,
            symbol="BTCUSDT",
        )
        cell = snapshot.get_cell(Decimal("95000"))
        cell.long_density = Decimal("1000000")
        db_service.save_snapshot(snapshot)

        # Try to load for ETHUSDT
        loaded = db_service.load_snapshots(
            symbol="ETHUSDT",
            start_time=test_time - timedelta(hours=1),
            end_time=test_time + timedelta(hours=1),
        )

        assert loaded == []

        # Cleanup
        db_service.conn.execute(
            "DELETE FROM liquidation_snapshots WHERE symbol = 'BTCUSDT' AND timestamp = ?",
            [test_time],
        )

    def test_snapshot_preserves_long_and_short_densities(self, db_service):
        """Verify both long and short densities are preserved."""
        test_time = datetime(2025, 12, 1, 12, 0, 0)
        snapshot = HeatmapSnapshot(
            timestamp=test_time,
            symbol="BTCUSDT",
        )

        # Add cell with both long and short densities
        cell = snapshot.get_cell(Decimal("97500"))
        cell.long_density = Decimal("500000")
        cell.short_density = Decimal("750000")

        db_service.save_snapshot(snapshot)

        # Load and verify
        loaded = db_service.load_snapshots(
            symbol="BTCUSDT",
            start_time=test_time - timedelta(hours=1),
            end_time=test_time + timedelta(hours=1),
        )

        assert len(loaded) == 1
        cells = loaded[0]["cells"]

        # Should have 2 rows (one for long, one for short)
        assert len(cells) == 2

        long_cell = next((c for c in cells if c["side"] == "long"), None)
        short_cell = next((c for c in cells if c["side"] == "short"), None)

        assert long_cell is not None
        assert short_cell is not None
        assert float(long_cell["active_volume"]) == 500000.0
        assert float(short_cell["active_volume"]) == 750000.0

        # Cleanup
        db_service.conn.execute(
            "DELETE FROM liquidation_snapshots WHERE symbol = 'BTCUSDT' AND timestamp = ?",
            [test_time],
        )
