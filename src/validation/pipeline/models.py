"""Data models for the validation pipeline.

Defines entities for pipeline runs, gate decisions, and dashboard metrics
per specs/014-validation-pipeline/data-model.md.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class PipelineStatus(str, Enum):
    """Status of a pipeline run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ValidationType(str, Enum):
    """Type of validation performed."""

    BACKTEST = "backtest"
    COINGLASS = "coinglass"
    REALTIME = "realtime"
    FULL = "full"  # All validation types


class GateDecision(str, Enum):
    """Gate pass/fail decision."""

    PASS = "pass"
    ACCEPTABLE = "acceptable"
    FAIL = "fail"
    SKIP = "skip"  # Gate not evaluated


class TriggerType(str, Enum):
    """How the pipeline was triggered."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    CI = "ci"
    API = "api"


@dataclass
class ValidationPipelineRun:
    """A complete pipeline run containing all validation results.

    Tracks the execution state and results of a validation pipeline run.
    """

    run_id: str
    started_at: datetime
    trigger_type: TriggerType
    triggered_by: str  # User ID or 'system'
    symbol: str  # e.g., 'BTCUSDT'

    # Status
    status: PipelineStatus = PipelineStatus.PENDING
    completed_at: datetime | None = None
    duration_seconds: int | None = None

    # Gate decisions
    gate_2_decision: GateDecision = GateDecision.SKIP
    gate_2_reason: str = ""

    # Aggregate metrics
    overall_grade: str | None = None  # 'A', 'B', 'C', 'F'
    overall_score: Decimal | None = None  # 0-100

    # Sub-results (references)
    backtest_result_id: str | None = None
    coinglass_result_id: str | None = None
    realtime_result_id: str | None = None

    # Error handling
    error_message: str | None = None

    # Validation types requested
    validation_types: list[ValidationType] = field(
        default_factory=lambda: [ValidationType.BACKTEST]
    )

    # Configuration
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "trigger_type": self.trigger_type.value,
            "triggered_by": self.triggered_by,
            "symbol": self.symbol,
            "status": self.status.value,
            "duration_seconds": self.duration_seconds,
            "gate_2_decision": self.gate_2_decision.value,
            "gate_2_reason": self.gate_2_reason,
            "overall_grade": self.overall_grade,
            "overall_score": float(self.overall_score) if self.overall_score else None,
            "validation_types": [vt.value for vt in self.validation_types],
            "sub_results": {
                "backtest": self.backtest_result_id,
                "coinglass": self.coinglass_result_id,
                "realtime": self.realtime_result_id,
            },
            "error_message": self.error_message,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationPipelineRun":
        """Create from JSON dict."""
        return cls(
            run_id=data["run_id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            trigger_type=TriggerType(data["trigger_type"]),
            triggered_by=data["triggered_by"],
            symbol=data["symbol"],
            status=PipelineStatus(data.get("status", "pending")),
            completed_at=datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None,
            duration_seconds=data.get("duration_seconds"),
            gate_2_decision=GateDecision(data.get("gate_2_decision", "skip")),
            gate_2_reason=data.get("gate_2_reason", ""),
            overall_grade=data.get("overall_grade"),
            overall_score=Decimal(str(data["overall_score"]))
            if data.get("overall_score")
            else None,
            validation_types=[
                ValidationType(vt) for vt in data.get("validation_types", ["backtest"])
            ],
            backtest_result_id=data.get("sub_results", {}).get("backtest"),
            coinglass_result_id=data.get("sub_results", {}).get("coinglass"),
            realtime_result_id=data.get("sub_results", {}).get("realtime"),
            error_message=data.get("error_message"),
            config=data.get("config", {}),
        )


@dataclass
class BacktestResultSummary:
    """Summary of backtest results for dashboard/pipeline use.

    Extracted from BacktestResult to avoid circular dependencies.
    """

    result_id: str
    symbol: str
    start_date: datetime
    end_date: datetime
    f1_score: float
    precision: float
    recall: float
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    snapshots_analyzed: int = 0
    processing_time_ms: int = 0
    gate_passed: bool = False
    tolerance_pct: float = 2.0
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "result_id": self.result_id,
            "symbol": self.symbol,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "f1_score": self.f1_score,
            "precision": self.precision,
            "recall": self.recall,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "snapshots_analyzed": self.snapshots_analyzed,
            "processing_time_ms": self.processing_time_ms,
            "gate_passed": self.gate_passed,
            "tolerance_pct": self.tolerance_pct,
            "error_message": self.error_message,
        }


@dataclass
class TrendDataPoint:
    """Single data point for trend chart."""

    date: str  # ISO date string YYYY-MM-DD
    f1_score: float
    precision: float | None = None
    recall: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result = {"date": self.date, "f1_score": self.f1_score}
        if self.precision is not None:
            result["precision"] = self.precision
        if self.recall is not None:
            result["recall"] = self.recall
        return result


@dataclass
class Alert:
    """Dashboard alert."""

    level: str  # 'info', 'warning', 'error'
    message: str
    timestamp: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "level": self.level,
            "message": self.message,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class DashboardMetrics:
    """Metrics displayed on the validation dashboard."""

    # Current status
    status: str  # 'healthy', 'warning', 'critical'
    last_validation_timestamp: datetime
    last_validation_grade: str

    # Latest metrics
    f1_score: float
    precision: float
    recall: float

    # Trend data (last 30 days)
    trend: list[TrendDataPoint] = field(default_factory=list)

    # Alerts
    alerts: list[Alert] = field(default_factory=list)

    # Backtest-specific
    backtest_coverage: int = 0  # Number of snapshots analyzed
    backtest_period_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict for API response."""
        return {
            "status": self.status,
            "last_validation": {
                "timestamp": self.last_validation_timestamp.isoformat(),
                "grade": self.last_validation_grade,
                "f1_score": self.f1_score,
                "precision": self.precision,
                "recall": self.recall,
            },
            "backtest_coverage": {
                "snapshots": self.backtest_coverage,
                "period_days": self.backtest_period_days,
            },
            "trend": [t.to_dict() for t in self.trend],
            "alerts": [a.to_dict() for a in self.alerts],
        }


def evaluate_gate_2(f1_score: float) -> tuple[GateDecision, str]:
    """Evaluate Gate 2 based on F1 score.

    Args:
        f1_score: F1 score between 0 and 1

    Returns:
        Tuple of (decision, reason)
    """
    if f1_score >= 0.6:
        return GateDecision.PASS, f"F1={f1_score:.2%} >= 60% threshold"
    elif f1_score >= 0.4:
        return GateDecision.ACCEPTABLE, f"F1={f1_score:.2%} acceptable (40-60%)"
    else:
        return GateDecision.FAIL, f"F1={f1_score:.2%} < 40% threshold - model rework required"


def compute_overall_grade(f1_score: float) -> str:
    """Compute letter grade from F1 score.

    Args:
        f1_score: F1 score between 0 and 1

    Returns:
        Grade letter: 'A', 'B', 'C', or 'F'
    """
    if f1_score >= 0.8:
        return "A"
    elif f1_score >= 0.7:
        return "B"
    elif f1_score >= 0.6:
        return "C"
    else:
        return "F"


def compute_overall_score(f1_score: float) -> Decimal:
    """Convert F1 score to 0-100 scale.

    Args:
        f1_score: F1 score between 0 and 1

    Returns:
        Score on 0-100 scale
    """
    return Decimal(str(round(f1_score * 100, 2)))


def determine_dashboard_status(f1_score: float, days_since_validation: int) -> str:
    """Determine dashboard status based on metrics.

    Args:
        f1_score: Latest F1 score
        days_since_validation: Days since last validation run

    Returns:
        Status: 'healthy', 'warning', or 'critical'
    """
    # Critical if validation is stale (>14 days) or F1 < 40%
    if days_since_validation > 14 or f1_score < 0.4:
        return "critical"

    # Warning if validation is aging (>7 days) or F1 < 60%
    if days_since_validation > 7 or f1_score < 0.6:
        return "warning"

    return "healthy"
