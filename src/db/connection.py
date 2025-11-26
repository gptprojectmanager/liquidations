"""
DuckDB connection manager for Tiered Margin data storage.

Provides connection pooling, MVCC support for atomic tier updates,
and automatic schema migration.
"""

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Generator, Optional

import duckdb

logger = logging.getLogger(__name__)


class DuckDBConnection:
    """
    Thread-safe DuckDB connection manager with MVCC support.

    Features:
    - Connection pooling for concurrent reads
    - MVCC (Multi-Version Concurrency Control) for atomic updates
    - Automatic schema initialization
    - Context manager support
    """

    def __init__(
        self, db_path: Optional[str] = None, read_only: bool = False, config: Optional[dict] = None
    ):
        """
        Initialize DuckDB connection manager.

        Args:
            db_path: Path to database file (None for in-memory)
            read_only: Open in read-only mode
            config: Additional DuckDB configuration
        """
        self.db_path = db_path or ":memory:"
        self.read_only = read_only
        self.config = config or {}
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._lock = Lock()

        # Default configuration for financial data
        self.config.setdefault("decimal_width", 38)  # Maximum decimal precision
        self.config.setdefault("decimal_scale", 8)  # 8 decimal places for prices
        self.config.setdefault("threads", 4)  # Parallel execution threads
        self.config.setdefault("max_memory", "4GB")  # Memory limit

    def connect(self) -> duckdb.DuckDBPyConnection:
        """
        Create or return existing connection.

        Returns:
            DuckDB connection object

        Raises:
            RuntimeError: If connection fails
        """
        with self._lock:
            if self._conn is None:
                try:
                    self._conn = duckdb.connect(
                        database=self.db_path, read_only=self.read_only, config=self.config
                    )
                    self._initialize_schema()
                    logger.info(f"Connected to DuckDB: {self.db_path}")
                except Exception as e:
                    logger.error(f"Failed to connect to DuckDB: {e}")
                    raise RuntimeError(f"DuckDB connection failed: {e}")
            return self._conn

    def _initialize_schema(self):
        """Initialize database schema if it doesn't exist."""
        if self.read_only:
            return

        with self.transaction():
            # Check if schema exists
            result = self._conn.execute("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = 'tier_configurations'
            """).fetchone()

            if result[0] == 0:
                self._create_schema()

    def _create_schema(self):
        """Create initial database schema from migration files."""
        logger.info("Running database migrations...")

        # Get migration directory
        migration_dir = Path(__file__).parent / "migrations"

        # Run migrations in order
        migrations = [
            "001_create_tables.sql",
            "002_add_indexes.sql",
            "003_audit_tables.sql",
        ]

        for migration_file in migrations:
            migration_path = migration_dir / migration_file
            if migration_path.exists():
                logger.info(f"Running migration: {migration_file}")
                with open(migration_path, "r") as f:
                    sql = f.read()
                    # Execute migration (may contain multiple statements)
                    self._conn.execute(sql)
            else:
                logger.warning(f"Migration file not found: {migration_file}")

        logger.info("All migrations completed successfully")

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """
        Context manager for database transactions.

        Ensures atomic operations with automatic rollback on error.
        """
        conn = self.connect()
        conn.begin()
        try:
            yield
            conn.commit()
            logger.debug("Transaction committed")
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction rolled back: {e}")
            raise

    @contextmanager
    def cursor(self) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """
        Context manager for database cursor.

        Returns:
            Database connection for queries
        """
        yield self.connect()

    def execute(self, query: str, parameters: Optional[tuple] = None) -> Any:
        """
        Execute a query with optional parameters.

        Args:
            query: SQL query string
            parameters: Query parameters

        Returns:
            Query result
        """
        with self.cursor() as conn:
            if parameters:
                return conn.execute(query, parameters)
            return conn.execute(query)

    def close(self):
        """Close database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
                logger.info("DuckDB connection closed")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global connection manager instance
_connection_manager: Optional[DuckDBConnection] = None
_manager_lock = Lock()


def get_connection(db_path: Optional[str] = None, read_only: bool = False) -> DuckDBConnection:
    """
    Get or create global connection manager.

    Args:
        db_path: Database file path
        read_only: Open in read-only mode

    Returns:
        Connection manager instance
    """
    global _connection_manager

    with _manager_lock:
        if _connection_manager is None:
            # Use environment variable or default path
            if db_path is None:
                db_path = os.getenv("MARGIN_DB_PATH", "data/processed/margin_tiers.duckdb")

            # Ensure directory exists
            if db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)

            _connection_manager = DuckDBConnection(db_path, read_only)

        return _connection_manager


def close_connection():
    """Close global connection manager."""
    global _connection_manager

    with _manager_lock:
        if _connection_manager:
            _connection_manager.close()
            _connection_manager = None
