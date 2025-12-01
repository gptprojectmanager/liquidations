-- Migration 002: Add performance indexes
-- Creates indexes for fast tier lookup and audit queries

-- Index for tier lookup by symbol
CREATE INDEX IF NOT EXISTS idx_tiers_symbol
ON margin_tiers(symbol);

-- Composite index for tier lookup by symbol and notional range
-- This enables fast if-chain tier lookup
CREATE INDEX IF NOT EXISTS idx_tiers_notional
ON margin_tiers(symbol, min_notional, max_notional);

-- Index for audit trail queries by timestamp
CREATE INDEX IF NOT EXISTS idx_margins_calculated
ON position_margins(calculated_at);

-- Index for finding calculations by configuration version
CREATE INDEX IF NOT EXISTS idx_margins_version
ON position_margins(configuration_version);
