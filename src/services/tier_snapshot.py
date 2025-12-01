"""
Tier configuration snapshot service.

Provides snapshot functionality for tier configurations before updates:
- Automatic snapshot creation before tier updates
- Versioned snapshots with timestamps
- Snapshot storage and retrieval
- Integration with rollback mechanism
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from src.models.tier_config import TierConfiguration

logger = logging.getLogger(__name__)


class TierSnapshot:
    """
    Single snapshot of a tier configuration.

    Captures complete state at a specific point in time for rollback purposes.
    """

    def __init__(
        self,
        snapshot_id: UUID,
        symbol: str,
        config: TierConfiguration,
        timestamp: datetime,
        reason: str = "manual",
        created_by: Optional[str] = None,
    ):
        """
        Create a tier configuration snapshot.

        Args:
            snapshot_id: Unique identifier for this snapshot
            symbol: Trading pair symbol
            config: TierConfiguration being snapshot
            timestamp: When snapshot was created
            reason: Reason for snapshot (update, manual, rollback, etc.)
            created_by: User/system that created snapshot
        """
        self.snapshot_id = snapshot_id
        self.symbol = symbol
        self.config = config
        self.timestamp = timestamp
        self.reason = reason
        self.created_by = created_by or "system"

    def to_dict(self) -> dict:
        """
        Convert snapshot to dictionary for serialization.

        Returns:
            Dictionary with snapshot metadata and configuration
        """
        return {
            "snapshot_id": str(self.snapshot_id),
            "symbol": self.symbol,
            "config_version": self.config.version,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "created_by": self.created_by,
            "tiers": [
                {
                    "tier_number": tier.tier_number,
                    "min_notional": str(tier.min_notional),
                    "max_notional": str(tier.max_notional),
                    "margin_rate": str(tier.margin_rate),
                    "maintenance_amount": str(tier.maintenance_amount),
                }
                for tier in self.config.tiers
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TierSnapshot":
        """
        Create snapshot from dictionary.

        Args:
            data: Dictionary with snapshot data

        Returns:
            TierSnapshot instance
        """
        from decimal import Decimal

        from src.models.margin_tier import MarginTier

        # Reconstruct tier configuration
        tiers = [
            MarginTier(
                symbol=data["symbol"],
                tier_number=tier_data["tier_number"],
                min_notional=Decimal(tier_data["min_notional"]),
                max_notional=Decimal(tier_data["max_notional"]),
                margin_rate=Decimal(tier_data["margin_rate"]),
                maintenance_amount=Decimal(tier_data["maintenance_amount"]),
            )
            for tier_data in data["tiers"]
        ]

        config = TierConfiguration(
            symbol=data["symbol"],
            version=data["config_version"],
            tiers=tiers,
        )

        return cls(
            snapshot_id=UUID(data["snapshot_id"]),
            symbol=data["symbol"],
            config=config,
            timestamp=datetime.fromisoformat(data["timestamp"]),
            reason=data["reason"],
            created_by=data.get("created_by", "system"),
        )

    def __repr__(self) -> str:
        """String representation of snapshot."""
        return (
            f"TierSnapshot(id={self.snapshot_id}, symbol={self.symbol}, "
            f"version={self.config.version}, timestamp={self.timestamp.isoformat()})"
        )


class TierSnapshotService:
    """
    Service for managing tier configuration snapshots.

    Features:
    - Automatic snapshot before updates
    - Versioned snapshot history
    - Snapshot retention policies
    - Rollback support
    """

    def __init__(self, snapshot_dir: Optional[Path] = None):
        """
        Initialize snapshot service.

        Args:
            snapshot_dir: Directory to store snapshots (defaults to data/snapshots/)
        """
        if snapshot_dir is None:
            snapshot_dir = Path("data/snapshots")

        self.snapshot_dir = snapshot_dir
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache of recent snapshots
        self._snapshot_cache: Dict[str, List[TierSnapshot]] = {}

        logger.info(f"TierSnapshotService initialized with directory: {snapshot_dir}")

    def create_snapshot(
        self,
        config: TierConfiguration,
        reason: str = "manual",
        created_by: Optional[str] = None,
    ) -> TierSnapshot:
        """
        Create snapshot of tier configuration.

        Args:
            config: TierConfiguration to snapshot
            reason: Reason for snapshot
            created_by: User/system creating snapshot

        Returns:
            TierSnapshot instance

        Example:
            >>> service = TierSnapshotService()
            >>> snapshot = service.create_snapshot(config, reason="pre_update")
        """
        snapshot_id = uuid4()
        timestamp = datetime.utcnow()

        snapshot = TierSnapshot(
            snapshot_id=snapshot_id,
            symbol=config.symbol,
            config=config,
            timestamp=timestamp,
            reason=reason,
            created_by=created_by,
        )

        # Save snapshot to disk
        self._save_snapshot(snapshot)

        # Add to cache
        if config.symbol not in self._snapshot_cache:
            self._snapshot_cache[config.symbol] = []
        self._snapshot_cache[config.symbol].append(snapshot)

        logger.info(
            f"Created snapshot {snapshot_id} for {config.symbol} "
            f"(reason: {reason}, version: {config.version})"
        )

        return snapshot

    def get_latest_snapshot(self, symbol: str) -> Optional[TierSnapshot]:
        """
        Get most recent snapshot for symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            Latest TierSnapshot or None if no snapshots exist

        Example:
            >>> snapshot = service.get_latest_snapshot("BTCUSDT")
        """
        snapshots = self.list_snapshots(symbol)
        return snapshots[0] if snapshots else None

    def get_snapshot(self, snapshot_id: UUID) -> Optional[TierSnapshot]:
        """
        Get specific snapshot by ID.

        Args:
            snapshot_id: Snapshot UUID

        Returns:
            TierSnapshot or None if not found

        Example:
            >>> snapshot = service.get_snapshot(snapshot_id)
        """
        # Search in cache first
        for snapshots in self._snapshot_cache.values():
            for snapshot in snapshots:
                if snapshot.snapshot_id == snapshot_id:
                    return snapshot

        # Search in disk
        return self._load_snapshot_by_id(snapshot_id)

    def list_snapshots(
        self,
        symbol: str,
        limit: Optional[int] = None,
    ) -> List[TierSnapshot]:
        """
        List snapshots for symbol, sorted by timestamp (newest first).

        Args:
            symbol: Trading pair symbol
            limit: Maximum number of snapshots to return

        Returns:
            List of TierSnapshot instances

        Example:
            >>> snapshots = service.list_snapshots("BTCUSDT", limit=10)
        """
        # Load from cache if available
        if symbol in self._snapshot_cache:
            snapshots = self._snapshot_cache[symbol]
        else:
            # Load from disk
            snapshots = self._load_snapshots_for_symbol(symbol)
            self._snapshot_cache[symbol] = snapshots

        # Sort by timestamp (newest first)
        snapshots.sort(key=lambda s: s.timestamp, reverse=True)

        # Apply limit
        if limit is not None:
            snapshots = snapshots[:limit]

        return snapshots

    def delete_snapshot(self, snapshot_id: UUID) -> bool:
        """
        Delete specific snapshot.

        Args:
            snapshot_id: Snapshot UUID to delete

        Returns:
            True if deleted, False if not found

        Example:
            >>> service.delete_snapshot(snapshot_id)
        """
        snapshot = self.get_snapshot(snapshot_id)
        if snapshot is None:
            logger.warning(f"Snapshot {snapshot_id} not found for deletion")
            return False

        # Remove from cache
        if snapshot.symbol in self._snapshot_cache:
            self._snapshot_cache[snapshot.symbol] = [
                s for s in self._snapshot_cache[snapshot.symbol] if s.snapshot_id != snapshot_id
            ]

        # Remove from disk
        snapshot_path = self._get_snapshot_path(snapshot_id)
        if snapshot_path.exists():
            snapshot_path.unlink()
            logger.info(f"Deleted snapshot {snapshot_id}")
            return True

        return False

    def cleanup_old_snapshots(self, symbol: str, keep_last_n: int = 10):
        """
        Clean up old snapshots for symbol, keeping only the N most recent.

        Args:
            symbol: Trading pair symbol
            keep_last_n: Number of recent snapshots to keep

        Example:
            >>> service.cleanup_old_snapshots("BTCUSDT", keep_last_n=5)
        """
        snapshots = self.list_snapshots(symbol)

        if len(snapshots) <= keep_last_n:
            logger.info(f"No cleanup needed for {symbol} ({len(snapshots)} snapshots)")
            return

        # Keep first N (newest), delete rest
        to_keep = snapshots[:keep_last_n]
        to_delete = snapshots[keep_last_n:]

        for snapshot in to_delete:
            self.delete_snapshot(snapshot.snapshot_id)

        logger.info(
            f"Cleaned up {len(to_delete)} old snapshots for {symbol}, kept {len(to_keep)} recent"
        )

    def _save_snapshot(self, snapshot: TierSnapshot):
        """Save snapshot to disk as JSON."""
        import json

        snapshot_path = self._get_snapshot_path(snapshot.snapshot_id)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)

        with open(snapshot_path, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

        logger.debug(f"Saved snapshot to {snapshot_path}")

    def _load_snapshot_by_id(self, snapshot_id: UUID) -> Optional[TierSnapshot]:
        """Load snapshot from disk by ID."""
        import json

        snapshot_path = self._get_snapshot_path(snapshot_id)

        if not snapshot_path.exists():
            return None

        with open(snapshot_path, "r") as f:
            data = json.load(f)

        return TierSnapshot.from_dict(data)

    def _load_snapshots_for_symbol(self, symbol: str) -> List[TierSnapshot]:
        """Load all snapshots for symbol from disk."""
        import json

        symbol_dir = self.snapshot_dir / symbol.upper()

        if not symbol_dir.exists():
            return []

        snapshots = []
        for snapshot_file in symbol_dir.glob("*.json"):
            try:
                with open(snapshot_file, "r") as f:
                    data = json.load(f)
                snapshots.append(TierSnapshot.from_dict(data))
            except Exception as e:
                logger.error(f"Failed to load snapshot {snapshot_file}: {e}")

        return snapshots

    def _get_snapshot_path(self, snapshot_id: UUID) -> Path:
        """Get file path for snapshot (organized by symbol/snapshot_id.json)."""
        # Note: We don't know the symbol from just the ID, so we use a flat structure
        # for lookup by ID. Symbol-based organization happens during save.
        return self.snapshot_dir / f"{snapshot_id}.json"


# Global snapshot service instance
_global_snapshot_service: Optional[TierSnapshotService] = None


def get_global_snapshot_service(snapshot_dir: Optional[Path] = None) -> TierSnapshotService:
    """
    Get or create global snapshot service instance.

    Args:
        snapshot_dir: Directory for snapshots (only used on first call)

    Returns:
        Global TierSnapshotService instance

    Example:
        >>> service = get_global_snapshot_service()
        >>> snapshot = service.create_snapshot(config)
    """
    global _global_snapshot_service

    if _global_snapshot_service is None:
        _global_snapshot_service = TierSnapshotService(snapshot_dir=snapshot_dir)
        logger.info("Created global snapshot service")

    return _global_snapshot_service
