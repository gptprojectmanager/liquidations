#!/usr/bin/env python3
"""Initialize DuckDB database with schema from data-model.md.

Creates 5 tables:
- liquidation_levels: Calculated liquidation prices
- heatmap_cache: Pre-aggregated heatmap buckets
- open_interest_history: Binance Open Interest data
- funding_rate_history: 8-hour funding rates
- liquidation_history: Actual liquidation events (for backtesting)
"""

import sys
from pathlib import Path

import duckdb

DB_PATH = "data/processed/liquidations.duckdb"


def create_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create all tables and indexes."""

    # Table 1: liquidation_levels
    conn.execute("""
        CREATE TABLE IF NOT EXISTS liquidation_levels (
            id BIGINT PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            model VARCHAR(50) NOT NULL,
            price_level DECIMAL(18, 2) NOT NULL,
            liquidation_volume DECIMAL(18, 8) NOT NULL,
            leverage_tier VARCHAR(10),
            side VARCHAR(10) NOT NULL,
            confidence DECIMAL(3, 2) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_liquidation_levels_timestamp
        ON liquidation_levels(timestamp);
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_liquidation_levels_symbol_model
        ON liquidation_levels(symbol, model);
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_liquidation_levels_price
        ON liquidation_levels(price_level);
    """)

    print("✅ Created table: liquidation_levels (with 3 indexes)")

    # Table 2: heatmap_cache
    conn.execute("""
        CREATE TABLE IF NOT EXISTS heatmap_cache (
            id BIGINT PRIMARY KEY,
            time_bucket TIMESTAMP NOT NULL,
            price_bucket DECIMAL(18, 2) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            model VARCHAR(50) NOT NULL,
            density BIGINT NOT NULL,
            volume DECIMAL(18, 8) NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_heatmap_time_price
        ON heatmap_cache(time_bucket, price_bucket);
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_heatmap_symbol_model
        ON heatmap_cache(symbol, model);
    """)

    print("✅ Created table: heatmap_cache (with 2 indexes)")

    # Table 3: open_interest_history
    conn.execute("""
        CREATE TABLE IF NOT EXISTS open_interest_history (
            id BIGINT PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            open_interest_value DECIMAL(20, 8) NOT NULL,
            open_interest_contracts DECIMAL(18, 8),
            source VARCHAR(50) DEFAULT 'binance_csv'
        );
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_oi_timestamp_symbol
        ON open_interest_history(timestamp, symbol);
    """)

    print("✅ Created table: open_interest_history (with 1 index)")

    # Table 4: funding_rate_history
    conn.execute("""
        CREATE TABLE IF NOT EXISTS funding_rate_history (
            id BIGINT PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            funding_rate DECIMAL(10, 8) NOT NULL,
            funding_interval_hours INT DEFAULT 8
        );
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_funding_timestamp_symbol
        ON funding_rate_history(timestamp, symbol);
    """)

    print("✅ Created table: funding_rate_history (with 1 index)")

    # Table 5: aggtrades_history
    conn.execute("""
        CREATE TABLE IF NOT EXISTS aggtrades_history (
            id BIGINT PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            price DECIMAL(18, 8) NOT NULL,
            quantity DECIMAL(18, 8) NOT NULL,
            side VARCHAR(4) NOT NULL,
            gross_value DOUBLE NOT NULL
        );
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_aggtrades_timestamp_symbol
        ON aggtrades_history(timestamp, symbol);
    """)

    print("✅ Created table: aggtrades_history (with 1 index)")


def verify_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Verify all tables exist."""
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]

    expected_tables = [
        "liquidation_levels",
        "heatmap_cache",
        "open_interest_history",
        "funding_rate_history",
    ]

    print("\n📊 Database Schema:")
    for table in expected_tables:
        if table in table_names:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  ✅ {table}: {count} rows")
        else:
            print(f"  ❌ {table}: NOT FOUND")
            sys.exit(1)


def main():
    """Initialize database schema."""
    # Ensure data directory exists
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    print(f"📥 Initializing database: {DB_PATH}")

    # Connect and create schema
    conn = duckdb.connect(DB_PATH)

    try:
        create_schema(conn)
        verify_schema(conn)
        print(f"\n✅ Database initialized successfully at {DB_PATH}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
