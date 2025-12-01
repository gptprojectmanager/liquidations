"""
ValidationRun data model.

Represents a single validation execution (manual or scheduled) with
status tracking, timing information, and results.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class ValidationStatus(str, Enum):
    """Validation run status values."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


class ValidationGrade(str, Enum):
    """Validation grade values."""

    A = "A"
    B = "B"
    C = "C"
    F = "F"


class TriggerType(str, Enum):
    """Validation trigger type."""

    SCHEDULED = "scheduled"
    MANUAL = "manual"


class ValidationRun(BaseModel):
    """
    Represents a single validation execution.

    Tracks execution metadata, timing, status, and results for a validation run.
    Supports both scheduled (automatic) and manual (on-demand) triggers.
    """

    # Primary key
    run_id: str = Field(..., description="Unique run identifier")

    # Execution metadata
    model_name: str = Field(..., description="Model being validated")
    trigger_type: TriggerType = Field(..., description="Scheduled or manual trigger")
    triggered_by: Optional[str] = Field(None, description="User ID or 'system' for scheduled runs")

    # Timing
    started_at: datetime = Field(..., description="Run start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Run completion timestamp")
    duration_seconds: Optional[int] = Field(None, description="Execution duration in seconds")

    # Status
    status: ValidationStatus = Field(..., description="Current run status")
    error_message: Optional[str] = Field(None, description="Error details if failed")

    # Data window
    data_start_date: date = Field(..., description="Start date of validation data window")
    data_end_date: date = Field(..., description="End date of validation data window")
    data_completeness: Optional[Decimal] = Field(
        None, ge=0, le=100, description="Percentage of expected data available (0-100)"
    )

    # Results summary
    overall_grade: Optional[ValidationGrade] = Field(None, description="Overall grade (A/B/C/F)")
    overall_score: Optional[Decimal] = Field(
        None, ge=0, le=100, description="Overall score (0-100)"
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record creation time"
    )
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")

    @computed_field
    @property
    def duration_calculated(self) -> Optional[int]:
        """
        Calculate duration from timestamps if not explicitly set.

        Returns:
            Duration in seconds, or None if run not completed
        """
        if self.duration_seconds is not None:
            return self.duration_seconds

        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds())

        return None

    @field_validator("data_completeness")
    @classmethod
    def validate_completeness_range(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate data completeness is 0-100."""
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Data completeness must be between 0 and 100")
        return v

    @field_validator("overall_score")
    @classmethod
    def validate_score_range(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate score is 0-100."""
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Overall score must be between 0 and 100")
        return v

    model_config = ConfigDict(
        use_enum_values=False,  # Keep enum objects, not string values
        validate_assignment=True,  # Validate on attribute assignment
    )

    def __init__(self, **data):
        """Initialize and auto-calculate duration if not provided."""
        # Auto-calculate duration if timestamps present
        if "duration_seconds" not in data or data["duration_seconds"] is None:
            if "completed_at" in data and data["completed_at"] and "started_at" in data:
                delta = data["completed_at"] - data["started_at"]
                data["duration_seconds"] = int(delta.total_seconds())

        super().__init__(**data)
