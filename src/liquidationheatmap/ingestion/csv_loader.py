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
                to_timestamp(timestamp / 1000) AS timestamp,
                symbol,
                CAST(sumOpenInterestValue AS DECIMAL(20, 8)) AS open_interest_value,
                CAST(sumOpenInterest AS DECIMAL(20, 8)) AS open_interest_contracts
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

        if df.empty:
            raise ValueError(f"CSV file is empty: {file_path}")

        # Convert to timezone-naive for consistent date comparisons
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
            to_timestamp(timestamp / 1000) AS timestamp,
            symbol,
            CAST(fundingRate AS DECIMAL(10, 8)) AS funding_rate,
            CAST(markPrice AS DECIMAL(18, 2)) AS mark_price
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

        if df.empty:
            raise ValueError(f"CSV file is empty: {file_path}")

        # Convert to timezone-naive for consistent date comparisons
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
