"""Tests for DuckDB service."""

from decimal import Decimal

import pytest

from src.liquidationheatmap.ingestion.db_service import DuckDBService


class TestDuckDBService:
    """Tests for DuckDBService data queries."""

    def test_get_latest_open_interest_returns_real_data(self, tmp_path):
        """Test that service loads and returns real Open Interest from CSV."""
        # Use temporary database
        db_path = tmp_path / "test.duckdb"
        
        with DuckDBService(str(db_path)) as db:
            current_price, open_interest = db.get_latest_open_interest("BTCUSDT")
            
            # Should return real data from sample CSV (not default mock)
            assert isinstance(current_price, Decimal)
            assert isinstance(open_interest, Decimal)
            assert open_interest > Decimal("1000000")  # Should be >1M from real data

    def test_get_latest_funding_rate_returns_real_data(self, tmp_path):
        """Test that service returns real funding rate from CSV."""
        db_path = tmp_path / "test.duckdb"
        
        with DuckDBService(str(db_path)) as db:
            funding_rate = db.get_latest_funding_rate("BTCUSDT")
            
            assert isinstance(funding_rate, Decimal)
            # Should be realistic funding rate (0.0001-0.0002 from sample data)
            assert Decimal("0.00001") < funding_rate < Decimal("0.001")

    def test_no_duplicates_when_loading_same_csv_twice(self, tmp_path):
        """Test that loading same CSV twice doesn't create duplicates."""
        db_path = tmp_path / "test.duckdb"
        
        # Load data first time
        with DuckDBService(str(db_path)) as db:
            current_price1, oi1 = db.get_latest_open_interest("BTCUSDT")
            
            # Count rows
            count1 = db.conn.execute(
                "SELECT COUNT(*) FROM open_interest_history WHERE symbol = 'BTCUSDT'"
            ).fetchone()[0]
        
        # Load data second time (should not duplicate)
        with DuckDBService(str(db_path)) as db:
            current_price2, oi2 = db.get_latest_open_interest("BTCUSDT")
            
            count2 = db.conn.execute(
                "SELECT COUNT(*) FROM open_interest_history WHERE symbol = 'BTCUSDT'"
            ).fetchone()[0]
        
        # Should have same count (no duplicates)
        assert count1 == count2
        # Values should be same (within precision tolerance)
        assert abs(oi1 - oi2) < Decimal("0.01")
