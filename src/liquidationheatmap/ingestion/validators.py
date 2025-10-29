"""Data validation utilities for ingested data."""

from decimal import Decimal
from typing import List

import pandas as pd


# Price validation constants
MIN_PRICE = Decimal("10000.00")  # $10,000 minimum
MAX_PRICE = Decimal("500000.00")  # $500,000 maximum (future-proof)


def validate_price(price: Decimal) -> bool:
    """Validate that price is within reasonable range for BTC/USDT.
    
    Args:
        price: Price in USDT
    
    Returns:
        True if price is valid, False otherwise
    
    Examples:
        >>> validate_price(Decimal("67000.00"))
        True
        >>> validate_price(Decimal("5000.00"))  # Too low
        False
        >>> validate_price(Decimal("600000.00"))  # Too high
        False
    """
    try:
        price = Decimal(str(price))
        return MIN_PRICE <= price <= MAX_PRICE
    except (ValueError, TypeError, ArithmeticError):
        return False


def validate_date_range(df: pd.DataFrame, expected_days: int, tolerance: int = 1) -> bool:
    """Validate that DataFrame covers expected date range without gaps.
    
    Args:
        df: DataFrame with 'timestamp' column (datetime)
        expected_days: Expected number of days of data
        tolerance: Acceptable missing days (default: 1)
    
    Returns:
        True if date range is valid, False if too many gaps
    
    Examples:
        >>> df = pd.DataFrame({
        ...     'timestamp': pd.date_range('2024-10-22', periods=7, freq='D')
        ... })
        >>> validate_date_range(df, expected_days=7)
        True
        >>> validate_date_range(df, expected_days=10)  # Missing 3 days
        False
    """
    if df.empty or 'timestamp' not in df.columns:
        return False
    
    # Get unique dates
    dates = pd.to_datetime(df['timestamp']).dt.date
    unique_dates = dates.unique()
    
    # Calculate actual days covered
    actual_days = len(unique_dates)
    
    # Check if within tolerance
    missing_days = abs(expected_days - actual_days)
    return missing_days <= tolerance


def detect_outliers(df: pd.DataFrame, column: str, std_threshold: float = 3.0) -> List[int]:
    """Detect outliers in DataFrame column using Z-score method.
    
    Outliers are defined as values more than `std_threshold` standard deviations
    from the mean.
    
    Args:
        df: DataFrame to analyze
        column: Column name to check for outliers
        std_threshold: Number of standard deviations for outlier detection (default: 3.0)
    
    Returns:
        List of DataFrame row indexes that are outliers
    
    Examples:
        >>> df = pd.DataFrame({'value': [10, 12, 11, 10, 100, 9]})
        >>> detect_outliers(df, 'value')
        [4]  # Index of value 100
    """
    if df.empty or column not in df.columns:
        return []
    
    # Get numeric column
    series = pd.to_numeric(df[column], errors='coerce')
    
    # Drop NaN values for calculation
    valid_series = series.dropna()
    
    if valid_series.empty or len(valid_series) < 2:
        return []
    
    # Calculate Z-scores
    mean = valid_series.mean()
    std = valid_series.std()
    
    if std == 0:
        return []  # No variation, no outliers
    
    z_scores = (series - mean) / std
    
    # Find outliers
    outlier_mask = z_scores.abs() > std_threshold
    outlier_indices = df[outlier_mask].index.tolist()
    
    return outlier_indices


def validate_volume(volume: Decimal, min_volume: Decimal = Decimal("0.0")) -> bool:
    """Validate that volume is non-negative.
    
    Args:
        volume: Volume in USDT or contracts
        min_volume: Minimum acceptable volume (default: 0.0)
    
    Returns:
        True if volume is valid, False otherwise
    
    Examples:
        >>> validate_volume(Decimal("1234567.89"))
        True
        >>> validate_volume(Decimal("-100.00"))
        False
    """
    try:
        volume = Decimal(str(volume))
        return volume >= min_volume
    except (ValueError, TypeError, ArithmeticError):
        return False


def validate_funding_rate(rate: Decimal, max_rate: Decimal = Decimal("0.01")) -> bool:
    """Validate that funding rate is within reasonable bounds.
    
    Normal funding rates are between -0.01 and +0.01 (±1%).
    
    Args:
        rate: Funding rate (e.g., 0.0001 = 0.01%)
        max_rate: Maximum absolute funding rate (default: 0.01)
    
    Returns:
        True if funding rate is valid, False otherwise
    
    Examples:
        >>> validate_funding_rate(Decimal("0.0001"))
        True
        >>> validate_funding_rate(Decimal("0.05"))  # Too high (5%)
        False
    """
    try:
        rate = Decimal(str(rate))
        return abs(rate) <= max_rate
    except (ValueError, TypeError, ArithmeticError):
        return False


def validate_symbol(symbol: str, allowed_symbols: List[str] = None) -> bool:
    """Validate that trading symbol is supported.
    
    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        allowed_symbols: List of allowed symbols (default: ['BTCUSDT'])
    
    Returns:
        True if symbol is valid, False otherwise
    
    Examples:
        >>> validate_symbol('BTCUSDT')
        True
        >>> validate_symbol('ETHUSDT', allowed_symbols=['BTCUSDT'])
        False
    """
    if allowed_symbols is None:
        allowed_symbols = ['BTCUSDT']  # MVP only supports BTC/USDT
    
    return symbol in allowed_symbols
