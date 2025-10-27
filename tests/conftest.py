"""Pytest configuration and shared fixtures."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_csv_data():
    """Sample CSV data for testing ingestion."""
    return """timestamp,price,volume,side
1704067200000,42000.50,1.5,BUY
1704067260000,42010.25,0.8,SELL
1704067320000,42005.00,2.3,BUY
"""


@pytest.fixture
def sample_trade_data():
    """Sample trade data as list of dicts."""
    return [
        {"timestamp": 1704067200000, "price": 42000.50, "volume": 1.5, "side": "BUY"},
        {"timestamp": 1704067260000, "price": 42010.25, "volume": 0.8, "side": "SELL"},
        {"timestamp": 1704067320000, "price": 42005.00, "volume": 2.3, "side": "BUY"},
    ]
