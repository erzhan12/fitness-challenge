"""API services layer for database operations.

This module provides reusable functions for CRUD operations on exercises,
challenges, logs, and stats. It shares business logic with the Telegram
bot while returning structured data instead of HTML.
"""

import math
from datetime import date, datetime
from typing import Optional, List, Dict, Any, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from app.dependencies import get_supabase
from app.config import settings
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
# Exercise Types
# =============================================================================


def list_exercise_types(
    is_active: Optional[bool] = True,
    challenge_only: bool = False,
) -> List[ExerciseTypeOut]:
    """List exercise types with optional filters.

    Args:
        is_active: Filter by active status (None = all)
        challenge_only: If True, only return types with active challenges
    """
    sb = get_supabase()

    query = sb.table("exercise_types").select("*")

    if is_active is not None:
        query = query.eq("is_active", is_active)

    query = query.order("id")
    res = query.execute()

    exercise_types = [ExerciseTypeOut(**row) for row in res.data]

    if challenge_only:
        # Get exercise type IDs with active challenges
        challenges_res = (
            sb.table("exercise_challenges")
            .select("exercise_type_id")
            .eq("is_active", True)
            .execute()
        )
        active_type_ids = {c["exercise_type_id"] for c in challenges_res.data}
        exercise_types = [et for et in exercise_types if et.id in active_type_ids]

    return exercise_types


def get_exercise_type(exercise_type_id: int) -> Optional[ExerciseTypeOut]:
    """Get a single exercise type by ID."""
    sb = get_supabase()
    res = (
        sb.table("exercise_types")
        .select("*")
        .eq("id", exercise_type_id)
        .execute()
    )
    if res.data:
        return ExerciseTypeOut(**res.data[0])
    return None


def create_exercise_type(data: ExerciseTypeCreate) -> ExerciseTypeOut:
    """Create a new exercise type."""
    sb = get_supabase()
    insert_data = data.model_dump()
    res = sb.table("exercise_types").insert(insert_data).execute()
    return ExerciseTypeOut(**res.data[0])


def update_exercise_type(
    exercise_type_id: int, data: ExerciseTypeUpdate
) -> Optional[ExerciseTypeOut]:
    """Update an exercise type."""
    sb = get_supabase()
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return get_exercise_type(exercise_type_id)

    res = (
        sb.table("exercise_types")
        .update(update_data)
        .eq("id", exercise_type_id)
        .execute()
    )
    if res.data:
        return ExerciseTypeOut(**res.data[0])
    return None


# =============================================================================
# Challenges
# =============================================================================


def _enrich_challenge(challenge_data: Dict[str, Any], today: date) -> Dict[str, Any]:
    """Add computed fields to challenge data."""
    start = date.fromisoformat(challenge_data["start_date"])
    end = date.fromisoformat(challenge_data["end_date"])
    challenge_data["total_days"] = (end - start).days + 1
    challenge_data["is_current"] = start <= today <= end
    return challenge_data


def list_challenges(
    exercise_type_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    starts_before: Optional[date] = None,
    ends_after: Optional[date] = None,
) -> List[ExerciseChallengeOut]:
    """List challenges with optional filters."""
    sb = get_supabase()
    today = datetime.now(TZ).date()

    query = sb.table("exercise_challenges").select("*")

    if exercise_type_id is not None:
        query = query.eq("exercise_type_id", exercise_type_id)
    if is_active is not None:
        query = query.eq("is_active", is_active)
    if starts_before is not None:
        query = query.lte("start_date", starts_before.isoformat())
    if ends_after is not None:
        query = query.gte("end_date", ends_after.isoformat())

    query = query.order("start_date", desc=True)
    res = query.execute()

    return [
        ExerciseChallengeOut(**_enrich_challenge(row, today)) for row in res.data
    ]


def get_challenge(challenge_id: int) -> Optional[ExerciseChallengeOut]:
    """Get a single challenge by ID."""
    sb = get_supabase()
    today = datetime.now(TZ).date()

    res = (
        sb.table("exercise_challenges")
        .select("*")
        .eq("id", challenge_id)
        .execute()
    )
    if res.data:
        return ExerciseChallengeOut(**_enrich_challenge(res.data[0], today))
    return None


def get_active_challenge_for_type(
    exercise_type_id: int, target_date: Optional[date] = None
) -> Optional[Dict[str, Any]]:
    """Get the active challenge for an exercise type on a given date.

    This mirrors the logic from workout_service.get_active_challenge.
    """
    sb = get_supabase()
    current_date = target_date or datetime.now(TZ).date()

    # 1. Try to find challenge that wraps the current date
    res = (
        sb.table("exercise_challenges")
        .select("*")
        .eq("exercise_type_id", exercise_type_id)
        .eq("is_active", True)
        .lte("start_date", current_date.isoformat())
        .gte("end_date", current_date.isoformat())
        .execute()
    )
    if res.data:
        return res.data[0]

    # 2. Fallback: any active challenge for this type (latest end_date)
    res_fallback = (
        sb.table("exercise_challenges")
        .select("*")
        .eq("exercise_type_id", exercise_type_id)
        .eq("is_active", True)
        .order("end_date", desc=True)
        .limit(1)
        .execute()
    )
    if res_fallback.data:
        return res_fallback.data[0]

    return None


def create_challenge(data: ExerciseChallengeCreate) -> ExerciseChallengeOut:
    """Create a new challenge."""
    sb = get_supabase()
    today = datetime.now(TZ).date()

    insert_data = data.model_dump()
    # Convert dates to ISO strings for Supabase
    insert_data["start_date"] = data.start_date.isoformat()
    insert_data["end_date"] = data.end_date.isoformat()

    res = sb.table("exercise_challenges").insert(insert_data).execute()
    return ExerciseChallengeOut(**_enrich_challenge(res.data[0], today))


def update_challenge(
    challenge_id: int, data: ExerciseChallengeUpdate
) -> Optional[ExerciseChallengeOut]:
    """Update a challenge."""
    sb = get_supabase()
    today = datetime.now(TZ).date()

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return get_challenge(challenge_id)

    # Convert dates to ISO strings if present
    if "start_date" in update_data and update_data["start_date"]:
        update_data["start_date"] = update_data["start_date"].isoformat()
    if "end_date" in update_data and update_data["end_date"]:
        update_data["end_date"] = update_data["end_date"].isoformat()

    res = (
        sb.table("exercise_challenges")
        .update(update_data)
        .eq("id", challenge_id)
        .execute()
    )
    if res.data:
        return ExerciseChallengeOut(**_enrich_challenge(res.data[0], today))
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


def compute_exercise_stats(
    exercise_type_id: int,
    target_date: Optional[date] = None,
    added_count: int = 0,
) -> ExerciseStatsOut:
    """Compute stats for an exercise type within its challenge context.

    This is the core stats computation extracted from workout_service,
    returning structured data instead of HTML.

    Args:
        exercise_type_id: The exercise type to compute stats for
        target_date: Date context (defaults to today)
        added_count: Optional count to add (for preview before insertion)
    """
    sb = get_supabase()
    today_local = target_date or datetime.now(TZ).date()

    # Get exercise type
    ex_res = sb.table("exercise_types").select("*").eq("id", exercise_type_id).execute()
    if not ex_res.data:
        raise ValueError(f"Exercise type {exercise_type_id} not found")
    etype = ex_res.data[0]

    # Get challenge
    challenge = get_active_challenge_for_type(exercise_type_id, today_local)

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
        start_date = date.fromisoformat(challenge["start_date"])
        end_date = date.fromisoformat(challenge["end_date"])
        total_days = (end_date - start_date).days + 1
        # Clamp day_number to challenge window for historical snapshots
        day_number = max(1, min((today_local - start_date).days + 1, total_days))
        target_total = challenge["target_total"]
        daily_target = challenge.get("daily_target")

    # Query cumulative total
    query = sb.table("exercise_logs").select("count").eq("exercise_type_id", exercise_type_id)
    if challenge_id is not None:
        query = query.eq("challenge_id", challenge_id)
    else:
        query = query.is_("challenge_id", "null")
    
    # Filter by target_date to get historical snapshots
    query = query.lte("date", today_local.isoformat())

    logs_res = query.execute()
    current_total = sum(r["count"] for r in logs_res.data)
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
    today_logs = (
        sb.table("exercise_logs")
        .select("count")
        .eq("exercise_type_id", exercise_type_id)
        .eq("date", today_local.isoformat())
        .execute()
    )
    current_today_total = sum(r["count"] for r in today_logs.data)
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


def get_all_exercise_stats(
    target_date: Optional[date] = None,
    challenge_only: bool = True,
) -> List[ExerciseStatsOut]:
    """Get stats for all exercises (optionally limited to those with challenges)."""
    exercise_types = list_exercise_types(is_active=True, challenge_only=challenge_only)
    return [
        compute_exercise_stats(et.id, target_date) for et in exercise_types
    ]


# =============================================================================
# Exercise Logs
# =============================================================================


def list_logs(
    exercise_type_id: Optional[int] = None,
    challenge_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedLogsResponse:
    """List log entries with pagination and filters."""
    sb = get_supabase()

    # Build query
    query = sb.table("exercise_logs").select(
        "*, exercise_types(id, name, display_name, emoji, unit, aliases, is_active)",
        count="exact",
    )

    if exercise_type_id is not None:
        query = query.eq("exercise_type_id", exercise_type_id)
    if challenge_id is not None:
        query = query.eq("challenge_id", challenge_id)
    if date_from is not None:
        query = query.gte("date", date_from.isoformat())
    if date_to is not None:
        query = query.lte("date", date_to.isoformat())

    # Order and paginate
    query = query.order("timestamp", desc=True).range(offset, offset + limit - 1)

    res = query.execute()

    # Transform data
    logs = []
    for row in res.data:
        exercise_type_data = row.pop("exercise_types", None)
        log = ExerciseLogOut(**row)
        if exercise_type_data:
            log.exercise_type = ExerciseTypeOut(**exercise_type_data)
        logs.append(log)

    # Get total count
    total = res.count if res.count is not None else len(logs)

    return PaginatedLogsResponse(
        data=logs,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(logs)) < total,
        ),
    )


def get_log(log_id: int) -> Optional[ExerciseLogOut]:
    """Get a single log entry by ID."""
    sb = get_supabase()
    res = (
        sb.table("exercise_logs")
        .select(
            "*, exercise_types(id, name, display_name, emoji, unit, aliases, is_active)"
        )
        .eq("id", log_id)
        .execute()
    )
    if res.data:
        row = res.data[0]
        exercise_type_data = row.pop("exercise_types", None)
        log = ExerciseLogOut(**row)
        if exercise_type_data:
            log.exercise_type = ExerciseTypeOut(**exercise_type_data)
        return log
    return None


def create_log(data: ExerciseLogCreate) -> Tuple[ExerciseLogOut, ExerciseStatsOut]:
    """Create a new log entry and update stats.

    Returns:
        Tuple of (created_log, updated_stats)
    """
    sb = get_supabase()
    today_local = datetime.now(TZ).date()
    log_date = data.date or today_local

    # Get exercise type
    etype = get_exercise_type(data.exercise_type_id)
    if not etype:
        raise ValueError(f"Exercise type {data.exercise_type_id} not found")

    # Get challenge
    challenge = get_active_challenge_for_type(data.exercise_type_id, log_date)

    # Compute stats before insertion to get cumulative values
    stats = compute_exercise_stats(data.exercise_type_id, log_date, added_count=data.count)

    # Build log data
    # Safely get challenge_id
    challenge_id = None
    if challenge and isinstance(challenge, dict):
        challenge_id = challenge.get("id")

    # Generate default raw_message if not provided (for API-created logs)
    raw_message = data.raw_message
    if raw_message is None:
        # Create a simple default message based on the exercise
        raw_message = f"{data.count} {etype.name}"
        if data.notes:
            raw_message += f" - {data.notes}"

    log_data = {
        "exercise_type_id": data.exercise_type_id,
        "challenge_id": challenge_id,
        "date": log_date.isoformat(),
        "timestamp": datetime.now(TZ).isoformat(),
        "count": data.count,
        "cumulative_total": stats.cumulative_total,
        "day_number": stats.day_number,
        "status": stats.status,
        "raw_message": raw_message,
        "duration_seconds": data.duration_seconds,
        "notes": data.notes,
    }

    # Insert log
    res = sb.table("exercise_logs").insert(log_data).execute()
    created_log = ExerciseLogOut(**res.data[0])

    # Update user_stats
    _update_user_stats_after_insert(
        sb, data.exercise_type_id, data.count, log_date
    )

    return created_log, stats


def delete_log(log_id: int) -> Tuple[Optional[ExerciseLogOut], Optional[ExerciseStatsOut]]:
    """Delete a log entry and update stats.

    Returns:
        Tuple of (deleted_log, updated_stats) or (None, None) if not found
    """
    sb = get_supabase()

    # Get the log entry first
    log = get_log(log_id)
    if not log:
        return None, None

    exercise_type_id = log.exercise_type_id
    count_to_remove = log.count
    log_date = log.date

    # Delete the log
    sb.table("exercise_logs").delete().eq("id", log_id).execute()

    # Update user_stats
    _update_user_stats_after_delete(sb, exercise_type_id, count_to_remove, log_date)

    # Compute updated stats
    stats = compute_exercise_stats(exercise_type_id)

    return log, stats


def _update_user_stats_after_insert(
    sb, exercise_type_id: int, count: int, log_date: date
):
    """Update user_stats after inserting a log."""
    stats_res = (
        sb.table("user_stats")
        .select("*")
        .eq("exercise_type_id", exercise_type_id)
        .execute()
    )

    if stats_res.data:
        curr_stats = stats_res.data[0]
        new_all_time = curr_stats["all_time_total"] + count
        sb.table("user_stats").update(
            {
                "all_time_total": new_all_time,
                "last_logged_date": log_date.isoformat(),
            }
        ).eq("id", curr_stats["id"]).execute()
    else:
        sb.table("user_stats").insert(
            {
                "exercise_type_id": exercise_type_id,
                "all_time_total": count,
                "last_logged_date": log_date.isoformat(),
            }
        ).execute()


def _update_user_stats_after_delete(
    sb, exercise_type_id: int, count_removed: int, deleted_log_date: date
):
    """Update user_stats after deleting a log."""
    stats_res = (
        sb.table("user_stats")
        .select("*")
        .eq("exercise_type_id", exercise_type_id)
        .execute()
    )

    if not stats_res.data:
        return

    curr_stats = stats_res.data[0]
    new_all_time = max(0, curr_stats["all_time_total"] - count_removed)

    # Determine new last_logged_date
    # Check for any remaining logs
    remaining_logs = (
        sb.table("exercise_logs")
        .select("date")
        .eq("exercise_type_id", exercise_type_id)
        .order("date", desc=True)
        .limit(1)
        .execute()
    )

    new_last_date = remaining_logs.data[0]["date"] if remaining_logs.data else None

    update_data = {"all_time_total": new_all_time}
    if new_last_date:
        update_data["last_logged_date"] = new_last_date
    else:
        update_data["last_logged_date"] = None

    sb.table("user_stats").update(update_data).eq("id", curr_stats["id"]).execute()


# =============================================================================
# User Stats
# =============================================================================


def list_user_stats() -> List[UserStatsOut]:
    """List all user stats."""
    sb = get_supabase()
    res = (
        sb.table("user_stats")
        .select(
            "*, exercise_types(id, name, display_name, emoji, unit, aliases, is_active)"
        )
        .execute()
    )

    stats = []
    for row in res.data:
        exercise_type_data = row.pop("exercise_types", None)
        stat = UserStatsOut(**row)
        if exercise_type_data:
            stat.exercise_type = ExerciseTypeOut(**exercise_type_data)
        stats.append(stat)

    return stats


def get_stats_summary() -> StatsSummaryOut:
    """Get overall stats summary."""
    sb = get_supabase()

    # Get all user stats
    user_stats = list_user_stats()

    # Calculate totals
    total_reps = sum(s.all_time_total for s in user_stats)

    # Count distinct days with activity
    days_res = (
        sb.table("exercise_logs")
        .select("date")
        .execute()
    )
    distinct_days = len(set(r["date"] for r in days_res.data))

    return StatsSummaryOut(
        total_reps_all_time=total_reps,
        total_active_days=distinct_days,
        exercise_stats=user_stats,
    )

