"""
Tests for retention_policy.py - 90-day data retention policy.

Tests cover:
- Retention period configuration
- Cutoff date calculation
- Retention decision logic
- Statistics calculation
"""

from datetime import datetime, timedelta

from src.validation.retention_policy import RetentionPolicy, get_retention_policy


class TestRetentionPolicy:
    """Test RetentionPolicy functionality."""

    def test_initialization_with_defaults(self):
        """RetentionPolicy should initialize with 90-day default."""
        # Act
        policy = RetentionPolicy()

        # Assert
        assert policy.run_retention_days == 90
        assert policy.report_retention_days == 90
        assert policy.alert_retention_days == 30

    def test_get_run_cutoff_date_returns_90_days_ago(self):
        """get_run_cutoff_date should return date 90 days ago."""
        # Arrange
        policy = RetentionPolicy(run_retention_days=90)
        now = datetime.utcnow()
        expected_cutoff = now - timedelta(days=90)

        # Act
        cutoff = policy.get_run_cutoff_date()

        # Assert
        # Allow 1 second tolerance for test execution time
        assert abs((cutoff - expected_cutoff).total_seconds()) < 1

    def test_should_retain_run_returns_true_for_recent_date(self):
        """should_retain_run should return True for dates within retention."""
        # Arrange
        policy = RetentionPolicy(run_retention_days=90)
        recent_date = datetime.utcnow() - timedelta(days=30)

        # Act
        result = policy.should_retain_run(recent_date)

        # Assert
        assert result is True

    def test_should_retain_run_returns_false_for_old_date(self):
        """should_retain_run should return False for dates beyond retention."""
        # Arrange
        policy = RetentionPolicy(run_retention_days=90)
        old_date = datetime.utcnow() - timedelta(days=120)

        # Act
        result = policy.should_retain_run(old_date)

        # Assert
        assert result is False

    def test_should_retain_report_uses_report_retention_days(self):
        """should_retain_report should use report_retention_days."""
        # Arrange
        policy = RetentionPolicy(report_retention_days=60)
        date_70_days_ago = datetime.utcnow() - timedelta(days=70)
        date_50_days_ago = datetime.utcnow() - timedelta(days=50)

        # Act
        old_result = policy.should_retain_report(date_70_days_ago)
        recent_result = policy.should_retain_report(date_50_days_ago)

        # Assert
        assert old_result is False  # Beyond 60 days
        assert recent_result is True  # Within 60 days

    def test_should_retain_alert_uses_alert_retention_days(self):
        """should_retain_alert should use alert_retention_days."""
        # Arrange
        policy = RetentionPolicy(alert_retention_days=30)
        date_40_days_ago = datetime.utcnow() - timedelta(days=40)
        date_20_days_ago = datetime.utcnow() - timedelta(days=20)

        # Act
        old_result = policy.should_retain_alert(date_40_days_ago)
        recent_result = policy.should_retain_alert(date_20_days_ago)

        # Assert
        assert old_result is False  # Beyond 30 days
        assert recent_result is True  # Within 30 days

    def test_calculate_retention_stats_counts_correctly(self):
        """calculate_retention_stats should count retained vs deleted."""
        # Arrange
        policy = RetentionPolicy(run_retention_days=90)

        run_dates = [
            datetime.utcnow() - timedelta(days=30),  # Retained
            datetime.utcnow() - timedelta(days=60),  # Retained
            datetime.utcnow() - timedelta(days=120),  # Deleted
            datetime.utcnow() - timedelta(days=150),  # Deleted
        ]

        # Act
        stats = policy.calculate_retention_stats(
            run_dates=run_dates,
            report_dates=[],
            alert_dates=[],
        )

        # Assert
        assert stats["runs"]["total"] == 4
        assert stats["runs"]["retained"] == 2
        assert stats["runs"]["deleted"] == 2

    def test_custom_retention_periods_can_be_configured(self):
        """RetentionPolicy should accept custom retention periods."""
        # Act
        policy = RetentionPolicy(
            run_retention_days=120,
            report_retention_days=45,
            alert_retention_days=15,
        )

        # Assert
        assert policy.run_retention_days == 120
        assert policy.report_retention_days == 45
        assert policy.alert_retention_days == 15

    def test_get_retention_policy_returns_singleton(self):
        """get_retention_policy should return same instance."""
        # Act
        policy1 = get_retention_policy()
        policy2 = get_retention_policy()

        # Assert
        assert policy1 is policy2


class TestRetentionEdgeCases:
    """Test edge cases for retention policy."""

    def test_retention_at_exactly_cutoff_date(self):
        """Date exactly at cutoff should be retained."""
        # Arrange
        policy = RetentionPolicy(run_retention_days=90)
        cutoff_date = policy.get_run_cutoff_date()

        # Act
        result = policy.should_retain_run(cutoff_date, cutoff=cutoff_date)

        # Assert
        assert result is True  # Exactly at cutoff should be retained

    def test_retention_one_second_before_cutoff(self):
        """Date one second before cutoff should be retained."""
        # Arrange
        policy = RetentionPolicy(run_retention_days=90)
        cutoff_date = policy.get_run_cutoff_date()
        just_before = cutoff_date + timedelta(seconds=1)

        # Act
        result = policy.should_retain_run(just_before)

        # Assert
        assert result is True

    def test_retention_one_second_after_cutoff(self):
        """Date one second after cutoff should be deleted."""
        # Arrange
        policy = RetentionPolicy(run_retention_days=90)
        cutoff_date = policy.get_run_cutoff_date()
        just_after = cutoff_date - timedelta(seconds=1)

        # Act
        result = policy.should_retain_run(just_after)

        # Assert
        assert result is False
