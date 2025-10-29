"""Tests for data validation functionality."""

from decimal import Decimal

import pandas as pd
import pytest

from src.liquidationheatmap.ingestion.validators import (
    detect_outliers,
    validate_date_range,
    validate_funding_rate,
    validate_price,
    validate_symbol,
    validate_volume,
)


class TestValidatePrice:
    """Tests for validate_price function."""
    
    def test_validate_price_accepts_valid_btc_price(self):
        """Test that valid BTC prices are accepted."""
        assert validate_price(Decimal("67000.00")) is True
        assert validate_price(Decimal("42000.50")) is True
        assert validate_price(Decimal("100000.00")) is True
    
    def test_validate_price_rejects_outliers(self):
        """Test that prices outside reasonable range are rejected."""
        # Too low
        assert validate_price(Decimal("5000.00")) is False
        assert validate_price(Decimal("9999.99")) is False
        
        # Too high
        assert validate_price(Decimal("600000.00")) is False
        assert validate_price(Decimal("1000000.00")) is False
    
    def test_validate_price_rejects_negative(self):
        """Test that negative prices are rejected."""
        assert validate_price(Decimal("-100.00")) is False
    
    def test_validate_price_handles_invalid_input(self):
        """Test that invalid inputs return False."""
        assert validate_price("invalid") is False
        assert validate_price(None) is False


class TestValidateDateRange:
    """Tests for validate_date_range function."""
    
    def test_validate_date_range_accepts_complete_range(self):
        """Test that complete date range is validated."""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-10-22', periods=7, freq='D')
        })
        
        assert validate_date_range(df, expected_days=7) is True
    
    def test_validate_date_range_detects_missing_days(self):
        """Test that missing days are detected."""
        # Only 5 days instead of 7
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-10-22', periods=5, freq='D')
        })
        
        # Should fail with 2 missing days (tolerance=1)
        assert validate_date_range(df, expected_days=7, tolerance=1) is False
        
        # But should pass with higher tolerance
        assert validate_date_range(df, expected_days=7, tolerance=3) is True
    
    def test_validate_date_range_handles_empty_dataframe(self):
        """Test that empty DataFrame returns False."""
        df = pd.DataFrame()
        assert validate_date_range(df, expected_days=7) is False
    
    def test_validate_date_range_handles_missing_column(self):
        """Test that DataFrame without timestamp column returns False."""
        df = pd.DataFrame({'price': [42000, 43000, 44000]})
        assert validate_date_range(df, expected_days=3) is False
    
    def test_validate_date_range_handles_duplicate_dates(self):
        """Test that duplicate dates are counted once."""
        # Create DataFrame with hourly data (multiple rows per day)
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-10-22', periods=24, freq='H')
        })
        
        # Should count as 2 days (22nd and 23rd), not 24
        assert validate_date_range(df, expected_days=1, tolerance=0) is True


class TestDetectOutliers:
    """Tests for detect_outliers function."""
    
    def test_detect_outliers_finds_extreme_values(self):
        """Test that obvious outliers are detected."""
        df = pd.DataFrame({
            'value': [10, 12, 11, 10, 100, 9, 11]  # 100 is outlier
        })
        
        outliers = detect_outliers(df, 'value', std_threshold=2.0)
        
        assert 4 in outliers  # Index of 100
        assert len(outliers) == 1
    
    def test_detect_outliers_returns_empty_for_normal_data(self):
        """Test that no outliers detected in normal distribution."""
        df = pd.DataFrame({
            'value': [10, 11, 12, 11, 10, 9, 11, 10, 12]
        })
        
        outliers = detect_outliers(df, 'value', std_threshold=3.0)
        
        assert len(outliers) == 0
    
    def test_detect_outliers_handles_empty_dataframe(self):
        """Test that empty DataFrame returns empty list."""
        df = pd.DataFrame()
        outliers = detect_outliers(df, 'value')
        assert outliers == []
    
    def test_detect_outliers_handles_missing_column(self):
        """Test that missing column returns empty list."""
        df = pd.DataFrame({'price': [10, 20, 30]})
        outliers = detect_outliers(df, 'non_existent')
        assert outliers == []
    
    def test_detect_outliers_handles_constant_values(self):
        """Test that constant values (std=0) return empty list."""
        df = pd.DataFrame({'value': [10, 10, 10, 10]})
        outliers = detect_outliers(df, 'value')
        assert outliers == []
    
    def test_detect_outliers_with_different_threshold(self):
        """Test that threshold changes outlier detection."""
        df = pd.DataFrame({
            'value': [10, 12, 11, 10, 25, 9, 11]  # 25 is mild outlier
        })
        
        # Strict threshold (2.0) should catch it
        outliers_strict = detect_outliers(df, 'value', std_threshold=2.0)
        assert len(outliers_strict) > 0
        
        # Lenient threshold (5.0) might not
        outliers_lenient = detect_outliers(df, 'value', std_threshold=5.0)
        assert len(outliers_lenient) <= len(outliers_strict)


class TestValidateVolume:
    """Tests for validate_volume function."""
    
    def test_validate_volume_accepts_positive_values(self):
        """Test that positive volumes are accepted."""
        assert validate_volume(Decimal("1234567.89")) is True
        assert validate_volume(Decimal("0.01")) is True
    
    def test_validate_volume_accepts_zero(self):
        """Test that zero volume is accepted."""
        assert validate_volume(Decimal("0.0")) is True
    
    def test_validate_volume_rejects_negative(self):
        """Test that negative volumes are rejected."""
        assert validate_volume(Decimal("-100.00")) is False
    
    def test_validate_volume_with_custom_minimum(self):
        """Test that custom minimum volume threshold works."""
        assert validate_volume(Decimal("10.00"), min_volume=Decimal("5.0")) is True
        assert validate_volume(Decimal("3.00"), min_volume=Decimal("5.0")) is False


class TestValidateFundingRate:
    """Tests for validate_funding_rate function."""
    
    def test_validate_funding_rate_accepts_normal_rates(self):
        """Test that normal funding rates are accepted."""
        assert validate_funding_rate(Decimal("0.0001")) is True
        assert validate_funding_rate(Decimal("-0.0001")) is True
        assert validate_funding_rate(Decimal("0.001")) is True
    
    def test_validate_funding_rate_rejects_extreme_rates(self):
        """Test that extreme funding rates are rejected."""
        # >1% is abnormal
        assert validate_funding_rate(Decimal("0.05")) is False
        assert validate_funding_rate(Decimal("-0.05")) is False
        assert validate_funding_rate(Decimal("0.02")) is False
    
    def test_validate_funding_rate_accepts_zero(self):
        """Test that zero funding rate is accepted."""
        assert validate_funding_rate(Decimal("0.0")) is True
    
    def test_validate_funding_rate_with_custom_max(self):
        """Test that custom maximum rate threshold works."""
        # Custom max of 0.005 (0.5%)
        assert validate_funding_rate(Decimal("0.003"), max_rate=Decimal("0.005")) is True
        assert validate_funding_rate(Decimal("0.008"), max_rate=Decimal("0.005")) is False


class TestValidateSymbol:
    """Tests for validate_symbol function."""
    
    def test_validate_symbol_accepts_btcusdt(self):
        """Test that BTCUSDT is accepted by default."""
        assert validate_symbol('BTCUSDT') is True
    
    def test_validate_symbol_rejects_other_symbols(self):
        """Test that other symbols are rejected by default."""
        assert validate_symbol('ETHUSDT') is False
        assert validate_symbol('SOLUSDT') is False
    
    def test_validate_symbol_with_custom_list(self):
        """Test that custom symbol list works."""
        allowed = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        
        assert validate_symbol('BTCUSDT', allowed_symbols=allowed) is True
        assert validate_symbol('ETHUSDT', allowed_symbols=allowed) is True
        assert validate_symbol('DOGEUSDT', allowed_symbols=allowed) is False
    
    def test_validate_symbol_case_sensitive(self):
        """Test that symbol validation is case-sensitive."""
        assert validate_symbol('btcusdt') is False  # Wrong case
        assert validate_symbol('BTCUSDT') is True
