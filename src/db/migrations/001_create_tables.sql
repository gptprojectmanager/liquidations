-- Migration 001: Create core tier tables
-- Creates tier_configurations and margin_tiers tables with continuity validation

-- Tier configurations (versioned)
CREATE TABLE IF NOT EXISTS tier_configurations (
    symbol VARCHAR PRIMARY KEY,
    version VARCHAR NOT NULL,
    last_updated TIMESTAMP NOT NULL DEFAULT current_timestamp,
    source VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT true,
    tiers JSON NOT NULL,
    CHECK (json_array_length(tiers) > 0)
);

-- Individual tiers (denormalized for query performance)
CREATE TABLE IF NOT EXISTS margin_tiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR NOT NULL,
    tier_number INTEGER NOT NULL,
    min_notional DECIMAL(20, 2) NOT NULL,
    max_notional DECIMAL(20, 2),
    margin_rate DECIMAL(8, 6) NOT NULL,
    maintenance_amount DECIMAL(20, 2) NOT NULL,
    UNIQUE(symbol, tier_number),
    CHECK (min_notional < max_notional),
    CHECK (margin_rate > 0 AND margin_rate <= 1),
    CHECK (maintenance_amount >= 0)
);

-- Calculation audit trail
CREATE TABLE IF NOT EXISTS position_margins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notional_value DECIMAL(20, 2) NOT NULL,
    tier_number INTEGER NOT NULL,
    margin_required DECIMAL(20, 2) NOT NULL,
    liquidation_price DECIMAL(20, 8) NOT NULL,
    calculated_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    configuration_version VARCHAR NOT NULL
);
