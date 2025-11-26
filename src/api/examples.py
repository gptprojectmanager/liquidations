"""
API request/response examples for documentation.

Provides concrete examples for OpenAPI documentation.
"""

# Calculate margin examples
CALCULATE_EXAMPLES = {
    "basic": {
        "summary": "Basic margin calculation",
        "description": "Calculate margin for a $50k position in BTCUSDT",
        "value": {"symbol": "BTCUSDT", "notional": "50000"},
    },
    "with_liquidation": {
        "summary": "Calculate with liquidation price",
        "description": "Calculate margin and liquidation price for leveraged position",
        "value": {
            "symbol": "BTCUSDT",
            "entry_price": "50000",
            "position_size": "1",
            "leverage": "10",
            "side": "long",
        },
    },
    "with_display": {
        "summary": "Calculate with display formatting",
        "description": "Include user-friendly formatted strings",
        "value": {
            "symbol": "BTCUSDT",
            "notional": "100000",
            "include_display": True,
            "include_tier_details": True,
        },
    },
}

# Calculate response examples
CALCULATE_RESPONSE_EXAMPLES = {
    "tier_1": {
        "summary": "Tier 1 position ($50k)",
        "value": {
            "symbol": "BTCUSDT",
            "notional": "50000.00",
            "margin": "250.00",
            "tier": 1,
            "margin_rate": "0.5%",
            "maintenance_amount": "0.00",
        },
    },
    "tier_3": {
        "summary": "Tier 3 position ($500k)",
        "value": {
            "symbol": "BTCUSDT",
            "notional": "500000.00",
            "margin": "8500.00",
            "tier": 3,
            "margin_rate": "2.5%",
            "maintenance_amount": "4000.00",
        },
    },
}

# Batch examples
BATCH_EXAMPLES = {
    "multiple_tiers": {
        "summary": "Positions across multiple tiers",
        "value": {
            "calculations": [
                {"symbol": "BTCUSDT", "notional": "50000"},
                {"symbol": "BTCUSDT", "notional": "100000"},
                {"symbol": "BTCUSDT", "notional": "500000"},
            ]
        },
    }
}
