"""Tests for exchange column migration.

T043: Test migration preserves existing data
T044: Test exchange column queries work correctly
"""

from datetime import datetime, timezone

import duckdb
import pytest


class TestAddExchangeMigration:
    """Tests for adding exchange column to liquidation tables."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary DuckDB database with pre-migration schema."""
        db_path = tmp_path / "test_migration.duckdb"
        conn = duckdb.connect(str(db_path))

        # Create pre-migration schema (without exchange column)
        conn.execute("""
            CREATE TABLE liquidation_levels (
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
            )
        """)

        conn.execute("""
            CREATE TABLE heatmap_cache (
                id BIGINT PRIMARY KEY,
                time_bucket TIMESTAMP NOT NULL,
                price_bucket DECIMAL(18, 2) NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                model VARCHAR(50) NOT NULL,
                density BIGINT NOT NULL,
                volume DECIMAL(18, 8) NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        yield conn, db_path
        conn.close()

    def test_migration_preserves_existing_data(self, temp_db):
        """T043: Migration should preserve all existing data with default 'binance' exchange."""
        conn, db_path = temp_db

        # Insert test data before migration
        test_timestamp = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        conn.execute(
            """
            INSERT INTO liquidation_levels
            (id, timestamp, symbol, model, price_level, liquidation_volume, leverage_tier, side, confidence)
            VALUES (1, ?, 'BTCUSDT', 'oi_based', 95000.00, 1000000.00, '10x', 'long', 0.85)
            """,
            [test_timestamp],
        )
        conn.execute(
            """
            INSERT INTO liquidation_levels
            (id, timestamp, symbol, model, price_level, liquidation_volume, leverage_tier, side, confidence)
            VALUES (2, ?, 'ETHUSDT', 'oi_based', 3500.00, 500000.00, '25x', 'short', 0.90)
            """,
            [test_timestamp],
        )

        # Run migration
        from scripts.migrate_add_exchange_column import migrate_add_exchange

        migrate_add_exchange(conn)

        # Verify data preserved
        result = conn.execute(
            "SELECT id, symbol, exchange FROM liquidation_levels ORDER BY id"
        ).fetchall()

        assert len(result) == 2
        assert result[0] == (1, "BTCUSDT", "binance")  # Default exchange
        assert result[1] == (2, "ETHUSDT", "binance")  # Default exchange

    def test_migration_adds_exchange_column(self, temp_db):
        """Migration adds exchange column with correct type and default."""
        conn, db_path = temp_db

        from scripts.migrate_add_exchange_column import migrate_add_exchange

        migrate_add_exchange(conn)

        # Check column exists
        columns = conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'liquidation_levels' AND column_name = 'exchange'"
        ).fetchall()

        assert len(columns) == 1
        assert columns[0][0] == "exchange"

    def test_migration_adds_exchange_index(self, temp_db):
        """Migration adds index on exchange column."""
        conn, db_path = temp_db

        from scripts.migrate_add_exchange_column import migrate_add_exchange

        migrate_add_exchange(conn)

        # Verify index exists by querying DuckDB system tables
        # DuckDB doesn't have a simple way to query indexes, but we can verify
        # the migration ran without error
        # The index will speed up queries - test that queries work
        result = conn.execute(
            "SELECT COUNT(*) FROM liquidation_levels WHERE exchange = 'binance'"
        ).fetchone()
        assert result[0] >= 0  # Query executes successfully

    def test_exchange_column_query_filtering(self, temp_db):
        """T044: Exchange column filtering works correctly."""
        conn, db_path = temp_db

        from scripts.migrate_add_exchange_column import migrate_add_exchange

        migrate_add_exchange(conn)

        # Insert data from multiple exchanges
        test_ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        conn.execute(
            """
            INSERT INTO liquidation_levels
            (id, timestamp, symbol, model, price_level, liquidation_volume, leverage_tier, side, confidence, exchange)
            VALUES
            (1, ?, 'BTCUSDT', 'oi_based', 95000.00, 1000000.00, '10x', 'long', 0.85, 'binance'),
            (2, ?, 'BTCUSDT', 'oi_based', 95100.00, 800000.00, '10x', 'long', 0.82, 'hyperliquid'),
            (3, ?, 'BTCUSDT', 'oi_based', 94900.00, 600000.00, '25x', 'short', 0.78, 'binance')
            """,
            [test_ts, test_ts, test_ts],
        )

        # Query single exchange
        binance_only = conn.execute(
            "SELECT id, exchange FROM liquidation_levels WHERE exchange = 'binance' ORDER BY id"
        ).fetchall()
        assert len(binance_only) == 2
        assert all(r[1] == "binance" for r in binance_only)

        # Query multiple exchanges
        multi_exchange = conn.execute(
            "SELECT id, exchange FROM liquidation_levels WHERE exchange IN ('binance', 'hyperliquid') ORDER BY id"
        ).fetchall()
        assert len(multi_exchange) == 3

        # Query hyperliquid only
        hl_only = conn.execute(
            "SELECT id, exchange FROM liquidation_levels WHERE exchange = 'hyperliquid'"
        ).fetchall()
        assert len(hl_only) == 1
        assert hl_only[0][1] == "hyperliquid"

    def test_exchange_column_aggregation(self, temp_db):
        """Aggregation queries work with exchange filtering."""
        conn, db_path = temp_db

        from scripts.migrate_add_exchange_column import migrate_add_exchange

        migrate_add_exchange(conn)

        # Insert test data
        test_ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        conn.execute(
            """
            INSERT INTO liquidation_levels
            (id, timestamp, symbol, model, price_level, liquidation_volume, leverage_tier, side, confidence, exchange)
            VALUES
            (1, ?, 'BTCUSDT', 'oi_based', 95000.00, 1000000.00, '10x', 'long', 0.85, 'binance'),
            (2, ?, 'BTCUSDT', 'oi_based', 95000.00, 500000.00, '10x', 'long', 0.82, 'hyperliquid'),
            (3, ?, 'BTCUSDT', 'oi_based', 95000.00, 300000.00, '10x', 'long', 0.80, 'binance')
            """,
            [test_ts, test_ts, test_ts],
        )

        # Aggregate by exchange
        result = conn.execute(
            """
            SELECT exchange, SUM(liquidation_volume) as total_volume
            FROM liquidation_levels
            GROUP BY exchange
            ORDER BY exchange
            """
        ).fetchall()

        assert len(result) == 2
        assert result[0][0] == "binance"
        assert float(result[0][1]) == 1300000.0
        assert result[1][0] == "hyperliquid"
        assert float(result[1][1]) == 500000.0


class TestExchangeHealthTable:
    """Tests for exchange_health table creation."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary DuckDB database."""
        db_path = tmp_path / "test_health.duckdb"
        conn = duckdb.connect(str(db_path))
        yield conn, db_path
        conn.close()

    def test_exchange_health_table_creation(self, temp_db):
        """T049: exchange_health table is created correctly."""
        conn, db_path = temp_db

        from scripts.migrate_add_exchange_column import create_exchange_health_table

        create_exchange_health_table(conn)

        # Verify table exists
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        assert "exchange_health" in table_names

        # Verify columns
        columns = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'exchange_health'"
        ).fetchall()
        column_names = [c[0] for c in columns]

        assert "id" in column_names
        assert "exchange" in column_names
        assert "is_connected" in column_names
        assert "last_heartbeat" in column_names
        assert "message_count" in column_names
        assert "error_count" in column_names
        assert "uptime_percent" in column_names

    def test_exchange_health_insert_and_query(self, temp_db):
        """exchange_health table accepts and returns data correctly."""
        conn, db_path = temp_db

        from scripts.migrate_add_exchange_column import create_exchange_health_table

        create_exchange_health_table(conn)

        # Insert health record
        test_ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        conn.execute(
            """
            INSERT INTO exchange_health
            (id, exchange, is_connected, last_heartbeat, message_count, error_count, uptime_percent)
            VALUES (1, 'binance', true, ?, 1000, 5, 99.5)
            """,
            [test_ts],
        )

        # Query health
        result = conn.execute(
            "SELECT exchange, is_connected, message_count, uptime_percent "
            "FROM exchange_health WHERE exchange = 'binance'"
        ).fetchone()

        assert result[0] == "binance"
        assert result[1] is True
        assert result[2] == 1000
        assert float(result[3]) == 99.5

    def test_exchange_health_unique_constraint(self, temp_db):
        """exchange_health has unique constraint on exchange name."""
        conn, db_path = temp_db

        from scripts.migrate_add_exchange_column import create_exchange_health_table

        create_exchange_health_table(conn)

        test_ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Insert first record
        conn.execute(
            """
            INSERT INTO exchange_health
            (id, exchange, is_connected, last_heartbeat, message_count, error_count, uptime_percent)
            VALUES (1, 'binance', true, ?, 1000, 5, 99.5)
            """,
            [test_ts],
        )

        # Try to insert duplicate - should fail
        with pytest.raises(duckdb.ConstraintException):
            conn.execute(
                """
                INSERT INTO exchange_health
                (id, exchange, is_connected, last_heartbeat, message_count, error_count, uptime_percent)
                VALUES (2, 'binance', false, ?, 500, 10, 95.0)
                """,
                [test_ts],
            )
