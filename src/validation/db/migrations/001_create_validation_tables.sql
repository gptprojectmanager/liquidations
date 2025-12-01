-- ============================================================================
-- Validation Suite Database Schema
-- ============================================================================
-- Creates tables for storing validation run results, individual test scores,
-- aggregated reports, and historical trend data.
--
-- Design Principles:
-- - Normalized schema for data integrity
-- - Timestamp tracking for all entities
-- - Support for multi-model validation
-- - 90-day retention policy support
-- ============================================================================

-- ============================================================================
-- Table: validation_runs
-- ============================================================================
-- Represents a single validation execution (manual or scheduled)
--
CREATE TABLE IF NOT EXISTS validation_runs (
    -- Primary key
    run_id VARCHAR PRIMARY KEY,

    -- Execution metadata
    model_name VARCHAR NOT NULL,  -- Model being validated
    trigger_type VARCHAR NOT NULL,  -- 'scheduled' | 'manual'
    triggered_by VARCHAR,  -- User ID or 'system' for scheduled

    -- Timing
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,

    -- Status
    status VARCHAR NOT NULL,  -- 'running' | 'completed' | 'failed' | 'incomplete'
    error_message VARCHAR,

    -- Data window
    data_start_date DATE NOT NULL,
    data_end_date DATE NOT NULL,
    data_completeness DECIMAL(5, 2),  -- Percentage of expected data available

    -- Results summary
    overall_grade VARCHAR,  -- 'A' | 'B' | 'C' | 'F'
    overall_score DECIMAL(5, 2),  -- 0-100

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_validation_runs_started_at ON validation_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_validation_runs_model_name ON validation_runs(model_name);
CREATE INDEX IF NOT EXISTS idx_validation_runs_status ON validation_runs(status);
CREATE INDEX IF NOT EXISTS idx_validation_runs_trigger_type ON validation_runs(trigger_type);

-- ============================================================================
-- Table: validation_tests
-- ============================================================================
-- Individual test results within a validation run
--
CREATE TABLE IF NOT EXISTS validation_tests (
    -- Primary key
    test_id VARCHAR PRIMARY KEY,

    -- Foreign key to validation_runs
    run_id VARCHAR NOT NULL,

    -- Test identification
    test_type VARCHAR NOT NULL,  -- 'funding_correlation' | 'oi_conservation' | 'directional_positioning'
    test_name VARCHAR NOT NULL,

    -- Results
    passed BOOLEAN NOT NULL,
    score DECIMAL(5, 2),  -- 0-100
    weight DECIMAL(5, 2),  -- Weight in overall score (0-1)

    -- Statistical metrics
    primary_metric DECIMAL(10, 6),  -- Main test result (e.g., correlation coefficient)
    secondary_metric DECIMAL(10, 6),  -- Supporting metric (e.g., p-value)

    -- Diagnostics
    diagnostics JSON,  -- Detailed test-specific diagnostics
    error_message VARCHAR,

    -- Timing
    executed_at TIMESTAMP NOT NULL,
    duration_ms INTEGER,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraint
    FOREIGN KEY (run_id) REFERENCES validation_runs(run_id) ON DELETE CASCADE
);

-- Indexes for test queries
CREATE INDEX IF NOT EXISTS idx_validation_tests_run_id ON validation_tests(run_id);
CREATE INDEX IF NOT EXISTS idx_validation_tests_test_type ON validation_tests(test_type);
CREATE INDEX IF NOT EXISTS idx_validation_tests_passed ON validation_tests(passed);

-- ============================================================================
-- Table: validation_reports
-- ============================================================================
-- Generated reports for each validation run
--
CREATE TABLE IF NOT EXISTS validation_reports (
    -- Primary key
    report_id VARCHAR PRIMARY KEY,

    -- Foreign key to validation_runs
    run_id VARCHAR NOT NULL,

    -- Report metadata
    format VARCHAR NOT NULL,  -- 'json' | 'text' | 'html'
    report_content TEXT NOT NULL,

    -- Report summary
    summary JSON,  -- Structured summary data
    recommendations JSON,  -- Array of recommendation strings

    -- Alert status
    alert_sent BOOLEAN DEFAULT FALSE,
    alert_sent_at TIMESTAMP,
    alert_recipients JSON,  -- Array of recipient emails/webhooks

    -- Metadata
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraint
    FOREIGN KEY (run_id) REFERENCES validation_runs(run_id) ON DELETE CASCADE
);

-- Indexes for report queries
CREATE INDEX IF NOT EXISTS idx_validation_reports_run_id ON validation_reports(run_id);
CREATE INDEX IF NOT EXISTS idx_validation_reports_format ON validation_reports(format);
CREATE INDEX IF NOT EXISTS idx_validation_reports_alert_sent ON validation_reports(alert_sent);

-- ============================================================================
-- Table: historical_trends
-- ============================================================================
-- Time-series data for metric tracking and trend analysis
--
CREATE TABLE IF NOT EXISTS historical_trends (
    -- Primary key
    trend_id VARCHAR PRIMARY KEY,

    -- Metric identification
    model_name VARCHAR NOT NULL,
    metric_name VARCHAR NOT NULL,  -- 'overall_score' | 'funding_correlation' | 'oi_error' | etc.

    -- Time series data
    timestamp TIMESTAMP NOT NULL,
    value DECIMAL(10, 6) NOT NULL,

    -- Associated run (optional - null for external metrics)
    run_id VARCHAR,

    -- Moving averages (pre-calculated for performance)
    moving_avg_7d DECIMAL(10, 6),
    moving_avg_30d DECIMAL(10, 6),
    moving_avg_90d DECIMAL(10, 6),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraint
    FOREIGN KEY (run_id) REFERENCES validation_runs(run_id) ON DELETE SET NULL
);

-- Indexes for trend queries
CREATE INDEX IF NOT EXISTS idx_historical_trends_model_metric ON historical_trends(model_name, metric_name);
CREATE INDEX IF NOT EXISTS idx_historical_trends_timestamp ON historical_trends(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_historical_trends_run_id ON historical_trends(run_id);

-- ============================================================================
-- Table: alert_configurations
-- ============================================================================
-- Configuration for alert thresholds and notification settings
--
CREATE TABLE IF NOT EXISTS alert_configurations (
    -- Primary key
    config_id VARCHAR PRIMARY KEY,

    -- Alert identification
    model_name VARCHAR NOT NULL,
    alert_type VARCHAR NOT NULL,  -- 'grade_drop' | 'test_failure' | 'data_gap'

    -- Thresholds
    threshold_value DECIMAL(10, 6),
    threshold_condition VARCHAR,  -- 'less_than' | 'greater_than' | 'equals'

    -- Notification settings
    enabled BOOLEAN DEFAULT TRUE,
    channels JSON,  -- Array of channel names ['email', 'slack', 'webhook']
    recipients JSON,  -- Array of recipient addresses

    -- Suppression rules
    suppression_window_hours INTEGER DEFAULT 24,
    last_alert_sent_at TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for alert queries
CREATE INDEX IF NOT EXISTS idx_alert_configurations_model_name ON alert_configurations(model_name);
CREATE INDEX IF NOT EXISTS idx_alert_configurations_enabled ON alert_configurations(enabled);

-- ============================================================================
-- Table: validation_queue
-- ============================================================================
-- Queue for managing manual validation triggers
--
CREATE TABLE IF NOT EXISTS validation_queue (
    -- Primary key
    queue_id VARCHAR PRIMARY KEY,

    -- Request metadata
    model_name VARCHAR NOT NULL,
    requested_by VARCHAR NOT NULL,
    request_params JSON,  -- Custom parameters for validation run

    -- Queue status
    status VARCHAR NOT NULL,  -- 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
    position INTEGER,  -- Position in queue (1-indexed)

    -- Timing
    queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Associated run (when executed)
    run_id VARCHAR,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraint
    FOREIGN KEY (run_id) REFERENCES validation_runs(run_id) ON DELETE SET NULL
);

-- Indexes for queue management
CREATE INDEX IF NOT EXISTS idx_validation_queue_status ON validation_queue(status);
CREATE INDEX IF NOT EXISTS idx_validation_queue_position ON validation_queue(position);
CREATE INDEX IF NOT EXISTS idx_validation_queue_queued_at ON validation_queue(queued_at);

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

-- View: Latest validation results per model
CREATE OR REPLACE VIEW latest_validation_results AS
SELECT
    vr.model_name,
    vr.run_id,
    vr.started_at,
    vr.overall_grade,
    vr.overall_score,
    vr.status,
    vr.data_completeness
FROM validation_runs vr
INNER JOIN (
    SELECT model_name, MAX(started_at) AS max_started_at
    FROM validation_runs
    WHERE status = 'completed'
    GROUP BY model_name
) latest ON vr.model_name = latest.model_name AND vr.started_at = latest.max_started_at;

-- View: Validation success rate by model (last 30 days)
CREATE OR REPLACE VIEW validation_success_rate AS
SELECT
    model_name,
    COUNT(*) AS total_runs,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS successful_runs,
    ROUND(100.0 * SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 2) AS success_rate,
    AVG(CASE WHEN status = 'completed' THEN overall_score END) AS avg_score
FROM validation_runs
WHERE started_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY model_name;

-- View: Active alerts requiring attention
CREATE OR REPLACE VIEW active_alerts AS
SELECT
    vr.model_name,
    vr.run_id,
    vr.started_at,
    vr.overall_grade,
    vr.overall_score,
    vrep.alert_sent,
    vrep.alert_sent_at
FROM validation_runs vr
INNER JOIN validation_reports vrep ON vr.run_id = vrep.run_id
WHERE vr.overall_grade IN ('C', 'F')
  AND vr.status = 'completed'
  AND vr.started_at >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY vr.started_at DESC;

-- ============================================================================
-- Data Retention Policy Trigger
-- ============================================================================
-- Automatically delete validation data older than 90 days
--
-- Note: DuckDB doesn't support triggers, so this should be executed as a
-- scheduled job via Python/APScheduler

-- Manual cleanup query (to be wrapped in Python scheduled job):
/*
DELETE FROM validation_runs
WHERE started_at < CURRENT_DATE - INTERVAL '90 days';

-- Cascade delete will handle related records in:
-- - validation_tests
-- - validation_reports
-- - historical_trends (via SET NULL)
*/

-- ============================================================================
-- End of Schema
-- ============================================================================
