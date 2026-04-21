"""Shared utility functions used by both API and Telegram layers."""

from datetime import date, timedelta
from typing import Iterable, Tuple


def calculate_expected_progress(
    daily_target: int, day_number: int, total_days: int
) -> float:
    """Calculate expected progress based on daily target and timeline.

    Args:
        daily_target: Daily target count
        day_number: Current day number in the challenge
        total_days: Total days in the challenge (must be > 0)

    Returns:
        Expected cumulative progress as a float
    """
    return daily_target * day_number


def calculate_status_and_deficit(
    cumulative: int,
    daily_target: int,
    day_number: int,
    total_days: int,
) -> Tuple[str, float]:
    """Calculate status and deficit in a single function.

    Returns:
        Tuple of (status, deficit) where deficit is positive when behind, negative when ahead
    """
    expected = calculate_expected_progress(daily_target, day_number, total_days)

    diff = cumulative - expected
    deficit = expected - cumulative  # positive when behind
    threshold = daily_target

    if diff > threshold:
        return "ahead", deficit
    elif diff < -threshold:
        return "behind", deficit
    else:
        return "on_track", deficit


def calculate_status(
    cumulative: int,
    daily_target: int,
    day_number: int,
    total_days: int,
) -> str:
    """Calculate status (backward compatibility wrapper)."""
    status, _ = calculate_status_and_deficit(
        cumulative, daily_target, day_number, total_days
    )
    return status


def expand_exception_dates(
    start: date,
    end: date,
    iso_weekdays: Iterable[int],
    explicit_dates: Iterable[date],
) -> set[date]:
    """Build the full set of exception dates for a challenge window.

    Walks ``[start, end]`` (inclusive on both ends) and includes any day
    whose ``isoweekday()`` is in ``iso_weekdays`` (1=Mon..7=Sun), then
    unions in any ``explicit_dates`` clamped to the window. Dates outside
    ``[start, end]`` are silently dropped.

    Returns an empty set when both inputs are empty or when ``start > end``.

    Reused by stats math, challenge creation, and the ``/exception`` parser.
    """
    if start > end:
        return set()

    weekday_set = {int(w) for w in iso_weekdays}
    result: set[date] = set()

    if weekday_set:
        cur = start
        while cur <= end:
            if cur.isoweekday() in weekday_set:
                result.add(cur)
            cur += timedelta(days=1)

    for d in explicit_dates:
        if start <= d <= end:
            result.add(d)

    return result


def ensure_date(value) -> date:
    """Normalize a value to a ``date`` object.

    Args:
        value: A ``datetime.date`` instance (returned as-is) or an
            ISO 8601 date string such as ``"2024-01-15"``.

    Returns:
        A ``datetime.date`` object.

    Raises:
        ValueError: If *value* is a string that cannot be parsed by
            ``date.fromisoformat()``.
        TypeError: If *value* is neither a ``date`` nor a ``str``.

    Example::

        >>> ensure_date("2024-01-15")
        datetime.date(2024, 1, 15)
        >>> ensure_date(date(2024, 1, 15))
        datetime.date(2024, 1, 15)
    """
    if isinstance(value, str):
        return date.fromisoformat(value)
    return value
