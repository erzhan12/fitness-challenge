import logging
import math
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from app.dependencies import get_supabase
from app.models import ExerciseType
from app.services.openai_service import (
    parse_workout_message,
    generate_motivational_response,
)
from app.services.telegram_client import send_telegram_message
from app.config import settings

logger = logging.getLogger(__name__)
TZ = ZoneInfo(settings.TZ)


async def get_exercise_types() -> List[ExerciseType]:
    sb = get_supabase()
    # Supabase-py: select("*").execute() returns .data
    res = (
        sb.table("exercise_types")
        .select("*")
        .eq("is_active", True)
        .order("id")
        .execute()
    )
    return [ExerciseType(**row) for row in res.data]


def get_active_challenge(exercise_type_id: int, current_date: date) -> Optional[Dict]:
    sb = get_supabase()
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

    # 2. Fallback: Find ANY active challenge for this exercise type (by is_active=True)
    # Pick the one with the latest end_date (most recent or future)
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
    """Calculate status and deficit in a single function to avoid duplication.

    Returns:
        Tuple of (status, deficit) where deficit is positive when behind, negative when ahead
    """
    expected = calculate_expected_progress(
        target_total, day_number, total_days, daily_target
    )

    diff = cumulative - expected
    deficit = expected - cumulative  # positive when behind
    threshold = (daily_target or (target_total / total_days)) * 0.5  # loose threshold

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


def get_exercise_stats_and_message(
    sb,
    etype: ExerciseType,
    challenge: Optional[Dict],
    today_local: date,
    added_count: int = 0,
) -> Tuple[str, Dict[str, Any]]:
    # 1. Params
    challenge_id = None
    day_number = 1
    total_days = 30
    target_total = 1000
    daily_target = 33

    if challenge:
        challenge_id = challenge["id"]
        start_date = date.fromisoformat(challenge["start_date"])
        end_date = date.fromisoformat(challenge["end_date"])
        day_number = (today_local - start_date).days + 1
        total_days = (end_date - start_date).days + 1
        target_total = challenge["target_total"]
        daily_target = challenge.get("daily_target")

    # 2. Query Cumulative
    query = sb.table("exercise_logs").select("count").eq("exercise_type_id", etype.id)
    if challenge_id is not None:
        query = query.eq("challenge_id", challenge_id)
    else:
        query = query.is_("challenge_id", "null")

    logs_res = query.execute()
    current_total = sum(r["count"] for r in logs_res.data)
    new_cumulative = current_total + added_count

    # 3. Status and deficit calculation
    status, deficit = calculate_status_and_deficit(
        new_cumulative, target_total, day_number, total_days, daily_target
    )

    # 4. Catch-up calculation
    catch_up_reps = 0
    if status == "behind" and deficit > 0:
        catch_up_reps = math.ceil(deficit)

    # 6. Today's Total
    # Query existing today logs and add added_count
    today_logs = (
        sb.table("exercise_logs")
        .select("count")
        .eq("exercise_type_id", etype.id)
        .eq("date", today_local.isoformat())
        .execute()
    )
    current_today_total = sum(r["count"] for r in today_logs.data)
    new_today_total = current_today_total + added_count

    # 7. Format Message
    progress_percent = (
        min(1.0, new_cumulative / target_total) if target_total > 0 else 0
    )
    filled_blocks = int(progress_percent * 10)
    bar = "█" * filled_blocks + "░" * (10 - filled_blocks)

    unit_label = "min" if etype.unit in ["minutes", "min"] else ""

    # Differentiate formatting based on added_count
    if added_count > 0:
        header = (
            f"{etype.emoji} <b>{etype.display_name}</b>: +{added_count} {unit_label}"
        )
    else:
        header = f"{etype.emoji} <b>{etype.display_name}</b>"

    msg_part = (
        f"{header}\n"
        f"Day {day_number}/{total_days} • Today: {new_today_total} • Total: {new_cumulative}/{target_total}\n"
        f"[{bar}] {int(progress_percent * 100)}%\n"
    )

    # Add catch-up message if behind
    if catch_up_reps > 0:
        msg_part += f"Need {catch_up_reps} more to catch up!\n"

    stats = {
        "cumulative_total": new_cumulative,
        "today_total": new_today_total,
        "status": status,
        "day_number": day_number,
        "target_total": target_total,
        "total_days": total_days,
        "daily_target": daily_target,
        "challenge_id": challenge_id,
        "catch_up_reps": catch_up_reps,
    }

    return msg_part, stats


async def process_incoming_message(text: str, chat_id: int):
    # Handle commands
    text_lower = text.strip().lower()

    if text_lower == "/start":
        welcome_message = (
            "👋 <b>Welcome to Fitness Challenge Bot!</b>\n\n"
            "I help you track your workouts. Just send me your exercises:\n\n"
            "Examples:\n"
            "• <code>20 pushups</code>\n"
            "• <code>30 squats</code>\n"
            "• <code>2 min plank</code>\n"
            "• <code>20 pushups and 30 squats</code>\n\n"
            "I'll track your progress and keep you motivated! 💪"
        )
        await send_telegram_message(chat_id, welcome_message)
        return

    # 1. Get Definitions (filtered by active challenges)
    sb = get_supabase()

    # Fetch active challenges
    challenges_res = (
        sb.table("exercise_challenges").select("*").eq("is_active", True).execute()
    )
    challenges_data = challenges_res.data

    # Determine relevant exercise type IDs
    challenge_type_ids = list({c["exercise_type_id"] for c in challenges_data})

    if not challenge_type_ids:
        # If no challenges found, maybe fallback to all or empty.
        # Based on user request to "only see challenge exercises", we return empty/limited list.
        # But to avoid breaking the bot completely for new users, let's fallback to ALL if NONE are found?
        # User said: "I don't want to see Plank... because my challenge only..."
        # This implies if they have challenges, restrict to them.
        # If they have ZERO challenges, maybe showing nothing is correct, or fallback.
        # Let's fallback to get_exercise_types() (all active) if NO challenges exist at all.
        exercise_types = await get_exercise_types()
        challenge_map = {}
    else:
        types_res = (
            sb.table("exercise_types")
            .select("*")
            .in_("id", challenge_type_ids)
            .eq("is_active", True)
            .order("id")
            .execute()
        )
        exercise_types = [ExerciseType(**row) for row in types_res.data]

        # Build map: type_id -> best challenge
        # Sort challenges by end_date desc so we pick the latest/future one if duplicates
        challenges_data.sort(key=lambda x: x["end_date"], reverse=True)
        challenge_map = {}
        for c in challenges_data:
            tid = c["exercise_type_id"]
            if tid not in challenge_map:
                challenge_map[tid] = c

    # 2. Parse
    parsed_result = parse_workout_message(text, exercise_types)

    if not parsed_result.is_valid:
        await send_telegram_message(
            chat_id, parsed_result.error_reason or "Couldn't understand that workout."
        )
        return

    sb = get_supabase()
    today_local = datetime.now(TZ).date()
    response_map = {}
    witty_comments = []
    updated_exercise_ids = set()

    # 3. Process Each Entry
    for entry in parsed_result.entries:
        # Match exercise type
        etype = next(
            (et for et in exercise_types if et.name == entry.exercise_type_name), None
        )
        if not etype:
            continue  # Should not happen if AI follows constraints

        updated_exercise_ids.add(etype.id)

        # Find Challenge
        challenge = challenge_map.get(etype.id)

        # Use Helper to get stats and message
        msg_part, stats = get_exercise_stats_and_message(
            sb, etype, challenge, today_local, added_count=entry.count
        )

        response_map[etype.id] = msg_part

        # Insert Log
        log_data = {
            "exercise_type_id": etype.id,
            "challenge_id": stats["challenge_id"],
            "date": today_local.isoformat(),
            "timestamp": datetime.now(TZ).isoformat(),
            "count": entry.count,
            "cumulative_total": stats["cumulative_total"],
            "day_number": stats["day_number"],
            "status": stats["status"],
            "raw_message": text,
            "duration_seconds": entry.duration_seconds,
            "notes": entry.notes,
        }
        sb.table("exercise_logs").insert(log_data).execute()

        # Upsert User Stats
        stats_res = (
            sb.table("user_stats")
            .select("*")
            .eq("exercise_type_id", etype.id)
            .execute()
        )
        if stats_res.data:
            curr_stats = stats_res.data[0]
            new_all_time = curr_stats["all_time_total"] + entry.count
            sb.table("user_stats").update(
                {
                    "all_time_total": new_all_time,
                    "last_logged_date": today_local.isoformat(),
                }
            ).eq("id", curr_stats["id"]).execute()
        else:
            sb.table("user_stats").insert(
                {
                    "exercise_type_id": etype.id,
                    "all_time_total": entry.count,
                    "last_logged_date": today_local.isoformat(),
                }
            ).execute()

        # Generate Witty Comment (using stats from helper)
        if challenge:
            comment = generate_motivational_response(
                etype.display_name,
                {
                    "status": stats["status"],
                    "today_total": stats["today_total"],
                    "day_number": stats["day_number"],
                    "streak": "N/A",
                },
            )
            witty_comments.append(comment)

    # 4. Process Remaining Exercises
    for etype in exercise_types:
        if etype.id in updated_exercise_ids:
            continue

        # Find Challenge
        challenge = challenge_map.get(etype.id)

        # Use Helper
        msg_part, _ = get_exercise_stats_and_message(
            sb, etype, challenge, today_local, added_count=0
        )
        response_map[etype.id] = msg_part

    # Final Response Assembly
    final_parts = []
    for et in exercise_types:
        if et.id in response_map:
            final_parts.append(response_map[et.id])

    full_response = "\n".join(final_parts)
    if witty_comments:
        full_response += f"\n<i>{witty_comments[-1]}</i>"

    await send_telegram_message(chat_id, full_response)


async def check_daily_reminders():
    """
    Checks active challenges. If no log for today, send a reminder.
    """
    sb = get_supabase()
    today_local = datetime.now(TZ).date()

    # Get active challenges
    res = (
        sb.table("exercise_challenges")
        .select("*, exercise_types(name, emoji, display_name)")
        .eq("is_active", True)
        .lte("start_date", today_local.isoformat())
        .gte("end_date", today_local.isoformat())
        .execute()
    )

    challenges = res.data

    # We need the user's chat_id.
    # Since this is single user, we can just grab the chat_id from the last log or config.
    # For now, let's assume we can query the last log to get a chat_id (if we stored it, which we didn't).
    # User didn't ask to store user_id/chat_id in DB schema provided, but we need it to send messages.
    # OPTION: Store a default CHAT_ID in env, or we rely on 'user_stats' having a user_id if we added it.
    # Given the constraints, I will assume we put target CHAT_ID in settings for the reminder.

    # Actually, the prompt says "Only one user (me) for now".
    # So I should add TARGET_CHAT_ID to settings.
    from app.config import settings

    # Note: You'll need to add TARGET_CHAT_ID to app/config.py manually or via env
    target_chat_id = getattr(settings, "TARGET_CHAT_ID", None)

    if not target_chat_id:
        logger.warning("No TARGET_CHAT_ID set for reminders.")
        return

    for ch in challenges:
        # Check if logged today
        logs = (
            sb.table("exercise_logs")
            .select("id")
            .eq("challenge_id", ch["id"])
            .eq("date", today_local.isoformat())
            .execute()
        )

        if not logs.data:
            # Send Reminder
            ex_name = ch["exercise_types"]["display_name"]
            emoji = ch["exercise_types"]["emoji"]
            msg = f"Hey, your {emoji} {ex_name} are missing you today! 🥺"
            await send_telegram_message(target_chat_id, msg)
