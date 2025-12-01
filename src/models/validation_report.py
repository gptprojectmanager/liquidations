"""
ValidationReport data model.

Represents aggregated validation results with grade and recommendations.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReportFormat(str, Enum):
    """Report format types."""

    JSON = "json"
    TEXT = "text"
    HTML = "html"


class ValidationReport(BaseModel):
    """
    Aggregated validation report with grade and recommendations.

    Generated after ValidationRun completes, contains summary of all
    tests, overall grade, and actionable recommendations.
    """

    # Primary key
    report_id: str = Field(..., description="Unique report identifier")

    # Foreign key to ValidationRun
    run_id: str = Field(..., description="Parent validation run ID")

    # Report metadata
    format: ReportFormat = Field(..., description="Report format (json/text/html)")
    report_content: str = Field(..., description="Full report content")

    # Report summary
    summary: dict[str, Any] = Field(..., description="Structured summary data")
    recommendations: list[str] = Field(
        default_factory=list, description="Actionable recommendations"
    )

    # Alert status
    alert_sent: bool = Field(default=False, description="Whether alert was sent")
    alert_sent_at: Optional[datetime] = Field(None, description="Alert send timestamp")
    alert_recipients: list[str] = Field(default_factory=list, description="Alert recipients")

    # Metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Report generation timestamp"
    )

    model_config = ConfigDict(
        use_enum_values=False,
        validate_assignment=True,
    )
