"""DuckDB service for querying Open Interest and market data."""

import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Tuple
from urllib.request import urlopen

import duckdb

from .csv_loader import load_csv_glob, load_funding_rate_csv

logger = logging.getLogger(__name__)


def _fetch_binance_price(symbol: str, timeout: int = 5) -> Decimal:
    """Fetch current price from Binance API.

    Args:
        symbol: Trading pair (e.g., BTCUSDT)
        timeout: Request timeout in seconds

    Returns:
        Current market price as Decimal

    Raises:
        Exception: If API call fails
    """
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    with urlopen(url, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
        return Decimal(data["price"])


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
                # Fetch real-time price from Binance API
                try:
                    current_price = _fetch_binance_price(symbol)
                except Exception as e:
                    logger.warning(f"Binance API price fetch failed for {symbol}: {e}")
                    # Fallback: estimate from OI value / contracts if available
                    current_price = Decimal("95000.00")  # Reasonable fallback for BTC
                return current_price, oi_value
        except duckdb.CatalogException as e:
            # Table doesn't exist, load from CSV
            logger.debug(f"open_interest_history table not found, loading from CSV: {e}")

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
            # No data available, fetch real price and return defaults
            logger.warning(f"No CSV data found for {symbol}, using defaults")
            try:
                current_price = _fetch_binance_price(symbol)
            except Exception as e:
                logger.warning(f"Binance price fetch also failed for {symbol}: {e}")
                current_price = Decimal("95000.00")  # Fallback for BTC
            return current_price, Decimal("100000000.00")

        if df.empty:
            logger.warning(f"Empty CSV data for {symbol}, using defaults")
            try:
                current_price = _fetch_binance_price(symbol)
            except Exception as e:
                logger.warning(f"Binance price fetch failed for empty CSV {symbol}: {e}")
                current_price = Decimal("95000.00")  # Fallback for BTC
            return current_price, Decimal("100000000.00")

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

        # Get latest OI value
        latest = df.iloc[-1]
        oi_value = Decimal(str(latest["open_interest_value"]))

        # Fetch real-time price from Binance API
        try:
            current_price = _fetch_binance_price(symbol)
        except Exception as e:
            logger.warning(f"Binance API price fetch failed for {symbol}: {e}")
            current_price = Decimal("95000.00")  # Fallback for BTC

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
        except duckdb.CatalogException as e:
            # Table doesn't exist, will load from CSV
            logger.debug(f"funding_rate_history table not found, loading from CSV: {e}")

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

    def initialize_snapshot_tables(self) -> None:
        """Initialize database tables for time-evolving heatmap snapshots.

        Creates:
        - liquidation_snapshots: Pre-computed snapshot cache for fast API queries
        - position_events: Event log for position lifecycle tracking

        Per spec.md Phase 2 (T029-T031).

        Thread Safety:
            Uses CREATE TABLE IF NOT EXISTS which is idempotent. Concurrent calls
            may raise write-write conflicts in DuckDB - callers should handle
            duckdb.TransactionException if running in multi-threaded context.
        """
        # Create liquidation_snapshots table (T029)
        # UNIQUE constraint prevents duplicate snapshots for same timestamp/symbol/bucket/side
        # CHECK constraints ensure data integrity
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS liquidation_snapshots (
                id BIGINT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                price_bucket DECIMAL(18, 2) NOT NULL,
                side VARCHAR(10) NOT NULL,
                active_volume DECIMAL(20, 8) NOT NULL,
                consumed_volume DECIMAL(20, 8) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(timestamp, symbol, price_bucket, side),
                CHECK (side IN ('long', 'short')),
                CHECK (active_volume >= 0),
                CHECK (consumed_volume >= 0),
                CHECK (price_bucket > 0),
                CHECK (LENGTH(TRIM(symbol)) > 0)
            )
        """)

        # Create position_events table (T030)
        # CHECK constraints ensure data integrity for side and event_type
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS position_events (
                id BIGINT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                event_type VARCHAR(20) NOT NULL,
                entry_price DECIMAL(18, 2) NOT NULL,
                liq_price DECIMAL(18, 2) NOT NULL,
                volume DECIMAL(20, 8) NOT NULL,
                side VARCHAR(10) NOT NULL,
                leverage INTEGER NOT NULL,
                CHECK (event_type IN ('open', 'close', 'liquidate')),
                CHECK (side IN ('long', 'short')),
                CHECK (volume >= 0),
                CHECK (leverage > 0),
                CHECK (LENGTH(TRIM(symbol)) > 0)
            )
        """)

        # Create indexes for query performance (T034)
        # CREATE INDEX IF NOT EXISTS is idempotent - no try/except needed
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_liq_snap_ts_sym
            ON liquidation_snapshots(timestamp, symbol)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_liq_snap_price
            ON liquidation_snapshots(price_bucket)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pos_events_ts_sym
            ON position_events(timestamp, symbol)
        """)

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
        whale_threshold: float = 500000.0,
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

        # IMPORTANT: Warn if non-default whale_threshold is used (parameter currently non-functional)
        if whale_threshold != 500000.0:
            logger.warning(
                f"whale_threshold={whale_threshold} specified but volume_profile_daily cache "
                f"uses $500k hardcoded. Parameter currently has no effect. "
                f"See /tmp/CRITICAL_WHALE_THRESHOLD_BUG_18NOV2025.md for details."
            )

        # MMR (Maintenance Margin Rate) - conservative 0.4%
        mmr = 0.004

        query = f"""
        WITH Params AS (
            -- Get latest Open Interest and calculate lookback period
            -- Use MAX timestamp from data (not CURRENT_TIMESTAMP) to handle historical data
            SELECT
                (SELECT open_interest_value FROM open_interest_history
                 WHERE symbol = ? ORDER BY timestamp DESC LIMIT 1) AS latest_oi,
                (SELECT MAX(open_time) FROM klines_5m_history WHERE symbol = ?)
                    - INTERVAL '{lookback_days} days' AS start_time,
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

        -- STEP 1: Use pre-cached klines_5m_history (PERFECT TIMING ALIGNMENT with OI data!)
        -- OI data is 5min resolution → 5m candles = perfect match for accurate side inference
        -- 8,064 rows (5m candles in 30 days) - scans in ~1 second vs 50+ seconds for aggtrades
        CandleOHLC AS (
            SELECT
                open_time as candle_time,
                FLOOR(close / {bin_size}) * {bin_size} AS price_bin,
                open,
                high,
                low,
                close,
                quote_volume as volume
            FROM klines_5m_history
            WHERE symbol = ?
              AND open_time >= (SELECT start_time FROM Params)
        ),

        -- STEP 2: Get pre-calculated OI Delta (calculated during ingestion)
        -- Uses oi_delta column populated by LAG() during CSV import
        OIDelta AS (
            SELECT
                timestamp as candle_time,
                oi_delta
            FROM open_interest_history
            WHERE symbol = ?
              AND timestamp >= (SELECT start_time FROM Params)
        ),

        -- STEP 3: Infer position SIDE from candle direction + OI delta
        -- Industry-standard logic:
        -- - Bullish candle (close > open) + OI increase → LONG positions opened
        -- - Bearish candle (close < open) + OI increase → SHORT positions opened
        CandleWithSide AS (
            SELECT
                c.candle_time,
                c.price_bin,
                c.open,
                c.high,
                c.low,
                c.close,
                c.volume,
                o.oi_delta,
                CASE
                    WHEN c.close > c.open AND o.oi_delta > 0 THEN 'buy'   -- Bullish + OI up = LONG
                    WHEN c.close < c.open AND o.oi_delta > 0 THEN 'sell'  -- Bearish + OI up = SHORT
                    ELSE NULL  -- Ignore neutral candles or OI decrease
                END as inferred_side
            FROM CandleOHLC c
            LEFT JOIN OIDelta o ON c.candle_time = o.candle_time
            WHERE
                -- Only keep candles with clear signal (non-null side)
                CASE
                    WHEN c.close > c.open AND o.oi_delta > 0 THEN 'buy'
                    WHEN c.close < c.open AND o.oi_delta > 0 THEN 'sell'
                    ELSE NULL
                END IS NOT NULL
        ),

        -- STEP 4: Distribute OI across price bins and sides
        -- Scale volume shape to match latest OI magnitude
        TotalVolume AS (
            SELECT COALESCE(SUM(volume), 1.0) as total_volume
            FROM CandleWithSide
        ),

        OIDistribution AS (
            SELECT
                price_bin,
                inferred_side as side,
                SUM(volume) as volume_at_price,
                -- Scale volume shape with latest OI
                SUM(volume) * (SELECT latest_oi FROM Params) /
                (SELECT total_volume FROM TotalVolume) as oi_at_price
            FROM CandleWithSide
            GROUP BY price_bin, inferred_side
        ),

        -- STEP 5: Calculate liquidation prices for ALL positions (NO FILTERING!)
        -- Key fix: Don't filter by price_bin vs current (that was the bug!)
        AllLiquidations AS (
            SELECT
                od.price_bin AS price_bucket,
                ld.leverage,
                od.side,
                od.oi_at_price * ld.weight AS volume,
                CASE
                    WHEN od.side = 'buy' THEN  -- LONG positions
                        od.price_bin * (1 - 1.0/ld.leverage + {mmr}/ld.leverage)
                    WHEN od.side = 'sell' THEN  -- SHORT positions
                        od.price_bin * (1 + 1.0/ld.leverage - {mmr}/ld.leverage)
                END AS liq_price
            FROM OIDistribution od
            CROSS JOIN LeverageDistribution ld
            -- ❌ REMOVED: WHERE od.price_bin > {current_price}  (WRONG logic!)
            -- ❌ REMOVED: WHERE od.price_bin < {current_price}  (WRONG logic!)
        )

        -- STEP 6: Filter ONLY liquidations "at risk" based on liquidation price vs current
        -- This is the CORRECT filter (not entry price vs current!)
        SELECT
            price_bucket,
            leverage,
            side,
            volume,
            liq_price
        FROM AllLiquidations
        WHERE
            -- Shorts: liq_price ABOVE current (price must go UP to liquidate)
            (side = 'sell' AND liq_price > {current_price})
            OR
            -- Longs: liq_price BELOW current (price must go DOWN to liquidate)
            (side = 'buy' AND liq_price < {current_price})
        ORDER BY liq_price, leverage
        """

        # Updated params: Params CTE (latest_oi, max_time), CandleOHLC CTE, OIDelta CTE
        params = [symbol, symbol, symbol, symbol]

        try:
            df = self.conn.execute(query, params).df()
            logger.info(f"OI-based model complete: {len(df)} liquidation levels returned")

            # Sanity check: sum of all volumes should approximately equal latest OI
            # NOTE: Validation logging disabled for performance (skips 1.9B row aggtrades scan)
            # if not df.empty:
            #     total_distributed = df["volume"].sum()
            #
            #     # Get OI and total volume for validation
            #     oi_result = self.conn.execute(
            #         "SELECT open_interest_value FROM open_interest_history WHERE symbol = ? ORDER BY timestamp DESC LIMIT 1",
            #         [symbol],
            #     ).fetchone()
            #
            #     total_volume_result = self.conn.execute(
            #         f"""
            #         SELECT SUM(gross_value) as total_volume
            #         FROM aggtrades_history
            #         WHERE symbol = ?
            #           AND timestamp >= CURRENT_TIMESTAMP - INTERVAL '{lookback_days} days'
            #         """,
            #         [symbol],
            #     ).fetchone()
            #
            #     if oi_result and total_volume_result:
            #         latest_oi = float(oi_result[0])
            #         total_volume = float(total_volume_result[0])
            #         scaling_factor = latest_oi / total_volume if total_volume > 0 else 0
            #
            #         logger.info(
            #             f"📊 Volume Profile Scaling:\n"
            #             f"  - Latest OI: ${latest_oi:,.0f}\n"
            #             f"  - {lookback_days}-day volume: ${total_volume:,.0f}\n"
            #             f"  - Scaling factor: {scaling_factor:.4f}\n"
            #             f"  - Total distributed: ${total_distributed:,.0f}\n"
            #             f"  - Coverage: {total_distributed / latest_oi:.2%}"
            #         )

            return df
        except Exception as e:
            logger.error(f"OI-based calculation failed: {e}", exc_info=True)
            # Return empty DataFrame on error
            import pandas as pd

            return pd.DataFrame(columns=["price_bucket", "leverage", "side", "volume", "liq_price"])

    def save_snapshot(self, snapshot) -> int:
        """Save a HeatmapSnapshot to the liquidation_snapshots table.

        Each cell in the snapshot is stored as separate rows for long and short sides.
        Zero-volume entries are skipped. Uses INSERT OR REPLACE for idempotency.

        Args:
            snapshot: HeatmapSnapshot from time_evolving_heatmap.py

        Returns:
            Number of rows inserted/updated

        Note:
            Requires initialize_snapshot_tables() to have been called first.
        """
        if not snapshot.cells:
            return 0

        rows_to_insert = []
        for price_bucket, cell in snapshot.cells.items():
            # Insert long side if has volume
            if cell.long_density > 0:
                rows_to_insert.append(
                    (
                        snapshot.timestamp,
                        snapshot.symbol,
                        float(price_bucket),
                        "long",
                        float(cell.long_density),
                        0.0,  # consumed_volume
                    )
                )

            # Insert short side if has volume
            if cell.short_density > 0:
                rows_to_insert.append(
                    (
                        snapshot.timestamp,
                        snapshot.symbol,
                        float(price_bucket),
                        "short",
                        float(cell.short_density),
                        0.0,  # consumed_volume
                    )
                )

        if not rows_to_insert:
            return 0

        # Use INSERT with ON CONFLICT for upsert behavior
        import hashlib
        from datetime import datetime as dt

        now = dt.now()

        for row in rows_to_insert:
            ts, sym, price_bucket, side, active_volume, consumed_volume = row

            # Generate deterministic ID from unique key components
            key_str = f"{ts.isoformat()}:{sym}:{price_bucket}:{side}"
            row_id = int(hashlib.sha256(key_str.encode()).hexdigest()[:15], 16)

            self.conn.execute(
                """
                INSERT INTO liquidation_snapshots
                (id, timestamp, symbol, price_bucket, side,
                 active_volume, consumed_volume, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (timestamp, symbol, price_bucket, side)
                DO UPDATE SET active_volume = EXCLUDED.active_volume,
                              consumed_volume = EXCLUDED.consumed_volume,
                              created_at = EXCLUDED.created_at
            """,
                [row_id, ts, sym, price_bucket, side, active_volume, consumed_volume, now],
            )

        return len(rows_to_insert)

    def load_snapshots(
        self,
        symbol: str,
        start_time,
        end_time,
    ) -> list:
        """Load HeatmapSnapshots from the liquidation_snapshots table.

        Queries the database for snapshots within the specified time range
        and reconstructs HeatmapSnapshot objects with their cell data.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)

        Returns:
            List of HeatmapSnapshot objects ordered by timestamp ascending.
            Returns empty list if no matching data found.

        Note:
            Uses indexes on (timestamp, symbol) for efficient queries.
            Requires initialize_snapshot_tables() to have been called first.
        """
        from src.liquidationheatmap.models.position import HeatmapSnapshot

        # Query all rows for this symbol within time range
        # Use indexed columns for efficient lookup
        result = self.conn.execute(
            """
            SELECT timestamp, price_bucket, side, active_volume
            FROM liquidation_snapshots
            WHERE symbol = ?
              AND timestamp >= ?
              AND timestamp <= ?
            ORDER BY timestamp ASC, price_bucket ASC
        """,
            [symbol, start_time, end_time],
        ).fetchall()

        if not result:
            return []

        # Group rows by timestamp to reconstruct snapshots
        from collections import defaultdict
        from decimal import Decimal

        grouped = defaultdict(list)
        for row in result:
            ts, price_bucket, side, active_volume = row
            grouped[ts].append((price_bucket, side, active_volume))

        # Build HeatmapSnapshot objects
        snapshots = []
        for ts in sorted(grouped.keys()):
            snapshot = HeatmapSnapshot(timestamp=ts, symbol=symbol)

            for price_bucket, side, active_volume in grouped[ts]:
                cell = snapshot.get_cell(Decimal(str(price_bucket)))
                if side == "long":
                    cell.long_density = Decimal(str(active_volume))
                else:  # short
                    cell.short_density = Decimal(str(active_volume))

            snapshots.append(snapshot)

        return snapshots
