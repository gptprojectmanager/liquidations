"""Unit tests for save_snapshot() method in DuckDBService.

TDD RED phase: Write tests first before implementation.

Tests for T032: Implement save_snapshot(snapshot) method.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from src.liquidationheatmap.models.position import HeatmapSnapshot


class TestSaveSnapshot:
    """Tests for DuckDBService.save_snapshot() method."""

    def test_save_snapshot_creates_rows_for_each_cell(self, tmp_path):
        """save_snapshot should insert one row per cell in the snapshot."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            # Create a snapshot with multiple cells
            snapshot = HeatmapSnapshot(
                timestamp=datetime(2025, 11, 15, 12, 0, 0),
                symbol="BTCUSDT",
            )
            # Add cells
            cell1 = snapshot.get_cell(Decimal("95000"))
            cell1.long_density = Decimal("1000000")
            cell1.short_density = Decimal("500000")

            cell2 = snapshot.get_cell(Decimal("96000"))
            cell2.long_density = Decimal("2000000")
            cell2.short_density = Decimal("0")

            # Save snapshot
            db.save_snapshot(snapshot)

            # Verify rows created
            count = db.conn.execute("""
                SELECT COUNT(*) FROM liquidation_snapshots
                WHERE symbol = 'BTCUSDT'
            """).fetchone()[0]

            # 2 cells x 2 sides (long, short) = 4 rows
            # But cells with 0 density should be skipped
            assert count == 3  # 2 longs + 1 short (0 density skipped)

    def test_save_snapshot_stores_correct_volumes(self, tmp_path):
        """save_snapshot should store long_density and short_density correctly."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            snapshot = HeatmapSnapshot(
                timestamp=datetime(2025, 11, 15, 12, 0, 0),
                symbol="BTCUSDT",
            )
            cell = snapshot.get_cell(Decimal("95000"))
            cell.long_density = Decimal("1234567.89")
            cell.short_density = Decimal("9876543.21")

            db.save_snapshot(snapshot)

            # Query long side
            long_row = db.conn.execute("""
                SELECT active_volume FROM liquidation_snapshots
                WHERE symbol = 'BTCUSDT' AND price_bucket = 95000 AND side = 'long'
            """).fetchone()

            assert long_row is not None
            assert float(long_row[0]) == pytest.approx(1234567.89, rel=1e-6)

            # Query short side
            short_row = db.conn.execute("""
                SELECT active_volume FROM liquidation_snapshots
                WHERE symbol = 'BTCUSDT' AND price_bucket = 95000 AND side = 'short'
            """).fetchone()

            assert short_row is not None
            assert float(short_row[0]) == pytest.approx(9876543.21, rel=1e-6)

    def test_save_snapshot_stores_timestamp_correctly(self, tmp_path):
        """save_snapshot should store the snapshot timestamp."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            target_ts = datetime(2025, 11, 15, 14, 30, 45)
            snapshot = HeatmapSnapshot(
                timestamp=target_ts,
                symbol="BTCUSDT",
            )
            cell = snapshot.get_cell(Decimal("95000"))
            cell.long_density = Decimal("1000")

            db.save_snapshot(snapshot)

            row = db.conn.execute("""
                SELECT timestamp FROM liquidation_snapshots LIMIT 1
            """).fetchone()

            assert row[0] == target_ts

    def test_save_snapshot_handles_unique_constraint_gracefully(self, tmp_path):
        """save_snapshot should handle duplicate inserts gracefully (upsert or ignore)."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            snapshot = HeatmapSnapshot(
                timestamp=datetime(2025, 11, 15, 12, 0, 0),
                symbol="BTCUSDT",
            )
            cell = snapshot.get_cell(Decimal("95000"))
            cell.long_density = Decimal("1000")

            # Save twice - should not raise
            db.save_snapshot(snapshot)

            # Second save with different value - should update or ignore
            cell.long_density = Decimal("2000")
            db.save_snapshot(snapshot)  # Should not raise

            # Verify only one row exists (upsert behavior preferred)
            count = db.conn.execute("""
                SELECT COUNT(*) FROM liquidation_snapshots
                WHERE symbol = 'BTCUSDT' AND price_bucket = 95000 AND side = 'long'
            """).fetchone()[0]

            assert count == 1

    def test_save_snapshot_skips_zero_volume_cells(self, tmp_path):
        """save_snapshot should not create rows for zero-volume cells."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            snapshot = HeatmapSnapshot(
                timestamp=datetime(2025, 11, 15, 12, 0, 0),
                symbol="BTCUSDT",
            )
            # Cell with zero density
            cell = snapshot.get_cell(Decimal("95000"))
            cell.long_density = Decimal("0")
            cell.short_density = Decimal("0")

            db.save_snapshot(snapshot)

            count = db.conn.execute("""
                SELECT COUNT(*) FROM liquidation_snapshots
            """).fetchone()[0]

            assert count == 0

    def test_save_snapshot_returns_row_count(self, tmp_path):
        """save_snapshot should return the number of rows inserted."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            snapshot = HeatmapSnapshot(
                timestamp=datetime(2025, 11, 15, 12, 0, 0),
                symbol="BTCUSDT",
            )
            cell = snapshot.get_cell(Decimal("95000"))
            cell.long_density = Decimal("1000")
            cell.short_density = Decimal("2000")

            rows_inserted = db.save_snapshot(snapshot)

            assert rows_inserted == 2

    def test_save_empty_snapshot_returns_zero(self, tmp_path):
        """save_snapshot with no cells should return 0."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            snapshot = HeatmapSnapshot(
                timestamp=datetime(2025, 11, 15, 12, 0, 0),
                symbol="BTCUSDT",
            )
            # No cells added

            rows_inserted = db.save_snapshot(snapshot)

            assert rows_inserted == 0
