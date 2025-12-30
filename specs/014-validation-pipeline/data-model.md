# Data Model: 014-validation-pipeline

**Feature**: Validation Pipeline
**Date**: 2025-12-30
**Purpose**: Define entities, relationships, and validation rules

---

## Entities

### 1. ValidationPipelineRun

**Description**: A single execution of the validation pipeline, orchestrating multiple validation types.

```python
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


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


@dataclass
class ValidationPipelineRun:
    """A complete pipeline run containing all validation results."""

    run_id: str
    started_at: datetime
    trigger_type: str  # 'manual', 'scheduled', 'ci'
    triggered_by: str  # User ID or 'system'
    symbol: str  # e.g., 'BTCUSDT'

    # Status
    status: PipelineStatus = PipelineStatus.PENDING
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None

    # Gate decisions
    gate_2_decision: GateDecision = GateDecision.SKIP
    gate_2_reason: str = ""

    # Aggregate metrics
    overall_grade: Optional[str] = None  # 'A', 'B', 'C', 'F'
    overall_score: Optional[Decimal] = None  # 0-100

    # Sub-results (references)
    backtest_result_id: Optional[str] = None
    coinglass_result_id: Optional[str] = None
    realtime_result_id: Optional[str] = None

    # Error handling
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "trigger_type": self.trigger_type,
            "triggered_by": self.triggered_by,
            "symbol": self.symbol,
            "status": self.status.value,
            "duration_seconds": self.duration_seconds,
            "gate_2_decision": self.gate_2_decision.value,
            "gate_2_reason": self.gate_2_reason,
            "overall_grade": self.overall_grade,
            "overall_score": float(self.overall_score) if self.overall_score else None,
            "sub_results": {
                "backtest": self.backtest_result_id,
                "coinglass": self.coinglass_result_id,
                "realtime": self.realtime_result_id,
            },
            "error_message": self.error_message,
        }
```

---

### 2. BacktestValidationResult

**Description**: Result from historical backtest validation (reuses existing `BacktestResult` from `backtest.py`).

**Location**: `src/liquidationheatmap/validation/backtest.py`

**Fields** (already defined):
- `config`: BacktestConfig
- `metrics`: PredictionMetrics (precision, recall, f1_score)
- `true_positives`, `false_positives`, `false_negatives`
- `matched_zones`, `missed_liquidations`, `false_alarms`
- `processing_time_ms`, `snapshots_analyzed`
- `error`

**Validation Rules**:
- `f1_score >= 0.6` → Gate 2 PASS
- `0.4 <= f1_score < 0.6` → ACCEPTABLE
- `f1_score < 0.4` → FAIL

---

### 3. CoinglassValidationResult

**Description**: Result from Coinglass comparison (OCR-based).

**Location**: `src/liquidationheatmap/validation/zone_comparator.py`

**Fields** (already defined in `AggregateMetrics`):
- `total_screenshots`
- `processed`
- `ocr_failures`, `api_failures`
- `avg_hit_rate`, `median_hit_rate`, `std_hit_rate`
- `pass_count`, `fail_count`, `pass_rate`
- `by_symbol`

**Note**: Coinglass validation is **informational only** due to methodology differences (see research.md).

---

### 4. DashboardMetrics

**Description**: Aggregated metrics for the validation dashboard.

```python
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
    trend: list[dict]  # [{"date": "2025-12-28", "f1_score": 0.81}]

    # Alerts
    alerts: list[dict]  # [{"level": "warning", "message": "..."}]

    # Backtest-specific
    backtest_coverage: int  # Number of snapshots analyzed
    backtest_period_days: int

    def to_dict(self) -> dict:
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
            "trend": self.trend,
            "alerts": self.alerts,
        }
```

---

## Database Schema

### Table: validation_pipeline_runs

```sql
CREATE TABLE IF NOT EXISTS validation_pipeline_runs (
    run_id VARCHAR(36) PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    trigger_type VARCHAR(20) NOT NULL,
    triggered_by VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    gate_2_decision VARCHAR(20) DEFAULT 'skip',
    gate_2_reason VARCHAR(500),
    overall_grade VARCHAR(1),
    overall_score DECIMAL(5,2),
    backtest_result_id VARCHAR(36),
    coinglass_result_id VARCHAR(36),
    realtime_result_id VARCHAR(36),
    error_message VARCHAR(1000),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pipeline_runs_started ON validation_pipeline_runs(started_at DESC);
CREATE INDEX idx_pipeline_runs_symbol ON validation_pipeline_runs(symbol);
CREATE INDEX idx_pipeline_runs_status ON validation_pipeline_runs(status);
```

### Table: validation_backtest_results

```sql
CREATE TABLE IF NOT EXISTS validation_backtest_results (
    result_id VARCHAR(36) PRIMARY KEY,
    pipeline_run_id VARCHAR(36) REFERENCES validation_pipeline_runs(run_id),
    symbol VARCHAR(20) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    tolerance_pct DECIMAL(5,2) DEFAULT 2.0,
    prediction_horizon_minutes INTEGER DEFAULT 60,
    f1_score DECIMAL(5,4),
    precision DECIMAL(5,4),
    recall DECIMAL(5,4),
    true_positives INTEGER DEFAULT 0,
    false_positives INTEGER DEFAULT 0,
    false_negatives INTEGER DEFAULT 0,
    snapshots_analyzed INTEGER DEFAULT 0,
    processing_time_ms INTEGER,
    gate_passed BOOLEAN,
    config_json VARCHAR,
    error_message VARCHAR(1000),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_backtest_results_pipeline ON validation_backtest_results(pipeline_run_id);
CREATE INDEX idx_backtest_results_created ON validation_backtest_results(created_at DESC);
```

### Table: validation_metrics_history

```sql
-- For dashboard trend chart
CREATE TABLE IF NOT EXISTS validation_metrics_history (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    metric_type VARCHAR(20) NOT NULL,  -- 'f1_score', 'precision', 'recall'
    value DECIMAL(5,4) NOT NULL,
    source_run_id VARCHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_history_date ON validation_metrics_history(date DESC);
CREATE INDEX idx_metrics_history_symbol ON validation_metrics_history(symbol, date);
CREATE UNIQUE INDEX idx_metrics_unique ON validation_metrics_history(date, symbol, metric_type);
```

---

## Relationships

```
ValidationPipelineRun
    │
    ├── 1:1 → BacktestValidationResult (backtest_result_id)
    │
    ├── 1:1 → CoinglassValidationResult (coinglass_result_id, optional)
    │
    └── 1:1 → RealtimeValidationResult (realtime_result_id, optional)

DashboardMetrics
    │
    └── aggregates → validation_metrics_history (last 30 days)
```

---

## Validation Rules

### Pipeline Run

| Field | Rule | Error Message |
|-------|------|---------------|
| `run_id` | UUID format | "Invalid run ID format" |
| `symbol` | Pattern `^[A-Z]{3,10}USDT$` | "Symbol must be format XXXUSDT" |
| `trigger_type` | Enum: manual, scheduled, ci | "Invalid trigger type" |
| `overall_score` | Range 0-100 | "Score must be 0-100" |

### Backtest Result

| Field | Rule | Error Message |
|-------|------|---------------|
| `f1_score` | Range 0-1 | "F1 must be 0-1" |
| `precision` | Range 0-1 | "Precision must be 0-1" |
| `recall` | Range 0-1 | "Recall must be 0-1" |
| `start_date < end_date` | Date order | "Start date must be before end date" |
| `end_date - start_date <= 365` | Max 1 year | "Date range cannot exceed 1 year" |

### Gate 2 Decision Logic

```python
def evaluate_gate_2(f1_score: float) -> tuple[GateDecision, str]:
    """Evaluate Gate 2 based on F1 score."""
    if f1_score >= 0.6:
        return GateDecision.PASS, f"F1={f1_score:.2%} >= 60% threshold"
    elif f1_score >= 0.4:
        return GateDecision.ACCEPTABLE, f"F1={f1_score:.2%} acceptable (40-60%)"
    else:
        return GateDecision.FAIL, f"F1={f1_score:.2%} < 40% threshold - model rework required"
```

---

## State Transitions

### Pipeline Run Status

```
[PENDING] → [RUNNING] → [COMPLETED]
    │           │
    │           └──────→ [FAILED]
    │
    └─────────────────→ [CANCELLED]
```

### Trigger Events

| From | To | Trigger |
|------|-----|---------|
| PENDING | RUNNING | Orchestrator starts execution |
| RUNNING | COMPLETED | All validations complete successfully |
| RUNNING | FAILED | Any validation throws unhandled error |
| PENDING | CANCELLED | User cancels before start |

---

## Integration Points

### Existing Modules

| Module | Integration |
|--------|-------------|
| `src/liquidationheatmap/validation/backtest.py` | Reuse `BacktestResult`, `run_backtest()` |
| `src/liquidationheatmap/validation/zone_comparator.py` | Reuse `ZoneComparator`, `AggregateMetrics` |
| `src/validation/storage.py` | Extend with new tables |
| `src/validation/test_runner.py` | Reference for orchestration pattern |

### New Modules

| Module | Purpose |
|--------|---------|
| `src/validation/pipeline/orchestrator.py` | Coordinate all validation types |
| `src/validation/pipeline/metrics_aggregator.py` | Compute dashboard metrics |
| `src/api/endpoints/dashboard.py` | Serve dashboard metrics API |
