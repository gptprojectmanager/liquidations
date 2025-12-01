"""
ValidationTest data model.

Represents an individual test result within a validation run.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ValidationTestType(str, Enum):
    """Valid validation test types."""

    FUNDING_CORRELATION = "funding_correlation"
    OI_CONSERVATION = "oi_conservation"
    DIRECTIONAL_POSITIONING = "directional_positioning"


class ValidationTest(BaseModel):
    """
    Represents an individual validation test result.

    Each ValidationRun contains multiple ValidationTests, one for each
    validation method (funding correlation, OI conservation, directional).
    """

    # Primary key
    test_id: str = Field(..., description="Unique test identifier")

    # Foreign key to ValidationRun
    run_id: str = Field(..., description="Parent validation run ID")

    # Test identification
    test_type: ValidationTestType = Field(..., description="Type of validation test")
    test_name: str = Field(..., description="Human-readable test name")

    # Results
    passed: bool = Field(..., description="Whether test passed")
    score: Decimal = Field(..., ge=0, le=100, description="Test score (0-100)")
    weight: Decimal = Field(..., ge=0, le=1, description="Weight in overall score (0-1)")

    # Statistical metrics
    primary_metric: Optional[Decimal] = Field(
        None, description="Main test result (e.g., correlation coefficient)"
    )
    secondary_metric: Optional[Decimal] = Field(
        None, description="Supporting metric (e.g., p-value)"
    )

    # Diagnostics
    diagnostics: Optional[dict[str, Any]] = Field(
        None, description="Test-specific diagnostic information"
    )
    error_message: Optional[str] = Field(None, description="Error details if test failed")

    # Timing
    executed_at: datetime = Field(..., description="Test execution timestamp")
    duration_ms: Optional[int] = Field(None, description="Test duration in milliseconds")

    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record creation timestamp"
    )

    model_config = ConfigDict(
        use_enum_values=False,  # Keep enum objects
        validate_assignment=True,  # Validate on attribute changes
    )

    @field_validator("score")
    @classmethod
    def validate_score_range(cls, v: Decimal) -> Decimal:
        """Validate score is 0-100."""
        if v < 0 or v > 100:
            raise ValueError("Score must be between 0 and 100")
        return v

    @field_validator("weight")
    @classmethod
    def validate_weight_range(cls, v: Decimal) -> Decimal:
        """Validate weight is 0-1."""
        if v < 0 or v > 1:
            raise ValueError("Weight must be between 0 and 1")
        return v

    def weighted_contribution(self) -> Decimal:
        """
        Calculate this test's weighted contribution to overall score.

        Returns:
            Score multiplied by weight
        """
        return self.score * self.weight
