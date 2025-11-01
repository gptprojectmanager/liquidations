#!/usr/bin/env python3
"""Date-aware ingestion utilities."""

from calendar import monthrange


def get_last_day_of_month(year: int, month: int) -> int:
    """Get the last day of the month (28/29/30/31)."""
    return monthrange(year, month)[1]
