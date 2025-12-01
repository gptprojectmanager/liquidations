#!/usr/bin/env python3
"""
Create pre-aggregated volume profile cache for fast OI-based calculations.

This pre-aggregates whale trades (>$500k) by day and price bin, making
30-day queries 100x faster (milliseconds instead of minutes).
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.liquidationheatmap.ingestion.db_service import DuckDBService


def create_volume_profile_cache():
    """Create volume_profile_daily table for fast aggregation."""

    with DuckDBService() as db:
        print("Creating volume_profile_daily table...")

        # Drop existing table
        db.conn.execute("DROP TABLE IF EXISTS volume_profile_daily")

        # Create pre-aggregated table
        # This groups whale trades by date and $500 price bins
        query = """
        CREATE TABLE volume_profile_daily AS
        SELECT
            symbol,
            DATE_TRUNC('day', timestamp) as trade_date,
            FLOOR(price / 500) * 500 AS price_bin,
            SUM(gross_value) as total_volume,
            COUNT(*) as trade_count
        FROM aggtrades_history
        WHERE gross_value >= 500000  -- Whale trades only
        GROUP BY symbol, trade_date, price_bin
        ORDER BY symbol, trade_date, price_bin
        """

        db.conn.execute(query)

        # Get row count
        result = db.conn.execute("SELECT COUNT(*) FROM volume_profile_daily").fetchone()
        print(f"✅ Created volume_profile_daily with {result[0]:,} rows")

        # Show sample
        sample = db.conn.execute("""
            SELECT * FROM volume_profile_daily
            WHERE symbol = 'BTCUSDT'
            ORDER BY trade_date DESC
            LIMIT 5
        """).df()

        print("\nSample data:")
        print(sample)


if __name__ == "__main__":
    create_volume_profile_cache()
