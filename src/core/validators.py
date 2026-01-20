"""Validation helpers for core models and data."""

from django.core.exceptions import ValidationError

try:
    from zoneinfo import available_timezones
except ImportError:
    from backports.zoneinfo import available_timezones

_AVAILABLE_TIMEZONES = None


def _get_available_timezones() -> set[str]:
    """Cache available timezones to avoid repeated lookups."""
    global _AVAILABLE_TIMEZONES
    if _AVAILABLE_TIMEZONES is None:
        _AVAILABLE_TIMEZONES = available_timezones()
    return _AVAILABLE_TIMEZONES


def validate_telegram_chat_id(chat_id: int) -> None:
    """Validate that chat_id is within valid Telegram chat ID range.

    Telegram chat IDs can be:
    - User IDs: positive integers
    - Group IDs: negative integers (for groups created before supergroups)
    - Supergroup/channel IDs: large negative integers (starting with -100)

    All valid Telegram chat IDs fall within the range -10^15 to 10^15.

    Args:
        chat_id: The chat ID to validate

    Raises:
        ValueError: If chat_id is outside valid range
    """
    if not (-10**15 <= chat_id <= 10**15):
        raise ValueError(
            f"Invalid chat_id: {chat_id}. "
            "Telegram chat IDs must be in range -10^15 to 10^15."
        )


def validate_telegram_user_id(user_id: int) -> None:
    """Validate that user_id is a valid Telegram user ID.

    Telegram user IDs are positive integers. The theoretical maximum
    based on Telegram's architecture is around 10^12.

    Args:
        user_id: The Telegram user ID to validate

    Raises:
        ValueError: If user_id is outside valid range
    """
    if not (0 < user_id <= 10**12):
        raise ValueError(
            f"Invalid Telegram user ID: {user_id}. "
            "Must be a positive integer up to 10^12."
        )


def validate_timezone(value: str) -> None:
    """Validate that timezone is a known IANA timezone name."""
    if value not in _get_available_timezones():
        raise ValueError(
            f"Invalid timezone: {value}. Must be a valid IANA timezone name."
        )


def validate_timezone_field(value: str) -> None:
    """Django model validator wrapper for timezone values."""
    try:
        validate_timezone(value)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
