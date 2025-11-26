-- Migration 003: Create audit and transition tables
-- Tracks tier configuration changes for rollback and compliance

-- Configuration change history
CREATE TABLE IF NOT EXISTS tier_transitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR NOT NULL,
    old_version VARCHAR NOT NULL,
    new_version VARCHAR NOT NULL,
    changes JSON NOT NULL,
    transitioned_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    triggered_by VARCHAR NOT NULL,
    rollback_available BOOLEAN DEFAULT true
);

-- Index for transition history queries
CREATE INDEX IF NOT EXISTS idx_transitions_symbol
ON tier_transitions(symbol, transitioned_at);

-- Index for finding rollback-eligible transitions
CREATE INDEX IF NOT EXISTS idx_transitions_rollback
ON tier_transitions(rollback_available, transitioned_at);

-- Configuration snapshots for rollback
CREATE TABLE IF NOT EXISTS tier_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR NOT NULL,
    version VARCHAR NOT NULL,
    configuration JSON NOT NULL,
    snapshot_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    snapshot_reason VARCHAR NOT NULL,
    UNIQUE(symbol, version)
);

-- Index for snapshot retrieval
CREATE INDEX IF NOT EXISTS idx_snapshots_symbol_version
ON tier_snapshots(symbol, version);
