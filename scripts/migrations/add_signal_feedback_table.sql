-- Migration: Add signal_feedback table for P&L tracking
-- Feature: 015-adaptive-signals
-- Date: 2025-12-28

-- Create sequence for auto-increment (DuckDB style)
CREATE SEQUENCE IF NOT EXISTS signal_feedback_id_seq;

-- Signal feedback table stores P&L results from trading systems
CREATE TABLE IF NOT EXISTS signal_feedback (
    id INTEGER PRIMARY KEY DEFAULT nextval('signal_feedback_id_seq'),
    symbol VARCHAR NOT NULL,
    signal_id VARCHAR NOT NULL,
    entry_price DECIMAL(28, 8) NOT NULL,
    exit_price DECIMAL(28, 8) NOT NULL,
    pnl DECIMAL(28, 8) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    source VARCHAR NOT NULL,  -- 'nautilus' or 'manual'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraint for source validation
    CHECK (source IN ('nautilus', 'manual'))
);

-- Index for symbol + time-based queries (rolling windows)
CREATE INDEX IF NOT EXISTS idx_signal_feedback_symbol_time
ON signal_feedback(symbol, timestamp DESC);

-- Index for signal_id lookups (joining back to original signals)
CREATE INDEX IF NOT EXISTS idx_signal_feedback_signal_id
ON signal_feedback(signal_id);

-- Index for source filtering
CREATE INDEX IF NOT EXISTS idx_signal_feedback_source
ON signal_feedback(source);
