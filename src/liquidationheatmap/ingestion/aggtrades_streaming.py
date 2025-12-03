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
# NOTE: 200ms recommended for HDD safety in production, 0ms safe for SSD
THROTTLE_MS = 200


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


def load_aggtrades_streaming(conn, data_dir, symbol, start_date, end_date, throttle_ms=THROTTLE_MS):
    """Ingest aggTrades files one-by-one with dual-format support.

    Handles both old format (no header) and new format (with header).
    Prevents OOM by streaming files individually instead of buffering in pandas.
    Uses original agg_trade_id from CSV as PRIMARY KEY for idempotency.

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

    # Get initial count for reporting
    initial_count = conn.execute("SELECT COUNT(*) FROM aggtrades_history").fetchone()[0]

    logger.info(f"Starting from {initial_count:,} existing rows")

    # Process files one by one
    total_rows = 0
    success_count = 0
    skip_count = 0

    for idx, file_path in enumerate(files, 1):
        try:
            # Try new format first (with header)
            csv_rows = 0
            try:
                # Count rows in CSV before INSERT
                csv_rows = conn.execute(f"""
                    SELECT COUNT(*) FROM read_csv('{file_path}', auto_detect=true, header=true)
                    WHERE transact_time / 1000 >= {start_ts} AND transact_time / 1000 <= {end_ts}
                """).fetchone()[0]

                conn.execute(f"""
                    INSERT OR IGNORE INTO aggtrades_history
                    (agg_trade_id, timestamp, symbol, price, quantity, side, gross_value)
                    SELECT
                        agg_trade_id,
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
                if "transact_time" in str(e) or "agg_trade_id" in str(e):
                    logger.debug(f"Fallback to no-header format for {file_path.name}")

                    # Count rows in CSV before INSERT
                    csv_rows = conn.execute(f"""
                        SELECT COUNT(*) FROM read_csv('{file_path}', auto_detect=true, header=false)
                        WHERE column5 / 1000 >= {start_ts} AND column5 / 1000 <= {end_ts}
                    """).fetchone()[0]

                    conn.execute(f"""
                        INSERT OR IGNORE INTO aggtrades_history
                        (agg_trade_id, timestamp, symbol, price, quantity, side, gross_value)
                        SELECT
                            CAST(column0 AS BIGINT) AS agg_trade_id,
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
            current_count = conn.execute("SELECT COUNT(*) FROM aggtrades_history").fetchone()[0]
            file_rows = current_count - (initial_count + total_rows)
            skipped_rows = csv_rows - file_rows
            total_rows += file_rows
            success_count += 1

            logger.info(
                f"[{idx}/{len(files)}] {file_path.name}: {file_rows:,} inserted, {skipped_rows:,} skipped (format: {format_used})"
            )

            # I/O throttle to prevent HDD overload
            if throttle_ms > 0:
                time.sleep(throttle_ms / 1000.0)

        except Exception as e:
            skip_count += 1
            logger.warning(f"[{idx}/{len(files)}] Skip {file_path.name}: {e}")
            continue

    # Calculate total skipped rows for summary
    final_count = conn.execute("SELECT COUNT(*) FROM aggtrades_history").fetchone()[0]
    total_inserted = final_count - initial_count

    logger.info(f"Ingestion complete: {total_inserted:,} rows inserted from {success_count} files")
    logger.info(f"Skipped {skip_count} files due to errors")

    # Status assessment for monitoring
    if total_inserted == 0 and success_count > 0:
        logger.info("Status: Database already complete (all rows already exist)")
    elif total_inserted > 0:
        logger.info(f"Status: Database updated with {total_inserted:,} new rows")
    else:
        logger.warning("Status: No data processed (check for errors above)")

    return total_rows
