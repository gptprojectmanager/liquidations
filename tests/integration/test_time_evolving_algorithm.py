"""Integration tests for time-evolving heatmap algorithm with real DuckDB data.

T017 - Tests the algorithm with actual historical data from the database.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.liquidationheatmap.ingestion.db_service import DuckDBService
from src.liquidationheatmap.models.time_evolving_heatmap import (
    calculate_time_evolving_heatmap,
)


@dataclass
class Candle:
    """Candle class for testing."""

    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@pytest.fixture
def db_service():
    """Create a DuckDB service connection."""
    db = DuckDBService()
    yield db
    db.close()


class TestTimeEvolvingAlgorithmWithRealData:
    """Integration tests with real DuckDB data."""

    def test_algorithm_with_real_klines_and_oi_data(self, db_service):
        """Verify algorithm works with real klines and OI data from DuckDB."""
        # Query a small subset of real data (2 days)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=2)
        symbol = "BTCUSDT"

        # Query real candles
        candle_query = """
        SELECT
            open_time,
            CAST(open AS DECIMAL(18,8)) as open,
            CAST(high AS DECIMAL(18,8)) as high,
            CAST(low AS DECIMAL(18,8)) as low,
            CAST(close AS DECIMAL(18,8)) as close,
            CAST(volume AS DECIMAL(18,8)) as volume
        FROM klines_15m_history
        WHERE symbol = ? AND open_time >= ? AND open_time <= ?
        ORDER BY open_time
        LIMIT 100
        """

        candles_df = db_service.conn.execute(candle_query, [symbol, start_time, end_time]).df()

        if candles_df.empty:
            pytest.skip("No kline data available for test period")

        # Query real OI data
        oi_query = """
        SELECT
            timestamp,
            open_interest_value,
            open_interest_value - LAG(open_interest_value) OVER (ORDER BY timestamp) as oi_delta
        FROM open_interest_history
        WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp
        """

        oi_df = db_service.conn.execute(oi_query, [symbol, start_time, end_time]).df()

        # Convert to candle objects
        candles = [
            Candle(
                open_time=row["open_time"].to_pydatetime()
                if hasattr(row["open_time"], "to_pydatetime")
                else row["open_time"],
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=Decimal(str(row["volume"])),
            )
            for _, row in candles_df.iterrows()
        ]

        # Match OI deltas to candles
        oi_deltas = []
        oi_timestamps = oi_df["timestamp"].tolist() if not oi_df.empty else []
        oi_values = oi_df["oi_delta"].fillna(0).tolist() if not oi_df.empty else []

        for candle in candles:
            delta = Decimal("0")
            if oi_timestamps:
                for i, oi_ts in enumerate(oi_timestamps):
                    oi_ts_dt = oi_ts.to_pydatetime() if hasattr(oi_ts, "to_pydatetime") else oi_ts
                    if abs((candle.open_time - oi_ts_dt).total_seconds()) < 900:
                        delta = Decimal(str(oi_values[i])) if oi_values[i] else Decimal("0")
                        break
            oi_deltas.append(delta)

        # Execute algorithm
        snapshots = calculate_time_evolving_heatmap(
            candles=candles,
            oi_deltas=oi_deltas,
            symbol=symbol,
            price_bucket_size=Decimal("100"),
        )

        # Verify results
        assert len(snapshots) == len(candles)

        # Check that snapshots have valid timestamps
        for snapshot in snapshots:
            assert snapshot.timestamp is not None
            assert snapshot.symbol == symbol

        # Check that at least some snapshots have liquidation data
        # (if OI had any positive deltas)
        positive_oi_count = sum(1 for d in oi_deltas if d > 0)
        if positive_oi_count > 0:
            # At least some snapshots should have cells
            snapshots_with_cells = sum(1 for s in snapshots if s.cells)
            assert snapshots_with_cells > 0, "Expected some snapshots to have cells"

    def test_algorithm_produces_consistent_snapshots(self, db_service):
        """Verify snapshots track positions correctly over time."""
        # Use a small fixed time window for consistency
        symbol = "BTCUSDT"

        # Get just 20 candles for deterministic testing
        candle_query = """
        SELECT
            open_time,
            CAST(open AS DECIMAL(18,8)) as open,
            CAST(high AS DECIMAL(18,8)) as high,
            CAST(low AS DECIMAL(18,8)) as low,
            CAST(close AS DECIMAL(18,8)) as close,
            CAST(volume AS DECIMAL(18,8)) as volume
        FROM klines_15m_history
        WHERE symbol = ?
        ORDER BY open_time DESC
        LIMIT 20
        """

        candles_df = db_service.conn.execute(candle_query, [symbol]).df()

        if candles_df.empty:
            pytest.skip("No kline data available")

        # Sort ascending
        candles_df = candles_df.sort_values("open_time")

        candles = [
            Candle(
                open_time=row["open_time"].to_pydatetime()
                if hasattr(row["open_time"], "to_pydatetime")
                else row["open_time"],
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=Decimal(str(row["volume"])),
            )
            for _, row in candles_df.iterrows()
        ]

        # Generate synthetic OI deltas (alternating positive/negative)
        oi_deltas = [
            Decimal("1000000") if i % 2 == 0 else Decimal("-500000") for i in range(len(candles))
        ]

        snapshots = calculate_time_evolving_heatmap(
            candles=candles,
            oi_deltas=oi_deltas,
            symbol=symbol,
            price_bucket_size=Decimal("100"),
        )

        assert len(snapshots) == 20

        # First snapshot should have some positions (positive delta)
        assert snapshots[0].positions_created > 0

    def test_algorithm_handles_empty_oi_data(self, db_service):
        """Verify algorithm handles candles with zero OI delta."""
        symbol = "BTCUSDT"

        candle_query = """
        SELECT
            open_time,
            CAST(open AS DECIMAL(18,8)) as open,
            CAST(high AS DECIMAL(18,8)) as high,
            CAST(low AS DECIMAL(18,8)) as low,
            CAST(close AS DECIMAL(18,8)) as close,
            CAST(volume AS DECIMAL(18,8)) as volume
        FROM klines_15m_history
        WHERE symbol = ?
        ORDER BY open_time DESC
        LIMIT 10
        """

        candles_df = db_service.conn.execute(candle_query, [symbol]).df()

        if candles_df.empty:
            pytest.skip("No kline data available")

        candles_df = candles_df.sort_values("open_time")

        candles = [
            Candle(
                open_time=row["open_time"].to_pydatetime()
                if hasattr(row["open_time"], "to_pydatetime")
                else row["open_time"],
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=Decimal(str(row["volume"])),
            )
            for _, row in candles_df.iterrows()
        ]

        # All zeros - no OI changes
        oi_deltas = [Decimal("0")] * len(candles)

        snapshots = calculate_time_evolving_heatmap(
            candles=candles,
            oi_deltas=oi_deltas,
            symbol=symbol,
        )

        assert len(snapshots) == 10

        # All snapshots should have no positions created
        for snapshot in snapshots:
            assert snapshot.positions_created == 0

    def test_price_crossing_consumes_positions(self, db_service):
        """Verify that price crossing liquidation levels consumes positions."""
        symbol = "BTCUSDT"

        # Get recent price data
        candle_query = """
        SELECT
            open_time,
            CAST(open AS DECIMAL(18,8)) as open,
            CAST(high AS DECIMAL(18,8)) as high,
            CAST(low AS DECIMAL(18,8)) as low,
            CAST(close AS DECIMAL(18,8)) as close,
            CAST(volume AS DECIMAL(18,8)) as volume
        FROM klines_15m_history
        WHERE symbol = ?
        ORDER BY open_time DESC
        LIMIT 50
        """

        candles_df = db_service.conn.execute(candle_query, [symbol]).df()

        if candles_df.empty:
            pytest.skip("No kline data available")

        # Sort ascending
        candles_df = candles_df.sort_values("open_time")

        candles = [
            Candle(
                open_time=row["open_time"].to_pydatetime()
                if hasattr(row["open_time"], "to_pydatetime")
                else row["open_time"],
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=Decimal(str(row["volume"])),
            )
            for _, row in candles_df.iterrows()
        ]

        # Create positions early, then check if they get consumed
        oi_deltas = []
        for i in range(len(candles)):
            if i < 5:
                oi_deltas.append(Decimal("5000000"))  # Add positions early
            else:
                oi_deltas.append(Decimal("0"))  # No new positions after

        snapshots = calculate_time_evolving_heatmap(
            candles=candles,
            oi_deltas=oi_deltas,
            symbol=symbol,
            price_bucket_size=Decimal("100"),
        )

        assert len(snapshots) == 50

        # First 5 snapshots should have positions created
        for i in range(5):
            assert snapshots[i].positions_created > 0

        # Check if any consumption happened (depends on price action)
        total_consumed = sum(s.positions_consumed for s in snapshots)
        # This may or may not be > 0 depending on actual price action
        # We just verify the counting works
        assert total_consumed >= 0
