#!/usr/bin/env python3
"""Initialize the alerts DuckDB database with required schema.

This script creates the alerts.duckdb database and initializes the
liquidation_alerts and alert_cooldowns tables.

Usage:
    uv run python scripts/init_alert_db.py [--db-path PATH]

Options:
    --db-path PATH    Override database path (default: data/processed/alerts.duckdb)
"""

import argparse
import logging
import sys
from pathlib import Path

import duckdb

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# SQL schema for alerts database
SCHEMA_SQL = """
-- Liquidation alerts history
CREATE TABLE IF NOT EXISTS liquidation_alerts (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    symbol VARCHAR(20) NOT NULL,
    current_price DECIMAL(18,8) NOT NULL,
    zone_price DECIMAL(18,8) NOT NULL,
    zone_density DECIMAL(18,8) NOT NULL,
    zone_side VARCHAR(5) NOT NULL CHECK (zone_side IN ('long', 'short')),
    distance_pct DECIMAL(8,4) NOT NULL,
    severity VARCHAR(10) NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    channels_sent VARCHAR(255),
    delivery_status VARCHAR(50) NOT NULL CHECK (delivery_status IN ('pending', 'success', 'partial', 'failed')),
    error_message TEXT
);

-- Index for querying recent alerts
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON liquidation_alerts(timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON liquidation_alerts(symbol);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON liquidation_alerts(severity);

-- Cooldown state persistence
CREATE TABLE IF NOT EXISTS alert_cooldowns (
    zone_key VARCHAR(100) PRIMARY KEY,
    last_alert_time TIMESTAMP NOT NULL,
    alert_count_today INTEGER DEFAULT 0,
    last_reset_date DATE NOT NULL
);

-- Index for cooldown lookups
CREATE INDEX IF NOT EXISTS idx_cooldowns_zone ON alert_cooldowns(zone_key);
"""


def init_database(db_path: Path) -> None:
    """Initialize the alerts database with the required schema.

    Args:
        db_path: Path to the DuckDB database file.
    """
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Creating alerts database: {db_path}")

    try:
        conn = duckdb.connect(str(db_path))

        # Execute schema creation
        conn.execute(SCHEMA_SQL)

        # Verify tables were created
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        table_names = [t[0] for t in tables]

        if "liquidation_alerts" in table_names:
            logger.info("Created table: liquidation_alerts")
        if "alert_cooldowns" in table_names:
            logger.info("Created table: alert_cooldowns")

        conn.close()
        logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Initialize the alerts DuckDB database")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/processed/alerts.duckdb"),
        help="Path to the database file",
    )

    args = parser.parse_args()

    try:
        init_database(args.db_path)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
