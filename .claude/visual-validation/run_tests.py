#!/usr/bin/env python3
"""
Automated visual testing script for heatmap combinations.
This script generates curl commands to capture screenshots for all combinations.
"""

import json

combinations = [
    ("5m", "1d"), ("5m", "3d"), ("5m", "7d"), ("5m", "14d"),
    ("15m", "1d"), ("15m", "3d"), ("15m", "7d"), ("15m", "14d"),
    ("1h", "1d"), ("1h", "3d"), ("1h", "7d"), ("1h", "14d"),
    ("4h", "1d"), ("4h", "3d"), ("4h", "7d"), ("4h", "14d"),
]

for i, (interval, lookback) in enumerate(combinations, 1):
    print(f"Test {i}: {interval} + {lookback}")

