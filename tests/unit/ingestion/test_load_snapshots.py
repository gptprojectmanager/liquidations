"""Unit tests for load_snapshots() method in DuckDBService.

TDD RED phase: Write tests first before implementation.

Tests for T033: Implement load_snapshots(symbol, start_time, end_time) method.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from src.liquidationheatmap.models.position import HeatmapSnapshot


class TestLoadSnapshots:
    """Tests for DuckDBService.load_snapshots() method."""

    def test_load_snapshots_returns_list_of_snapshots(self, tmp_path):
        """load_snapshots should return a list of HeatmapSnapshot objects."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            # Create and save a snapshot
            ts = datetime(2025, 11, 15, 12, 0, 0)
            snapshot = HeatmapSnapshot(timestamp=ts, symbol="BTCUSDT")
            cell = snapshot.get_cell(Decimal("95000"))
            cell.long_density = Decimal("1000")
            db.save_snapshot(snapshot)

            # Load snapshots
            start_time = datetime(2025, 11, 15, 0, 0, 0)
            end_time = datetime(2025, 11, 15, 23, 59, 59)
            result = db.load_snapshots("BTCUSDT", start_time, end_time)

            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], HeatmapSnapshot)

    def test_load_snapshots_filters_by_symbol(self, tmp_path):
        """load_snapshots should only return snapshots for requested symbol."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            ts = datetime(2025, 11, 15, 12, 0, 0)

            # Save BTCUSDT snapshot
            btc_snapshot = HeatmapSnapshot(timestamp=ts, symbol="BTCUSDT")
            btc_snapshot.get_cell(Decimal("95000")).long_density = Decimal("1000")
            db.save_snapshot(btc_snapshot)

            # Save ETHUSDT snapshot
            eth_snapshot = HeatmapSnapshot(timestamp=ts, symbol="ETHUSDT")
            eth_snapshot.get_cell(Decimal("3000")).long_density = Decimal("500")
            db.save_snapshot(eth_snapshot)

            # Load only BTCUSDT
            start_time = datetime(2025, 11, 15, 0, 0, 0)
            end_time = datetime(2025, 11, 15, 23, 59, 59)
            result = db.load_snapshots("BTCUSDT", start_time, end_time)

            assert len(result) == 1
            assert result[0].symbol == "BTCUSDT"

    def test_load_snapshots_filters_by_time_range(self, tmp_path):
        """load_snapshots should only return snapshots within time range."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            # Save snapshots at different times
            for hour in [10, 12, 14, 16]:
                ts = datetime(2025, 11, 15, hour, 0, 0)
                snapshot = HeatmapSnapshot(timestamp=ts, symbol="BTCUSDT")
                snapshot.get_cell(Decimal("95000")).long_density = Decimal("1000")
                db.save_snapshot(snapshot)

            # Load only 11:00-15:00 range (should get 12:00 and 14:00)
            start_time = datetime(2025, 11, 15, 11, 0, 0)
            end_time = datetime(2025, 11, 15, 15, 0, 0)
            result = db.load_snapshots("BTCUSDT", start_time, end_time)

            assert len(result) == 2
            hours = [s.timestamp.hour for s in result]
            assert 12 in hours
            assert 14 in hours

    def test_load_snapshots_includes_boundaries(self, tmp_path):
        """load_snapshots should include snapshots at exact boundary times."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            # Save snapshot at exact boundary
            ts = datetime(2025, 11, 15, 12, 0, 0)
            snapshot = HeatmapSnapshot(timestamp=ts, symbol="BTCUSDT")
            snapshot.get_cell(Decimal("95000")).long_density = Decimal("1000")
            db.save_snapshot(snapshot)

            # Load with exact timestamp as boundaries
            result = db.load_snapshots("BTCUSDT", ts, ts)

            assert len(result) == 1
            assert result[0].timestamp == ts

    def test_load_snapshots_reconstructs_cells(self, tmp_path):
        """load_snapshots should reconstruct HeatmapCell objects with correct densities."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            ts = datetime(2025, 11, 15, 12, 0, 0)
            snapshot = HeatmapSnapshot(timestamp=ts, symbol="BTCUSDT")

            # Multiple cells with different densities
            cell1 = snapshot.get_cell(Decimal("95000"))
            cell1.long_density = Decimal("1000000")
            cell1.short_density = Decimal("500000")

            cell2 = snapshot.get_cell(Decimal("96000"))
            cell2.long_density = Decimal("2000000")
            cell2.short_density = Decimal("750000")

            db.save_snapshot(snapshot)

            # Load and verify
            start_time = datetime(2025, 11, 15, 0, 0, 0)
            end_time = datetime(2025, 11, 15, 23, 59, 59)
            result = db.load_snapshots("BTCUSDT", start_time, end_time)

            assert len(result) == 1
            loaded = result[0]

            # Check cells are reconstructed
            assert len(loaded.cells) == 2

            # Check values (convert to float for comparison due to precision)
            loaded_cell1 = loaded.get_cell(Decimal("95000"))
            assert float(loaded_cell1.long_density) == pytest.approx(1000000, rel=1e-6)
            assert float(loaded_cell1.short_density) == pytest.approx(500000, rel=1e-6)

            loaded_cell2 = loaded.get_cell(Decimal("96000"))
            assert float(loaded_cell2.long_density) == pytest.approx(2000000, rel=1e-6)
            assert float(loaded_cell2.short_density) == pytest.approx(750000, rel=1e-6)

    def test_load_snapshots_returns_empty_list_when_no_data(self, tmp_path):
        """load_snapshots should return empty list when no matching data."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            # No data saved, query should return empty
            start_time = datetime(2025, 11, 15, 0, 0, 0)
            end_time = datetime(2025, 11, 15, 23, 59, 59)
            result = db.load_snapshots("BTCUSDT", start_time, end_time)

            assert result == []

    def test_load_snapshots_orders_by_timestamp(self, tmp_path):
        """load_snapshots should return snapshots ordered by timestamp ascending."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            # Save in non-chronological order
            for hour in [16, 10, 14, 12]:
                ts = datetime(2025, 11, 15, hour, 0, 0)
                snapshot = HeatmapSnapshot(timestamp=ts, symbol="BTCUSDT")
                snapshot.get_cell(Decimal("95000")).long_density = Decimal("1000")
                db.save_snapshot(snapshot)

            # Load all
            start_time = datetime(2025, 11, 15, 0, 0, 0)
            end_time = datetime(2025, 11, 15, 23, 59, 59)
            result = db.load_snapshots("BTCUSDT", start_time, end_time)

            # Should be ordered chronologically
            assert len(result) == 4
            timestamps = [s.timestamp for s in result]
            assert timestamps == sorted(timestamps)

    def test_load_snapshots_multiple_snapshots_at_different_timestamps(self, tmp_path):
        """load_snapshots should correctly group cells by timestamp."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            # Two snapshots at different times
            ts1 = datetime(2025, 11, 15, 12, 0, 0)
            snapshot1 = HeatmapSnapshot(timestamp=ts1, symbol="BTCUSDT")
            snapshot1.get_cell(Decimal("95000")).long_density = Decimal("1000")
            db.save_snapshot(snapshot1)

            ts2 = datetime(2025, 11, 15, 13, 0, 0)
            snapshot2 = HeatmapSnapshot(timestamp=ts2, symbol="BTCUSDT")
            snapshot2.get_cell(Decimal("96000")).short_density = Decimal("2000")
            db.save_snapshot(snapshot2)

            # Load both
            start_time = datetime(2025, 11, 15, 0, 0, 0)
            end_time = datetime(2025, 11, 15, 23, 59, 59)
            result = db.load_snapshots("BTCUSDT", start_time, end_time)

            assert len(result) == 2

            # First snapshot should have cell at 95000
            assert result[0].timestamp == ts1
            assert Decimal("95000") in result[0].cells

            # Second snapshot should have cell at 96000
            assert result[1].timestamp == ts2
            assert Decimal("96000") in result[1].cells
