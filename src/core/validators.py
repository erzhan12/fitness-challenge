"""Validation helpers for core models and data."""

import re
import unicodedata
from typing import Iterable

from django.core.exceptions import ValidationError

try:
    from zoneinfo import available_timezones
except ImportError:
    from backports.zoneinfo import available_timezones


# Homoglyph table covering common Cyrillic/Greek lookalikes + a few
# leet-speak digit substitutions. Maps each char to its Latin equivalent
# so normalized text like "ign0re" or "игнорировать" collapses into the
# same bucket the suspicious-pattern check scans.
_HOMOGLYPH_MAP = str.maketrans(
    "аеорсухіјёАВЕНІКМОРСТХοеіа0134578",
    "aeopcyxijëABEHIKMOPCTXoeiaoieastb",
)

# Patterns that strongly suggest prompt-injection attempts. Hits here
# cause ``sanitize_llm_prompt`` to raise — we prefer false-positives on
# unusual phrasing over letting a jailbreak slip into the LLM context.
_INJECTION_PATTERNS = (
    "ignore previous", "ignore all", "ignore above",
    "disregard prior", "disregard previous",
    "forget everything", "forget above",
    "neglect above",
    "system:", "assistant:", "[inst]",
    "you are now",
)


def sanitize_llm_prompt(text: str) -> str:
    """Reject prompts that look like injection attempts; return the stripped text.

    Applied to any free-text the user ships off to the LLM (``/challenge``,
    ``/exception add``, the REST ``ChallengePromptRequest``). Normalizes
    Unicode homoglyphs and leet-speak so common evasions ("ign0re",
    "ігноре previous") collapse into the same suspicious-pattern check.

    Side-effect-free: the returned string is the caller-supplied text
    with leading/trailing whitespace removed. The normalization pipeline
    is only used for pattern detection — we never mangle what we hand
    to the LLM, so the parser still sees the user's literal wording.

    Raises:
        ValueError: If the text matches any entry in ``_INJECTION_PATTERNS``.
    """
    text = text.strip()
    decomposed = unicodedata.normalize("NFKD", text)
    transliterated = decomposed.translate(_HOMOGLYPH_MAP)
    # Strip non-Latin-alpha (removes digits, zero-width chars, symbols)
    # then collapse any resulting gaps so "ign0re" → "ignore" not "ign re"
    words = transliterated.split()
    cleaned_words = [re.sub(r"[^a-zA-Z:\[\]]", "", w).lower() for w in words]
    normalized = " ".join(w for w in cleaned_words if w)
    for pattern in _INJECTION_PATTERNS:
        if pattern in normalized:
            raise ValueError("Invalid input format")
    return text

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


def normalize_exception_weekdays(value) -> str:
    """Normalize an exception-weekdays input into canonical CSV form.

    Accepts:
        - An empty string / None / empty iterable → "".
        - A CSV string of ISO weekday ints (e.g. "6,7" → "6,7").
        - An iterable of ints (e.g. [7, 6, 6] → "6,7").

    Returns the canonical CSV: deduped, sorted ascending, no whitespace.

    Raises ValueError if any token is not an integer in 1..7 (ISO weekday).
    """
    if value is None or value == "":
        return ""

    if isinstance(value, str):
        tokens = [token.strip() for token in value.split(",")]
        # Reject empty tokens (catches "1,,2" and ",1")
        if any(token == "" for token in tokens):
            raise ValueError(
                f"Invalid exception_weekdays {value!r}: empty token in CSV"
            )
        try:
            ints = [int(token) for token in tokens]
        except ValueError as exc:
            raise ValueError(
                f"Invalid exception_weekdays {value!r}: non-integer token"
            ) from exc
    elif isinstance(value, Iterable):
        try:
            ints = [int(token) for token in value]
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid exception_weekdays {value!r}: non-integer entry"
            ) from exc
    else:
        raise ValueError(
            f"Invalid exception_weekdays {value!r}: expected str or iterable of ints"
        )

    for token in ints:
        if not (1 <= token <= 7):
            raise ValueError(
                f"Invalid exception_weekdays {value!r}: {token} is outside ISO range 1..7"
            )

    canonical = sorted(set(ints))
    return ",".join(str(i) for i in canonical)


def parse_exception_weekdays(value: str) -> set[int]:
    """Parse a stored canonical CSV back into a set of ISO weekday ints (1..7).

    Empty string returns an empty set. Mirrors ``normalize_exception_weekdays``.
    """
    if not value:
        return set()
    return {int(token) for token in value.split(",")}


def normalize_reminder_hours(value) -> list[int]:
    """Validate and normalize per-user reminder hours.

    Accepts a list of unique ints in 0..23. Returns sorted ascending with
    duplicates removed. Empty list is valid (opt-out). Raises ValidationError
    on invalid input.
    """
    if value is None:
        raise ValidationError("reminder_hours must be a list of integers 0-23")

    if not isinstance(value, list):
        raise ValidationError("reminder_hours must be a list of integers 0-23")

    if not value:
        return []

    normalized: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValidationError("reminder_hours must be a list of integers 0-23")
        if not (0 <= item <= 23):
            raise ValidationError("reminder_hours must be a list of integers 0-23")
        normalized.append(item)

    return sorted(set(normalized))


def validate_habit_id(habit_id: int) -> None:
    """Validate that habit_id is a valid positive integer.

    Args:
        habit_id: The habit ID to validate

    Raises:
        ValueError: If habit_id is not a positive integer within valid range
    """
    if habit_id <= 0:
        raise ValueError(
            f"Invalid habit ID: {habit_id}. Must be a positive integer."
        )
    if habit_id > 10**12:
        raise ValueError(
            f"Habit ID too large: {habit_id}. Must be at most 10^12."
        )
