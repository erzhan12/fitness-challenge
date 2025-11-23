import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from app.dependencies import get_supabase
from app.models import ExerciseType, ExerciseEntry
from app.services.openai_service import parse_workout_message, generate_motivational_response
from app.services.telegram_client import send_telegram_message
from app.config import settings

logger = logging.getLogger(__name__)
TZ = ZoneInfo(settings.TZ)

async def get_exercise_types() -> List[ExerciseType]:
    sb = get_supabase()
    # Supabase-py: select("*").execute() returns .data
    res = sb.table("exercise_types").select("*").eq("is_active", True).execute()
    return [ExerciseType(**row) for row in res.data]

def get_active_challenge(exercise_type_id: int, current_date: date) -> Optional[Dict]:
    sb = get_supabase()
    res = sb.table("exercise_challenges") \
            .select("*") \
            .eq("exercise_type_id", exercise_type_id) \
            .eq("is_active", True) \
            .lte("start_date", current_date.isoformat()) \
            .gte("end_date", current_date.isoformat()) \
            .execute()
    
    if res.data:
        return res.data[0]
    return None

def calculate_status(cumulative: int, target_total: int, day_number: int, total_days: int, daily_target: Optional[int]) -> str:
    if daily_target:
        expected = daily_target * day_number
    else:
        expected = (target_total / total_days) * day_number
    
    diff = cumulative - expected
    threshold = (daily_target or (target_total/total_days)) * 0.5 # loose threshold
    
    if diff > threshold:
        return "ahead"
    elif diff < -threshold:
        return "behind"
    else:
        return "on_track"

async def process_incoming_message(text: str, chat_id: int):
    # 1. Get Definitions
    exercise_types = await get_exercise_types()
    
    # 2. Parse
    parsed_result = parse_workout_message(text, exercise_types)
    
    if not parsed_result.is_valid:
        await send_telegram_message(chat_id, parsed_result.error_reason or "Couldn't understand that workout.")
        return

    sb = get_supabase()
    today_local = datetime.now(TZ).date()
    response_parts = []
    witty_comments = []

    # 3. Process Each Entry
    for entry in parsed_result.entries:
        # Match exercise type
        etype = next((et for et in exercise_types if et.name == entry.exercise_type_name), None)
        if not etype:
            continue # Should not happen if AI follows constraints

        # Find Challenge
        challenge = get_active_challenge(etype.id, today_local)
        
        # Defaults if no challenge
        challenge_id = None
        day_number = 1
        total_days = 30
        target_total = 1000 # arbitrary default
        daily_target = 33
        
        if challenge:
            challenge_id = challenge['id']
            start_date = date.fromisoformat(challenge['start_date'])
            end_date = date.fromisoformat(challenge['end_date'])
            day_number = (today_local - start_date).days + 1
            total_days = (end_date - start_date).days + 1
            target_total = challenge['target_total']
            daily_target = challenge.get('daily_target')

        # Calculate Cumulative (Pre-insertion query or sum after)
        # Better: Get current cumulative sum, then add new count
        # This is a slight race condition risk but acceptable for single user
        logs_res = sb.table("exercise_logs") \
                     .select("count") \
                     .eq("challenge_id", challenge_id) \
                     .execute()
        current_total = sum(r['count'] for r in logs_res.data) if challenge_id else 0
        new_cumulative = current_total + entry.count
        
        # Determine Status
        status = calculate_status(new_cumulative, target_total, day_number, total_days, daily_target)
        
        # Insert Log
        log_data = {
            "exercise_type_id": etype.id,
            "challenge_id": challenge_id,
            "date": today_local.isoformat(),
            "timestamp": datetime.now(TZ).isoformat(),
            "count": entry.count,
            "cumulative_total": new_cumulative,
            "day_number": day_number,
            "status": status,
            "raw_message": text,
            "duration_seconds": entry.duration_seconds,
            "notes": entry.notes
        }
        sb.table("exercise_logs").insert(log_data).execute()
        
        # Upsert User Stats (Simplified for now - just total)
        # Check existing
        stats_res = sb.table("user_stats").select("*").eq("exercise_type_id", etype.id).execute()
        if stats_res.data:
            curr_stats = stats_res.data[0]
            new_all_time = curr_stats['all_time_total'] + entry.count
            # Streak logic omitted for brevity, can add later
            sb.table("user_stats").update({"all_time_total": new_all_time, "last_logged_date": today_local.isoformat()}).eq("id", curr_stats['id']).execute()
        else:
            sb.table("user_stats").insert({
                "exercise_type_id": etype.id, 
                "all_time_total": entry.count,
                "last_logged_date": today_local.isoformat()
            }).execute()

        # Get today's specific total for response
        today_logs = sb.table("exercise_logs").select("count").eq("exercise_type_id", etype.id).eq("date", today_local.isoformat()).execute()
        today_total = sum(r['count'] for r in today_logs.data)

        # Generate Witty Comment
        if challenge:
            comment = generate_motivational_response(etype.display_name, {
                "status": status,
                "today_total": today_total,
                "day_number": day_number,
                "streak": "N/A"
            })
            witty_comments.append(comment)

        # Build Response String Component
        progress_percent = min(1.0, new_cumulative / target_total) if target_total > 0 else 0
        filled_blocks = int(progress_percent * 10)
        bar = "█" * filled_blocks + "░" * (10 - filled_blocks)
        
        unit_label = "min" if etype.unit in ['minutes', 'min'] else ""
        
        msg_part = (
            f"{etype.emoji} <b>{etype.display_name}</b>: +{entry.count} {unit_label}\n"
            f"Day {day_number}/{total_days} • Today: {today_total} • Total: {new_cumulative}/{target_total}\n"
            f"[{bar}] {int(progress_percent * 100)}%\n"
        )
        response_parts.append(msg_part)

    # Final Response Assembly
    full_response = "\n".join(response_parts)
    if witty_comments:
        full_response += f"\n<i>{witty_comments[-1]}</i>" # Just take the last one or random one
        
    await send_telegram_message(chat_id, full_response)

async def check_daily_reminders():
    """
    Checks active challenges. If no log for today, send a reminder.
    """
    sb = get_supabase()
    today_local = datetime.now(TZ).date()
    
    # Get active challenges
    res = sb.table("exercise_challenges") \
            .select("*, exercise_types(name, emoji, display_name)") \
            .eq("is_active", True) \
            .lte("start_date", today_local.isoformat()) \
            .gte("end_date", today_local.isoformat()) \
            .execute()
            
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
        logs = sb.table("exercise_logs") \
                 .select("id") \
                 .eq("challenge_id", ch['id']) \
                 .eq("date", today_local.isoformat()) \
                 .execute()
                 
        if not logs.data:
            # Send Reminder
            ex_name = ch['exercise_types']['display_name']
            emoji = ch['exercise_types']['emoji']
            msg = f"Hey, your {emoji} {ex_name} are missing you today! 🥺"
            await send_telegram_message(target_chat_id, msg)


