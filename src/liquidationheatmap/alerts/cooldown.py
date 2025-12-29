"""Cooldown management for rate-limiting alerts.

Provides per-zone cooldown and daily limit enforcement
with DuckDB persistence.
"""

import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb

from .models import AlertCooldown

logger = logging.getLogger(__name__)


class CooldownManager:
    """Manages alert cooldowns with DuckDB persistence.

    Features:
    - Per-zone cooldown (e.g., 1 hour between alerts for same zone)
    - Daily limit (e.g., max 10 alerts per day)
    - Persistence across restarts
    - Database lock retry logic
    """

    def __init__(
        self,
        db_path: Path,
        cooldown_minutes: int = 60,
        max_daily_alerts: int = 10,
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ):
        """Initialize the cooldown manager.

        Args:
            db_path: Path to DuckDB database file
            cooldown_minutes: Cooldown period per zone in minutes
            max_daily_alerts: Maximum alerts per day
            max_retries: Maximum retries on database lock
            retry_delay: Delay between retries in seconds
        """
        self.db_path = db_path
        self.cooldown_minutes = cooldown_minutes
        self.max_daily_alerts = max_daily_alerts
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database tables if they don't exist."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_cooldowns (
                    zone_key VARCHAR PRIMARY KEY,
                    last_alert_time TIMESTAMP WITH TIME ZONE,
                    alert_count_today INTEGER DEFAULT 0,
                    last_reset_date DATE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_counter (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    count INTEGER DEFAULT 0,
                    reset_date DATE
                )
            """)
            # Initialize daily counter if not exists
            cursor.execute("""
                INSERT OR IGNORE INTO daily_counter (id, count, reset_date)
                VALUES (1, 0, CURRENT_DATE)
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get a database connection."""
        return duckdb.connect(str(self.db_path))

    def _execute_with_retry(self, func, *args, **kwargs):
        """Execute a function with retry on database lock."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except duckdb.IOException as e:
                last_error = e
                if "locked" in str(e).lower():
                    logger.warning(f"Database locked, retry {attempt + 1}/{self.max_retries}")
                    time.sleep(self.retry_delay)
                else:
                    raise
        raise RuntimeError(f"Max retries exceeded: {last_error}")

    def is_on_cooldown(self, zone_key: str) -> bool:
        """Check if a zone is currently on cooldown.

        Args:
            zone_key: Unique identifier for the zone

        Returns:
            True if zone is on cooldown, False otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            result = cursor.execute(
                "SELECT last_alert_time FROM alert_cooldowns WHERE zone_key = ?",
                [zone_key],
            ).fetchone()

            if result is None:
                return False

            last_alert_time = result[0]
            if last_alert_time is None:
                return False

            # Handle timezone-aware comparison
            now = datetime.now(timezone.utc)
            if last_alert_time.tzinfo is None:
                last_alert_time = last_alert_time.replace(tzinfo=timezone.utc)

            cooldown_delta = timedelta(minutes=self.cooldown_minutes)
            return now - last_alert_time < cooldown_delta
        finally:
            conn.close()

    def can_send_alert(self) -> bool:
        """Check if we can send an alert (under daily limit).

        Returns:
            True if under daily limit, False otherwise
        """
        self._check_daily_reset()
        return self.get_daily_count() < self.max_daily_alerts

    def get_daily_count(self) -> int:
        """Get the current daily alert count.

        Returns:
            Number of alerts sent today
        """
        self._check_daily_reset()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            result = cursor.execute("SELECT count FROM daily_counter WHERE id = 1").fetchone()
            return result[0] if result else 0
        finally:
            conn.close()

    def _check_daily_reset(self) -> None:
        """Check and reset daily counter if new day."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            result = cursor.execute("SELECT reset_date FROM daily_counter WHERE id = 1").fetchone()

            if result:
                reset_date = result[0]
                today = datetime.now(timezone.utc).date()

                if reset_date is None or (isinstance(reset_date, date) and reset_date < today):
                    cursor.execute(
                        "UPDATE daily_counter SET count = 0, reset_date = ? WHERE id = 1",
                        [today],
                    )
                    conn.commit()
        finally:
            conn.close()

    def record_alert(self, zone_key: str) -> None:
        """Record that an alert was sent for a zone.

        Args:
            zone_key: Unique identifier for the zone
        """
        now = datetime.now(timezone.utc)
        today = now.date()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Update or insert cooldown record
            cursor.execute(
                """
                INSERT INTO alert_cooldowns (zone_key, last_alert_time, alert_count_today, last_reset_date)
                VALUES (?, ?, 1, ?)
                ON CONFLICT (zone_key) DO UPDATE SET
                    last_alert_time = excluded.last_alert_time,
                    alert_count_today = alert_cooldowns.alert_count_today + 1,
                    last_reset_date = excluded.last_reset_date
            """,
                [zone_key, now, today],
            )

            # Increment daily counter
            cursor.execute("UPDATE daily_counter SET count = count + 1 WHERE id = 1")

            conn.commit()
            logger.info(f"Recorded alert for zone {zone_key}")
        finally:
            conn.close()

    def _save_cooldown(self, cooldown: AlertCooldown) -> None:
        """Save a cooldown record (used for testing).

        Args:
            cooldown: AlertCooldown instance to save
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO alert_cooldowns (zone_key, last_alert_time, alert_count_today, last_reset_date)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (zone_key) DO UPDATE SET
                    last_alert_time = excluded.last_alert_time,
                    alert_count_today = excluded.alert_count_today,
                    last_reset_date = excluded.last_reset_date
            """,
                [
                    cooldown.zone_key,
                    cooldown.last_alert_time,
                    cooldown.alert_count_today,
                    cooldown.last_reset_date,
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def _set_daily_counter(self, count: int, reset_date: date) -> None:
        """Set daily counter (used for testing).

        Args:
            count: Alert count
            reset_date: Date when counter was last reset
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE daily_counter SET count = ?, reset_date = ? WHERE id = 1",
                [count, reset_date],
            )
            conn.commit()
        finally:
            conn.close()

    def get_cooldown(self, zone_key: str) -> AlertCooldown | None:
        """Get cooldown record for a zone.

        Args:
            zone_key: Unique identifier for the zone

        Returns:
            AlertCooldown instance or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            result = cursor.execute(
                """SELECT zone_key, last_alert_time, alert_count_today, last_reset_date
                   FROM alert_cooldowns WHERE zone_key = ?""",
                [zone_key],
            ).fetchone()

            if result is None:
                return None

            return AlertCooldown(
                zone_key=result[0],
                last_alert_time=result[1],
                alert_count_today=result[2],
                last_reset_date=result[3],
            )
        finally:
            conn.close()
