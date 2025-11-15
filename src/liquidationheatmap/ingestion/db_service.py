"""DuckDB service for querying Open Interest and market data."""

import logging
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

    def get_large_trades(
        self,
        symbol: str = "BTCUSDT",
        min_gross_value: Decimal = Decimal("100000"),
        start_datetime: str = None,
        end_datetime: str = None,
    ):
        """Get large trades from aggTrades data (filtered by timeframe only, no limit)."""
        import pandas as pd

        logger = logging.getLogger(__name__)

        logger.info(
            f"get_large_trades called: symbol={symbol}, min_gross_value={min_gross_value}, timeframe={start_datetime} to {end_datetime}"
        )

        # Try to query from DB first
        try:
            # Build query with temporal filters - use ALL trades (no sampling)
            query_parts = [
                "SELECT timestamp, price, quantity, side, gross_value",
                "FROM aggtrades_history",
                "WHERE symbol = ? AND gross_value >= ?",
            ]
            params = [symbol, float(min_gross_value)]

            if start_datetime:
                query_parts.append("AND timestamp >= ?")
                params.append(start_datetime)

            if end_datetime:
                query_parts.append("AND timestamp <= ?")
                params.append(end_datetime)

            query_parts.append("ORDER BY timestamp DESC")

            query = " ".join(query_parts)
            df = self.conn.execute(query, params).df()
            if not df.empty:
                logger.info(
                    f"Loaded {len(df)} trades from timeframe {start_datetime} to {end_datetime}"
                )
                return df
            logger.info("DB cache empty, loading from CSV")
        except Exception as e:
            logger.warning(f"DB query failed: {e}, loading from CSV")

        # Load from CSV if not in DB
        csv_path = f"/media/sam/3TB-WDC/binance-history-data-downloader/data/{symbol}/aggTrades/{symbol}-aggTrades-2025-10-*.csv"
        logger.info(f"CSV pattern: {csv_path}")

        # Create table
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS aggtrades_history (
                    timestamp TIMESTAMP,
                    symbol VARCHAR,
                    price DOUBLE,
                    quantity DOUBLE,
                    side VARCHAR,
                    gross_value DOUBLE
                )
            """)
        except Exception as e:
            logger.debug(f"Table creation skipped (may exist): {e}")

        # Load data using DOUBLE to avoid DECIMAL overflow
        try:
            logger.info(f"Loading CSV files matching: {csv_path}")
            self.conn.execute(f"""
                INSERT INTO aggtrades_history
                SELECT 
                    epoch_ms(transact_time) as timestamp,
                    '{symbol}' as symbol,
                    price::DOUBLE as price,
                    quantity::DOUBLE as quantity,
                    CASE WHEN is_buyer_maker THEN 'sell' ELSE 'buy' END as side,
                    (price::DOUBLE * quantity::DOUBLE) as gross_value
                FROM read_csv_auto('{csv_path}')
                WHERE (price::DOUBLE * quantity::DOUBLE) >= {float(min_gross_value)}
                LIMIT 10000
            """)

            # Return loaded data
            df = self.conn.execute(
                """
                SELECT timestamp, price, quantity, side, gross_value
                FROM aggtrades_history
                WHERE symbol = ? AND gross_value >= ?
                ORDER BY timestamp DESC
                LIMIT 10000
            """,
                [symbol, float(min_gross_value)],
            ).df()

            logger.info(
                f"✅ Loaded {len(df)} large trades from CSV (buy: {len(df[df['side'] == 'buy'])}, sell: {len(df[df['side'] == 'sell'])})"
            )
            return df

        except Exception as e:
            logger.error(f"❌ Failed to load trades from CSV: {e}", exc_info=True)
            # Return empty DataFrame on error
            return pd.DataFrame(columns=["timestamp", "price", "quantity", "side", "gross_value"])

    def calculate_liquidations_sql(
        self,
        symbol: str = "BTCUSDT",
        current_price: float = None,
        bin_size: float = 200.0,
        min_gross_value: float = 500000.0,
        start_datetime: str = None,
        end_datetime: str = None,
    ):
        """Calculate liquidation levels DIRECTLY in DuckDB (100x faster than Python loops).

        Args:
            symbol: Trading pair
            current_price: Current market price
            bin_size: Price bucket size for aggregation
            min_gross_value: Minimum trade size (whale trades)
            start_datetime: Start of timeframe
            end_datetime: End of timeframe

        Returns:
            DataFrame with columns: price_bucket, leverage, side, volume, count
        """
        import logging

        logger = logging.getLogger(__name__)

        logger.info(
            f"calculate_liquidations_sql: symbol={symbol}, current_price={current_price}, "
            f"bin_size={bin_size}, timeframe={start_datetime} to {end_datetime}"
        )

        # MMR for simplicity (0.4% - conservative)
        mmr = 0.004

        query = f"""
        WITH leverage_tiers AS (
            SELECT unnest([5, 10, 25, 50, 100]) as leverage
        ),
        -- Step 1: Calculate liquidation prices for EACH leverage tier
        trades_with_liq_prices AS (
            SELECT
                t.timestamp,
                t.gross_value,
                t.side,
                t.price as entry_price,
                l.leverage,
                CASE
                    WHEN t.side = 'buy' THEN t.price * (1 - 1.0/l.leverage + {mmr}/l.leverage)
                    WHEN t.side = 'sell' THEN t.price * (1 + 1.0/l.leverage - {mmr}/l.leverage)
                END as liq_price
            FROM aggtrades_history t
            CROSS JOIN leverage_tiers l
            WHERE t.symbol = ?
              AND t.gross_value >= ?
        """

        params = [symbol, min_gross_value]

        if start_datetime:
            query += " AND t.timestamp >= ?"
            params.append(start_datetime)

        if end_datetime:
            query += " AND t.timestamp <= ?"
            params.append(end_datetime)

        query += f"""
        ),
        -- Step 2: Filter for valid liquidations and count active leverage tiers per trade
        valid_liqs AS (
            SELECT
                *,
                -- Count how many leverage tiers result in valid liquidations for this trade
                COUNT(*) OVER (PARTITION BY timestamp, entry_price, gross_value, side) as active_leverage_count
            FROM trades_with_liq_prices
            WHERE (side = 'buy' AND liq_price < {current_price})
               OR (side = 'sell' AND liq_price > {current_price})
        ),
        -- Step 3: Bucket the valid liquidations
        bucketed_liqs AS (
            SELECT
                FLOOR(liq_price / {bin_size}) * {bin_size} as price_bucket,
                leverage,
                side,
                gross_value,
                active_leverage_count
            FROM valid_liqs
        )
        -- Step 4: Aggregate - distribute volume among active leverage tiers
        SELECT
            price_bucket,
            leverage,
            side,
            -- Divide by ACTUAL number of active leverage tiers (not hardcoded 5)
            SUM(gross_value / active_leverage_count) as total_volume,
            COUNT(*) as count
        FROM bucketed_liqs
        GROUP BY price_bucket, leverage, side
        ORDER BY price_bucket, leverage
        """

        df = self.conn.execute(query, params).df()
        logger.info(f"SQL aggregation complete: {len(df)} bins returned")
        return df

    def calculate_liquidations_oi_based(
        self,
        symbol: str = "BTCUSDT",
        current_price: float = None,
        bin_size: float = 500.0,
        lookback_days: int = 30,
    ):
        """Calculate liquidations using Open Interest-based volume profile scaling.

        This model uses volume profile from aggTrades for DISTRIBUTION SHAPE,
        then scales the total to match current Open Interest (positions still open).

        Methodology (Gemini AI - Option B: OpenInterest + Volume Profile Scaling):
        1. Build 30-day volume profile from aggTrades (relative distribution by price)
        2. Calculate total 30-day volume
        3. Get current OI from Binance API (~$8.5B)
        4. Calculate scaling factor: current_oi / total_30day_volume ≈ 0.017
        5. Apply scaling: scaled_volume = volume_at_price * scaling_factor
        6. Distribute across leverage tiers (5x: 15%, 10x: 30%, 25x: 25%, 50x: 20%, 100x: 10%)
        7. Split 50/50 between longs and shorts
        8. Calculate liquidation prices for each bin+leverage combination

        This produces numbers in ~3-4B range (like Coinglass) instead of inflated 200B (aggTrades only).

        Args:
            symbol: Trading pair (default: BTCUSDT)
            current_price: Current market price
            bin_size: Price bucket size for aggregation
            lookback_days: Days to look back for volume profile (default: 30)

        Returns:
            DataFrame with columns: price_bucket, leverage, side, volume, liq_price
        """
        import logging

        logger = logging.getLogger(__name__)

        logger.info(
            f"calculate_liquidations_oi_based: symbol={symbol}, lookback={lookback_days}d, bin_size={bin_size}"
        )

        # MMR (Maintenance Margin Rate) - conservative 0.4%
        mmr = 0.004

        query = f"""
        WITH Params AS (
            -- Get latest Open Interest and calculate lookback period
            SELECT
                (SELECT open_interest_value FROM open_interest_history
                 WHERE symbol = ? ORDER BY timestamp DESC LIMIT 1) AS latest_oi,
                CURRENT_TIMESTAMP - INTERVAL '{lookback_days} days' AS start_time,
                {bin_size} AS price_bin_size
        ),

        -- Leverage distribution weights (matching Coinglass 5 tiers)
        LeverageDistribution AS (
            SELECT * FROM (VALUES
                (5,   0.15),  -- 15% at 5x (safer traders)
                (10,  0.30),  -- 30% at 10x (conservative)
                (25,  0.25),  -- 25% at 25x (moderate)
                (50,  0.20),  -- 20% at 50x (aggressive)
                (100, 0.10)   -- 10% at 100x (degens)
            ) AS t (leverage, weight)
        ),

        -- Step 1: Use pre-cached volume_profile_daily table (BLAZING FAST!)
        -- This table is pre-aggregated from aggtrades_history with whale trades only
        -- No need to scan 1.9B rows - just query ~7K pre-computed rows
        DailyProfile AS (
            SELECT
                FLOOR(price_bin / (SELECT price_bin_size FROM Params)) * (SELECT price_bin_size FROM Params) AS price_bin,
                total_volume AS daily_volume
            FROM volume_profile_daily
            WHERE symbol = ?
              AND trade_date >= DATE_TRUNC('day', (SELECT start_time FROM Params))
        ),

        VolumeProfile AS (
            SELECT
                price_bin,
                SUM(daily_volume) AS volume_at_price
            FROM DailyProfile
            GROUP BY 1
        ),

        -- Step 2: Calculate total volume in period
        TotalVolume AS (
            SELECT COALESCE(SUM(volume_at_price), 1.0) as total_volume
            FROM VolumeProfile
        ),

        -- Step 3: Calculate scaling factor (OI / total_volume ≈ 0.017 for 30-day)
        -- Step 4: Apply scaling to get OI distribution matching volume profile SHAPE
        OIDistribution AS (
            SELECT
                vp.price_bin,
                -- Scaled volume = (volume_at_price / total_volume) * latest_oi
                -- This is equivalent to: volume_at_price * scaling_factor
                -- where scaling_factor = latest_oi / total_volume
                vp.volume_at_price * (p.latest_oi / tv.total_volume) AS oi_at_price
            FROM VolumeProfile vp
            CROSS JOIN Params p
            CROSS JOIN TotalVolume tv
        ),

        -- Step 5-7: Calculate liquidation levels with leverage distribution
        -- CRITICAL FIX: Divide logic based on entry price vs current price
        -- - Volume BELOW current = Long positions (bought low)
        -- - Volume ABOVE current = Short positions (sold high)
        AllLiquidations AS (
            -- Short positions: Only from price bins ABOVE current price
            -- (Traders who sold high, liquidate if price goes higher)
            SELECT
                od.price_bin AS price_bucket,
                ld.leverage,
                'sell' AS side,
                od.oi_at_price * ld.weight AS volume,  -- 100% of OI at this price
                od.price_bin * (1 + 1.0/ld.leverage - {mmr}/ld.leverage) AS liq_price
            FROM OIDistribution od
            CROSS JOIN LeverageDistribution ld
            WHERE od.price_bin > {current_price}  -- Only bins above current

            UNION ALL

            -- Long positions: Only from price bins BELOW current price
            -- (Traders who bought low, liquidate if price goes lower)
            SELECT
                od.price_bin AS price_bucket,
                ld.leverage,
                'buy' AS side,
                od.oi_at_price * ld.weight AS volume,  -- 100% of OI at this price
                od.price_bin * (1 - 1.0/ld.leverage + {mmr}/ld.leverage) AS liq_price
            FROM OIDistribution od
            CROSS JOIN LeverageDistribution ld
            WHERE od.price_bin < {current_price}  -- Only bins below current
        )

        -- Final: Filter to show only liquidations at risk
        -- (liquidation price has already been crossed by current price)
        SELECT
            price_bucket,
            leverage,
            side,
            volume,
            liq_price
        FROM AllLiquidations
        WHERE
            -- Shorts: liq_price above current (price must go UP to liquidate)
            (side = 'sell' AND liq_price > {current_price})
            OR
            -- Longs: liq_price below current (price must go DOWN to liquidate)
            (side = 'buy' AND liq_price < {current_price})
        ORDER BY liq_price, leverage
        """

        params = [symbol, symbol]

        try:
            df = self.conn.execute(query, params).df()
            logger.info(f"OI-based model complete: {len(df)} liquidation levels returned")

            # Sanity check: sum of all volumes should approximately equal latest OI
            if not df.empty:
                total_distributed = df["volume"].sum()

                # Get OI and total volume for validation
                oi_result = self.conn.execute(
                    "SELECT open_interest_value FROM open_interest_history WHERE symbol = ? ORDER BY timestamp DESC LIMIT 1",
                    [symbol],
                ).fetchone()

                total_volume_result = self.conn.execute(
                    f"""
                    SELECT SUM(gross_value) as total_volume
                    FROM aggtrades_history
                    WHERE symbol = ?
                      AND timestamp >= CURRENT_TIMESTAMP - INTERVAL '{lookback_days} days'
                    """,
                    [symbol],
                ).fetchone()

                if oi_result and total_volume_result:
                    latest_oi = float(oi_result[0])
                    total_volume = float(total_volume_result[0])
                    scaling_factor = latest_oi / total_volume if total_volume > 0 else 0

                    logger.info(
                        f"📊 Volume Profile Scaling:\n"
                        f"  - Latest OI: ${latest_oi:,.0f}\n"
                        f"  - {lookback_days}-day volume: ${total_volume:,.0f}\n"
                        f"  - Scaling factor: {scaling_factor:.4f}\n"
                        f"  - Total distributed: ${total_distributed:,.0f}\n"
                        f"  - Coverage: {total_distributed / latest_oi:.2%}"
                    )

            return df
        except Exception as e:
            logger.error(f"OI-based calculation failed: {e}", exc_info=True)
            # Return empty DataFrame on error
            import pandas as pd

            return pd.DataFrame(columns=["price_bucket", "leverage", "side", "volume", "liq_price"])
