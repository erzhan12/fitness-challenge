import logging
import asyncio
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
from app.services.telegram_client import send_telegram_message, send_chat_action
from app.config import settings
from src.api.services import compute_exercise_stats

logger = logging.getLogger(__name__)
TZ = ZoneInfo(settings.TZ)


async def keep_typing(chat_id: int, stop_event: asyncio.Event):
    """
    Continuously sends 'typing' action to Telegram while processing.
    Stops when stop_event is set.
    """
    logger.debug(f"Starting typing indicator for chat_id {chat_id}")
    while not stop_event.is_set():
        await send_chat_action(chat_id, "typing")
        try:
            # Wait 4 seconds or until stop event is set
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
            break  # Stop event was set
        except asyncio.TimeoutError:
            # Continue sending typing action
            continue
    logger.debug(f"Stopped typing indicator for chat_id {chat_id}")


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
    """Get stats and format HTML message using the shared stats helper.
    
    This now calls compute_exercise_stats from src.api.services to ensure
    consistent business logic between Telegram and REST API.
    """
    # Use the shared stats helper
    stats_out = compute_exercise_stats(
        exercise_type_id=etype.id,
        target_date=today_local,
        added_count=added_count,
    )
    
    # Format the HTML message from the stats
    progress_percent = stats_out.progress_percent / 100.0  # Convert to 0-1 range
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
        f"Day {stats_out.day_number}/{stats_out.total_days} • "
        f"Today: {stats_out.today_total} • "
        f"Total: {stats_out.cumulative_total}/{stats_out.target_total}\n"
        f"[{bar}] {int(stats_out.progress_percent)}%\n"
    )
    
    # Add catch-up / ahead message
    if stats_out.catch_up_reps > 0:
        msg_part += f"Need {stats_out.catch_up_reps} more to catch up!\n"
    else:
        # Compute "ahead" amount vs expected cumulative by day_number.
        # This mirrors the stats logic thresholding but gives a concrete "ahead by X" number.
        expected = calculate_expected_progress(
            stats_out.target_total,
            stats_out.day_number,
            stats_out.total_days,
            stats_out.daily_target,
        )
        diff = stats_out.cumulative_total - expected  # positive means ahead
        ahead_reps = max(0, int(diff))  # floor for floats
        if ahead_reps > 0:
            msg_part += f"You're doing great — you are {ahead_reps} reps ahead!\n"
        else:
            msg_part += "You're doing great — you're on track!\n"
    
    # Return stats dict for backward compatibility with existing code
    stats = {
        "cumulative_total": stats_out.cumulative_total,
        "today_total": stats_out.today_total,
        "status": stats_out.status,
        "day_number": stats_out.day_number,
        "target_total": stats_out.target_total,
        "total_days": stats_out.total_days,
        "daily_target": stats_out.daily_target,
        "challenge_id": stats_out.challenge_id,
        "catch_up_reps": stats_out.catch_up_reps,
    }
    
    return msg_part, stats


async def get_recent_logs(chat_id: int, limit: int = 5) -> str:
    """Get recent log entries for the user."""
    sb = get_supabase()

    # Get recent logs with exercise type info
    res = (
        sb.table("exercise_logs")
        .select(
            "id, exercise_type_id, count, date, timestamp, raw_message, exercise_types(display_name, emoji)"
        )
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )

    if not res.data:
        return "No logs found."

    lines = ["📋 <b>Recent Logs:</b>\n"]
    for log in res.data:
        ex_info = log.get("exercise_types", {})
        ex_name = ex_info.get("display_name", "Unknown")
        emoji = ex_info.get("emoji", "🏋️")
        log_date = log["date"]
        count = log["count"]
        log_id = log["id"]
        timestamp = log.get("timestamp", "")

        # Format timestamp if available
        time_str = ""
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M")
            except (ValueError, AttributeError):
                pass

        lines.append(
            f"{emoji} <b>{ex_name}</b>: {count} • {log_date} {time_str}\n"
            f'   ID: <code>{log_id}</code> • "{log.get("raw_message", "")[:30]}..."'
        )

    lines.append("\n💡 Use <code>/delete &lt;id&gt;</code> to remove a log")
    return "\n".join(lines)


async def delete_log_entry(log_id: int, chat_id: int) -> str:
    """Delete a log entry and update related stats."""
    sb = get_supabase()

    # Get the log entry first
    log_res = (
        sb.table("exercise_logs")
        .select("id, exercise_type_id, count, challenge_id, date")
        .eq("id", log_id)
        .execute()
    )

    if not log_res.data:
        return f"❌ Log entry {log_id} not found."

    log_entry = log_res.data[0]
    exercise_type_id = log_entry["exercise_type_id"]
    count_to_remove = log_entry["count"]
    log_date = log_entry["date"]

    # Get exercise type info for response
    ex_res = (
        sb.table("exercise_types")
        .select("display_name, emoji")
        .eq("id", exercise_type_id)
        .execute()
    )
    ex_info = (
        ex_res.data[0] if ex_res.data else {"display_name": "Exercise", "emoji": "🏋️"}
    )

    # Delete the log entry
    delete_res = sb.table("exercise_logs").delete().eq("id", log_id).execute()

    if not delete_res.data:
        return f"❌ Failed to delete log entry {log_id}."

    # Update user_stats: subtract the count
    stats_res = (
        sb.table("user_stats")
        .select("*")
        .eq("exercise_type_id", exercise_type_id)
        .execute()
    )

    if stats_res.data:
        curr_stats = stats_res.data[0]
        new_all_time = max(0, curr_stats["all_time_total"] - count_to_remove)

        # Update last_logged_date if this was the last log
        # Check if there are any logs after this date
        later_logs = (
            sb.table("exercise_logs")
            .select("date")
            .eq("exercise_type_id", exercise_type_id)
            .gt("date", log_date)
            .order("date", desc=True)
            .limit(1)
            .execute()
        )

        new_last_date = log_date
        if later_logs.data:
            new_last_date = later_logs.data[0]["date"]
        else:
            # Check for logs on the same date (there might be others)
            same_date_logs = (
                sb.table("exercise_logs")
                .select("date")
                .eq("exercise_type_id", exercise_type_id)
                .eq("date", log_date)
                .limit(1)
                .execute()
            )
            if same_date_logs.data:
                new_last_date = log_date
            else:
                # No logs on this date or later, find the most recent log
                prev_logs = (
                    sb.table("exercise_logs")
                    .select("date")
                    .eq("exercise_type_id", exercise_type_id)
                    .lt("date", log_date)
                    .order("date", desc=True)
                    .limit(1)
                    .execute()
                )
                if prev_logs.data:
                    new_last_date = prev_logs.data[0]["date"]
                else:
                    new_last_date = None

        update_data = {"all_time_total": new_all_time}
        if new_last_date:
            update_data["last_logged_date"] = new_last_date

        sb.table("user_stats").update(update_data).eq("id", curr_stats["id"]).execute()

    return (
        f"✅ Deleted log entry {log_id}\n"
        f"{ex_info['emoji']} <b>{ex_info['display_name']}</b>: -{count_to_remove}\n"
        f"Date: {log_date}"
    )


async def undo_last_log(chat_id: int) -> str:
    """Undo the most recent log entry."""
    sb = get_supabase()

    # Get the most recent log
    res = (
        sb.table("exercise_logs")
        .select("id")
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )

    if not res.data:
        return "❌ No logs found to undo."

    log_id = res.data[0]["id"]
    return await delete_log_entry(log_id, chat_id)


async def process_incoming_message(text: str, chat_id: int):
    # Send typing action immediately
    await send_chat_action(chat_id, "typing")

    # Start typing indicator loop
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(chat_id, stop_typing))

    try:
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
                "<b>Commands:</b>\n"
                "• <code>/undo</code> - Remove last log entry\n"
                "• <code>/recent [N]</code> - Show recent logs (default: 5)\n"
                "• <code>/delete &lt;id&gt;</code> - Delete a specific log\n\n"
                "I'll track your progress and keep you motivated! 💪"
            )
            await send_telegram_message(chat_id, welcome_message)
            return

        # Handle /undo command
        if text_lower == "/undo":
            result = await undo_last_log(chat_id)
            await send_telegram_message(chat_id, result)
            return

        # Handle /recent command
        if text_lower.startswith("/recent"):
            parts = text_lower.split()
            limit = 5
            if len(parts) > 1:
                try:
                    limit = int(parts[1])
                    limit = max(1, min(limit, 20))  # Clamp between 1 and 20
                except ValueError:
                    pass
            result = await get_recent_logs(chat_id, limit)
            await send_telegram_message(chat_id, result)
            return

        # Handle /delete command
        if text_lower.startswith("/delete"):
            parts = text_lower.split()
            if len(parts) < 2:
                await send_telegram_message(
                    chat_id,
                    "❌ Usage: <code>/delete &lt;log_id&gt;</code>\n"
                    "Use <code>/recent</code> to see log IDs.",
                )
                return

            try:
                log_id = int(parts[1])
                result = await delete_log_entry(log_id, chat_id)
                await send_telegram_message(chat_id, result)
            except ValueError:
                await send_telegram_message(
                    chat_id, f"❌ Invalid log ID: {parts[1]}\nLog ID must be a number."
                )
            return

        # 1. Get Definitions (filtered by active challenges)
        sb = get_supabase()
        today_local = datetime.now(TZ).date()

        # Fetch active challenges within current date range
        challenges_res = (
            sb.table("exercise_challenges")
            .select("*")
            .eq("is_active", True)
            .lte("start_date", today_local.isoformat())
            .gte("end_date", today_local.isoformat())
            .execute()
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

        # Determine default exercise based on active challenges
        if len(challenges_data) == 1:
            single_challenge = challenges_data[0]
            default_etype = next(
                (et for et in exercise_types if et.id == single_challenge["exercise_type_id"]),
                None
            )
            default_exercise_name = default_etype.name if default_etype else "pushups"
        else:
            default_exercise_name = "pushups"

        # 2. Parse
        parsed_result = parse_workout_message(text, exercise_types, default_exercise_name)

        if not parsed_result.is_valid:
            await send_telegram_message(
                chat_id, parsed_result.error_reason or "Couldn't understand that workout."
            )
            return

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
    finally:
        # Stop typing indicator
        stop_typing.set()
        await typing_task


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
