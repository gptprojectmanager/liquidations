-- ============================================================================
-- Validation Pipeline Tables
-- ============================================================================
-- Tables for the unified validation pipeline (Phase 5 CI Integration)
-- Per specs/014-validation-pipeline/data-model.md
-- ============================================================================

-- ============================================================================
-- Table: validation_pipeline_runs
-- ============================================================================
-- Tracks complete pipeline runs with gate decisions
--
CREATE TABLE IF NOT EXISTS validation_pipeline_runs (
    -- Primary key
    run_id VARCHAR PRIMARY KEY,

    -- Execution metadata
    symbol VARCHAR(20) NOT NULL,  -- Trading pair (e.g., 'BTCUSDT')
    trigger_type VARCHAR(20) NOT NULL,  -- 'manual' | 'scheduled' | 'ci' | 'api'
    triggered_by VARCHAR(200) NOT NULL,  -- User ID or 'system'

    -- Timing
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,

    -- Status
    status VARCHAR(20) NOT NULL,  -- 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
    error_message TEXT,

    -- Gate 2 decision
    gate_2_decision VARCHAR(20) DEFAULT 'skip',  -- 'pass' | 'acceptable' | 'fail' | 'skip'
    gate_2_reason TEXT,

    -- Overall results
    overall_grade VARCHAR(1),  -- 'A' | 'B' | 'C' | 'F'
    overall_score DECIMAL(5, 2),  -- 0-100

    -- Validation types run
    validation_types JSON,  -- Array of validation type strings

    -- Sub-result references
    backtest_result_id VARCHAR,
    coinglass_result_id VARCHAR,
    realtime_result_id VARCHAR,

    -- Configuration used
    config JSON,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON validation_pipeline_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_symbol ON validation_pipeline_runs(symbol);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON validation_pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_gate_decision ON validation_pipeline_runs(gate_2_decision);

-- ============================================================================
-- Table: validation_backtest_results
-- ============================================================================
-- Stores backtest validation results with F1/precision/recall
--
CREATE TABLE IF NOT EXISTS validation_backtest_results (
    -- Primary key
    result_id VARCHAR PRIMARY KEY,

    -- Reference to pipeline run (optional - can be standalone)
    run_id VARCHAR,

    -- Trading pair
    symbol VARCHAR(20) NOT NULL,

    -- Date range validated
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    -- Primary metrics
    f1_score DECIMAL(5, 4),  -- 0.0000 - 1.0000
    precision DECIMAL(5, 4),
    recall DECIMAL(5, 4),

    -- Counts
    true_positives INTEGER DEFAULT 0,
    false_positives INTEGER DEFAULT 0,
    false_negatives INTEGER DEFAULT 0,
    snapshots_analyzed INTEGER DEFAULT 0,

    -- Performance
    processing_time_ms INTEGER DEFAULT 0,

    -- Gate result
    gate_passed BOOLEAN DEFAULT FALSE,

    -- Configuration
    tolerance_pct DECIMAL(4, 2) DEFAULT 2.0,

    -- Error handling
    error_message TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraint
    FOREIGN KEY (run_id) REFERENCES validation_pipeline_runs(run_id) ON DELETE SET NULL
);

-- Indexes for backtest queries
CREATE INDEX IF NOT EXISTS idx_backtest_results_run_id ON validation_backtest_results(run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_results_symbol ON validation_backtest_results(symbol);
CREATE INDEX IF NOT EXISTS idx_backtest_results_created_at ON validation_backtest_results(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backtest_results_f1_score ON validation_backtest_results(f1_score);

-- ============================================================================
-- Table: validation_metrics_history
-- ============================================================================
-- Time-series metrics for dashboard trend charts
-- Note: Created dynamically by MetricsAggregator, but defined here for schema clarity
--
CREATE TABLE IF NOT EXISTS validation_metrics_history (
    -- Composite primary key
    date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    metric_type VARCHAR(20) NOT NULL,  -- 'f1_score' | 'precision' | 'recall'

    -- Value
    value DECIMAL(5, 4) NOT NULL,

    -- Reference to source run
    source_run_id VARCHAR(36),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Primary key constraint
    PRIMARY KEY (date, symbol, metric_type)
);

-- Indexes for history queries
CREATE INDEX IF NOT EXISTS idx_metrics_history_symbol ON validation_metrics_history(symbol);
CREATE INDEX IF NOT EXISTS idx_metrics_history_date ON validation_metrics_history(date DESC);

-- ============================================================================
-- View: Latest Pipeline Results
-- ============================================================================
CREATE OR REPLACE VIEW latest_pipeline_results AS
SELECT
    pr.run_id,
    pr.symbol,
    pr.started_at,
    pr.completed_at,
    pr.status,
    pr.gate_2_decision,
    pr.overall_grade,
    pr.overall_score,
    br.f1_score,
    br.precision,
    br.recall,
    br.snapshots_analyzed
FROM validation_pipeline_runs pr
LEFT JOIN validation_backtest_results br ON pr.backtest_result_id = br.result_id
WHERE pr.status = 'completed'
ORDER BY pr.started_at DESC;

-- ============================================================================
-- End of Pipeline Schema
-- ============================================================================
