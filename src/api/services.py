"""API services layer for database operations.

This module provides reusable functions for CRUD operations on exercises,
challenges, logs, and stats. It shares business logic with the Telegram
bot while returning structured data instead of HTML.

Migrated to use Django ORM via repositories instead of direct Supabase calls.
"""

import logging
import math
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Optional, List, Dict, Any, Tuple

if TYPE_CHECKING:
    from src.core.models import ExerciseType as ExerciseTypeModel

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from app.config import settings
from src.core.utils import (
    calculate_expected_progress,
    calculate_status_and_deficit,
    expand_exception_dates,
)
from src.core.repositories import (
    exercise_type_repo,
    challenge_repo,
    challenge_exception_day_repo,
    log_repo,
    user_stats_repo,
    user_settings_repo,
)
from src.api.models import (
    ExerciseTypeOut,
    ExerciseTypeCreate,
    ExerciseTypeUpdate,
    ExerciseChallengeOut,
    ExerciseChallengeCreate,
    ExerciseChallengeUpdate,
    ChallengeExceptionDayOut,
    ChallengePromptParsed,
    ExerciseLogOut,
    ExerciseLogCreate,
    ExerciseStatsOut,
    UserStatsOut,
    StatsSummaryOut,
    PaginatedLogsResponse,
    PaginationMeta,
    SettingsOut,
    SettingsUpdate,
)
from app.models import ExerciseType as TelegramExerciseType
from app.services.openai_service import parse_challenge_prompt
from app.constants import MAX_DURATION_DAYS, MAX_DAILY_TARGET, MAX_START_DATE_DRIFT_DAYS

TZ = ZoneInfo(settings.TZ)
logger = logging.getLogger(__name__)

# Maximum allowed difference between LLM-provided daily_target and the computed
# ceil(target_total / duration_days).  Set to 1 because ceil() can introduce a
# ±1 rounding discrepancy (e.g. 901/30 = ceil 31, but LLM may return 30).
TARGET_CONSISTENCY_TOLERANCE = 1


# =============================================================================
# Helper functions for model conversion
# =============================================================================


def _model_to_dict(model) -> Dict[str, Any]:
    """Convert Django model instance to dict."""
    if model is None:
        return None

    data = {}
    # Use field.attname to correctly serialize FK/OneToOne fields as `*_id`
    # (e.g., `exercise_type_id`) instead of embedding related model instances.
    for field in model._meta.fields:
        value = getattr(model, field.attname)
        # Convert dates to ISO format strings for consistency
        if isinstance(value, date) and not isinstance(value, datetime):
            data[field.attname] = value.isoformat()
        elif isinstance(value, datetime):
            data[field.attname] = value.isoformat()
        else:
            data[field.attname] = value
    return data


# =============================================================================
# Exercise Types
# =============================================================================


async def list_exercise_types(
    user_id: int,
    is_active: Optional[bool] = True,
    challenge_only: bool = False,
) -> List[ExerciseTypeOut]:
    """List exercise types with optional filters.

    Args:
        is_active: Filter by active status (None = all)
        challenge_only: If True, only return types with active challenges
    """
    types = await exercise_type_repo.get_all(is_active=is_active, user_id=user_id)
    exercise_types = [ExerciseTypeOut(**_model_to_dict(t)) for t in types]

    if challenge_only:
        # Get exercise type IDs with active challenges
        challenges = await challenge_repo.get_all(
            filters={"is_active": True},
            user_id=user_id,
        )
        active_type_ids = {c.exercise_type_id for c in challenges}
        exercise_types = [et for et in exercise_types if et.id in active_type_ids]

    return exercise_types


async def get_exercise_type(
    exercise_type_id: int,
    user_id: int,
) -> Optional[ExerciseTypeOut]:
    """Get a single exercise type by ID."""
    etype = await exercise_type_repo.get_by_id(exercise_type_id, user_id=user_id)
    if etype:
        return ExerciseTypeOut(**_model_to_dict(etype))
    return None


async def create_exercise_type(
    data: ExerciseTypeCreate,
    user_id: int,
) -> ExerciseTypeOut:
    """Create a new exercise type."""
    insert_data = data.model_dump()
    insert_data["user_id"] = user_id
    created = await exercise_type_repo.create(insert_data)
    return ExerciseTypeOut(**_model_to_dict(created))


async def update_exercise_type(
    exercise_type_id: int,
    data: ExerciseTypeUpdate,
    user_id: int,
) -> Optional[ExerciseTypeOut]:
    """Update an exercise type."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_exercise_type(exercise_type_id, user_id)

    updated = await exercise_type_repo.update(
        exercise_type_id,
        update_data,
        user_id=user_id,
    )
    if updated:
        return ExerciseTypeOut(**_model_to_dict(updated))
    return None


# =============================================================================
# Challenges
# =============================================================================


def _parse_exception_weekdays_csv(value: Any) -> List[int]:
    """Parse the canonical CSV stored on ExerciseChallenge.exception_weekdays."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        return sorted({int(p) for p in parts})
    # Already a list/tuple
    return sorted({int(w) for w in value})


def _enrich_challenge(
    challenge_data: Dict[str, Any],
    today: date,
    exception_dates: Optional[set] = None,
) -> Dict[str, Any]:
    """Add computed fields to challenge data.

    When ``exception_dates`` is provided (caller already prefetched the
    one-off rows), it is unioned with any recurring weekday exceptions to
    produce ``effective_total_days``. When it is None, only weekday
    exceptions are considered — caller is responsible for hydrating the
    ``exception_dates`` field on the response if needed.
    """
    start = date.fromisoformat(challenge_data["start_date"]) if isinstance(challenge_data["start_date"], str) else challenge_data["start_date"]
    end = date.fromisoformat(challenge_data["end_date"]) if isinstance(challenge_data["end_date"], str) else challenge_data["end_date"]
    total_days = (end - start).days + 1
    if total_days <= 0:
        raise ValueError(f"Invalid date range: start={start}, end={end}, total_days={total_days}")
    challenge_data["total_days"] = total_days
    challenge_data["is_current"] = start <= today <= end

    # Exception-aware effective day count
    weekdays = _parse_exception_weekdays_csv(challenge_data.get("exception_weekdays", ""))
    challenge_data["exception_weekdays"] = weekdays
    explicit_dates = exception_dates or set()
    exception_set = expand_exception_dates(start, end, weekdays, explicit_dates)
    effective_total_days = max(0, total_days - len(exception_set))
    challenge_data["effective_total_days"] = effective_total_days

    # target_total reflects scheduled (non-exception) days only.
    challenge_data["target_total"] = challenge_data["daily_target"] * effective_total_days
    return challenge_data


async def list_challenges(
    user_id: int,
    exercise_type_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    starts_before: Optional[date] = None,
    ends_after: Optional[date] = None,
) -> List[ExerciseChallengeOut]:
    """List challenges with optional filters."""
    today = datetime.now(TZ).date()

    filters = {}
    if exercise_type_id is not None:
        filters["exercise_type_id"] = exercise_type_id
    if is_active is not None:
        filters["is_active"] = is_active

    challenges = await challenge_repo.get_all(
        filters=filters if filters else None,
        user_id=user_id,
    )

    # Apply date filters in Python (since repo doesn't support these yet)
    filtered_challenges = []
    for c in challenges:
        include = True
        if starts_before is not None and c.start_date > starts_before:
            include = False
        if ends_after is not None and c.end_date < ends_after:
            include = False
        if include:
            filtered_challenges.append(c)

    challenge_ids = [c.id for c in filtered_challenges]
    exception_map = await challenge_exception_day_repo.list_dates_for_challenges(
        challenge_ids,
        user_id=user_id,
    )
    result: List[ExerciseChallengeOut] = []
    for c in filtered_challenges:
        data = _model_to_dict(c)
        dates_set = exception_map.get(c.id, set())
        enriched = _enrich_challenge(data, today, exception_dates=dates_set)
        enriched["exception_dates"] = sorted(dates_set)
        result.append(ExerciseChallengeOut(**enriched))
    return result


async def deactivate_expired_challenges(
    target_date: Optional[date] = None,
    user_id: Optional[int] = None,
) -> int:
    """Deactivate challenges whose end_date is before the cutoff date.

    ``target_date`` *is* the cutoff: rows with ``end_date < reference_date``
    are cleared. Production call sites pass no date (uses real today in TZ).
    Only unit tests should pass an explicit ``target_date``.
    """
    reference_date = target_date or datetime.now(TZ).date()
    return await challenge_repo.deactivate_expired(
        reference_date, user_id=user_id
    )


async def list_current_active_challenges(
    target_date: Optional[date] = None,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """List active challenges valid for the target date (default: today).

    Note: expired-challenge hygiene is NOT run here. ``get_current_active``
    already filters by the date window (``start_date <= today <= end_date``),
    so expired rows are excluded from reads regardless of a stale
    ``is_active`` flag. Clearing the flag is admin-only hygiene handled by the
    evening reminder sweep (``send_evening_reminder``) — running a DB write on
    every workout parse/log would add latency to the hot read path for no
    functional benefit.
    """
    current_date = target_date or datetime.now(TZ).date()
    challenges = await challenge_repo.get_current_active(
        current_date,
        user_id=user_id,
    )
    return [_model_to_dict(c) for c in challenges]


def get_ordered_challenges(challenges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Order challenges for multi-number mapping:
    1. Default challenge (is_default=True, lowest ID)
    2. Remaining challenges (increasing ID)
    """
    if not challenges:
        return []

    defaults = [c for c in challenges if c.get("is_default")]
    non_defaults = [c for c in challenges if not c.get("is_default")]

    # Sort both groups by ID
    defaults.sort(key=lambda x: x["id"])
    non_defaults.sort(key=lambda x: x["id"])

    ordered = []
    remaining = []

    if defaults:
        ordered.append(defaults[0])
        remaining.extend(defaults[1:])
        remaining.extend(non_defaults)
    else:
        # No default, pick lowest ID as first
        # Combine all, sort by ID
        all_sorted = sorted(challenges, key=lambda x: x["id"])
        ordered.append(all_sorted[0])
        remaining.extend(all_sorted[1:])

    # Sort remaining by ID
    remaining.sort(key=lambda x: x["id"])
    ordered.extend(remaining)

    return ordered


async def get_challenge(
    challenge_id: int,
    user_id: int,
) -> Optional[ExerciseChallengeOut]:
    """Get a single challenge by ID."""
    today = datetime.now(TZ).date()
    challenge = await challenge_repo.get_by_id(challenge_id, user_id=user_id)
    if challenge is None:
        return None
    exception_rows = await challenge_exception_day_repo.list_for_challenge(
        challenge_id,
        user_id=user_id,
    )
    dates_set = {row.date for row in exception_rows}
    data = _enrich_challenge(_model_to_dict(challenge), today, exception_dates=dates_set)
    data["exception_dates"] = sorted(dates_set)
    return ExerciseChallengeOut(**data)


async def get_active_challenge_for_type(
    exercise_type_id: int,
    target_date: Optional[date] = None,
    user_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Get the active challenge for an exercise type on a given date.

    This mirrors the logic from workout_service.get_active_challenge.
    """
    current_date = target_date or datetime.now(TZ).date()

    # Try to find challenge that wraps the current date
    challenge = await challenge_repo.get_active_for_type(
        exercise_type_id,
        current_date,
        user_id=user_id,
    )
    if challenge:
        return _model_to_dict(challenge)

    return None


async def create_challenge(
    data: ExerciseChallengeCreate,
    user_id: int,
) -> ExerciseChallengeOut:
    """Create a new challenge."""
    today = datetime.now(TZ).date()

    if data.end_date < data.start_date:
        raise ValueError(f"end_date ({data.end_date}) must be >= start_date ({data.start_date})")

    insert_data = data.model_dump()
    insert_data["user_id"] = user_id

    # Convert weekday list -> CSV for ExerciseChallenge column;
    # peel off exception_dates so they don't reach the parent insert.
    exception_dates_payload: List[date] = list(insert_data.pop("exception_dates", []) or [])
    weekdays = insert_data.pop("exception_weekdays", []) or []
    insert_data["exception_weekdays"] = ",".join(str(w) for w in sorted(set(weekdays)))

    # Atomic insert: parent row + one-off exception days happen inside a
    # single transaction, so a failure on the child rows rolls back the
    # parent. ``create_with_exception_dates`` no-ops the bulk insert when
    # ``exception_dates_payload`` is empty.
    created = await challenge_repo.create_with_exception_dates(
        insert_data, exception_dates_payload
    )

    dates_set = set(exception_dates_payload)
    enriched = _enrich_challenge(_model_to_dict(created), today, exception_dates=dates_set)
    enriched["exception_dates"] = sorted(dates_set)
    return ExerciseChallengeOut(**enriched)


async def update_challenge(
    challenge_id: int,
    data: ExerciseChallengeUpdate,
    user_id: int,
) -> Optional[ExerciseChallengeOut]:
    """Update a challenge.

    ``exception_dates`` REPLACES the existing one-off rest dates (not merges).
    ``exception_weekdays`` REPLACES the recurring weekday set.
    """
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_challenge(challenge_id, user_id)

    # Peel off exception fields — they're handled outside challenge_repo.update
    has_dates_update = "exception_dates" in update_data
    new_exception_dates = update_data.pop("exception_dates", None) or []
    has_weekdays_update = "exception_weekdays" in update_data
    if has_weekdays_update:
        wd = update_data.pop("exception_weekdays", None) or []
        update_data["exception_weekdays"] = ",".join(str(w) for w in sorted(set(wd)))

    # Need existing for window math whenever date or exception_dates change
    existing = None
    if (
        "start_date" in update_data
        or "end_date" in update_data
        or has_dates_update
    ):
        existing = await challenge_repo.get_by_id(challenge_id, user_id=user_id)
        if existing is None:
            return None

    # Validate date range if dates are being updated
    if "start_date" in update_data or "end_date" in update_data:
        new_start = update_data.get("start_date", existing.start_date)
        new_end = update_data.get("end_date", existing.end_date)
        if new_end < new_start:
            raise ValueError(f"end_date ({new_end}) must be >= start_date ({new_start})")

    # Window-validate any new exception_dates against the (possibly updated) window
    if has_dates_update and new_exception_dates:
        eff_start = update_data.get("start_date", existing.start_date)
        eff_end = update_data.get("end_date", existing.end_date)
        for d in new_exception_dates:
            if not (eff_start <= d <= eff_end):
                raise ValueError(
                    f"exception_dates entry {d.isoformat()} is outside challenge window "
                    f"[{eff_start.isoformat()}, {eff_end.isoformat()}]"
                )

    # When the window changes WITHOUT an explicit exception_dates payload,
    # trim any existing one-off rest rows that now fall outside the new
    # window. Otherwise stale rows would survive past a PATCH and could
    # silently re-activate if the window is later expanded — and the
    # response model would also hand them back, contradicting the in-window
    # invariant. We skip this when ``has_dates_update`` is true because the
    # explicit body is the user's authoritative replacement set.
    window_changed = (
        ("start_date" in update_data or "end_date" in update_data)
        and not has_dates_update
    )
    if window_changed:
        eff_start = update_data.get("start_date", existing.start_date)
        eff_end = update_data.get("end_date", existing.end_date)
        existing_rows = await challenge_exception_day_repo.list_for_challenge(
            challenge_id, user_id=user_id
        )
        surviving = [
            row.date for row in existing_rows if eff_start <= row.date <= eff_end
        ]
        if len(surviving) != len(existing_rows):
            await challenge_exception_day_repo.replace_dates(
                challenge_id,
                surviving,
                user_id=user_id,
            )

    updated = None
    if update_data:
        updated = await challenge_repo.update(
            challenge_id,
            update_data,
            user_id=user_id,
        )
        if updated is None:
            return None

    if has_dates_update:
        await challenge_exception_day_repo.replace_dates(
            challenge_id,
            list(new_exception_dates),
            user_id=user_id,
        )

    # Build the response from `updated` (or `existing` when only exception_dates changed)
    # rather than re-fetching via get_challenge — keeps the response consistent with the
    # repo write that just happened and avoids an extra round-trip.
    challenge_model = updated or existing
    if challenge_model is None:
        # Neither path ran any read; need a fresh fetch to populate the response.
        challenge_model = await challenge_repo.get_by_id(challenge_id, user_id=user_id)
        if challenge_model is None:
            return None

    if has_dates_update:
        dates_set = set(new_exception_dates)
    else:
        rows = await challenge_exception_day_repo.list_for_challenge(
            challenge_id, user_id=user_id
        )
        dates_set = {row.date for row in rows}

    today = datetime.now(TZ).date()
    enriched = _enrich_challenge(
        _model_to_dict(challenge_model), today, exception_dates=dates_set
    )
    enriched["exception_dates"] = sorted(dates_set)
    return ExerciseChallengeOut(**enriched)


# =============================================================================
# Challenge Exception Days
# =============================================================================


def _exception_day_to_out(row, challenge_id: int) -> ChallengeExceptionDayOut:
    """Convert a ChallengeExceptionDay ORM row to its API representation."""
    return ChallengeExceptionDayOut(
        id=row.id,
        challenge_id=challenge_id,
        date=row.date,
        reason=row.reason or "",
        created_at=row.created_at,
    )


async def list_exception_days(
    challenge_id: int,
    user_id: int,
) -> List[ChallengeExceptionDayOut]:
    """List all one-off exception (rest) days for a challenge.

    Returns rows ordered by date. Enforces ownership via the parent challenge.
    """
    rows = await challenge_exception_day_repo.list_for_challenge(
        challenge_id,
        user_id=user_id,
    )
    return [_exception_day_to_out(r, challenge_id) for r in rows]


async def add_exception_day(
    challenge_id: int,
    exception_date: date,
    reason: str,
    user_id: int,
) -> ChallengeExceptionDayOut:
    """Idempotently add a one-off exception day.

    Verifies the date falls within the challenge window. Raises
    ``ValueError`` on out-of-window dates and ``ExerciseChallenge.DoesNotExist``
    when the parent challenge cannot be found / owned by ``user_id``.
    """
    challenge = await challenge_repo.get_by_id(challenge_id, user_id=user_id)
    if challenge is None:
        from src.core.models import ExerciseChallenge
        raise ExerciseChallenge.DoesNotExist
    if not (challenge.start_date <= exception_date <= challenge.end_date):
        raise ValueError(
            f"Exception date {exception_date.isoformat()} is outside challenge "
            f"window [{challenge.start_date.isoformat()}, {challenge.end_date.isoformat()}]"
        )
    row, _created = await challenge_exception_day_repo.add(
        challenge_id,
        exception_date,
        reason=reason or "",
        user_id=user_id,
    )
    return _exception_day_to_out(row, challenge_id)


async def remove_exception_day(
    challenge_id: int,
    exception_date: date,
    user_id: int,
) -> bool:
    """Delete a one-off exception day. Returns True if a row was removed."""
    return await challenge_exception_day_repo.remove(
        challenge_id,
        exception_date,
        user_id=user_id,
    )


async def replace_exception_dates(
    challenge_id: int,
    dates: List[date],
    user_id: int,
) -> List[ChallengeExceptionDayOut]:
    """Replace the full one-off exception-date set for a challenge.

    Validates each date is within the challenge window before replacing.
    """
    challenge = await challenge_repo.get_by_id(challenge_id, user_id=user_id)
    if challenge is None:
        from src.core.models import ExerciseChallenge
        raise ExerciseChallenge.DoesNotExist
    for d in dates:
        if not (challenge.start_date <= d <= challenge.end_date):
            raise ValueError(
                f"Exception date {d.isoformat()} is outside challenge window "
                f"[{challenge.start_date.isoformat()}, {challenge.end_date.isoformat()}]"
            )
    rows = await challenge_exception_day_repo.replace_dates(
        challenge_id,
        list(dates),
        user_id=user_id,
    )
    return [_exception_day_to_out(r, challenge_id) for r in rows]


async def set_exception_weekdays(
    challenge_id: int,
    weekdays: List[int],
    user_id: int,
) -> Optional[ExerciseChallengeOut]:
    """Replace the recurring exception-weekday set for a challenge."""
    csv = ",".join(str(w) for w in sorted(set(weekdays)))
    updated = await challenge_repo.update(
        challenge_id,
        {"exception_weekdays": csv},
        user_id=user_id,
    )
    if updated is None:
        return None
    return await get_challenge(challenge_id, user_id)


async def clear_exception_days(
    challenge_id: int,
    user_id: int,
) -> Optional[ExerciseChallengeOut]:
    """Clear ALL exception days (recurring + one-off) for a challenge."""
    challenge = await challenge_repo.get_by_id(challenge_id, user_id=user_id)
    if challenge is None:
        return None
    await challenge_exception_day_repo.replace_dates(
        challenge_id, [], user_id=user_id
    )
    await challenge_repo.update(
        challenge_id,
        {"exception_weekdays": ""},
        user_id=user_id,
    )
    return await get_challenge(challenge_id, user_id)


class ExerciseTypeNotFoundError(Exception):
    """Raised when an exercise type referenced by name cannot be found."""

    def __init__(self, exercise_type_name: str, available_names: List[str]):
        self.exercise_type_name = exercise_type_name
        self.available_names = available_names
        super().__init__(
            f"Exercise type '{exercise_type_name}' not found. "
            f"Available types: {', '.join(available_names)}"
        )


def _resolve_exercise_type(
    name: str, exercise_type_models: List["ExerciseTypeModel"],
) -> Optional["ExerciseTypeModel"]:
    """Look up exercise type by exact name, then by case-insensitive alias."""
    match = next(
        (et for et in exercise_type_models if et.name == name),
        None,
    )
    if match is not None:
        return match
    name_lower = name.lower()
    for et in exercise_type_models:
        all_names = [et.name] + (et.aliases or [])
        if any(n.lower() == name_lower for n in all_names):
            return et
    return None


def _compute_daily_target(
    target_total: Optional[int],
    daily_target: Optional[int],
    duration_days: int,
) -> int:
    """Derive daily_target from target_total/daily_target, validating consistency."""
    if duration_days < 1:
        raise ValueError("duration_days must be at least 1.")

    if target_total is None and daily_target is None:
        raise ValueError(
            "Please specify either a total target (e.g. '2000 reps total') "
            "or a daily target (e.g. '50 reps daily')."
        )

    if target_total is not None and daily_target is None:
        result = math.ceil(target_total / duration_days)
    elif daily_target is not None and target_total is None:
        result = daily_target
    else:
        expected_daily = math.ceil(target_total / duration_days)
        if abs(daily_target - expected_daily) > TARGET_CONSISTENCY_TOLERANCE:
            raise ValueError(
                f"Inconsistent targets: {target_total} total over {duration_days} days implies "
                f"~{expected_daily}/day, but '{daily_target}/day' was also specified. "
                "Please provide only one or ensure they match."
            )
        result = expected_daily

    if result < 1:
        raise ValueError("daily_target must be at least 1.")
    return result


def _validate_challenge_dates(start_date: date, today: date) -> None:
    """Validate that start_date is not unreasonably far in the past or future."""
    if start_date < today - timedelta(days=MAX_START_DATE_DRIFT_DAYS):
        raise ValueError(
            f"start_date ({start_date}) is more than a year in the past. "
            "Did you mean a future date?"
        )
    if start_date > today + timedelta(days=MAX_START_DATE_DRIFT_DAYS):
        raise ValueError(
            f"start_date ({start_date}) is more than a year in the future. "
            "Did you mean a closer date?"
        )


async def _fetch_and_convert_exercise_types(
    user_id: int,
) -> Tuple[List["ExerciseTypeModel"], List[TelegramExerciseType]]:
    """Fetch user's exercise types and convert to LLM-compatible format."""
    exercise_type_models = await exercise_type_repo.get_all(user_id=user_id)
    exercise_types_for_llm = [
        TelegramExerciseType(
            id=et.id,
            name=et.name,
            display_name=et.display_name,
            emoji=et.emoji,
            unit=et.unit,
            aliases=et.aliases or [],
        )
        for et in exercise_type_models
    ]
    return exercise_type_models, exercise_types_for_llm


def _parse_and_validate_llm_response(
    raw_parsed: Dict[str, Any], text: str,
) -> ChallengePromptParsed:
    """Parse raw LLM output through Pydantic and validate required fields + bounds."""
    try:
        parsed = ChallengePromptParsed(**raw_parsed)
    except Exception:
        logger.warning("LLM returned unparseable data for prompt: %s | raw: %s", text, raw_parsed, exc_info=True)
        raise ValueError(
            "Could not understand your challenge description. "
            "Please include exercise type, duration, and daily target."
        )

    if not parsed.is_valid:
        raise ValueError(parsed.error_reason or "Could not parse challenge description.")

    if not parsed.exercise_type_name:
        raise ValueError("LLM did not return an exercise type name.")
    if not parsed.start_date:
        raise ValueError("LLM did not return a start date.")
    if not parsed.duration_days or parsed.duration_days < 1:
        raise ValueError("LLM did not return a valid duration (must be >= 1 day).")
    if not parsed.challenge_name:
        raise ValueError("LLM did not return a challenge name.")

    # Upper-bound sanity check on duration. The MAX_DAILY_TARGET cap is
    # enforced in _build_challenge_data() against the *effective* daily target,
    # because a target_total over a window with exception days can pass a
    # naive precheck (target_total / calendar_days) and still produce an
    # over-cap daily_target after exceptions shrink the schedule.
    if parsed.duration_days > MAX_DURATION_DAYS:
        raise ValueError(f"Duration too long ({parsed.duration_days} days). Maximum is {MAX_DURATION_DAYS} days.")

    return parsed


def _build_challenge_data(
    parsed: ChallengePromptParsed,
    exercise_type_models: List["ExerciseTypeModel"],
    today: date,
) -> ExerciseChallengeCreate:
    """Resolve exercise type, validate dates, compute targets, and build creation data.

    Honours exception days extracted by the LLM:
      * ``exception_weekdays`` and ``exception_dates`` are normalized and
        passed through to ``ExerciseChallengeCreate`` (which validates them
        a second time inside Pydantic).
      * When the LLM returns ``target_total`` (and not an explicit
        ``daily_target``), the daily target is divided by **effective** days
        — i.e. "1000 reps over weekdays in January" distributes across
        weekdays only.
      * An all-exception window with no explicit ``daily_target`` is rejected
        with a clear error.
    """
    start_date = parsed.start_date
    duration_days = parsed.duration_days
    end_date = start_date + timedelta(days=duration_days - 1)

    _validate_challenge_dates(start_date, today)

    exercise_type = _resolve_exercise_type(parsed.exercise_type_name, exercise_type_models)
    if exercise_type is None:
        available_names = [et.name for et in exercise_type_models]
        raise ExerciseTypeNotFoundError(parsed.exercise_type_name, available_names)

    # Normalize exception fields from the LLM. Reject (don't silently drop)
    # any explicit date the LLM returned that falls outside the resolved
    # challenge window — otherwise "April challenge except May 1" would
    # create a successful challenge missing the rest day the user asked for.
    weekdays = sorted(set(parsed.exception_weekdays or []))
    raw_dates = sorted(set(parsed.exception_dates or []))
    out_of_window = [d for d in raw_dates if not (start_date <= d <= end_date)]
    if out_of_window:
        raise ValueError(
            f"Exception dates outside challenge window "
            f"[{start_date.isoformat()}, {end_date.isoformat()}]: "
            f"{[d.isoformat() for d in out_of_window]}."
        )
    explicit_dates = raw_dates
    exception_set = expand_exception_dates(
        start_date, end_date, weekdays, explicit_dates
    )
    effective_days = max(0, duration_days - len(exception_set))

    # Use effective days for derived targets so a "1000 reps over weekdays"
    # prompt distributes across the weekdays only.
    if parsed.daily_target is not None:
        daily_target = _compute_daily_target(
            parsed.target_total, parsed.daily_target, duration_days
        )
    else:
        if effective_days < 1:
            raise ValueError(
                "Cannot derive a daily target — every day in the requested "
                "window is an exception day. Specify a daily target explicitly."
            )
        daily_target = _compute_daily_target(
            parsed.target_total, parsed.daily_target, effective_days
        )

    # Cap check happens here (not in _parse_and_validate_llm_response) so it
    # sees the *effective* daily_target — i.e. the value after exception days
    # have shrunk the schedule. This closes the bypass where target_total
    # divided by calendar days passes the cap but divided by effective days
    # would exceed it.
    if daily_target > MAX_DAILY_TARGET:
        raise ValueError(
            f"Daily target too high ({daily_target}). "
            f"Maximum is {MAX_DAILY_TARGET} per day."
        )

    return ExerciseChallengeCreate(
        exercise_type_id=exercise_type.id,
        start_date=start_date,
        end_date=end_date,
        daily_target=daily_target,
        challenge_name=parsed.challenge_name,
        is_active=True,
        is_default=False,
        exception_weekdays=weekdays,
        exception_dates=explicit_dates,
    )


async def validate_and_prepare_challenge(
    text: str,
    user_id: int,
) -> Tuple[ChallengePromptParsed, ExerciseChallengeCreate]:
    """Parse and validate a natural language challenge description without creating it.

    Returns:
        Tuple of (parsed LLM data, ready-to-create challenge data).

    Raises:
        ValueError: If LLM parsing fails or extracted data is invalid.
        ExerciseTypeNotFoundError: If the exercise type name is not found for this user.
    """
    today = datetime.now(TZ).date()
    exercise_type_models, exercise_types_for_llm = await _fetch_and_convert_exercise_types(user_id)
    raw_parsed = await parse_challenge_prompt(text, exercise_types_for_llm, today)
    parsed = _parse_and_validate_llm_response(raw_parsed, text)
    challenge_data = _build_challenge_data(parsed, exercise_type_models, today)
    return parsed, challenge_data


async def create_challenge_from_prompt(
    text: str,
    user_id: int,
) -> ExerciseChallengeOut:
    """
    Parse a natural language challenge description and create the challenge.

    Raises:
        ValueError: If LLM parsing fails or extracted data is invalid.
        ExerciseTypeNotFoundError: If the exercise type name is not found for this user.
    """
    _, challenge_data = await validate_and_prepare_challenge(text, user_id)
    return await create_challenge(challenge_data, user_id=user_id)


# =============================================================================
# Stats Computation (shared logic)
# =============================================================================



# calculate_expected_progress, calculate_status_and_deficit
# are imported from src.core.utils


async def compute_exercise_stats(
    exercise_type_id: int,
    target_date: Optional[date] = None,
    added_count: int = 0,
    etype: Optional[Dict[str, Any]] = None,
    challenge: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
) -> ExerciseStatsOut:
    """Compute stats for an exercise type within its challenge context.

    This is the core stats computation extracted from workout_service,
    returning structured data instead of HTML.

    Exception (rest) days are honored:
      * ``effective_total_days`` = calendar days minus exceptions in window
      * ``effective_day_number`` skips exception days; on a rest day it is
        frozen at the count of scheduled days strictly before today
      * ``target_total`` = ``daily_target × effective_total_days`` (can be 0)
      * ``cumulative_total`` is unchanged — logs on rest days still bank
      * ``is_today_exception`` flags the rest day so the daily ring is hidden

    Args:
        exercise_type_id: The exercise type to compute stats for
        target_date: Date context (defaults to today)
        added_count: Optional count to add (for preview before insertion)
        etype: Optional pre-fetched exercise type data (to avoid duplicate queries)
        challenge: Optional pre-fetched challenge data. May contain a
            ``_exception_dates`` set populated by bulk callers — when present,
            no per-call DB lookup is performed.
    """
    today_local = target_date or datetime.now(TZ).date()

    # Get exercise type (only if not provided)
    if etype is None:
        etype_model = await exercise_type_repo.get_by_id(
            exercise_type_id,
            user_id=user_id,
        )
        if not etype_model:
            raise ValueError(f"Exercise type {exercise_type_id} not found")
        etype = _model_to_dict(etype_model)

    # Get challenge (only if not provided)
    if challenge is None:
        challenge = await get_active_challenge_for_type(
            exercise_type_id,
            user_id=user_id,
            target_date=today_local,
        )

    # Default values (no challenge context)
    challenge_id = None
    challenge_name = None
    day_number = 1
    total_days = 30
    effective_total_days = 30
    daily_target = 33
    is_today_exception = False

    if challenge:
        challenge_id = challenge["id"]
        challenge_name = challenge.get("challenge_name")
        start_date = date.fromisoformat(challenge["start_date"]) if isinstance(challenge["start_date"], str) else challenge["start_date"]
        end_date = date.fromisoformat(challenge["end_date"]) if isinstance(challenge["end_date"], str) else challenge["end_date"]
        total_days = (end_date - start_date).days + 1
        daily_target = challenge["daily_target"]

        # Resolve exception set: prefer caller-supplied (bulk N+1 avoidance),
        # otherwise read from the repo.
        weekdays = _parse_exception_weekdays_csv(challenge.get("exception_weekdays", ""))
        if "_exception_dates" in challenge:
            explicit_dates = challenge["_exception_dates"] or set()
        else:
            rows = await challenge_exception_day_repo.list_for_challenge(
                challenge_id,
                user_id=user_id,
            )
            explicit_dates = {row.date for row in rows}
        exception_set = expand_exception_dates(
            start_date, end_date, weekdays, explicit_dates
        )

        # Effective totals (allow 0)
        effective_total_days = max(0, total_days - len(exception_set))

        # Effective day_number: count non-exception days in [start, min(today, end)].
        # If today is itself an exception, freeze at the count strictly before today.
        clamped_today = min(today_local, end_date)
        if clamped_today < start_date:
            day_number = 0
        else:
            cutoff = clamped_today
            if today_local in exception_set:
                cutoff = today_local - timedelta(days=1)
            if cutoff < start_date:
                day_number = 0
            else:
                span_days = (cutoff - start_date).days + 1
                if not weekdays and not explicit_dates:
                    day_number = span_days
                else:
                    skipped = sum(
                        1 for d in exception_set if start_date <= d <= cutoff
                    )
                    day_number = max(0, span_days - skipped)

        is_today_exception = today_local in exception_set

    # target_total reflects scheduled (non-exception) days only.
    target_total = daily_target * effective_total_days

    # Query cumulative total — logs on rest days still count.
    current_total = await log_repo.get_cumulative_count(
        exercise_type_id,
        challenge_id,
        today_local,
        user_id=user_id,
    )
    new_cumulative = current_total + added_count

    # Status and deficit are computed against effective_total_days so the
    # math collapses to "no work expected" on an all-exception window.
    status, deficit = calculate_status_and_deficit(
        new_cumulative,
        daily_target,
        day_number,
        max(1, effective_total_days),
    )

    # Catch-up calculation - show for any positive deficit
    catch_up_reps = 0
    if deficit > 0 and not is_today_exception:
        catch_up_reps = math.ceil(deficit)

    # Today's total
    current_today_total = await log_repo.get_today_count(
        exercise_type_id,
        today_local,
        challenge_id,
        user_id=user_id,
    )
    new_today_total = current_today_total + added_count

    # Progress percentage
    progress_percent = (
        min(100.0, (new_cumulative / target_total) * 100) if target_total > 0 else 0
    )

    # Determine if on track with cumulative progress (not just today's target).
    # On a rest day, "daily complete" is implicitly true — there is no daily
    # ring to fail.
    if is_today_exception:
        daily_complete = True
    else:
        expected = calculate_expected_progress(
            daily_target, day_number, max(1, effective_total_days)
        )
        daily_complete = new_cumulative >= expected

    return ExerciseStatsOut(
        exercise_type_id=exercise_type_id,
        exercise_type_name=etype["display_name"],
        exercise_type_emoji=etype["emoji"],
        challenge_id=challenge_id,
        challenge_name=challenge_name,
        day_number=day_number,
        total_days=effective_total_days,
        target_total=target_total,
        daily_target=daily_target,
        today_total=new_today_total,
        cumulative_total=new_cumulative,
        progress_percent=round(progress_percent, 1),
        status=status,
        catch_up_reps=catch_up_reps,
        is_daily_complete=daily_complete,
        is_today_exception=is_today_exception,
    )


async def get_all_exercise_stats(
    user_id: int,
    target_date: Optional[date] = None,
    challenge_only: bool = True,
) -> List[ExerciseStatsOut]:
    """Get stats for all exercises (optionally limited to those with challenges).

    Bulk-prefetches exception dates for all matched challenges to avoid an
    N+1 lookup inside ``compute_exercise_stats``.
    """
    today_local = target_date or datetime.now(TZ).date()

    exercise_types = await list_exercise_types(
        user_id=user_id,
        is_active=True,
        challenge_only=challenge_only,
    )

    # Resolve the active challenge for each exercise type up front so we can
    # bulk-prefetch their exception dates.
    type_to_challenge: Dict[int, Optional[Dict[str, Any]]] = {}
    for et in exercise_types:
        type_to_challenge[et.id] = await get_active_challenge_for_type(
            et.id,
            user_id=user_id,
            target_date=today_local,
        )
    challenge_ids = [
        c["id"] for c in type_to_challenge.values() if c is not None
    ]
    exception_map = await challenge_exception_day_repo.list_dates_for_challenges(
        challenge_ids,
        user_id=user_id,
    )

    stats = []
    for et in exercise_types:
        challenge = type_to_challenge.get(et.id)
        if challenge is not None:
            challenge = dict(challenge)
            challenge["_exception_dates"] = exception_map.get(challenge["id"], set())
        stat = await compute_exercise_stats(
            et.id,
            user_id=user_id,
            target_date=target_date,
            challenge=challenge,
        )
        stats.append(stat)
    return stats


# =============================================================================
# Exercise Logs
# =============================================================================


async def list_logs(
    user_id: int,
    exercise_type_id: Optional[int] = None,
    challenge_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedLogsResponse:
    """List log entries with pagination and filters."""
    filters = {}
    if exercise_type_id is not None:
        filters["exercise_type_id"] = exercise_type_id
    if challenge_id is not None:
        filters["challenge_id"] = challenge_id
    if date_from is not None:
        filters["date_from"] = date_from
    if date_to is not None:
        filters["date_to"] = date_to

    logs_models, total = await log_repo.get_all(
        filters=filters if filters else None,
        limit=limit,
        offset=offset,
        user_id=user_id,
    )

    # Transform data
    logs = []
    for log_model in logs_models:
        log_dict = _model_to_dict(log_model)
        log = ExerciseLogOut(**log_dict)
        # Add exercise type relation
        if log_model.exercise_type:
            log.exercise_type = ExerciseTypeOut(**_model_to_dict(log_model.exercise_type))
        logs.append(log)

    return PaginatedLogsResponse(
        data=logs,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(logs)) < total,
        ),
    )


async def get_log(log_id: int, user_id: int) -> Optional[ExerciseLogOut]:
    """Get a single log entry by ID."""
    log_model = await log_repo.get_by_id(log_id, user_id=user_id)
    if log_model:
        log = ExerciseLogOut(**_model_to_dict(log_model))
        if log_model.exercise_type:
            log.exercise_type = ExerciseTypeOut(**_model_to_dict(log_model.exercise_type))
        return log
    return None


async def create_log(
    data: ExerciseLogCreate,
    user_id: int,
) -> Tuple[ExerciseLogOut, ExerciseStatsOut]:
    """Create a new log entry and update stats.

    Returns:
        Tuple of (created_log, updated_stats)
    """
    today_local = datetime.now(TZ).date()
    log_date = data.date or today_local

    # Get exercise type
    etype = await get_exercise_type(data.exercise_type_id, user_id)
    if not etype:
        raise ValueError(f"Exercise type {data.exercise_type_id} not found")

    # Get challenge
    challenge = await get_active_challenge_for_type(
        data.exercise_type_id,
        user_id=user_id,
        target_date=log_date,
    )

    # Compute stats before insertion to get cumulative values
    stats = await compute_exercise_stats(
        data.exercise_type_id,
        user_id=user_id,
        target_date=log_date,
        added_count=data.count,
    )

    # Build log data
    challenge_id = None
    if challenge and isinstance(challenge, dict):
        challenge_id = challenge.get("id")

    # Generate default raw_message if not provided (for API-created logs)
    raw_message = data.raw_message
    if raw_message is None:
        raw_message = f"{data.count} {etype.name}"
        if data.notes:
            raw_message += f" - {data.notes}"

    log_data = {
        "user_id": user_id,
        "exercise_type_id": data.exercise_type_id,
        "challenge_id": challenge_id,
        "date": log_date,
        "timestamp": datetime.now(TZ),
        "count": data.count,
        "cumulative_total": stats.cumulative_total,
        "day_number": stats.day_number,
        "status": stats.status,
        "raw_message": raw_message,
        "duration_seconds": data.duration_seconds,
        "notes": data.notes,
    }

    # Insert log
    created_log_model = await log_repo.create(log_data)
    created_log = ExerciseLogOut(**_model_to_dict(created_log_model))

    # Update user_stats
    await user_stats_repo.increment_total(
        data.exercise_type_id,
        data.count,
        log_date,
        user_id=user_id,
    )

    return created_log, stats


async def delete_log(
    log_id: int,
    user_id: int,
) -> Tuple[Optional[ExerciseLogOut], Optional[ExerciseStatsOut]]:
    """Delete a log entry and update stats.

    Returns:
        Tuple of (deleted_log, updated_stats) or (None, None) if not found
    """
    # Get the log entry first
    log = await get_log(log_id, user_id)
    if not log:
        return None, None

    exercise_type_id = log.exercise_type_id
    count_to_remove = log.count

    # Delete the log
    await log_repo.delete(log_id, user_id=user_id)

    # Update user_stats
    await user_stats_repo.decrement_total(
        exercise_type_id,
        count_to_remove,
        user_id=user_id,
    )
    await user_stats_repo.sync_last_logged_date(
        exercise_type_id,
        user_id=user_id,
    )

    # Compute updated stats
    stats = await compute_exercise_stats(exercise_type_id, user_id=user_id)

    return log, stats


# =============================================================================
# User Stats
# =============================================================================


async def list_user_stats(user_id: int) -> List[UserStatsOut]:
    """List all user stats."""
    stats_models = await user_stats_repo.get_all(user_id=user_id)

    stats = []
    for stat_model in stats_models:
        stat_dict = _model_to_dict(stat_model)
        stat = UserStatsOut(**stat_dict)
        if stat_model.exercise_type:
            stat.exercise_type = ExerciseTypeOut(**_model_to_dict(stat_model.exercise_type))
        stats.append(stat)

    return stats


async def get_stats_summary(user_id: int) -> StatsSummaryOut:
    """Get overall stats summary."""
    # Get all user stats
    user_stats = await list_user_stats(user_id)

    # Calculate totals
    total_reps = sum(s.all_time_total for s in user_stats)

    # Count distinct days with activity
    # Note: This is a simplified version - could be optimized with a raw query
    all_logs, _ = await log_repo.get_all(
        limit=10000,
        user_id=user_id,
    )  # Get all logs
    distinct_days = len(set(log.date for log in all_logs))

    return StatsSummaryOut(
        total_reps_all_time=total_reps,
        total_active_days=distinct_days,
        exercise_stats=user_stats,
    )


# =============================================================================
# Settings
# =============================================================================


async def get_settings(user_id: int) -> SettingsOut:
    """Get current user settings.

    Returns:
        Current user settings
    """
    settings_model = await user_settings_repo.get_or_create(user_id)
    return SettingsOut(
        is_reminder_active=settings_model.is_reminder_active,
        is_workout_motivation_active=settings_model.is_workout_motivation_active,
        telegram_chat_id=settings_model.telegram_chat_id,
    )


async def update_settings(update: SettingsUpdate, user_id: int) -> SettingsOut:
    """Update current user settings.

    Args:
        update: Settings fields to update

    Returns:
        Updated settings
    """
    update_data = {}
    if update.is_reminder_active is not None:
        update_data["is_reminder_active"] = update.is_reminder_active
    if update.is_workout_motivation_active is not None:
        update_data["is_workout_motivation_active"] = (
            update.is_workout_motivation_active
        )

    settings_model = await user_settings_repo.get_or_create(user_id)

    if update_data:
        updated = await user_settings_repo.update(user_id, update_data)
        if updated:
            settings_model = updated

    return SettingsOut(
        is_reminder_active=settings_model.is_reminder_active,
        is_workout_motivation_active=settings_model.is_workout_motivation_active,
        telegram_chat_id=settings_model.telegram_chat_id,
    )
