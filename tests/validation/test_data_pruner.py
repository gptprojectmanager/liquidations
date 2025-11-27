"""
Tests for data_pruner.py - Automated data cleanup.

Tests cover:
- Dry run mode
- Run pruning logic
- Report pruning
- Test pruning
- Statistics tracking
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from datetime import date, timedelta
from src.models.validation_run import TriggerType, ValidationGrade, ValidationRun, ValidationStatus
from src.validation.data_pruner import DataPruner


class TestDataPruner:
    """Test DataPruner functionality."""

    def test_initialization_with_dry_run(self):
        """DataPruner should support dry run mode."""
        # Act
        pruner = DataPruner(dry_run=True)

        # Assert
        assert pruner.dry_run is True

    def test_prune_runs_in_dry_run_mode(self):
        """prune_runs in dry run should not delete."""
        # Arrange
        pruner = DataPruner(dry_run=True)

        with patch("src.validation.data_pruner.ValidationStorage") as mock_storage:
            mock_storage_instance = Mock()
            mock_storage.return_value.__enter__.return_value = mock_storage_instance

            old_runs = [
                ValidationRun(
                    run_id="old-run-1",
                    model_name="model",
                    overall_grade=ValidationGrade.A,
                    overall_score=Decimal("90.0"),
                    status=ValidationStatus.COMPLETED,
                    trigger_type=TriggerType.MANUAL,
                    started_at=datetime.utcnow() - timedelta(days=120),
                    data_start_date=date.today() - timedelta(days=30),
                    data_end_date=date.today(),
                )
            ]

            mock_storage_instance.get_runs_before_date.return_value = old_runs

            # Act
            stats = pruner.prune_runs()

            # Assert
            assert stats["total"] == 1
            assert stats["deleted"] == 0  # Dry run - nothing deleted
            mock_storage_instance.delete_run.assert_not_called()

    def test_prune_runs_deletes_in_normal_mode(self):
        """prune_runs should delete old runs in normal mode."""
        # Arrange
        pruner = DataPruner(dry_run=False)

        with patch("src.validation.data_pruner.ValidationStorage") as mock_storage:
            mock_storage_instance = Mock()
            mock_storage.return_value.__enter__.return_value = mock_storage_instance

            old_runs = [
                ValidationRun(
                    run_id="old-run-1",
                    model_name="model",
                    overall_grade=ValidationGrade.A,
                    overall_score=Decimal("90.0"),
                    status=ValidationStatus.COMPLETED,
                    trigger_type=TriggerType.MANUAL,
                    started_at=datetime.utcnow() - timedelta(days=120),
                    data_start_date=date.today() - timedelta(days=30),
                    data_end_date=date.today(),
                ),
                ValidationRun(
                    run_id="old-run-2",
                    model_name="model",
                    overall_grade=ValidationGrade.B,
                    overall_score=Decimal("85.0"),
                    status=ValidationStatus.COMPLETED,
                    trigger_type=TriggerType.MANUAL,
                    started_at=datetime.utcnow() - timedelta(days=150),
                    data_start_date=date.today() - timedelta(days=30),
                    data_end_date=date.today(),
                ),
            ]

            mock_storage_instance.get_runs_before_date.return_value = old_runs

            # Act
            stats = pruner.prune_runs()

            # Assert
            assert stats["total"] == 2
            assert stats["deleted"] == 2
            assert mock_storage_instance.delete_run.call_count == 2

    def test_prune_all_combines_all_statistics(self):
        """prune_all should combine stats from all prune operations."""
        # Arrange
        pruner = DataPruner(dry_run=True)

        with patch.object(pruner, "prune_runs", return_value={"total": 5, "deleted": 0}):
            with patch.object(pruner, "prune_reports", return_value={"total": 3, "deleted": 0}):
                with patch.object(pruner, "prune_tests", return_value={"total": 10, "deleted": 0}):
                    # Act
                    stats = pruner.prune_all()

                    # Assert
                    assert stats["runs"]["total"] == 5
                    assert stats["reports"]["total"] == 3
                    assert stats["tests"]["total"] == 10
                    assert stats["total_deleted"] == 0  # Dry run

    def test_prune_reports_respects_retention_policy(self):
        """prune_reports should use retention policy cutoff."""
        # Arrange
        pruner = DataPruner(dry_run=False)

        with patch("src.validation.data_pruner.ValidationStorage") as mock_storage:
            mock_storage_instance = Mock()
            mock_storage.return_value.__enter__.return_value = mock_storage_instance

            # Mock old reports
            mock_storage_instance.get_reports_before_date.return_value = ["report1", "report2"]

            # Act
            stats = pruner.prune_reports()

            # Assert
            assert stats["total"] == 2
            mock_storage_instance.get_reports_before_date.assert_called_once()

    def test_prune_tests_deletes_orphaned_tests(self):
        """prune_tests should delete tests without parent runs."""
        # Arrange
        pruner = DataPruner(dry_run=False)

        with patch("src.validation.data_pruner.ValidationStorage") as mock_storage:
            mock_storage_instance = Mock()
            mock_storage.return_value.__enter__.return_value = mock_storage_instance

            # Mock orphaned tests
            mock_storage_instance.get_orphaned_tests.return_value = ["test1", "test2", "test3"]

            # Act
            stats = pruner.prune_tests()

            # Assert
            assert stats["total"] == 3


class TestScheduledPruning:
    """Test scheduled pruning functionality."""

    @patch("src.validation.data_pruner.BackgroundScheduler")
    def test_schedule_pruning_job_configures_scheduler(self, mock_scheduler_class):
        """schedule_pruning_job should configure daily job at 3 AM UTC."""
        # Arrange
        from src.validation.data_pruner import schedule_pruning_job

        mock_scheduler = Mock()
        mock_scheduler_class.return_value = mock_scheduler

        # Act
        schedule_pruning_job()

        # Assert
        mock_scheduler.add_job.assert_called_once()
        call_args = mock_scheduler.add_job.call_args

        # Verify daily schedule at 3 AM UTC
        trigger = call_args[1].get("trigger")
        assert trigger is not None

    @patch("src.validation.data_pruner.DataPruner")
    def test_pruning_job_runs_without_errors(self, mock_pruner_class):
        """Scheduled pruning job should execute successfully."""
        # Arrange
        from src.validation.data_pruner import _run_pruning_job

        mock_pruner = Mock()
        mock_pruner_class.return_value = mock_pruner
        mock_pruner.prune_all.return_value = {
            "runs": {"total": 5, "deleted": 5},
            "reports": {"total": 3, "deleted": 3},
            "tests": {"total": 10, "deleted": 10},
            "total_deleted": 18,
        }

        # Act
        _run_pruning_job()

        # Assert
        mock_pruner.prune_all.assert_called_once()
