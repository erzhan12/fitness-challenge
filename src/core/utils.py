"""Shared utility functions used by both API and Telegram layers."""

from datetime import date
from typing import Optional, Tuple


def calculate_expected_progress(
    target_total: int, day_number: int, total_days: int, daily_target: Optional[int]
) -> float:
    """Calculate expected progress based on target and timeline.

    Args:
        target_total: Total target for the challenge
        day_number: Current day number in the challenge
        total_days: Total days in the challenge (must be > 0)
        daily_target: Daily target (if set), or None

    Returns:
        Expected cumulative progress as a float
    """
    if daily_target:
        return daily_target * day_number
    if total_days <= 0:
        return 0.0
    return (target_total / total_days) * day_number


def calculate_status_and_deficit(
    cumulative: int,
    target_total: int,
    day_number: int,
    total_days: int,
    daily_target: Optional[int],
) -> Tuple[str, float]:
    """Calculate status and deficit in a single function.

    Returns:
        Tuple of (status, deficit) where deficit is positive when behind, negative when ahead
    """
    expected = calculate_expected_progress(
        target_total, day_number, total_days, daily_target
    )

    diff = cumulative - expected
    deficit = expected - cumulative  # positive when behind
    threshold = daily_target or (target_total / total_days if total_days > 0 else 1)

    if diff > threshold:
        return "ahead", deficit
    elif diff < -threshold:
        return "behind", deficit
    else:
        return "on_track", deficit


def calculate_status(
    cumulative: int,
    target_total: int,
    day_number: int,
    total_days: int,
    daily_target: Optional[int],
) -> str:
    """Calculate status (backward compatibility wrapper)."""
    status, _ = calculate_status_and_deficit(
        cumulative, target_total, day_number, total_days, daily_target
    )
    return status


def ensure_date(value) -> date:
    """Normalize a value to a date object.

    Handles both date objects and ISO format strings.
    """
    if isinstance(value, str):
        return date.fromisoformat(value)
    return value
