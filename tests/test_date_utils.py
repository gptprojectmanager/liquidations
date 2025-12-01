"""Tests for date utility functions."""


def test_get_last_day_of_month_returns_31_for_january():
    """January has 31 days."""
    from scripts.ingest_date_range import get_last_day_of_month

    assert get_last_day_of_month(2024, 1) == 31


def test_get_last_day_of_month_returns_28_for_february_non_leap_year():
    """February has 28 days in non-leap years."""
    from scripts.ingest_date_range import get_last_day_of_month

    assert get_last_day_of_month(2023, 2) == 28
