"""Streaming aggTrades ingestion - file-by-file (OOM-safe).

Fixes exit 137 OOM crash on large datasets by avoiding pandas buffering.
Uses direct DuckDB CSV streaming with automatic dual-format detection.
"""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

# I/O throttling to prevent HDD overload (milliseconds)
THROTTLE_MS = 100


def get_aggtrades_files(data_dir, symbol, start_date, end_date):
    """Get aggTrades CSV files within date range.

    Args:
        data_dir: Base data directory
        symbol: Trading pair (e.g., BTCUSDT)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        Sorted list of existing CSV file paths
    """
    aggtrades_dir = Path(data_dir) / symbol / "aggTrades"

    if not aggtrades_dir.exists():
        raise FileNotFoundError(f"aggTrades directory not found: {aggtrades_dir}")

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    files = []
    current = start_dt

    while current <= end_dt:
        date_str = current.strftime("%Y-%m-%d")
        file_path = aggtrades_dir / f"{symbol}-aggTrades-{date_str}.csv"

        if file_path.exists():
            files.append(file_path)
        else:
            logger.debug(f"File not found (skipped): {file_path.name}")

        current += timedelta(days=1)

    logger.info(f"Found {len(files)} aggTrades files for {symbol} ({start_date} to {end_date})")
    return sorted(files)


def load_aggtrades_streaming(
    conn, data_dir, symbol, start_date, end_date, throttle_ms=THROTTLE_MS
):
    """Ingest aggTrades files one-by-one with dual-format support.

    Handles both old format (no header) and new format (with header).
    Prevents OOM by streaming files individually instead of buffering in pandas.

    Args:
        conn: DuckDB connection
        data_dir: Base data directory
        symbol: Trading pair
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        throttle_ms: Sleep time between files (ms) to prevent I/O overload

    Returns:
        Total number of rows inserted
    """
    logger.info(f"Starting streaming aggTrades ingestion for {symbol}")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"I/O throttle: {throttle_ms}ms between files")

    files = get_aggtrades_files(data_dir, symbol, start_date, end_date)

    if not files:
        logger.warning(f"No aggTrades files found for {symbol}")
        return 0

    # Parse date range for filtering within files
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    end_dt = end_dt.replace(hour=23, minute=59, second=59)

    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    # Get current max ID for resume capability
    max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM aggtrades_history").fetchone()[0]
    initial_max_id = max_id

    logger.info(f"Starting from ID: {max_id}")

    # Process files one by one
    total_rows = 0
    success_count = 0
    skip_count = 0

    for idx, file_path in enumerate(files, 1):
        try:
            # Try new format first (with header)
            try:
                conn.execute(f"""
                    INSERT OR IGNORE INTO aggtrades_history
                    (id, timestamp, symbol, price, quantity, side, gross_value)
                    SELECT
                        row_number() OVER (ORDER BY transact_time) + {max_id} AS id,
                        to_timestamp(transact_time / 1000) AS timestamp,
                        '{symbol}' AS symbol,
                        CAST(price AS DECIMAL(18, 8)) AS price,
                        CAST(quantity AS DECIMAL(18, 8)) AS quantity,
                        CASE WHEN is_buyer_maker THEN 'sell' ELSE 'buy' END AS side,
                        price * quantity AS gross_value
                    FROM read_csv('{file_path}', auto_detect=true, header=true)
                    WHERE transact_time / 1000 >= {start_ts} AND transact_time / 1000 <= {end_ts}
                """)
                format_used = "header"

            except duckdb.BinderException as e:
                # Fallback to old format (no header)
                if "transact_time" in str(e):
                    logger.debug(f"Fallback to no-header format for {file_path.name}")
                    conn.execute(f"""
                        INSERT OR IGNORE INTO aggtrades_history
                        (id, timestamp, symbol, price, quantity, side, gross_value)
                        SELECT
                            row_number() OVER (ORDER BY column5) + {max_id} AS id,
                            to_timestamp(column5 / 1000) AS timestamp,
                            '{symbol}' AS symbol,
                            CAST(column1 AS DECIMAL(18, 8)) AS price,
                            CAST(column2 AS DECIMAL(18, 8)) AS quantity,
                            CASE WHEN column6 = 'true' THEN 'sell' ELSE 'buy' END AS side,
                            column1 * column2 AS gross_value
                        FROM read_csv('{file_path}', auto_detect=true, header=false)
                        WHERE column5 / 1000 >= {start_ts} AND column5 / 1000 <= {end_ts}
                    """)
                    format_used = "no-header"
                else:
                    raise

            # Count rows inserted from this file
            new_max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM aggtrades_history").fetchone()[0]
            file_rows = new_max_id - max_id
            total_rows += file_rows
            max_id = new_max_id
            success_count += 1

            logger.info(
                f"[{idx}/{len(files)}] {file_path.name}: {file_rows:,} rows (format: {format_used})"
            )

            # I/O throttle to prevent HDD overload
            if throttle_ms > 0:
                time.sleep(throttle_ms / 1000.0)

        except Exception as e:
            skip_count += 1
            logger.warning(f"[{idx}/{len(files)}] Skip {file_path.name}: {e}")
            continue

    logger.info(f"Ingestion complete: {total_rows:,} rows from {success_count} files")
    logger.info(f"Skipped {skip_count} files due to errors")
    logger.info(f"ID range: {initial_max_id} → {max_id}")

    return total_rows
