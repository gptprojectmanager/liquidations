"""CSV data loading utilities for Binance historical data."""

import glob
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd


def load_open_interest_csv(
    file_path: str, conn: Optional[duckdb.DuckDBPyConnection] = None
) -> pd.DataFrame:
    """Load Open Interest CSV from Binance using DuckDB's zero-copy ingestion.

    Expected CSV format (Binance metrics):
        timestamp,symbol,sumOpenInterest,sumOpenInterestValue,countTopTraderLongShortRatio
        1635724800000,BTCUSDT,123456.78,8123456789.12,1.23

    Args:
        file_path: Path to Binance metrics CSV file
        conn: Optional DuckDB connection (creates temporary if None)

    Returns:
        pd.DataFrame with columns: timestamp (datetime), symbol, open_interest_value

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    # Use provided connection or create temporary
    close_conn = False
    if conn is None:
        conn = duckdb.connect(":memory:")
        close_conn = True

    try:
        # Use DuckDB's zero-copy CSV ingestion with AUTO_DETECT
        # Convert Binance timestamp (milliseconds) to datetime
        try:
            df = conn.execute(f"""
            SELECT
                create_time AS timestamp,
                symbol,
                CAST(sum_open_interest_value AS DECIMAL(20, 8)) AS open_interest_value,
                CAST(sum_open_interest AS DECIMAL(20, 8)) AS open_interest_contracts
            FROM read_csv(
                '{file_path}',
                auto_detect=true,
                header=true,
                delim=','
            )
        """).fetchdf()
        except duckdb.BinderException as e:
            if "No function matches" in str(e):
                raise ValueError(f"CSV file is empty or has invalid format: {file_path}")
            raise ValueError(f"CSV missing required columns: {e}")

        # Convert timezone and precision
        df["timestamp"] = df["timestamp"].dt.tz_localize(None).astype("datetime64[ns]")
        if df.empty:
            raise ValueError(f"CSV file is empty: {file_path}")

        df["timestamp"] = df["timestamp"].dt.tz_localize(None)

        # Validate required columns exist
        required_cols = {"timestamp", "symbol", "open_interest_value"}
        if not required_cols.issubset(df.columns):
            raise ValueError(
                f"CSV missing required columns. Expected {required_cols}, got {set(df.columns)}"
            )

        return df

    finally:
        if close_conn:
            conn.close()


def load_funding_rate_csv(
    file_path: str, conn: Optional[duckdb.DuckDBPyConnection] = None
) -> pd.DataFrame:
    """Load Funding Rate CSV from Binance using DuckDB's zero-copy ingestion.

    Expected CSV format (Binance funding rate):
        timestamp,symbol,fundingRate,markPrice
        1635724800000,BTCUSDT,0.0001,67234.56

    Args:
        file_path: Path to Binance fundingRate CSV file
        conn: Optional DuckDB connection (creates temporary if None)

    Returns:
        pd.DataFrame with columns: timestamp (datetime), symbol, funding_rate

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    close_conn = False
    if conn is None:
        conn = duckdb.connect(":memory:")
        close_conn = True

    try:
        # Use DuckDB's zero-copy CSV ingestion
        try:
            df = conn.execute(f"""
            SELECT
            to_timestamp(calc_time / 1000) AS timestamp,
            'BTCUSDT' AS symbol,
            CAST(last_funding_rate AS DECIMAL(10, 8)) AS funding_rate,
            NULL AS mark_price
            FROM read_csv(
            '{file_path}',
            auto_detect=true,
            header=true,
            delim=','
            )
            """).fetchdf()
        except duckdb.BinderException as e:
            if "No function matches" in str(e):
                raise ValueError(f"CSV file is empty or has invalid format: {file_path}")
            raise ValueError(f"CSV missing required columns: {e}")

        # Convert timezone and precision
        df["timestamp"] = df["timestamp"].dt.tz_localize(None).astype("datetime64[ns]")
        if df.empty:
            raise ValueError(f"CSV file is empty: {file_path}")

        df["timestamp"] = df["timestamp"].dt.tz_localize(None)

        # Validate required columns
        required_cols = {"timestamp", "symbol", "funding_rate"}
        if not required_cols.issubset(df.columns):
            raise ValueError(
                f"CSV missing required columns. Expected {required_cols}, got {set(df.columns)}"
            )

        return df

    finally:
        if close_conn:
            conn.close()


def load_csv_glob(
    pattern: str,
    loader_func=load_open_interest_csv,
    conn: Optional[duckdb.DuckDBPyConnection] = None,
) -> pd.DataFrame:
    """Load multiple CSV files matching glob pattern and concatenate.

    Args:
        pattern: Glob pattern (e.g., 'data/raw/BTCUSDT/metrics/*.csv')
        loader_func: CSV loader function to use
        conn: Optional DuckDB connection

    Returns:
        pd.DataFrame with all files concatenated

    Raises:
        FileNotFoundError: If no files match pattern
    """
    files = sorted(glob.glob(pattern))

    if not files:
        raise FileNotFoundError(f"No files found matching pattern: {pattern}")

    dfs = []
    for file_path in files:
        try:
            df = loader_func(str(file_path), conn=conn)
            dfs.append(df)
        except Exception as e:
            print(f"Warning: Failed to load {file_path}: {e}")

    if not dfs:
        raise ValueError(f"No valid CSV files found in pattern: {pattern}")

    # Concatenate all DataFrames
    result = pd.concat(dfs, ignore_index=True)

    # Sort by timestamp
    result = result.sort_values("timestamp").reset_index(drop=True)

    return result


def load_aggtrades_csv(
    file_path: str, conn: Optional[duckdb.DuckDBPyConnection] = None
) -> pd.DataFrame:
    """Load aggTrades CSV from Binance using DuckDB's zero-copy ingestion.

    Expected CSV format (Binance aggTrades):
        agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker
        2867872924,113988.7,0.018,6669431038,6669431038,1759276800034,true

    Args:
        file_path: Path to Binance aggTrades CSV file
        conn: Optional DuckDB connection (creates temporary if None)

    Returns:
        pd.DataFrame with columns: timestamp, symbol, price, quantity, side, gross_value

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    # Extract symbol from filename (e.g., BTCUSDT-aggTrades-2025-10-01.csv)
    filename = file_path.stem  # Remove .csv extension
    symbol = filename.split("-")[0] if "-" in filename else "BTCUSDT"

    close_conn = False
    if conn is None:
        conn = duckdb.connect(":memory:")
        close_conn = True

    try:
        # Use DuckDB's zero-copy CSV ingestion
        try:
            df = conn.execute(f"""
            SELECT
                to_timestamp(transact_time / 1000) AS timestamp,
                '{symbol}' AS symbol,
                CAST(price AS DECIMAL(18, 8)) AS price,
                CAST(quantity AS DECIMAL(18, 8)) AS quantity,
                CASE 
                    WHEN is_buyer_maker = 'true' THEN 'sell'
                    ELSE 'buy'
                END AS side,
                CAST(price AS DOUBLE) * CAST(quantity AS DOUBLE) AS gross_value
            FROM read_csv(
                '{file_path}',
                auto_detect=true,
                header=true,
                delim=','
            )
            """).fetchdf()
        except duckdb.BinderException as e:
            # Fallback to old format (no header) if transact_time not found
            if "transact_time" in str(e) and "not found" in str(e):
                df = conn.execute(f"""
                SELECT
                    to_timestamp(column5 / 1000) AS timestamp,
                    '{symbol}' AS symbol,
                    CAST(column1 AS DECIMAL(18, 8)) AS price,
                    CAST(column2 AS DECIMAL(18, 8)) AS quantity,
                    CASE
                        WHEN column6 = 'true' THEN 'sell'
                        ELSE 'buy'
                    END AS side,
                    CAST(column1 AS DOUBLE) * CAST(column2 AS DOUBLE) AS gross_value
                FROM read_csv(
                    '{file_path}',
                    auto_detect=false,
                    header=false,
                    delim=',',
                    columns={{'column0': 'BIGINT', 'column1': 'DOUBLE', 'column2': 'DOUBLE',
                              'column3': 'BIGINT', 'column4': 'BIGINT', 'column5': 'BIGINT', 'column6': 'VARCHAR'}}
                )
                """).fetchdf()
            elif "No function matches" in str(e):
                raise ValueError(f"CSV file is empty or has invalid format: {file_path}")
            else:
                raise ValueError(f"CSV missing required columns: {e}")

        # Convert timezone and precision
        df["timestamp"] = df["timestamp"].dt.tz_localize(None).astype("datetime64[ns]")
        if df.empty:
            raise ValueError(f"CSV file is empty: {file_path}")

        df["timestamp"] = df["timestamp"].dt.tz_localize(None)

        # Validate required columns
        required_cols = {"timestamp", "symbol", "price", "quantity", "side", "gross_value"}
        if not required_cols.issubset(df.columns):
            raise ValueError(
                f"CSV missing required columns. Expected {required_cols}, got {set(df.columns)}"
            )

        return df

    finally:
        if close_conn:
            conn.close()
