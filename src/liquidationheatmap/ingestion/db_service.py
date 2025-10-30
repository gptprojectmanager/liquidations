"""DuckDB service for querying Open Interest and market data."""

from decimal import Decimal
from pathlib import Path
from typing import Tuple

import duckdb

from .csv_loader import load_csv_glob, load_funding_rate_csv


class DuckDBService:
    """Service for managing DuckDB connection and queries."""

    def __init__(self, db_path: str = "data/processed/liquidations.duckdb"):
        """Initialize DuckDB service.

        Args:
            db_path: Path to DuckDB database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))

    def get_latest_open_interest(self, symbol: str = "BTCUSDT") -> Tuple[Decimal, Decimal]:
        """Get latest Open Interest and current price for symbol.

        Args:
            symbol: Trading pair (default: BTCUSDT)

        Returns:
            Tuple of (current_price, open_interest_value)
        """
        # Try to query from database
        try:
            result = self.conn.execute(
                """
                SELECT 
                    open_interest_value,
                    timestamp
                FROM open_interest_history
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                [symbol],
            ).fetchone()

            if result:
                oi_value = Decimal(str(result[0]))
                # Mock current price (TODO: fetch from markPrice klines or API)
                current_price = Decimal("67000.00")
                return current_price, oi_value
        except duckdb.CatalogException:
            # Table doesn't exist, load from CSV
            pass

        # If no data in DB, load from CSV and insert
        return self._load_and_cache_data(symbol)

    def _load_and_cache_data(self, symbol: str) -> Tuple[Decimal, Decimal]:
        """Load data from CSV and cache in DuckDB.

        Args:
            symbol: Trading pair

        Returns:
            Tuple of (current_price, open_interest_value)
        """
        # Load from CSV
        csv_pattern = f"data/raw/{symbol}/metrics/{symbol}-metrics-*.csv"

        try:
            df = load_csv_glob(csv_pattern, conn=self.conn)
        except FileNotFoundError:
            # No data available, return defaults
            return Decimal("67000.00"), Decimal("100000000.00")

        if df.empty:
            return Decimal("67000.00"), Decimal("100000000.00")

        # Create table if not exists with UNIQUE constraint
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS open_interest_history (
                id BIGINT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                open_interest_value DECIMAL(20, 8) NOT NULL,
                open_interest_contracts DECIMAL(20, 8),
                UNIQUE(timestamp, symbol)
            )
        """)

        # Insert data with validation (INSERT OR IGNORE for duplicates)
        # Validate: OI value > 0, symbol not empty
        self.conn.execute("""
            INSERT OR IGNORE INTO open_interest_history 
            SELECT 
                row_number() OVER (ORDER BY timestamp) + 
                    COALESCE((SELECT MAX(id) FROM open_interest_history), 0) as id,
                timestamp,
                symbol,
                open_interest_value,
                open_interest_contracts
            FROM df
            WHERE open_interest_value > 0
              AND symbol IS NOT NULL
              AND symbol != ''
        """)

        # Get latest
        latest = df.iloc[-1]
        oi_value = Decimal(str(latest["open_interest_value"]))
        current_price = Decimal("67000.00")  # Mock for now

        return current_price, oi_value

    def get_latest_funding_rate(self, symbol: str = "BTCUSDT") -> Decimal:
        """Get latest funding rate for symbol.

        Args:
            symbol: Trading pair

        Returns:
            Current funding rate (e.g., 0.0001 for 0.01%)
        """
        # Try database first
        try:
            result = self.conn.execute(
                """
                SELECT funding_rate
                FROM funding_rate_history
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                [symbol],
            ).fetchone()

            if result:
                return Decimal(str(result[0]))
        except duckdb.CatalogException:
            # Table doesn't exist
            pass

        # Load from CSV
        csv_pattern = f"data/raw/{symbol}/fundingRate/{symbol}-fundingRate-*.csv"

        try:
            df = load_csv_glob(csv_pattern, loader_func=load_funding_rate_csv, conn=self.conn)
        except FileNotFoundError:
            return Decimal("0.0001")  # Default funding rate

        if df.empty:
            return Decimal("0.0001")

        # Create table if not exists with UNIQUE constraint
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS funding_rate_history (
                id BIGINT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                funding_rate DECIMAL(10, 8) NOT NULL,
                mark_price DECIMAL(18, 2),
                UNIQUE(timestamp, symbol)
            )
        """)

        # Insert with validation (INSERT OR IGNORE for duplicates)
        # Validate: funding rate within reasonable range (-1% to +1%), symbol not empty
        self.conn.execute("""
            INSERT OR IGNORE INTO funding_rate_history
            SELECT 
                row_number() OVER (ORDER BY timestamp) + 
                    COALESCE((SELECT MAX(id) FROM funding_rate_history), 0) as id,
                timestamp,
                symbol,
                funding_rate,
                mark_price
            FROM df
            WHERE funding_rate BETWEEN -0.01 AND 0.01
              AND symbol IS NOT NULL
              AND symbol != ''
        """)

        latest = df.iloc[-1]
        return Decimal(str(latest["funding_rate"]))

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def get_large_trades(self, symbol: str = "BTCUSDT", min_gross_value: Decimal = Decimal("100000")):
        """Get large trades from aggTrades data."""
        import pandas as pd
        
        # Try to query from DB first
        try:
            query = """
                SELECT timestamp, price, quantity, side, gross_value
                FROM aggtrades_history
                WHERE symbol = ? AND gross_value >= ?
                ORDER BY timestamp DESC
                LIMIT 10000
            """
            df = self.conn.execute(query, [symbol, float(min_gross_value)]).df()
            if not df.empty:
                return df
        except:
            pass
        
        # Load from CSV if not in DB
        csv_path = f"data/raw/{symbol}/aggTrades/{symbol}-aggTrades-*.csv"
        
        # Create table
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS aggtrades_history (
                    timestamp TIMESTAMP,
                    symbol VARCHAR,
                    price DECIMAL(18,8),
                    quantity DECIMAL(18,8),
                    side VARCHAR,
                    gross_value DECIMAL(20,2)
                )
            """)
        except:
            pass
        
        # Load data
        try:
            self.conn.execute(f"""
                INSERT INTO aggtrades_history
                SELECT 
                    epoch_ms(transact_time) as timestamp,
                    '{symbol}' as symbol,
                    CAST(price AS DECIMAL(18,8)) as price,
                    CAST(quantity AS DECIMAL(18,8)) as quantity,
                    CASE WHEN is_buyer_maker IN ('true', 'True', '1') THEN 'sell' ELSE 'buy' END as side,
                    CAST(price AS DECIMAL(18,8)) * CAST(quantity AS DECIMAL(18,8)) as gross_value
                FROM read_csv_auto('{csv_path}')
                WHERE CAST(price AS DECIMAL(18,8)) * CAST(quantity AS DECIMAL(18,8)) >= {float(min_gross_value)}
                LIMIT 10000
            """)
            
            # Return loaded data
            return self.conn.execute("""
                SELECT timestamp, price, quantity, side, gross_value
                FROM aggtrades_history
                WHERE symbol = ? AND gross_value >= ?
                ORDER BY timestamp DESC
                LIMIT 10000
            """, [symbol, float(min_gross_value)]).df()
        except Exception as e:
            # Return empty DataFrame on error
            return pd.DataFrame(columns=["timestamp", "price", "quantity", "side", "gross_value"])
