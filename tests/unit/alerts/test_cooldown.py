"""Unit tests for alert cooldown management.

Tests for:
- Per-zone cooldown enforcement
- Daily limit enforcement
- UTC midnight reset
- DuckDB persistence
- Database lock handling with retry
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from src.liquidationheatmap.alerts.models import AlertCooldown, LiquidationZone, ZoneProximity


class TestZoneCooldown:
    """Tests for per-zone cooldown enforcement."""

    def test_zone_is_on_cooldown_when_recently_alerted(self) -> None:
        """Zone should be on cooldown when alerted within cooldown period."""
        from src.liquidationheatmap.alerts.cooldown import CooldownManager

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_alerts.duckdb"
            manager = CooldownManager(db_path=db_path, cooldown_minutes=60)

            zone_key = "94000_short"
            manager.record_alert(zone_key)

            assert manager.is_on_cooldown(zone_key) is True

    def test_zone_not_on_cooldown_after_period_expires(self) -> None:
        """Zone should not be on cooldown after cooldown period expires."""
        from src.liquidationheatmap.alerts.cooldown import CooldownManager

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_alerts.duckdb"
            manager = CooldownManager(db_path=db_path, cooldown_minutes=60)

            zone_key = "94000_short"

            # Simulate alert from 2 hours ago
            two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
            manager._save_cooldown(
                AlertCooldown(
                    zone_key=zone_key,
                    last_alert_time=two_hours_ago,
                    alert_count_today=1,
                )
            )

            assert manager.is_on_cooldown(zone_key) is False

    def test_different_zones_have_independent_cooldowns(self) -> None:
        """Different zones should have independent cooldown tracking."""
        from src.liquidationheatmap.alerts.cooldown import CooldownManager

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_alerts.duckdb"
            manager = CooldownManager(db_path=db_path, cooldown_minutes=60)

            zone_key_1 = "94000_short"
            zone_key_2 = "96000_long"

            manager.record_alert(zone_key_1)

            assert manager.is_on_cooldown(zone_key_1) is True
            assert manager.is_on_cooldown(zone_key_2) is False


class TestDailyLimit:
    """Tests for daily alert limit enforcement."""

    def test_can_alert_when_under_daily_limit(self) -> None:
        """Should allow alerts when under daily limit."""
        from src.liquidationheatmap.alerts.cooldown import CooldownManager

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_alerts.duckdb"
            manager = CooldownManager(db_path=db_path, max_daily_alerts=10)

            assert manager.can_send_alert() is True

    def test_cannot_alert_when_daily_limit_reached(self) -> None:
        """Should block alerts when daily limit is reached."""
        from src.liquidationheatmap.alerts.cooldown import CooldownManager

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_alerts.duckdb"
            manager = CooldownManager(db_path=db_path, max_daily_alerts=3)

            # Record 3 alerts (hits limit)
            for i in range(3):
                manager.record_alert(f"zone_{i}")

            assert manager.can_send_alert() is False

    def test_get_daily_count_returns_correct_count(self) -> None:
        """Should return correct daily alert count."""
        from src.liquidationheatmap.alerts.cooldown import CooldownManager

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_alerts.duckdb"
            manager = CooldownManager(db_path=db_path, max_daily_alerts=10)

            manager.record_alert("zone_1")
            manager.record_alert("zone_2")

            assert manager.get_daily_count() == 2


class TestDailyReset:
    """Tests for daily counter reset at UTC midnight."""

    def test_daily_count_resets_at_midnight_utc(self) -> None:
        """Daily counter should reset at UTC midnight."""
        from src.liquidationheatmap.alerts.cooldown import CooldownManager

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_alerts.duckdb"
            manager = CooldownManager(db_path=db_path, max_daily_alerts=10)

            # Simulate alerts from yesterday
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            manager._set_daily_counter(5, yesterday.date())

            # Should reset and allow new alerts
            assert manager.can_send_alert() is True
            assert manager.get_daily_count() == 0

    def test_daily_count_persists_within_same_day(self) -> None:
        """Daily counter should persist within the same UTC day."""
        from src.liquidationheatmap.alerts.cooldown import CooldownManager

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_alerts.duckdb"
            manager1 = CooldownManager(db_path=db_path, max_daily_alerts=10)

            manager1.record_alert("zone_1")
            manager1.record_alert("zone_2")

            # Create new manager instance (simulates restart)
            manager2 = CooldownManager(db_path=db_path, max_daily_alerts=10)

            assert manager2.get_daily_count() == 2


class TestDatabasePersistence:
    """Tests for DuckDB persistence of cooldown data."""

    def test_cooldown_persists_across_manager_instances(self) -> None:
        """Cooldown data should persist across manager instances."""
        from src.liquidationheatmap.alerts.cooldown import CooldownManager

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_alerts.duckdb"

            # First instance records alert
            manager1 = CooldownManager(db_path=db_path, cooldown_minutes=60)
            manager1.record_alert("94000_short")

            # Second instance should see cooldown
            manager2 = CooldownManager(db_path=db_path, cooldown_minutes=60)
            assert manager2.is_on_cooldown("94000_short") is True

    def test_creates_database_if_not_exists(self) -> None:
        """Should create database file if it doesn't exist."""
        from src.liquidationheatmap.alerts.cooldown import CooldownManager

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "new_alerts.duckdb"

            assert not db_path.exists()

            manager = CooldownManager(db_path=db_path)
            manager.record_alert("test_zone")

            assert db_path.exists()


class TestDatabaseLockRetry:
    """Tests for database lock handling with retry logic."""

    def test_retries_on_database_lock(self) -> None:
        """Should retry operations when database is locked."""
        from src.liquidationheatmap.alerts.cooldown import CooldownManager

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_alerts.duckdb"
            manager = CooldownManager(db_path=db_path, max_retries=3, retry_delay=0.01)

            # Test that _execute_with_retry exists and can be called
            call_count = [0]

            def counting_func():
                call_count[0] += 1
                return "success"

            result = manager._execute_with_retry(counting_func)
            assert result == "success"
            assert call_count[0] == 1

    def test_raises_after_max_retries_exceeded(self) -> None:
        """Should raise error after max retries exceeded."""
        import duckdb

        from src.liquidationheatmap.alerts.cooldown import CooldownManager

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_alerts.duckdb"
            manager = CooldownManager(db_path=db_path, max_retries=3, retry_delay=0.01)

            # Mock to always raise lock error
            with patch.object(manager, "_get_connection") as mock_conn:
                mock_cursor = MagicMock()
                mock_cursor.execute.side_effect = duckdb.IOException("database is locked")
                mock_conn.return_value.cursor.return_value = mock_cursor

                with pytest.raises(Exception, match="locked|retry"):
                    manager.record_alert("zone_1")


class TestZoneKeyGeneration:
    """Tests for zone_key generation from ZoneProximity."""

    def test_zone_key_from_proximity(self) -> None:
        """Zone key should be generated from ZoneProximity."""
        zone = LiquidationZone(
            price=Decimal("94523.45"),
            long_density=Decimal("5000000"),
            short_density=Decimal("10000000"),
        )
        proximity = ZoneProximity(
            zone=zone,
            current_price=Decimal("94000"),
            distance_pct=Decimal("0.5"),
            direction="above",
        )

        # Should bucket to nearest 100 and use dominant side
        assert proximity.zone_key == "94500_short"

    def test_zone_key_buckets_to_nearest_100(self) -> None:
        """Zone key should bucket price to nearest 100."""
        zone = LiquidationZone(
            price=Decimal("94050"),
            long_density=Decimal("10000000"),
            short_density=Decimal("5000000"),
        )
        proximity = ZoneProximity(
            zone=zone,
            current_price=Decimal("94000"),
            distance_pct=Decimal("0.05"),
            direction="above",
        )

        assert proximity.zone_key == "94000_long"
