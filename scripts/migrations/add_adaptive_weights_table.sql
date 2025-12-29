-- Migration: Add adaptive_weights table for weight history
-- Feature: 015-adaptive-signals
-- Date: 2025-12-28

-- Create sequence for auto-increment
CREATE SEQUENCE IF NOT EXISTS adaptive_weights_id_seq;

-- Weight history table stores weight changes over time
CREATE TABLE IF NOT EXISTS adaptive_weights (
    id INTEGER PRIMARY KEY DEFAULT nextval('adaptive_weights_id_seq'),
    symbol VARCHAR NOT NULL,
    long_weight DECIMAL(10, 6) NOT NULL,
    short_weight DECIMAL(10, 6) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Weights should sum to 1.0
    CHECK (long_weight >= 0 AND long_weight <= 1),
    CHECK (short_weight >= 0 AND short_weight <= 1)
);

-- Index for symbol + time-based queries
CREATE INDEX IF NOT EXISTS idx_adaptive_weights_symbol_time
ON adaptive_weights(symbol, timestamp DESC);

-- Index for latest weight lookup
CREATE INDEX IF NOT EXISTS idx_adaptive_weights_latest
ON adaptive_weights(symbol, id DESC);
