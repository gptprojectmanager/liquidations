"""Integration tests for snapshot persistence round-trip.

Tests for T028: End-to-end save/load verification.

Tests the complete flow:
1. Create HeatmapSnapshot from time_evolving_heatmap algorithm
2. Save to DuckDB via save_snapshot()
3. Load from DuckDB via load_snapshots()
4. Verify data integrity and correctness
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.liquidationheatmap.models.position import HeatmapSnapshot


class TestSnapshotPersistenceRoundTrip:
    """Integration tests for snapshot save/load round-trip."""

    def test_save_load_round_trip_preserves_data(self, tmp_path):
        """Data saved should be identical when loaded back."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            # Create original snapshot with realistic data
            original_ts = datetime(2025, 11, 15, 12, 0, 0)
            original = HeatmapSnapshot(
                timestamp=original_ts,
                symbol="BTCUSDT",
            )

            # Add multiple cells with various densities
            price_levels = [
                (Decimal("94000"), Decimal("1500000"), Decimal("800000")),
                (Decimal("95000"), Decimal("2500000"), Decimal("1200000")),
                (Decimal("96000"), Decimal("1800000"), Decimal("2100000")),
                (Decimal("97000"), Decimal("900000"), Decimal("1600000")),
            ]

            for price, long_vol, short_vol in price_levels:
                cell = original.get_cell(price)
                cell.long_density = long_vol
                cell.short_density = short_vol

            # Save
            rows_saved = db.save_snapshot(original)
            assert rows_saved == 8  # 4 price levels x 2 sides

            # Load
            start = datetime(2025, 11, 15, 0, 0, 0)
            end = datetime(2025, 11, 15, 23, 59, 59)
            loaded_list = db.load_snapshots("BTCUSDT", start, end)

            assert len(loaded_list) == 1
            loaded = loaded_list[0]

            # Verify metadata
            assert loaded.timestamp == original_ts
            assert loaded.symbol == "BTCUSDT"
            assert len(loaded.cells) == 4

            # Verify each cell
            for price, long_vol, short_vol in price_levels:
                loaded_cell = loaded.get_cell(price)
                assert float(loaded_cell.long_density) == pytest.approx(float(long_vol), rel=1e-6)
                assert float(loaded_cell.short_density) == pytest.approx(float(short_vol), rel=1e-6)

    def test_time_range_filtering_accuracy(self, tmp_path):
        """Time range filtering should work accurately at boundaries."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            # Create 5 snapshots at 1-hour intervals
            base_time = datetime(2025, 11, 15, 10, 0, 0)
            snapshots_created = []

            for i in range(5):
                ts = base_time + timedelta(hours=i)
                snapshot = HeatmapSnapshot(timestamp=ts, symbol="BTCUSDT")
                snapshot.get_cell(Decimal("95000")).long_density = Decimal(str(1000 * (i + 1)))
                db.save_snapshot(snapshot)
                snapshots_created.append(ts)

            # Test various time ranges
            # 1. All snapshots
            loaded = db.load_snapshots(
                "BTCUSDT",
                base_time,
                base_time + timedelta(hours=4),
            )
            assert len(loaded) == 5

            # 2. First 3 snapshots (10:00, 11:00, 12:00)
            loaded = db.load_snapshots(
                "BTCUSDT",
                base_time,
                base_time + timedelta(hours=2),
            )
            assert len(loaded) == 3

            # 3. Middle snapshot only (12:00)
            loaded = db.load_snapshots(
                "BTCUSDT",
                base_time + timedelta(hours=2),
                base_time + timedelta(hours=2),
            )
            assert len(loaded) == 1
            assert loaded[0].timestamp == base_time + timedelta(hours=2)

            # 4. Last 2 snapshots (13:00, 14:00)
            loaded = db.load_snapshots(
                "BTCUSDT",
                base_time + timedelta(hours=3),
                base_time + timedelta(hours=4),
            )
            assert len(loaded) == 2

            # 5. Empty range (before any data)
            loaded = db.load_snapshots(
                "BTCUSDT",
                base_time - timedelta(hours=2),
                base_time - timedelta(hours=1),
            )
            assert len(loaded) == 0

    def test_multi_symbol_isolation(self, tmp_path):
        """Snapshots for different symbols should be isolated."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            ts = datetime(2025, 11, 15, 12, 0, 0)

            # Save snapshots for multiple symbols
            symbols_data = [
                ("BTCUSDT", Decimal("95000"), Decimal("5000000")),
                ("ETHUSDT", Decimal("3200"), Decimal("2000000")),
                ("SOLUSDT", Decimal("150"), Decimal("500000")),
            ]

            for symbol, price, volume in symbols_data:
                snapshot = HeatmapSnapshot(timestamp=ts, symbol=symbol)
                snapshot.get_cell(price).long_density = volume
                db.save_snapshot(snapshot)

            # Verify each symbol loads only its own data
            start = datetime(2025, 11, 15, 0, 0, 0)
            end = datetime(2025, 11, 15, 23, 59, 59)

            for symbol, expected_price, expected_volume in symbols_data:
                loaded = db.load_snapshots(symbol, start, end)
                assert len(loaded) == 1
                assert loaded[0].symbol == symbol
                assert expected_price in loaded[0].cells

                cell = loaded[0].get_cell(expected_price)
                assert float(cell.long_density) == pytest.approx(float(expected_volume), rel=1e-6)

    def test_snapshot_update_overwrites_previous(self, tmp_path):
        """Saving snapshot with same timestamp should update (not duplicate)."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            ts = datetime(2025, 11, 15, 12, 0, 0)

            # Save initial snapshot
            snapshot1 = HeatmapSnapshot(timestamp=ts, symbol="BTCUSDT")
            snapshot1.get_cell(Decimal("95000")).long_density = Decimal("1000000")
            db.save_snapshot(snapshot1)

            # Save updated snapshot at same timestamp
            snapshot2 = HeatmapSnapshot(timestamp=ts, symbol="BTCUSDT")
            snapshot2.get_cell(Decimal("95000")).long_density = Decimal("2000000")
            db.save_snapshot(snapshot2)

            # Load and verify only updated value exists
            start = datetime(2025, 11, 15, 0, 0, 0)
            end = datetime(2025, 11, 15, 23, 59, 59)
            loaded = db.load_snapshots("BTCUSDT", start, end)

            assert len(loaded) == 1
            cell = loaded[0].get_cell(Decimal("95000"))
            assert float(cell.long_density) == pytest.approx(2000000, rel=1e-6)

    def test_large_snapshot_persistence(self, tmp_path):
        """Should handle snapshots with many price levels efficiently."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            ts = datetime(2025, 11, 15, 12, 0, 0)

            # Create snapshot with many price levels (simulating dense heatmap)
            snapshot = HeatmapSnapshot(timestamp=ts, symbol="BTCUSDT")

            num_levels = 100
            base_price = Decimal("90000")

            for i in range(num_levels):
                price = base_price + Decimal(str(i * 100))  # 100 USDT bins
                cell = snapshot.get_cell(price)
                cell.long_density = Decimal(str(1000000 + i * 10000))
                cell.short_density = Decimal(str(500000 + i * 5000))

            # Save and verify
            rows_saved = db.save_snapshot(snapshot)
            assert rows_saved == num_levels * 2  # Both sides

            # Load and verify
            start = datetime(2025, 11, 15, 0, 0, 0)
            end = datetime(2025, 11, 15, 23, 59, 59)
            loaded = db.load_snapshots("BTCUSDT", start, end)

            assert len(loaded) == 1
            assert len(loaded[0].cells) == num_levels

    def test_persistence_across_connection_close(self, tmp_path):
        """Data should persist after closing and reopening database."""
        from src.liquidationheatmap.ingestion.db_service import DuckDBService

        db_path = tmp_path / "test.duckdb"

        ts = datetime(2025, 11, 15, 12, 0, 0)

        # First connection: save data
        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            snapshot = HeatmapSnapshot(timestamp=ts, symbol="BTCUSDT")
            snapshot.get_cell(Decimal("95000")).long_density = Decimal("1234567")
            db.save_snapshot(snapshot)

        # Second connection: verify data persisted
        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            start = datetime(2025, 11, 15, 0, 0, 0)
            end = datetime(2025, 11, 15, 23, 59, 59)
            loaded = db.load_snapshots("BTCUSDT", start, end)

            assert len(loaded) == 1
            cell = loaded[0].get_cell(Decimal("95000"))
            assert float(cell.long_density) == pytest.approx(1234567, rel=1e-6)


class TestSnapshotPersistenceWithTimeEvolvingHeatmap:
    """Integration tests using real time_evolving_heatmap output."""

    def test_save_load_time_evolving_snapshot(self, tmp_path):
        """Snapshots from time_evolving_heatmap should persist correctly."""
        from dataclasses import dataclass
        from datetime import datetime
        from decimal import Decimal

        from src.liquidationheatmap.ingestion.db_service import DuckDBService
        from src.liquidationheatmap.models.time_evolving_heatmap import (
            calculate_time_evolving_heatmap,
        )

        # Create mock candles
        @dataclass
        class MockCandle:
            open_time: datetime
            open: Decimal
            high: Decimal
            low: Decimal
            close: Decimal

        candles = [
            MockCandle(
                open_time=datetime(2025, 11, 15, 12, 0, 0),
                open=Decimal("95000"),
                high=Decimal("95500"),
                low=Decimal("94800"),
                close=Decimal("95300"),
            ),
            MockCandle(
                open_time=datetime(2025, 11, 15, 12, 5, 0),
                open=Decimal("95300"),
                high=Decimal("95800"),
                low=Decimal("95100"),
                close=Decimal("95600"),
            ),
        ]

        # OI deltas (positive = new positions)
        oi_deltas = [
            Decimal("10000000"),  # $10M new positions
            Decimal("5000000"),  # $5M new positions
        ]

        # Calculate snapshots
        snapshots = calculate_time_evolving_heatmap(
            candles=candles,
            oi_deltas=oi_deltas,
            symbol="BTCUSDT",
            price_bucket_size=Decimal("100"),
        )

        assert len(snapshots) == 2

        # Save to database
        db_path = tmp_path / "test.duckdb"

        with DuckDBService(str(db_path)) as db:
            db.initialize_snapshot_tables()

            for snapshot in snapshots:
                db.save_snapshot(snapshot)

            # Load and verify
            start = datetime(2025, 11, 15, 0, 0, 0)
            end = datetime(2025, 11, 15, 23, 59, 59)
            loaded = db.load_snapshots("BTCUSDT", start, end)

            assert len(loaded) == 2

            # Verify timestamps match
            original_timestamps = [s.timestamp for s in snapshots]
            loaded_timestamps = [s.timestamp for s in loaded]
            assert original_timestamps == loaded_timestamps

            # Verify both snapshots have cells with data
            for loaded_snapshot in loaded:
                assert len(loaded_snapshot.cells) > 0
                # At least one cell should have non-zero volume
                total_vol = sum(
                    c.long_density + c.short_density for c in loaded_snapshot.cells.values()
                )
                assert total_vol > 0
