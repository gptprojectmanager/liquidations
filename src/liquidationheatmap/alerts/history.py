"""Alert history logging to DuckDB.

Provides persistent storage of alert history for:
- Debugging and monitoring
- Analytics and reporting
- Audit trail
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from .models import Alert, AlertSeverity, DeliveryStatus

logger = logging.getLogger(__name__)


class AlertHistoryStore:
    """Stores alert history in DuckDB.

    Features:
    - Persistent storage of all alerts
    - Retention policy (auto-cleanup old alerts)
    - Query methods for analytics
    """

    def __init__(self, db_path: Path, retention_days: int = 90):
        """Initialize the history store.

        Args:
            db_path: Path to DuckDB database file
            retention_days: Number of days to retain alerts
        """
        self.db_path = db_path
        self.retention_days = retention_days
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database table if it doesn't exist."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY,
                    timestamp TIMESTAMP WITH TIME ZONE,
                    symbol VARCHAR,
                    current_price DECIMAL(18, 8),
                    zone_price DECIMAL(18, 8),
                    zone_density DECIMAL(24, 8),
                    zone_side VARCHAR,
                    distance_pct DECIMAL(8, 4),
                    severity VARCHAR,
                    message VARCHAR,
                    channels_sent VARCHAR,
                    delivery_status VARCHAR,
                    error_message VARCHAR
                )
            """)
            cursor.execute("""
                CREATE SEQUENCE IF NOT EXISTS alert_history_id_seq START 1
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get a database connection."""
        return duckdb.connect(str(self.db_path))

    def save_alert(self, alert: Alert) -> int:
        """Save an alert to history.

        Args:
            alert: Alert to save

        Returns:
            The assigned alert ID
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Get next ID
            result = cursor.execute("SELECT nextval('alert_history_id_seq')").fetchone()
            alert_id = result[0]

            cursor.execute(
                """
                INSERT INTO alert_history (
                    id, timestamp, symbol, current_price, zone_price,
                    zone_density, zone_side, distance_pct, severity,
                    message, channels_sent, delivery_status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    alert_id,
                    alert.timestamp,
                    alert.symbol,
                    float(alert.current_price),
                    float(alert.zone_price),
                    float(alert.zone_density),
                    alert.zone_side,
                    float(alert.distance_pct),
                    alert.severity.value,
                    alert.message,
                    ",".join(alert.channels_sent),
                    alert.delivery_status.value,
                    alert.error_message,
                ],
            )
            conn.commit()

            logger.info(f"Saved alert {alert_id} to history")
            return alert_id
        finally:
            conn.close()

    def get_recent_alerts(self, limit: int = 100) -> list[Alert]:
        """Get recent alerts from history.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of Alert instances, most recent first
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            results = cursor.execute(
                """
                SELECT id, timestamp, symbol, current_price, zone_price,
                       zone_density, zone_side, distance_pct, severity,
                       message, channels_sent, delivery_status, error_message
                FROM alert_history
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                [limit],
            ).fetchall()

            from decimal import Decimal

            alerts = []
            for row in results:
                alerts.append(
                    Alert(
                        id=row[0],
                        timestamp=row[1],
                        symbol=row[2],
                        current_price=Decimal(str(row[3])) if row[3] else Decimal("0"),
                        zone_price=Decimal(str(row[4])) if row[4] else Decimal("0"),
                        zone_density=Decimal(str(row[5])) if row[5] else Decimal("0"),
                        zone_side=row[6] or "long",
                        distance_pct=Decimal(str(row[7])) if row[7] else Decimal("0"),
                        severity=AlertSeverity(row[8]) if row[8] else AlertSeverity.INFO,
                        message=row[9],
                        channels_sent=row[10].split(",") if row[10] else [],
                        delivery_status=DeliveryStatus(row[11])
                        if row[11]
                        else DeliveryStatus.PENDING,
                        error_message=row[12],
                    )
                )

            return alerts
        finally:
            conn.close()

    def cleanup_old_alerts(self) -> int:
        """Remove alerts older than retention period.

        Returns:
            Number of alerts deleted
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            from datetime import timedelta

            # Get cutoff date
            cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff = cutoff - timedelta(days=self.retention_days)

            # Count before delete
            count_before = cursor.execute(
                "SELECT COUNT(*) FROM alert_history WHERE timestamp < ?",
                [cutoff],
            ).fetchone()[0]

            # Delete old alerts
            cursor.execute(
                "DELETE FROM alert_history WHERE timestamp < ?",
                [cutoff],
            )
            conn.commit()

            if count_before > 0:
                logger.info(f"Cleaned up {count_before} old alerts")

            return count_before
        finally:
            conn.close()

    def get_alert_count(self, since: datetime | None = None) -> int:
        """Get count of alerts in history.

        Args:
            since: Optional start date filter

        Returns:
            Number of alerts
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if since:
                result = cursor.execute(
                    "SELECT COUNT(*) FROM alert_history WHERE timestamp >= ?",
                    [since],
                ).fetchone()
            else:
                result = cursor.execute("SELECT COUNT(*) FROM alert_history").fetchone()

            return result[0]
        finally:
            conn.close()
