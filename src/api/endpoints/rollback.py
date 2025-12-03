"""
Rollback API endpoints for tier configuration management.

Provides REST API for:
- Rolling back to previous configuration
- Rolling back to specific snapshot
- Listing rollback points
- Previewing rollback changes
- Getting version history
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.tier_rollback import (
    get_global_rollback_service,
)

router = APIRouter(prefix="/rollback", tags=["rollback"])


# Request/Response Models


class RollbackToSnapshotRequest(BaseModel):
    """Request to rollback to specific snapshot."""

    snapshot_id: UUID = Field(..., description="UUID of snapshot to rollback to")
    created_by: Optional[str] = Field(None, description="User/system performing rollback")
    should_validate: bool = Field(True, description="Whether to validate before rollback")


class RollbackToPreviousRequest(BaseModel):
    """Request to rollback to previous version."""

    symbol: str = Field(..., description="Trading pair symbol")
    created_by: Optional[str] = Field(None, description="User/system performing rollback")
    should_validate: bool = Field(True, description="Whether to validate before rollback")


class RollbackResponse(BaseModel):
    """Response from rollback operation."""

    success: bool = Field(..., description="Whether rollback succeeded")
    message: str = Field(..., description="Result message")
    snapshot_id: Optional[str] = Field(None, description="Snapshot ID rolled back to")
    timestamp: str = Field(..., description="Operation timestamp")


class VersionHistoryEntry(BaseModel):
    """Single entry in version history."""

    snapshot_id: str = Field(..., description="Snapshot UUID")
    version: str = Field(..., description="Configuration version")
    timestamp: str = Field(..., description="When snapshot was created")
    reason: str = Field(..., description="Reason for snapshot")
    created_by: str = Field(..., description="Who created snapshot")
    tier_count: int = Field(..., description="Number of tiers in configuration")


class RollbackPreview(BaseModel):
    """Preview of what rollback would change."""

    snapshot_id: str = Field(..., description="Target snapshot ID")
    symbol: str = Field(..., description="Trading pair symbol")
    current_version: str = Field(..., description="Current configuration version")
    target_version: str = Field(..., description="Target configuration version")
    snapshot_timestamp: str = Field(..., description="When snapshot was created")
    snapshot_reason: str = Field(..., description="Why snapshot was created")
    is_valid: bool = Field(..., description="Whether rollback would succeed")
    validation_errors: List[str] = Field(..., description="Validation errors if any")
    validation_warnings: List[str] = Field(..., description="Validation warnings if any")
    tier_changes: dict = Field(..., description="Summary of tier changes")


class RollbackPoint(BaseModel):
    """Available rollback point."""

    snapshot_id: str = Field(..., description="Snapshot UUID")
    label: str = Field(..., description="User-friendly label")
    version: str = Field(..., description="Configuration version")
    timestamp: str = Field(..., description="When snapshot was created")
    age_hours: float = Field(..., description="How long ago (hours)")
    reason: str = Field(..., description="Why snapshot was created")


# API Endpoints


@router.post("/snapshot", response_model=RollbackResponse)
async def rollback_to_snapshot(request: RollbackToSnapshotRequest):
    """
    Rollback to specific snapshot by ID.

    This operation:
    - Validates the target snapshot configuration
    - Creates a pre-rollback snapshot of current state
    - Rolls back to the specified snapshot
    - Invalidates cache to force reload

    **Safety**: Always creates a pre-rollback snapshot so you can rollback the rollback.
    """
    service = get_global_rollback_service()

    result = service.rollback_to_snapshot(
        snapshot_id=request.snapshot_id,
        created_by=request.created_by,
        validate=request.should_validate,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return RollbackResponse(
        success=result.success,
        message=result.message,
        snapshot_id=str(result.snapshot.snapshot_id) if result.snapshot else None,
        timestamp=result.timestamp.isoformat(),
    )


@router.post("/previous", response_model=RollbackResponse)
async def rollback_to_previous(request: RollbackToPreviousRequest):
    """
    Rollback to previous version (most recent snapshot).

    Convenience endpoint that finds the latest snapshot for a symbol
    and rolls back to it.

    **Use case**: Quick rollback after a bad configuration update.
    """
    service = get_global_rollback_service()

    result = service.rollback_to_previous(
        symbol=request.symbol,
        created_by=request.created_by,
        validate=request.should_validate,
    )

    if not result.success:
        raise HTTPException(
            status_code=404 if "no snapshots" in result.message.lower() else 400,
            detail=result.message,
        )

    return RollbackResponse(
        success=result.success,
        message=result.message,
        snapshot_id=str(result.snapshot.snapshot_id) if result.snapshot else None,
        timestamp=result.timestamp.isoformat(),
    )


@router.get("/history/{symbol}", response_model=List[VersionHistoryEntry])
async def get_version_history(
    symbol: str,
    limit: int = Query(10, ge=1, le=100, description="Maximum number of versions to return"),
):
    """
    Get version history for a symbol.

    Returns list of snapshots ordered by timestamp (newest first).

    **Use case**: View configuration change history before deciding what to rollback to.
    """
    service = get_global_rollback_service()

    history = service.get_version_history(symbol, limit=limit)

    return [VersionHistoryEntry(**entry) for entry in history]


@router.get("/preview/{snapshot_id}", response_model=RollbackPreview)
async def preview_rollback(snapshot_id: UUID):
    """
    Preview what would happen in a rollback without executing it.

    Shows:
    - Current vs target version
    - Validation results
    - Tier changes summary

    **Use case**: Verify rollback target before executing the rollback.
    """
    service = get_global_rollback_service()

    is_valid, preview = service.preview_rollback(snapshot_id)

    if "error" in preview:
        raise HTTPException(status_code=404, detail=preview["error"])

    return RollbackPreview(**preview)


@router.get("/points/{symbol}", response_model=List[RollbackPoint])
async def list_rollback_points(
    symbol: str,
    limit: int = Query(10, ge=1, le=50, description="Maximum number of rollback points"),
):
    """
    List available rollback points for a symbol.

    Returns user-friendly list of snapshots that can be rolled back to,
    with labels, age information, and reasons.

    **Use case**: Display rollback options in a UI dropdown or CLI menu.
    """
    service = get_global_rollback_service()

    points = service.list_rollback_points(symbol, limit=limit)

    return [RollbackPoint(**point) for point in points]


# Health check endpoint


@router.get("/health")
async def rollback_health():
    """
    Check rollback service health.

    Returns basic status and service availability.
    """
    try:
        _ = get_global_rollback_service()  # Verify service availability
        return {
            "status": "healthy",
            "service": "TierRollbackService",
            "snapshot_service": "available",
            "validator": "available",
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Rollback service unhealthy: {str(e)}")
