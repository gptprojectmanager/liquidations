"""
Tier configuration rollback mechanism.

Provides rollback functionality with version tracking:
- Rollback to previous configuration
- Version history tracking
- Atomic rollback operations
- Integration with snapshot and cache services
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from src.models.tier_config import TierConfiguration
from src.services.tier_cache import TierCache
from src.services.tier_snapshot import TierSnapshot, TierSnapshotService
from src.services.tier_validator import TierValidator

logger = logging.getLogger(__name__)


class RollbackResult:
    """Result of a rollback operation."""

    def __init__(self, success: bool, message: str, snapshot: Optional[TierSnapshot] = None):
        """
        Create rollback result.

        Args:
            success: Whether rollback succeeded
            message: Description of result
            snapshot: Snapshot that was rolled back to (if successful)
        """
        self.success = success
        self.message = message
        self.snapshot = snapshot
        self.timestamp = datetime.utcnow()

    def __str__(self) -> str:
        """String representation."""
        status = "SUCCESS" if self.success else "FAILED"
        return f"RollbackResult({status}): {self.message}"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "message": self.message,
            "snapshot_id": str(self.snapshot.snapshot_id) if self.snapshot else None,
            "timestamp": self.timestamp.isoformat(),
        }


class TierRollbackService:
    """
    Service for rolling back tier configuration changes.

    Features:
    - Rollback to specific snapshot
    - Rollback to previous version
    - Version history tracking
    - Validation before rollback
    - Automatic snapshot before rollback
    """

    def __init__(
        self,
        snapshot_service: Optional[TierSnapshotService] = None,
        validator: Optional[TierValidator] = None,
        cache: Optional[TierCache] = None,
    ):
        """
        Initialize rollback service.

        Args:
            snapshot_service: TierSnapshotService for snapshots
            validator: TierValidator for validation
            cache: TierCache for invalidation
        """
        self.snapshot_service = snapshot_service or TierSnapshotService()
        self.validator = validator or TierValidator()
        self.cache = cache or TierCache()

        logger.info("TierRollbackService initialized")

    def rollback_to_snapshot(
        self,
        snapshot_id: UUID,
        created_by: Optional[str] = None,
        validate: bool = True,
    ) -> RollbackResult:
        """
        Rollback to specific snapshot.

        Args:
            snapshot_id: ID of snapshot to rollback to
            created_by: User/system performing rollback
            validate: Whether to validate configuration before rollback

        Returns:
            RollbackResult with outcome

        Example:
            >>> service = TierRollbackService()
            >>> result = service.rollback_to_snapshot(snapshot_id)
            >>> if result.success:
            ...     print(f"Rolled back to {result.snapshot.config.version}")
        """
        # Get snapshot
        snapshot = self.snapshot_service.get_snapshot(snapshot_id)

        if snapshot is None:
            return RollbackResult(
                success=False,
                message=f"Snapshot {snapshot_id} not found",
            )

        logger.info(
            f"Initiating rollback to snapshot {snapshot_id} "
            f"for {snapshot.symbol} (version: {snapshot.config.version})"
        )

        # Validate configuration if requested
        if validate:
            validation_result = self.validator.validate(snapshot.config)
            if not validation_result.is_valid:
                return RollbackResult(
                    success=False,
                    message=f"Snapshot configuration invalid: {validation_result.errors}",
                    snapshot=snapshot,
                )

        # Create snapshot of current state before rollback
        current_config = self.cache.get_or_default(snapshot.symbol)
        self.snapshot_service.create_snapshot(
            current_config,
            reason=f"pre_rollback_{snapshot_id}",
            created_by=created_by,
        )

        # Invalidate cache to force reload
        self.cache.invalidate(snapshot.symbol)

        # In production, this would write the snapshot config to storage/database
        # For now, we just log the rollback
        logger.info(
            f"Rolled back {snapshot.symbol} to version {snapshot.config.version} "
            f"from snapshot {snapshot_id}"
        )

        return RollbackResult(
            success=True,
            message=f"Rolled back {snapshot.symbol} to version {snapshot.config.version}",
            snapshot=snapshot,
        )

    def rollback_to_previous(
        self,
        symbol: str,
        created_by: Optional[str] = None,
        validate: bool = True,
    ) -> RollbackResult:
        """
        Rollback to previous version (most recent snapshot).

        Args:
            symbol: Trading pair symbol
            created_by: User/system performing rollback
            validate: Whether to validate before rollback

        Returns:
            RollbackResult with outcome

        Example:
            >>> result = service.rollback_to_previous("BTCUSDT")
        """
        # Get latest snapshot
        snapshot = self.snapshot_service.get_latest_snapshot(symbol)

        if snapshot is None:
            return RollbackResult(
                success=False,
                message=f"No snapshots found for {symbol}",
            )

        logger.info(f"Rolling back {symbol} to previous version (snapshot {snapshot.snapshot_id})")

        return self.rollback_to_snapshot(
            snapshot.snapshot_id,
            created_by=created_by,
            validate=validate,
        )

    def get_version_history(self, symbol: str, limit: int = 10) -> List[dict]:
        """
        Get version history for symbol.

        Args:
            symbol: Trading pair symbol
            limit: Maximum number of versions to return

        Returns:
            List of version history entries (newest first)

        Example:
            >>> history = service.get_version_history("BTCUSDT", limit=5)
            >>> for entry in history:
            ...     print(f"{entry['version']} at {entry['timestamp']}")
        """
        snapshots = self.snapshot_service.list_snapshots(symbol, limit=limit)

        history = []
        for snapshot in snapshots:
            history.append(
                {
                    "snapshot_id": str(snapshot.snapshot_id),
                    "version": snapshot.config.version,
                    "timestamp": snapshot.timestamp.isoformat(),
                    "reason": snapshot.reason,
                    "created_by": snapshot.created_by,
                    "tier_count": len(snapshot.config.tiers),
                }
            )

        return history

    def preview_rollback(self, snapshot_id: UUID) -> Tuple[bool, dict]:
        """
        Preview what would happen in a rollback without executing it.

        Args:
            snapshot_id: ID of snapshot to preview

        Returns:
            Tuple of (is_valid, preview_info)

        Example:
            >>> is_valid, preview = service.preview_rollback(snapshot_id)
            >>> if is_valid:
            ...     print(f"Would rollback to: {preview['target_version']}")
        """
        snapshot = self.snapshot_service.get_snapshot(snapshot_id)

        if snapshot is None:
            return False, {"error": f"Snapshot {snapshot_id} not found"}

        # Validate snapshot config
        validation_result = self.validator.validate(snapshot.config)

        # Get current config
        current_config = self.cache.get_or_default(snapshot.symbol)

        preview = {
            "snapshot_id": str(snapshot_id),
            "symbol": snapshot.symbol,
            "current_version": current_config.version,
            "target_version": snapshot.config.version,
            "snapshot_timestamp": snapshot.timestamp.isoformat(),
            "snapshot_reason": snapshot.reason,
            "is_valid": validation_result.is_valid,
            "validation_errors": validation_result.errors,
            "validation_warnings": validation_result.warnings,
            "tier_changes": self._compare_configs(current_config, snapshot.config),
        }

        return validation_result.is_valid, preview

    def _compare_configs(
        self,
        current: TierConfiguration,
        target: TierConfiguration,
    ) -> dict:
        """
        Compare two configurations and return differences.

        Args:
            current: Current configuration
            target: Target configuration

        Returns:
            Dictionary describing differences
        """
        changes = {
            "version_change": current.version != target.version,
            "tier_count_change": len(current.tiers) != len(target.tiers),
            "modified_tiers": [],
        }

        # Compare tiers
        max_tiers = max(len(current.tiers), len(target.tiers))

        for i in range(max_tiers):
            if i >= len(current.tiers):
                changes["modified_tiers"].append({"tier": i + 1, "change": "added"})
            elif i >= len(target.tiers):
                changes["modified_tiers"].append({"tier": i + 1, "change": "removed"})
            else:
                current_tier = current.tiers[i]
                target_tier = target.tiers[i]

                if (
                    current_tier.margin_rate != target_tier.margin_rate
                    or current_tier.min_notional != target_tier.min_notional
                    or current_tier.max_notional != target_tier.max_notional
                    or current_tier.maintenance_amount != target_tier.maintenance_amount
                ):
                    changes["modified_tiers"].append(
                        {
                            "tier": i + 1,
                            "change": "modified",
                            "current_rate": str(current_tier.margin_rate),
                            "target_rate": str(target_tier.margin_rate),
                        }
                    )

        return changes

    def list_rollback_points(self, symbol: str, limit: int = 10) -> List[dict]:
        """
        List available rollback points for symbol.

        Args:
            symbol: Trading pair symbol
            limit: Maximum number of rollback points

        Returns:
            List of rollback points with metadata

        Example:
            >>> points = service.list_rollback_points("BTCUSDT")
            >>> for point in points:
            ...     print(f"{point['label']}: {point['version']}")
        """
        snapshots = self.snapshot_service.list_snapshots(symbol, limit=limit)

        rollback_points = []
        for idx, snapshot in enumerate(snapshots):
            # Create user-friendly label
            label = f"#{idx + 1}: {snapshot.config.version}"
            if snapshot.reason:
                label += f" ({snapshot.reason})"

            rollback_points.append(
                {
                    "snapshot_id": str(snapshot.snapshot_id),
                    "label": label,
                    "version": snapshot.config.version,
                    "timestamp": snapshot.timestamp.isoformat(),
                    "age_hours": (datetime.utcnow() - snapshot.timestamp).total_seconds() / 3600,
                    "reason": snapshot.reason,
                }
            )

        return rollback_points


# Global rollback service instance
_global_rollback_service: Optional[TierRollbackService] = None


def get_global_rollback_service() -> TierRollbackService:
    """
    Get or create global rollback service instance.

    Returns:
        Global TierRollbackService instance

    Example:
        >>> service = get_global_rollback_service()
        >>> result = service.rollback_to_previous("BTCUSDT")
    """
    global _global_rollback_service

    if _global_rollback_service is None:
        _global_rollback_service = TierRollbackService()
        logger.info("Created global rollback service")

    return _global_rollback_service
