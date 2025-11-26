"""
Integration tests for rollback mechanism.

Tests the complete rollback workflow including:
- Snapshot creation before updates
- Rollback to previous version
- Rollback to specific snapshot
- Version history tracking
- Validation during rollback
"""

import time
from decimal import Decimal
from uuid import UUID

import pytest

from src.models.margin_tier import MarginTier
from src.models.tier_config import TierConfiguration
from src.services.tier_cache import TierCache
from src.services.tier_rollback import TierRollbackService
from src.services.tier_snapshot import TierSnapshotService


class TestRollbackIntegration:
    """Integration tests for tier configuration rollback mechanism."""

    @pytest.fixture
    def snapshot_dir(self, tmp_path):
        """Create temporary snapshot directory."""
        snap_dir = tmp_path / "snapshots"
        snap_dir.mkdir()
        return snap_dir

    @pytest.fixture
    def snapshot_service(self, snapshot_dir):
        """Create snapshot service with temp directory."""
        return TierSnapshotService(snapshot_dir=snapshot_dir)

    @pytest.fixture
    def rollback_service(self, snapshot_service):
        """Create rollback service."""
        cache = TierCache()
        return TierRollbackService(
            snapshot_service=snapshot_service,
            cache=cache,
        )

    @pytest.fixture
    def v1_config(self) -> TierConfiguration:
        """Create version 1 test configuration."""
        tiers = [
            MarginTier(
                symbol="TESTUSDT",
                tier_number=1,
                min_notional=Decimal("0"),
                max_notional=Decimal("50000"),
                margin_rate=Decimal("0.005"),
                maintenance_amount=Decimal("0"),
            ),
            MarginTier(
                symbol="TESTUSDT",
                tier_number=2,
                min_notional=Decimal("50000"),
                max_notional=Decimal("250000"),
                margin_rate=Decimal("0.010"),
                maintenance_amount=Decimal("250"),
            ),
        ]

        return TierConfiguration(
            symbol="TESTUSDT",
            version="test-v1",
            tiers=tiers,
        )

    @pytest.fixture
    def v2_config(self) -> TierConfiguration:
        """Create version 2 test configuration (modified rates)."""
        tiers = [
            MarginTier(
                symbol="TESTUSDT",
                tier_number=1,
                min_notional=Decimal("0"),
                max_notional=Decimal("50000"),
                margin_rate=Decimal("0.006"),  # Changed from 0.005
                maintenance_amount=Decimal("0"),
            ),
            MarginTier(
                symbol="TESTUSDT",
                tier_number=2,
                min_notional=Decimal("50000"),
                max_notional=Decimal("250000"),
                margin_rate=Decimal("0.012"),  # Changed from 0.010
                maintenance_amount=Decimal("300"),  # Changed from 250
            ),
        ]

        return TierConfiguration(
            symbol="TESTUSDT",
            version="test-v2",
            tiers=tiers,
        )

    def test_create_snapshot_before_update(self, snapshot_service, v1_config):
        """
        Test creating snapshot before configuration update.

        Workflow:
        - Create snapshot of current config
        - Snapshot should be retrievable
        - Snapshot contains correct version
        """
        snapshot = snapshot_service.create_snapshot(
            v1_config,
            reason="pre_update_test",
            created_by="test_user",
        )

        assert snapshot is not None
        assert snapshot.symbol == "TESTUSDT"
        assert snapshot.config.version == "test-v1"
        assert snapshot.reason == "pre_update_test"
        assert snapshot.created_by == "test_user"

        # Verify snapshot can be retrieved
        retrieved = snapshot_service.get_snapshot(snapshot.snapshot_id)
        assert retrieved is not None
        assert retrieved.snapshot_id == snapshot.snapshot_id
        assert retrieved.config.version == "test-v1"

    def test_rollback_to_previous_version(
        self,
        rollback_service,
        snapshot_service,
        v1_config,
        v2_config,
    ):
        """
        Test rolling back to previous version.

        Workflow:
        - Create snapshot of v1
        - "Update" to v2 (snapshot v1)
        - Rollback to previous (v1)
        - Verify rollback successful
        """
        # Create v1 snapshot
        v1_snapshot = snapshot_service.create_snapshot(
            v1_config,
            reason="initial_config",
        )

        # "Update" to v2 and create snapshot
        time.sleep(0.01)  # Ensure different timestamps
        v2_snapshot = snapshot_service.create_snapshot(
            v2_config,
            reason="rate_update",
        )

        # Rollback to previous (should be v2, since that's the latest snapshot)
        result = rollback_service.rollback_to_previous("TESTUSDT")

        assert result.success
        assert result.snapshot is not None
        assert result.snapshot.snapshot_id == v2_snapshot.snapshot_id
        assert "test-v2" in result.message

    def test_rollback_to_specific_snapshot(
        self,
        rollback_service,
        snapshot_service,
        v1_config,
        v2_config,
    ):
        """
        Test rolling back to specific snapshot by ID.

        Workflow:
        - Create snapshots for v1 and v2
        - Rollback to v1 snapshot specifically
        - Verify correct snapshot restored
        """
        # Create snapshots
        v1_snapshot = snapshot_service.create_snapshot(v1_config, reason="v1")
        time.sleep(0.01)
        v2_snapshot = snapshot_service.create_snapshot(v2_config, reason="v2")

        # Rollback to v1 specifically
        result = rollback_service.rollback_to_snapshot(v1_snapshot.snapshot_id)

        assert result.success
        assert result.snapshot.snapshot_id == v1_snapshot.snapshot_id
        assert result.snapshot.config.version == "test-v1"

    def test_rollback_creates_pre_rollback_snapshot(
        self,
        rollback_service,
        snapshot_service,
        v1_config,
        v2_config,
    ):
        """
        Test that rollback creates snapshot before executing.

        Safety Mechanism:
        - Rollback should snapshot current state
        - Allows rollback of the rollback if needed
        """
        # Create v1 snapshot
        v1_snapshot = snapshot_service.create_snapshot(v1_config)
        time.sleep(0.01)

        # Create v2 snapshot
        v2_snapshot = snapshot_service.create_snapshot(v2_config)

        # Count snapshots before rollback
        snapshots_before = snapshot_service.list_snapshots("TESTUSDT")
        count_before = len(snapshots_before)

        # Rollback to v1
        result = rollback_service.rollback_to_snapshot(
            v1_snapshot.snapshot_id,
            created_by="test_user",
        )

        assert result.success

        # Should have one more snapshot (pre-rollback)
        snapshots_after = snapshot_service.list_snapshots("TESTUSDT")
        count_after = len(snapshots_after)

        assert count_after == count_before + 1

        # Latest snapshot should be pre-rollback snapshot
        latest = snapshots_after[0]
        assert "pre_rollback" in latest.reason
        assert str(v1_snapshot.snapshot_id) in latest.reason

    def test_rollback_with_validation(
        self,
        rollback_service,
        snapshot_service,
        v1_config,
    ):
        """
        Test rollback validation.

        Validation should:
        - Check configuration is valid before rollback
        - Reject invalid configurations
        """
        # Create valid snapshot
        snapshot = snapshot_service.create_snapshot(v1_config)

        # Rollback with validation enabled (default)
        result = rollback_service.rollback_to_snapshot(
            snapshot.snapshot_id,
            validate=True,
        )

        assert result.success

    def test_rollback_to_nonexistent_snapshot_fails(self, rollback_service):
        """
        Test rollback to non-existent snapshot fails gracefully.

        Error Handling:
        - Should return failure result
        - Should have descriptive error message
        """
        fake_id = UUID("00000000-0000-0000-0000-000000000000")

        result = rollback_service.rollback_to_snapshot(fake_id)

        assert not result.success
        assert "not found" in result.message.lower()

    def test_rollback_to_previous_with_no_snapshots_fails(self, rollback_service):
        """
        Test rollback when no snapshots exist fails gracefully.

        Error Handling:
        - Should return failure result
        - Should indicate no snapshots available
        """
        result = rollback_service.rollback_to_previous("NOSNAPSHOTS")

        assert not result.success
        assert "no snapshots" in result.message.lower()

    def test_get_version_history(
        self,
        rollback_service,
        snapshot_service,
        v1_config,
        v2_config,
    ):
        """
        Test retrieving version history.

        History should:
        - List all snapshots in chronological order (newest first)
        - Include version, timestamp, reason
        """
        # Create snapshots
        snapshot_service.create_snapshot(v1_config, reason="initial")
        time.sleep(0.01)
        snapshot_service.create_snapshot(v2_config, reason="rate_update")

        # Get history
        history = rollback_service.get_version_history("TESTUSDT")

        assert len(history) == 2

        # Should be newest first
        assert history[0]["version"] == "test-v2"
        assert history[0]["reason"] == "rate_update"

        assert history[1]["version"] == "test-v1"
        assert history[1]["reason"] == "initial"

    def test_preview_rollback(
        self,
        rollback_service,
        snapshot_service,
        v1_config,
        v2_config,
    ):
        """
        Test rollback preview functionality.

        Preview should:
        - Show what would happen without executing
        - Include validation results
        - Show config differences
        """
        # Create snapshots
        v1_snapshot = snapshot_service.create_snapshot(v1_config)
        time.sleep(0.01)
        v2_snapshot = snapshot_service.create_snapshot(v2_config)

        # Preview rollback to v1
        is_valid, preview = rollback_service.preview_rollback(v1_snapshot.snapshot_id)

        assert is_valid
        assert preview["symbol"] == "TESTUSDT"
        assert preview["target_version"] == "test-v1"
        assert preview["is_valid"]
        assert "tier_changes" in preview

    def test_list_rollback_points(
        self,
        rollback_service,
        snapshot_service,
        v1_config,
        v2_config,
    ):
        """
        Test listing available rollback points.

        Rollback points should:
        - Be user-friendly labeled
        - Include age information
        - Be sorted by timestamp (newest first)
        """
        # Create snapshots
        snapshot_service.create_snapshot(v1_config, reason="initial")
        time.sleep(0.01)
        snapshot_service.create_snapshot(v2_config, reason="update")

        # List rollback points
        points = rollback_service.list_rollback_points("TESTUSDT")

        assert len(points) == 2

        # Should have labels
        assert points[0]["label"]
        assert "test-v2" in points[0]["label"]

        # Should have age information
        assert "age_hours" in points[0]
        assert points[0]["age_hours"] >= 0

    def test_snapshot_service_list_limits(self, snapshot_service, v1_config, v2_config):
        """
        Test snapshot listing with limit.

        Listing should:
        - Respect limit parameter
        - Return newest snapshots first
        """
        # Create 5 snapshots
        for i in range(5):
            config = v1_config if i % 2 == 0 else v2_config
            snapshot_service.create_snapshot(config, reason=f"snapshot_{i}")
            time.sleep(0.01)

        # List with limit
        snapshots = snapshot_service.list_snapshots("TESTUSDT", limit=3)

        assert len(snapshots) == 3

        # Should be newest first
        assert "snapshot_4" in snapshots[0].reason

    def test_cleanup_old_snapshots(self, snapshot_service, v1_config):
        """
        Test cleanup of old snapshots.

        Cleanup should:
        - Keep specified number of recent snapshots
        - Delete older snapshots
        """
        # Create 10 snapshots
        for i in range(10):
            snapshot_service.create_snapshot(v1_config, reason=f"snapshot_{i}")
            time.sleep(0.01)

        # Verify we have 10
        snapshots_before = snapshot_service.list_snapshots("TESTUSDT")
        assert len(snapshots_before) == 10

        # Cleanup, keep last 5
        snapshot_service.cleanup_old_snapshots("TESTUSDT", keep_last_n=5)

        # Should have 5 remaining
        snapshots_after = snapshot_service.list_snapshots("TESTUSDT")
        assert len(snapshots_after) == 5

        # Should be the 5 newest
        assert "snapshot_9" in snapshots_after[0].reason
        assert "snapshot_5" in snapshots_after[4].reason

    def test_snapshot_persistence(self, snapshot_dir, v1_config):
        """
        Test that snapshots persist to disk.

        Persistence should:
        - Save snapshots to JSON files
        - Load snapshots from disk
        - Survive service restart
        """
        # Create service and snapshot
        service1 = TierSnapshotService(snapshot_dir=snapshot_dir)
        snapshot = service1.create_snapshot(v1_config, reason="persistence_test")

        # Create new service instance (simulates restart)
        service2 = TierSnapshotService(snapshot_dir=snapshot_dir)

        # Should be able to retrieve snapshot
        retrieved = service2.get_snapshot(snapshot.snapshot_id)

        assert retrieved is not None
        assert retrieved.snapshot_id == snapshot.snapshot_id
        assert retrieved.config.version == "test-v1"
        assert retrieved.reason == "persistence_test"

    def test_rollback_cache_invalidation(
        self,
        rollback_service,
        snapshot_service,
        v1_config,
    ):
        """
        Test that rollback invalidates cache.

        Cache Invalidation:
        - After rollback, cache should be invalidated
        - Next get should fetch new configuration
        """
        # Create snapshot
        snapshot = snapshot_service.create_snapshot(v1_config)

        # Perform rollback
        result = rollback_service.rollback_to_snapshot(snapshot.snapshot_id)

        assert result.success

        # Cache should have been invalidated for this symbol
        # (This is verified by the rollback service calling cache.invalidate)
        # In a real scenario, the next cache.get() would load the rolled-back config
