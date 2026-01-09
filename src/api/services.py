"""API services layer for database operations.

This module provides reusable functions for CRUD operations on exercises,
challenges, logs, and stats. It shares business logic with the Telegram
bot while returning structured data instead of HTML.

Migrated to use Django ORM via repositories instead of direct Supabase calls.
"""

import math
from datetime import date, datetime
from typing import Optional, List, Dict, Any, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from app.config import settings
from src.core.repositories import (
    exercise_type_repo,
    challenge_repo,
    log_repo,
    user_stats_repo,
)
from src.api.models import (
    ExerciseTypeOut,
    ExerciseTypeCreate,
    ExerciseTypeUpdate,
    ExerciseChallengeOut,
    ExerciseChallengeCreate,
    ExerciseChallengeUpdate,
    ExerciseLogOut,
    ExerciseLogCreate,
    ExerciseStatsOut,
    UserStatsOut,
    StatsSummaryOut,
    PaginatedLogsResponse,
    PaginationMeta,
)

TZ = ZoneInfo(settings.TZ)


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
    is_active: Optional[bool] = True,
    challenge_only: bool = False,
) -> List[ExerciseTypeOut]:
    """List exercise types with optional filters.

    Args:
        is_active: Filter by active status (None = all)
        challenge_only: If True, only return types with active challenges
    """
    types = await exercise_type_repo.get_all(is_active=is_active)
    exercise_types = [ExerciseTypeOut(**_model_to_dict(t)) for t in types]

    if challenge_only:
        # Get exercise type IDs with active challenges
        challenges = await challenge_repo.get_all(filters={"is_active": True})
        active_type_ids = {c.exercise_type_id for c in challenges}
        exercise_types = [et for et in exercise_types if et.id in active_type_ids]

    return exercise_types


async def get_exercise_type(exercise_type_id: int) -> Optional[ExerciseTypeOut]:
    """Get a single exercise type by ID."""
    etype = await exercise_type_repo.get_by_id(exercise_type_id)
    if etype:
        return ExerciseTypeOut(**_model_to_dict(etype))
    return None


async def create_exercise_type(data: ExerciseTypeCreate) -> ExerciseTypeOut:
    """Create a new exercise type."""
    created = await exercise_type_repo.create(data.model_dump())
    return ExerciseTypeOut(**_model_to_dict(created))


async def update_exercise_type(
    exercise_type_id: int, data: ExerciseTypeUpdate
) -> Optional[ExerciseTypeOut]:
    """Update an exercise type."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_exercise_type(exercise_type_id)

    updated = await exercise_type_repo.update(exercise_type_id, update_data)
    if updated:
        return ExerciseTypeOut(**_model_to_dict(updated))
    return None


# =============================================================================
# Challenges
# =============================================================================


def _enrich_challenge(challenge_data: Dict[str, Any], today: date) -> Dict[str, Any]:
    """Add computed fields to challenge data."""
    start = date.fromisoformat(challenge_data["start_date"]) if isinstance(challenge_data["start_date"], str) else challenge_data["start_date"]
    end = date.fromisoformat(challenge_data["end_date"]) if isinstance(challenge_data["end_date"], str) else challenge_data["end_date"]
    challenge_data["total_days"] = (end - start).days + 1
    challenge_data["is_current"] = start <= today <= end
    return challenge_data


async def list_challenges(
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

    challenges = await challenge_repo.get_all(filters=filters if filters else None)

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

    return [
        ExerciseChallengeOut(**_enrich_challenge(_model_to_dict(c), today))
        for c in filtered_challenges
    ]


async def list_current_active_challenges(target_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """List active challenges valid for the target date (default: today)."""
    current_date = target_date or datetime.now(TZ).date()
    challenges = await challenge_repo.get_current_active(current_date)
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


async def get_challenge(challenge_id: int) -> Optional[ExerciseChallengeOut]:
    """Get a single challenge by ID."""
    today = datetime.now(TZ).date()
    challenge = await challenge_repo.get_by_id(challenge_id)
    if challenge:
        return ExerciseChallengeOut(**_enrich_challenge(_model_to_dict(challenge), today))
    return None


async def get_active_challenge_for_type(
    exercise_type_id: int, target_date: Optional[date] = None
) -> Optional[Dict[str, Any]]:
    """Get the active challenge for an exercise type on a given date.

    This mirrors the logic from workout_service.get_active_challenge.
    """
    current_date = target_date or datetime.now(TZ).date()

    # Try to find challenge that wraps the current date
    challenge = await challenge_repo.get_active_for_type(exercise_type_id, current_date)
    if challenge:
        return _model_to_dict(challenge)

    return None


async def create_challenge(data: ExerciseChallengeCreate) -> ExerciseChallengeOut:
    """Create a new challenge."""
    today = datetime.now(TZ).date()

    insert_data = data.model_dump()
    created = await challenge_repo.create(insert_data)
    return ExerciseChallengeOut(**_enrich_challenge(_model_to_dict(created), today))


async def update_challenge(
    challenge_id: int, data: ExerciseChallengeUpdate
) -> Optional[ExerciseChallengeOut]:
    """Update a challenge."""
    today = datetime.now(TZ).date()

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_challenge(challenge_id)

    updated = await challenge_repo.update(challenge_id, update_data)
    if updated:
        return ExerciseChallengeOut(**_enrich_challenge(_model_to_dict(updated), today))
    return None


# =============================================================================
# Stats Computation (shared logic)
# =============================================================================


def calculate_expected_progress(
    target_total: int, day_number: int, total_days: int, daily_target: Optional[int]
) -> float:
    """Calculate expected progress based on target and timeline."""
    if daily_target:
        return daily_target * day_number
    else:
        return (target_total / total_days) * day_number


def calculate_status_and_deficit(
    cumulative: int,
    target_total: int,
    day_number: int,
    total_days: int,
    daily_target: Optional[int],
) -> Tuple[str, float]:
    """Calculate status and deficit.

    Returns:
        Tuple of (status, deficit) where deficit is positive when behind
    """
    expected = calculate_expected_progress(
        target_total, day_number, total_days, daily_target
    )

    diff = cumulative - expected
    deficit = expected - cumulative
    threshold = daily_target or (target_total / total_days)  # full daily target

    if diff > threshold:
        return "ahead", deficit
    elif diff < -threshold:
        return "behind", deficit
    else:
        return "on_track", deficit


async def compute_exercise_stats(
    exercise_type_id: int,
    target_date: Optional[date] = None,
    added_count: int = 0,
    etype: Optional[Dict[str, Any]] = None,
    challenge: Optional[Dict[str, Any]] = None,
) -> ExerciseStatsOut:
    """Compute stats for an exercise type within its challenge context.

    This is the core stats computation extracted from workout_service,
    returning structured data instead of HTML.

    Args:
        exercise_type_id: The exercise type to compute stats for
        target_date: Date context (defaults to today)
        added_count: Optional count to add (for preview before insertion)
        etype: Optional pre-fetched exercise type data (to avoid duplicate queries)
        challenge: Optional pre-fetched challenge data (to avoid duplicate queries)
    """
    today_local = target_date or datetime.now(TZ).date()

    # Get exercise type (only if not provided)
    if etype is None:
        etype_model = await exercise_type_repo.get_by_id(exercise_type_id)
        if not etype_model:
            raise ValueError(f"Exercise type {exercise_type_id} not found")
        etype = _model_to_dict(etype_model)

    # Get challenge (only if not provided)
    if challenge is None:
        challenge = await get_active_challenge_for_type(exercise_type_id, today_local)

    # Default values
    challenge_id = None
    challenge_name = None
    day_number = 1
    total_days = 30
    target_total = 1000
    daily_target = 33

    if challenge:
        challenge_id = challenge["id"]
        challenge_name = challenge.get("challenge_name")
        start_date = date.fromisoformat(challenge["start_date"]) if isinstance(challenge["start_date"], str) else challenge["start_date"]
        end_date = date.fromisoformat(challenge["end_date"]) if isinstance(challenge["end_date"], str) else challenge["end_date"]
        total_days = (end_date - start_date).days + 1
        # Clamp day_number to challenge window for historical snapshots
        day_number = max(1, min((today_local - start_date).days + 1, total_days))
        target_total = challenge["target_total"]
        daily_target = challenge.get("daily_target")

    # Query cumulative total
    current_total = await log_repo.get_cumulative_count(
        exercise_type_id, challenge_id, today_local
    )
    new_cumulative = current_total + added_count

    # Status and deficit
    status, deficit = calculate_status_and_deficit(
        new_cumulative, target_total, day_number, total_days, daily_target
    )

    # Catch-up calculation - show for any positive deficit
    catch_up_reps = 0
    if deficit > 0:
        catch_up_reps = math.ceil(deficit)

    # Today's total
    current_today_total = await log_repo.get_today_count(
        exercise_type_id, today_local, challenge_id
    )
    new_today_total = current_today_total + added_count

    # Progress percentage
    progress_percent = (
        min(100.0, (new_cumulative / target_total) * 100) if target_total > 0 else 0
    )

    return ExerciseStatsOut(
        exercise_type_id=exercise_type_id,
        exercise_type_name=etype["display_name"],
        exercise_type_emoji=etype["emoji"],
        challenge_id=challenge_id,
        challenge_name=challenge_name,
        day_number=day_number,
        total_days=total_days,
        target_total=target_total,
        daily_target=daily_target,
        today_total=new_today_total,
        cumulative_total=new_cumulative,
        progress_percent=round(progress_percent, 1),
        status=status,
        catch_up_reps=catch_up_reps,
    )


async def get_all_exercise_stats(
    target_date: Optional[date] = None,
    challenge_only: bool = True,
) -> List[ExerciseStatsOut]:
    """Get stats for all exercises (optionally limited to those with challenges)."""
    exercise_types = await list_exercise_types(is_active=True, challenge_only=challenge_only)
    stats = []
    for et in exercise_types:
        stat = await compute_exercise_stats(et.id, target_date)
        stats.append(stat)
    return stats


# =============================================================================
# Exercise Logs
# =============================================================================


async def list_logs(
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
        offset=offset
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


async def get_log(log_id: int) -> Optional[ExerciseLogOut]:
    """Get a single log entry by ID."""
    log_model = await log_repo.get_by_id(log_id)
    if log_model:
        log = ExerciseLogOut(**_model_to_dict(log_model))
        if log_model.exercise_type:
            log.exercise_type = ExerciseTypeOut(**_model_to_dict(log_model.exercise_type))
        return log
    return None


async def create_log(data: ExerciseLogCreate) -> Tuple[ExerciseLogOut, ExerciseStatsOut]:
    """Create a new log entry and update stats.

    Returns:
        Tuple of (created_log, updated_stats)
    """
    today_local = datetime.now(TZ).date()
    log_date = data.date or today_local

    # Get exercise type
    etype = await get_exercise_type(data.exercise_type_id)
    if not etype:
        raise ValueError(f"Exercise type {data.exercise_type_id} not found")

    # Get challenge
    challenge = await get_active_challenge_for_type(data.exercise_type_id, log_date)

    # Compute stats before insertion to get cumulative values
    stats = await compute_exercise_stats(data.exercise_type_id, log_date, added_count=data.count)

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
    await user_stats_repo.increment_total(data.exercise_type_id, data.count, log_date)

    return created_log, stats


async def delete_log(log_id: int) -> Tuple[Optional[ExerciseLogOut], Optional[ExerciseStatsOut]]:
    """Delete a log entry and update stats.

    Returns:
        Tuple of (deleted_log, updated_stats) or (None, None) if not found
    """
    # Get the log entry first
    log = await get_log(log_id)
    if not log:
        return None, None

    exercise_type_id = log.exercise_type_id
    count_to_remove = log.count

    # Delete the log
    await log_repo.delete(log_id)

    # Update user_stats
    await user_stats_repo.decrement_total(exercise_type_id, count_to_remove)
    await user_stats_repo.sync_last_logged_date(exercise_type_id)

    # Compute updated stats
    stats = await compute_exercise_stats(exercise_type_id)

    return log, stats


# =============================================================================
# User Stats
# =============================================================================


async def list_user_stats() -> List[UserStatsOut]:
    """List all user stats."""
    stats_models = await user_stats_repo.get_all()

    stats = []
    for stat_model in stats_models:
        stat_dict = _model_to_dict(stat_model)
        stat = UserStatsOut(**stat_dict)
        if stat_model.exercise_type:
            stat.exercise_type = ExerciseTypeOut(**_model_to_dict(stat_model.exercise_type))
        stats.append(stat)

    return stats


async def get_stats_summary() -> StatsSummaryOut:
    """Get overall stats summary."""
    # Get all user stats
    user_stats = await list_user_stats()

    # Calculate totals
    total_reps = sum(s.all_time_total for s in user_stats)

    # Count distinct days with activity
    # Note: This is a simplified version - could be optimized with a raw query
    all_logs, _ = await log_repo.get_all(limit=10000)  # Get all logs
    distinct_days = len(set(log.date for log in all_logs))

    return StatsSummaryOut(
        total_reps_all_time=total_reps,
        total_active_days=distinct_days,
        exercise_stats=user_stats,
    )
