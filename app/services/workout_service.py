import logging
import asyncio
import math
from datetime import datetime, date
from html import escape
from typing import List, Dict, Any, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from app.models import ExerciseType, ParseResult, ExerciseEntry
from app.services.openai_service import (
    parse_workout_message,
    parse_exception_prompt,
    generate_motivational_response,
    generate_reminder_motivation,
    LLMUnavailableError,
)
from app.services.deterministic_parser import get_numbers_from_message
from app.services.telegram_client import (
    send_telegram_message,
    send_chat_action,
    send_telegram_message_with_keyboard,
    answer_callback_query,
)
from app.services.habit_reward_client import send_habit_completion, HabitCompletionResponse
from app.config import settings
from src.core import setup_django
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from src.core.repositories import (
    exercise_type_repo,
    challenge_repo,
    challenge_exception_day_repo,
    log_repo,
    user_stats_repo,
    app_settings_repo,
    app_user_repo,
    user_settings_repo,
)
from src.core.validators import sanitize_llm_prompt, validate_telegram_user_id
from src.core.utils import (
    calculate_expected_progress,
    ensure_date,
    expand_exception_dates,
)
from datetime import timedelta
from src.api.services import (
    compute_exercise_stats,
    list_current_active_challenges,
    get_ordered_challenges,
    deactivate_expired_challenges,
    validate_and_prepare_challenge,
    create_challenge,
    list_exception_days,
    add_exception_day,
    remove_exception_day,
    clear_exception_days,
    set_exception_weekdays,
    ExerciseTypeNotFoundError,
)
from src.api.constants import NO_ACTIVE_CHALLENGES_MSG
from app.services.challenge_flow import (
    start_flow,
    start_exception_flow,
    get_flow,
    set_awaiting_confirm,
    clear_flow,
    check_rate_limit,
    record_llm_call,
)

logger = logging.getLogger(__name__)
TZ = ZoneInfo(settings.TZ)
PROGRESS_BAR_WIDTH = 10
REGISTRATION_THROTTLE_SECONDS = 60


def _ensure_orm():
    setup_django()


def _to_app_exercise_type(model) -> ExerciseType:
    return ExerciseType(
        id=model.id,
        name=model.name,
        display_name=model.display_name,
        emoji=model.emoji,
        unit=model.unit,
        aliases=list(model.aliases or []),
    )


def _challenge_model_to_dict(model) -> Dict[str, Any]:
    return {
        "id": model.id,
        "exercise_type_id": model.exercise_type_id,
        "challenge_name": model.challenge_name,
        "start_date": model.start_date.isoformat(),
        "end_date": model.end_date.isoformat(),
        "daily_target": model.daily_target,
        "is_active": model.is_active,
        "is_default": model.is_default,
    }


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


async def get_exercise_types(user_id: Optional[int] = None) -> List[ExerciseType]:
    _ensure_orm()
    types = await exercise_type_repo.get_all(is_active=True, user_id=user_id)
    return [_to_app_exercise_type(t) for t in types]


async def get_active_challenge(
    exercise_type_id: int, current_date: date, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    _ensure_orm()
    challenge = await challenge_repo.get_active_for_type(
        exercise_type_id,
        current_date,
        user_id=user_id,
    )
    if challenge:
        return _challenge_model_to_dict(challenge)
    return None



# calculate_expected_progress, calculate_status_and_deficit, calculate_status
# are imported from src.core.utils


def _is_daily_complete(
    cumulative_total: int,
    daily_target: int,
    day_number: int,
    total_days: int,
) -> bool:
    """Check if on track with cumulative progress for a challenge.

    Args:
        cumulative_total: Total reps/minutes logged so far
        daily_target: Daily target count
        day_number: Current day number in the challenge
        total_days: Total days in the challenge

    Returns:
        True if cumulative progress is on track or ahead, False if behind
    """
    expected = calculate_expected_progress(daily_target, day_number, total_days)
    return cumulative_total >= expected


def _parse_weekdays_csv(value: Any) -> List[int]:
    """Parse the canonical CSV stored on ExerciseChallenge.exception_weekdays."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        return sorted({int(p) for p in parts})
    return sorted({int(w) for w in value})


def _compute_effective_progress(
    start_date: date,
    end_date: date,
    today_local: date,
    weekdays: List[int],
    explicit_dates: set,
) -> Tuple[int, int, bool]:
    """Return (effective_total_days, effective_day_number, is_today_exception).

    Mirrors compute_exercise_stats's effective math so reminders/habit-reward
    consumers can apply identical "skip rest day" semantics without round-tripping
    through the full stats helper.
    """
    total_days = (end_date - start_date).days + 1
    if total_days <= 0:
        return 0, 0, False

    exception_set = expand_exception_dates(
        start_date, end_date, weekdays, explicit_dates
    )
    effective_total_days = max(0, total_days - len(exception_set))

    clamped_today = min(today_local, end_date)
    is_today_exception = today_local in exception_set
    if clamped_today < start_date:
        return effective_total_days, 0, is_today_exception

    cutoff = clamped_today
    if is_today_exception:
        cutoff = today_local - timedelta(days=1)
    if cutoff < start_date:
        return effective_total_days, 0, is_today_exception

    span_days = (cutoff - start_date).days + 1
    if not weekdays and not explicit_dates:
        return effective_total_days, span_days, is_today_exception

    skipped = sum(1 for d in exception_set if start_date <= d <= cutoff)
    return effective_total_days, max(0, span_days - skipped), is_today_exception


async def _check_all_challenges_complete(
    challenges_data: List[Dict],
    today_local: date,
    user_id: Optional[int] = None,
) -> bool:
    """Check if all active challenges are on track with cumulative progress.

    Exception (rest) days are honored: a challenge whose ``today_local`` is a
    rest day never blocks Habit Reward (Feature 0018). Its expected progress is
    computed against the previous scheduled day and the challenge is skipped.

    A day on which *every* active challenge is a rest day is not completable:
    this function returns ``False`` so Habit Reward and ``Day Complete`` do not
    fire when there was no scheduled work (Feature 0019 / issue #29).

    Args:
        challenges_data: List of active challenge dicts. Each dict must contain
            ``id``, ``start_date``, ``end_date``, ``daily_target`` and
            (optionally) ``exception_weekdays`` (CSV string).
        today_local: Current date in local timezone

    Returns:
        True if at least one challenge had scheduled work today and all such
        challenges are on track or ahead; False if any scheduled challenge is
        behind, or if no challenge had scheduled work today.
    """
    if not challenges_data:
        return False

    challenge_ids = [c["id"] for c in challenges_data]
    cumulative_counts = await log_repo.get_cumulative_counts_by_challenge_ids(
        challenge_ids,
        today_local,
        user_id=user_id,
    )
    exception_map = await challenge_exception_day_repo.list_dates_for_challenges(
        challenge_ids,
        user_id=user_id,
    )

    scheduled_seen = False
    for challenge in challenges_data:
        challenge_id = challenge["id"]
        start_date = ensure_date(challenge["start_date"])
        end_date = ensure_date(challenge["end_date"])

        daily_target = challenge["daily_target"]
        weekdays = _parse_weekdays_csv(challenge.get("exception_weekdays", ""))
        explicit_dates = exception_map.get(challenge_id, set())

        effective_total_days, day_number, is_today_exception = _compute_effective_progress(
            start_date, end_date, today_local, weekdays, explicit_dates
        )

        # Rest day: never blocks Habit Reward.
        if is_today_exception:
            continue

        scheduled_seen = True
        cumulative_total = cumulative_counts.get(challenge_id, 0)
        expected = calculate_expected_progress(
            daily_target, day_number, max(1, effective_total_days)
        )
        if cumulative_total < expected:
            return False

    return scheduled_seen


def _format_habit_reward_message(response: HabitCompletionResponse) -> str:
    """Format habit completion response into a Telegram message.

    Args:
        response: Validated HabitCompletionResponse from Habit Reward API

    Returns:
        Formatted HTML message string
    """
    message_parts = []

    # Habit confirmation (escape external data to prevent HTML injection)
    habit_name = escape(response.habit_name)
    message_parts.append(f"✅ <b>Habit completed:</b> {habit_name}")

    # Streak with fire emojis (max 5)
    fire_emoji = "🔥" * min(response.streak_count, 5)
    message_parts.append(f"{fire_emoji} <b>Streak:</b> {response.streak_count} days")

    # Reward status (escape external data to prevent HTML injection)
    if response.got_reward and response.reward:
        reward_name = escape(response.reward.name)
        message_parts.append(f"\n🎁 <b>Reward:</b> {reward_name}")

        # Progress bar for reward pieces
        if response.cumulative_progress:
            earned = response.cumulative_progress.pieces_earned
            required = response.cumulative_progress.pieces_required
            bar_width = 12
            filled = max(0, min(bar_width, round(bar_width * earned / required))) if required > 0 else 0
            bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
            message_parts.append(f"\U0001f4ca <b>Progress:</b> {bar} {earned}/{required}")

            if earned >= required:
                message_parts.append("\u23f3 <b>Reward achieved! You can claim it now!</b>")
    elif response.got_reward and not response.reward:
        logger.warning("API returned got_reward=true but reward=null (possible schema drift)")
        message_parts.append("\n\u274c No reward this time - keep going!")
    else:
        message_parts.append("\n\u274c No reward this time - keep going!")

    return "\n".join(message_parts)


async def notify_habit_reward_if_complete(
    today_local: date, user_id: int, chat_id: Optional[int] = None
) -> bool:
    """Send habit completion to Habit Reward API if all challenges are complete.

    First checks if all active challenges are on track, then uses atomic claim
    pattern to prevent race conditions with concurrent requests.
    Per-user: reads config and tracks idempotency via UserSettings.

    Args:
        today_local: Current date in local timezone
        user_id: The AppUser ID
        chat_id: Optional Telegram chat_id to send notification to

    Returns:
        True if notification was sent successfully or not needed, False on error
    """
    # First check if all challenges are complete
    challenges = await challenge_repo.get_current_active(today_local, user_id=user_id)
    if not challenges:
        logger.debug("No active challenges, skipping habit reward check")
        return True  # No challenges to complete

    # Convert to dict format for _check_all_challenges_complete
    challenges_data = [
        {
            "id": c.id,
            "start_date": c.start_date,
            "end_date": c.end_date,
            "daily_target": c.daily_target,
            "exception_weekdays": getattr(c, "exception_weekdays", "") or "",
        }
        for c in challenges
    ]

    all_complete = await _check_all_challenges_complete(
        challenges_data, today_local, user_id=user_id
    )
    if not all_complete:
        logger.debug("Not all challenges complete, skipping habit reward notification")
        return True  # Not complete yet, but not an error

    # Atomically claim the date - prevents concurrent requests from double-sending
    # NOTE: There's a small race window between checking completion above and claiming below.
    # If a new challenge is added or existing progress changes in this window, we might
    # send the notification prematurely. This is an unlikely edge case with low impact,
    # as the atomic claim ensures we only send once per day regardless.
    claimed = await user_settings_repo.try_claim_habit_reward_date(user_id, today_local)
    if not claimed:
        logger.debug(f"Habit reward already claimed for {today_local}, skipping")
        return True  # Already claimed is considered success

    # Send the completion notification (checks per-user config internally)
    response = await send_habit_completion(user_id, today_local)

    if not response:
        # Clear claim on failure to allow retry
        await user_settings_repo.clear_habit_reward_claim(user_id, today_local)
        logger.warning(f"Habit reward send failed for {today_local}, claim cleared")
        return False

    logger.info(f"Habit reward notification sent for {today_local}")

    # Send Telegram notification if chat_id provided
    if chat_id:
        try:
            message = _format_habit_reward_message(response)
            await send_telegram_message(chat_id, message)
        except Exception as e:
            # Don't fail the whole operation if Telegram message fails
            logger.warning(f"Failed to send habit reward Telegram notification: {e}")

    return True


async def get_exercise_stats_and_message(
    etype: ExerciseType,
    challenge: Optional[Dict],
    today_local: date,
    added_count: int = 0,
    user_id: Optional[int] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Get stats and format HTML message using the shared stats helper.

    This now calls compute_exercise_stats from src.api.services to ensure
    consistent business logic between Telegram and REST API.
    """
    # Convert ExerciseType to dict format expected by compute_exercise_stats
    # Use model_dump() to get all fields from the Pydantic model
    etype_dict = etype.model_dump()

    # Use the shared stats helper with pre-fetched data to avoid duplicate queries
    stats_out = await compute_exercise_stats(
        exercise_type_id=etype.id,
        target_date=today_local,
        added_count=added_count,
        etype=etype_dict,
        challenge=challenge,
        user_id=user_id,
    )

    # Reuse computed daily completion flag from shared stats helper
    daily_complete = stats_out.is_daily_complete

    unit_label = "min" if etype.unit in ["minutes", "min"] else ""

    if stats_out.is_today_exception:
        # Rest-day card: hide the daily ring entirely. Show the cumulative
        # progress line and a banked-reps badge — logs on rest days still
        # add to cumulative_total.
        progress_percent = stats_out.progress_percent / 100.0
        filled_blocks = int(progress_percent * PROGRESS_BAR_WIDTH)
        bar = "█" * filled_blocks + "░" * (PROGRESS_BAR_WIDTH - filled_blocks)

        if added_count > 0:
            if unit_label:
                header = f"🏖️ {etype.emoji} <b>{etype.display_name}</b>: +{added_count} {unit_label}"
            else:
                header = f"🏖️ {etype.emoji} <b>{etype.display_name}</b>: +{added_count}"
        else:
            header = f"🏖️ {etype.emoji} <b>{etype.display_name}</b>"

        msg_part = (
            f"{header}\n"
            f"🏖️ Rest day — banked {stats_out.today_total} "
            f"{unit_label or 'reps'} today\n"
            f"Total: {stats_out.cumulative_total}/{stats_out.target_total}\n"
            f"{bar} {int(stats_out.progress_percent)}%\n"
        )
    else:
        # Format the HTML message from the stats
        progress_percent = stats_out.progress_percent / 100.0  # Convert to 0-1 range
        filled_blocks = int(progress_percent * PROGRESS_BAR_WIDTH)
        bar = "█" * filled_blocks + "░" * (PROGRESS_BAR_WIDTH - filled_blocks)

        # Add checkmark if this challenge is caught up (no deficit)
        checkmark = "✅ " if daily_complete else ""

        # Differentiate formatting based on added_count
        if added_count > 0:
            if unit_label:
                header = f"{checkmark}{etype.emoji} <b>{etype.display_name}</b>: +{added_count} {unit_label}"
            else:
                header = f"{checkmark}{etype.emoji} <b>{etype.display_name}</b>: +{added_count}"
        else:
            header = f"{checkmark}{etype.emoji} <b>{etype.display_name}</b>"

        msg_part = (
            f"{header}\n"
            f"Day {stats_out.day_number}/{stats_out.total_days} • "
            f"Today: {stats_out.today_total} • "
            f"Total: {stats_out.cumulative_total}/{stats_out.target_total}\n"
            f"{bar} {int(stats_out.progress_percent)}%\n"
        )

        # Add catch-up / ahead / on-track message
        if stats_out.catch_up_reps > 0:
            msg_part += f"Need {stats_out.catch_up_reps} more to catch up!\n"
        else:
            # Compute "ahead" amount vs expected cumulative by day_number
            expected = calculate_expected_progress(
                stats_out.daily_target,
                stats_out.day_number,
                max(1, stats_out.total_days),
            )
            diff = stats_out.cumulative_total - expected  # positive means ahead
            ahead_reps = max(0, int(diff))
            if ahead_reps > 0:
                msg_part += f"You're doing great — you are {ahead_reps} reps ahead!\n"
            elif stats_out.today_total == stats_out.daily_target:
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
        "is_daily_complete": daily_complete,
    }

    return msg_part, stats


async def get_recent_logs(user_id: int, limit: int = 5) -> str:
    """Get recent log entries for the user."""
    _ensure_orm()
    logs, _ = await log_repo.get_all(limit=limit, offset=0, user_id=user_id)

    if not logs:
        return "No logs found."

    lines = ["📋 <b>Recent Logs:</b>\n"]
    for log in logs:
        ex_name = getattr(log.exercise_type, "display_name", "Unknown")
        emoji = getattr(log.exercise_type, "emoji", "🏋️")
        log_date = log.date.isoformat()
        count = log.count
        log_id = log.id

        time_str = ""
        if log.timestamp:
            try:
                dt = log.timestamp.astimezone(TZ)
            except (ValueError, AttributeError):
                dt = log.timestamp
            time_str = dt.strftime("%H:%M")

        lines.append(
            f"{emoji} <b>{ex_name}</b>: {count} • {log_date} {time_str}\n"
            f'   ID: <code>{log_id}</code> • "{(log.raw_message or "")[:30]}..."'
        )

    lines.append("\n💡 Use <code>/delete &lt;id&gt;</code> to remove a log")
    return "\n".join(lines)


async def delete_log_entry(log_id: int, user_id: int) -> str:
    """Delete a log entry and update related stats."""
    _ensure_orm()
    log_entry = await log_repo.get_by_id(log_id, user_id=user_id)
    if not log_entry:
        return f"❌ Log entry {log_id} not found."

    exercise_type_id = log_entry.exercise_type_id
    count_to_remove = log_entry.count
    log_date = log_entry.date.isoformat()

    ex_info = {
        "display_name": getattr(log_entry.exercise_type, "display_name", "Exercise"),
        "emoji": getattr(log_entry.exercise_type, "emoji", "🏋️"),
    }

    deleted = await log_repo.delete(log_id, user_id=user_id)
    if not deleted:
        return f"❌ Failed to delete log entry {log_id}."

    await user_stats_repo.decrement_total(
        exercise_type_id,
        count_to_remove,
        user_id=user_id,
    )
    await user_stats_repo.sync_last_logged_date(exercise_type_id, user_id=user_id)

    return (
        f"✅ Deleted log entry {log_id}\n"
        f"{ex_info['emoji']} <b>{ex_info['display_name']}</b>: -{count_to_remove}\n"
        f"Date: {log_date}"
    )


async def undo_last_log(user_id: int) -> str:
    """Undo the most recent log entry."""
    _ensure_orm()
    logs, _ = await log_repo.get_all(limit=1, offset=0, user_id=user_id)
    if not logs:
        return "❌ No logs found to undo."

    log_id = logs[0].id
    return await delete_log_entry(log_id, user_id)


def determine_default_exercise(challenges_data: List[Dict], exercise_types: List[ExerciseType]) -> str:
    """
    Determine the default exercise name based on active challenges.
    
    Logic:
    1. 1 active challenge -> use that challenge's exercise
    2. >1 active challenges -> use the one with is_default=True (lowest ID wins ties)
    3. No active challenges or no defaults -> 'pushups'
    """
    if len(challenges_data) == 1:
        # Single challenge - use it as default
        single_challenge = challenges_data[0]
        default_etype = next(
            (et for et in exercise_types if et.id == single_challenge["exercise_type_id"]),
            None
        )
        return default_etype.name if default_etype else "pushups"
    elif len(challenges_data) > 1:
        # Multiple challenges - look for is_default=True
        # Sort by challenge id (ascending) to get deterministic result for ties
        default_challenges = [c for c in challenges_data if c.get("is_default", False)]
        if default_challenges:
            # Pick the one with lowest challenge_id
            default_challenge = min(default_challenges, key=lambda c: c["id"])
            default_etype = next(
                (et for et in exercise_types if et.id == default_challenge["exercise_type_id"]),
                None
            )
            return default_etype.name if default_etype else "pushups"
        else:
            # No is_default set - fallback to pushups
            return "pushups"
    else:
        # No active challenges
        return "pushups"


async def notify_superusers_of_new_registration(user):
    """
    Send approval request notifications to all configured superusers.

    This function is called when a new user registers via Telegram. It sends each
    superuser a message with the new user's details and approval/rejection commands.

    Args:
        user: The newly registered AppUser instance
    """
    if not settings.SUPERUSER_TELEGRAM_IDS:
        logger.debug("No superusers configured, skipping registration notification")
        return

    notification_message = (
        f"🔔 <b>New User Registration Request</b>\n\n"
        f"<b>Telegram ID:</b> <code>{user.telegram_user_id}</code>\n"
        f"<b>Username:</b> {user.username or 'N/A'}\n"
        f"<b>Name:</b> {user.first_name or 'N/A'}\n"
        f"<b>Registered:</b> {user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else 'N/A'}\n\n"
        f"<b>Actions:</b>\n"
        f"Approve: <code>/approve {user.telegram_user_id}</code>\n"
        f"Reject: <code>/reject {user.telegram_user_id}</code>"
    )

    superusers = await app_user_repo.get_by_telegram_user_ids(
        settings.SUPERUSER_TELEGRAM_IDS
    )
    superusers_by_telegram_id = {
        superuser.telegram_user_id: superuser for superuser in superusers
    }

    # Send to each superuser
    for superuser_id in settings.SUPERUSER_TELEGRAM_IDS:
        try:
            # Get superuser's UserSettings to find their chat_id
            superuser = superusers_by_telegram_id.get(superuser_id)
            if not superuser:
                logger.warning(f"Superuser {superuser_id} not found in database")
                continue

            # Get superuser's chat_id from UserSettings
            try:
                user_settings = superuser.settings
            except ObjectDoesNotExist:
                user_settings = None
            if not user_settings or not user_settings.telegram_chat_id:
                logger.warning(
                    f"Superuser {superuser_id} (user_id={superuser.id}) has no telegram_chat_id in UserSettings"
                )
                continue

            # Send notification
            await send_telegram_message(user_settings.telegram_chat_id, notification_message)
            logger.info(f"Sent registration notification to superuser {superuser_id}")
        except Exception as e:
            logger.error(f"Failed to notify superuser {superuser_id}: {e}")


async def process_incoming_message(
    text: str,
    chat_id: int,
    telegram_user_id: int,
    first_name: str,
    username: Optional[str] = None
):
    # Send typing action immediately
    await send_chat_action(chat_id, "typing")

    # Start typing indicator loop
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(chat_id, stop_typing))

    try:
        _ensure_orm()

        app_settings = await app_settings_repo.get_singleton()

        user = await app_user_repo.get_by_telegram_user_id(telegram_user_id)
        created = False

        if not user:
            if not app_settings.is_registration_open:
                await send_telegram_message(
                    chat_id,
                    "🚫 <b>Registrations are currently closed.</b>\n\n"
                    "Please try again later.",
                )
                return

            # Auto-register user or get existing user
            user, created = await app_user_repo.get_or_create_by_telegram_user_id(
                telegram_user_id=telegram_user_id,
                defaults={
                    "username": username,
                    "first_name": first_name,
                }
            )

        # If new user, log registration and notify superusers
        if created:
            logger.info(f"New user registered: telegram_user_id={telegram_user_id}, user_id={user.id}, status=pending")
            # Notify superusers of the new registration (non-blocking)
            if app_settings.is_registration_open:
                await notify_superusers_of_new_registration(user)

        # Update user fields if they've changed (refreshes stale Telegram data)
        # Check if username or first_name have been updated in Telegram
        fields_to_update = {}
        if user.username != username:
            fields_to_update["username"] = username
        if user.first_name != first_name:
            fields_to_update["first_name"] = first_name

        if fields_to_update:
            await app_user_repo.update(user.id, fields_to_update)
            # Refresh user object with updated fields
            user, _ = await app_user_repo.get_or_create_by_telegram_user_id(telegram_user_id)

        # Update telegram_chat_id for all users (creates UserSettings if needed)
        # This ensures existing users get their chat_id refreshed on every message
        user_settings = await user_settings_repo.update_chat_id(user.id, chat_id)

        if not user.is_approved:
            now = timezone.now()
            if user.last_registration_attempt_at:
                elapsed_seconds = (now - user.last_registration_attempt_at).total_seconds()
                if elapsed_seconds < REGISTRATION_THROTTLE_SECONDS:
                    await send_telegram_message(
                        chat_id,
                        "⏳ <b>Please wait before trying again.</b>\n\n"
                        "You can send one message per minute while your account is pending.",
                    )
                    return

            await app_user_repo.update(
                user.id,
                {"last_registration_attempt_at": now},
            )
            user.last_registration_attempt_at = now

        # Handle commands
        text_lower = text.strip().lower()

        # Strip @botname suffix from commands (e.g. "/challenge@MyBot" -> "/challenge")
        if text_lower.startswith("/") and "@" in text_lower.split()[0]:
            parts = text_lower.split(maxsplit=1)
            cmd = parts[0].split("@")[0]
            text_lower = cmd if len(parts) == 1 else f"{cmd} {parts[1]}"

        # Handle /status command BEFORE approval gate - allow all users to check status
        if text_lower == "/status":
            status_emoji = {
                "pending": "⏳",
                "approved": "✅",
                "rejected": "🚫"
            }.get(user.status, "❓")

            status_text = {
                "pending": "Pending Approval",
                "approved": "Approved",
                "rejected": "Rejected"
            }.get(user.status, "Unknown")

            status_message = (
                f"{status_emoji} <b>Registration Status</b>\n\n"
                f"<b>Status:</b> {status_text}\n"
                f"<b>Telegram ID:</b> <code>{telegram_user_id}</code>\n"
                f"<b>Username:</b> {user.username or 'N/A'}\n"
                f"<b>Registered:</b> {user.created_at.strftime('%Y-%m-%d %H:%M')}"
            )

            if user.approved_at:
                status_message += f"\n<b>Approved:</b> {user.approved_at.strftime('%Y-%m-%d %H:%M')}"

            await send_telegram_message(chat_id, status_message)
            return

        # Check if user is approved - gate all other commands
        if not user.is_approved:
            if user.status == "pending":
                pending_message = (
                    "⏳ <b>Registration Pending</b>\n\n"
                    "Thank you for registering! Your account is pending approval.\n"
                    "You'll be notified once you're approved and can start tracking workouts.\n\n"
                    f"Your Telegram ID: <code>{telegram_user_id}</code>\n\n"
                    "You can use <code>/status</code> to check your approval status."
                )
                await send_telegram_message(chat_id, pending_message)
            elif user.status == "rejected":
                rejected_message = (
                    "🚫 <b>Access Denied</b>\n\n"
                    "Your registration request has been rejected.\n"
                    "Please contact the administrator for more information.\n\n"
                    "You can use <code>/status</code> to see details."
                )
                await send_telegram_message(chat_id, rejected_message)
            return

        if text_lower in ("/start", "/help"):
            is_help = text_lower == "/help"
            header = (
                "📖 <b>Available Commands</b>\n\n"
                if is_help
                else "👋 <b>Welcome to Fitness Challenge Bot!</b>\n\n"
            )
            welcome_message = (
                header
                + "I help you track your workouts. Just send me your exercises:\n\n"
                "Examples:\n"
                "• <code>20 pushups</code>\n"
                "• <code>30 squats</code>\n"
                "• <code>2 min plank</code>\n"
                "• <code>20 pushups and 30 squats</code>\n\n"
                "<b>Commands:</b>\n"
                "• <code>/help</code> - Show this help message\n"
                "• <code>/status</code> - Check your registration status\n"
                "• <code>/challenge</code> - Create a new challenge via AI\n"
                "• <code>/exception</code> - Manage rest days (list/add/remove/clear)\n"
                "• <code>/undo</code> - Remove last log entry\n"
                "• <code>/recent [N]</code> - Show recent logs (default: 5)\n"
                "• <code>/delete &lt;id&gt;</code> - Delete a specific log\n"
            )

            # Add superuser commands if applicable
            if telegram_user_id in settings.SUPERUSER_TELEGRAM_IDS:
                welcome_message += (
                    "\n<b>Admin Commands:</b>\n"
                    "• <code>/approve &lt;telegram_user_id&gt;</code> - Approve user\n"
                    "• <code>/reject &lt;telegram_user_id&gt;</code> - Reject user\n"
                )

            welcome_message += "\nI'll track your progress and keep you motivated! 💪"

            await send_telegram_message(chat_id, welcome_message)
            return

        # Handle /registration command - superuser only
        if text_lower.startswith("/registration"):
            if telegram_user_id not in settings.SUPERUSER_TELEGRAM_IDS:
                await send_telegram_message(
                    chat_id,
                    "🚫 <b>Permission Denied</b>\n\n"
                    "Only superusers can manage registration.",
                )
                return

            parts = text_lower.split()
            if len(parts) == 1 or parts[1] == "status":
                status_text = "ON ✅" if app_settings.is_registration_open else "OFF 🚫"
                await send_telegram_message(
                    chat_id,
                    f"Registration is {status_text}.",
                )
                return

            if parts[1] not in ("on", "off"):
                await send_telegram_message(
                    chat_id,
                    "❌ Usage: <code>/registration on</code> or <code>/registration off</code>\n"
                    "Use <code>/registration status</code> to check current state.",
                )
                return

            is_open = parts[1] == "on"
            app_settings = await app_settings_repo.update(
                {"is_registration_open": is_open}
            )
            status_text = "ON ✅" if app_settings.is_registration_open else "OFF 🚫"
            await send_telegram_message(
                chat_id,
                f"Registration is now {status_text}.",
            )
            return

        # Handle /undo command
        if text_lower == "/undo":
            result = await undo_last_log(user.id)
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
            result = await get_recent_logs(user.id, limit)
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
                result = await delete_log_entry(log_id, user.id)
                await send_telegram_message(chat_id, result)
            except ValueError:
                await send_telegram_message(
                    chat_id, f"❌ Invalid log ID: {parts[1]}\nLog ID must be a number."
                )
            return

        # Handle /challenge command
        if text_lower == "/challenge":
            start_flow(telegram_user_id, chat_id)
            await send_telegram_message(
                chat_id,
                "📋 <b>Create a New Challenge</b>\n\n"
                "Describe your challenge in one message, for example:\n"
                "• <i>100 pushups in 30 days starting tomorrow</i>\n"
                "• <i>500 squats over 2 weeks</i>\n"
                "• <i>3000 pushups in 90 days</i>\n\n"
                "⏱ You have 5 minutes to respond.",
            )
            return

        # Handle /exception command (rest-day management)
        if text_lower == "/exception" or text_lower.startswith("/exception "):
            await _handle_exception_command(
                text, telegram_user_id, user.id, chat_id
            )
            return

        # Check if user is in /challenge flow (awaiting prompt)
        flow = get_flow(telegram_user_id)
        if flow and flow.step == "awaiting_prompt" and not text.startswith("/"):
            await _handle_challenge_prompt(text, telegram_user_id, user.id, chat_id)
            return

        # Handle /status command - show registration status
        if text_lower == "/status":
            status_emoji = {
                "pending": "⏳",
                "approved": "✅",
                "rejected": "🚫"
            }.get(user.status, "❓")

            status_text = {
                "pending": "Pending Approval",
                "approved": "Approved",
                "rejected": "Rejected"
            }.get(user.status, "Unknown")

            status_message = (
                f"{status_emoji} <b>Registration Status</b>\n\n"
                f"<b>Status:</b> {status_text}\n"
                f"<b>Telegram ID:</b> <code>{telegram_user_id}</code>\n"
                f"<b>Username:</b> {user.username or 'N/A'}\n"
                f"<b>Registered:</b> {user.created_at.strftime('%Y-%m-%d %H:%M')}"
            )

            if user.approved_at:
                status_message += f"\n<b>Approved:</b> {user.approved_at.strftime('%Y-%m-%d %H:%M')}"

            await send_telegram_message(chat_id, status_message)
            return

        # Handle /approve command - superuser only
        if text_lower.startswith("/approve"):
            if telegram_user_id not in settings.SUPERUSER_TELEGRAM_IDS:
                await send_telegram_message(
                    chat_id,
                    "🚫 <b>Permission Denied</b>\n\n"
                    "Only superusers can approve users."
                )
                return

            parts = text_lower.split()
            if len(parts) < 2:
                await send_telegram_message(
                    chat_id,
                    "❌ Usage: <code>/approve &lt;telegram_user_id&gt;</code>\n"
                    "Example: <code>/approve 123456789</code>"
                )
                return

            try:
                target_telegram_user_id = int(parts[1])
                validate_telegram_user_id(target_telegram_user_id)
                target_user = await app_user_repo.approve_by_telegram_user_id(target_telegram_user_id)

                if not target_user:
                    await send_telegram_message(
                        chat_id,
                        f"❌ User with Telegram ID <code>{target_telegram_user_id}</code> not found."
                    )
                    return

                await send_telegram_message(
                    chat_id,
                    f"✅ <b>User Approved</b>\n\n"
                    f"<b>User:</b> {target_user.first_name} (@{target_user.username or 'N/A'})\n"
                    f"<b>Telegram ID:</b> <code>{target_telegram_user_id}</code>\n"
                    f"<b>Status:</b> Approved"
                )

                # Notify the approved user
                target_settings = await user_settings_repo.get_by_user_id(target_user.id)
                if target_settings and target_settings.telegram_chat_id:
                    approval_notification = (
                        "🎉 <b>Congratulations!</b>\n\n"
                        "Your account has been approved! You can now start tracking your workouts.\n\n"
                        "Send me a workout like:\n"
                        "• <code>20 pushups</code>\n"
                        "• <code>30 squats</code>\n\n"
                        "Type /start to see all available commands. Let's get started! 💪"
                    )
                    await send_telegram_message(target_settings.telegram_chat_id, approval_notification)

            except ValueError as e:
                await send_telegram_message(
                    chat_id,
                    f"❌ Invalid Telegram User ID: {parts[1]}\n{str(e)}"
                )
            return

        # Handle /reject command - superuser only
        if text_lower.startswith("/reject"):
            if telegram_user_id not in settings.SUPERUSER_TELEGRAM_IDS:
                await send_telegram_message(
                    chat_id,
                    "🚫 <b>Permission Denied</b>\n\n"
                    "Only superusers can reject users."
                )
                return

            parts = text_lower.split()
            if len(parts) < 2:
                await send_telegram_message(
                    chat_id,
                    "❌ Usage: <code>/reject &lt;telegram_user_id&gt;</code>\n"
                    "Example: <code>/reject 123456789</code>"
                )
                return

            try:
                target_telegram_user_id = int(parts[1])
                validate_telegram_user_id(target_telegram_user_id)
                target_user = await app_user_repo.reject_by_telegram_user_id(target_telegram_user_id)

                if not target_user:
                    await send_telegram_message(
                        chat_id,
                        f"❌ User with Telegram ID <code>{target_telegram_user_id}</code> not found."
                    )
                    return

                await send_telegram_message(
                    chat_id,
                    f"🚫 <b>User Rejected</b>\n\n"
                    f"<b>User:</b> {target_user.first_name} (@{target_user.username or 'N/A'})\n"
                    f"<b>Telegram ID:</b> <code>{target_telegram_user_id}</code>\n"
                    f"<b>Status:</b> Rejected"
                )

                # Notify the rejected user
                target_settings = await user_settings_repo.get_by_user_id(target_user.id)
                if target_settings and target_settings.telegram_chat_id:
                    rejection_notification = (
                        "🚫 <b>Registration Update</b>\n\n"
                        "Your registration request has been rejected.\n"
                        "Please contact the administrator for more information."
                    )
                    await send_telegram_message(target_settings.telegram_chat_id, rejection_notification)

            except ValueError as e:
                await send_telegram_message(
                    chat_id,
                    f"❌ Invalid Telegram User ID: {parts[1]}\n{str(e)}"
                )
            return

        # 1. Get Definitions (filtered by active challenges)
        today_local = datetime.now(TZ).date()

        # Fetch active challenges within current date range
        challenges_data = await list_current_active_challenges(
            today_local,
            user_id=user.id,
        )

        if not challenges_data:
            await send_telegram_message(chat_id, NO_ACTIVE_CHALLENGES_MSG)
            return

        # Determine relevant exercise type IDs
        challenge_type_ids = list({c["exercise_type_id"] for c in challenges_data})

        types_models = await exercise_type_repo.get_by_ids(
            challenge_type_ids,
            user_id=user.id,
        )
        types_models = [t for t in types_models if t.is_active]
        types_models.sort(key=lambda x: x.id)
        exercise_types = [_to_app_exercise_type(t) for t in types_models]

        # Build map: type_id -> best challenge
        # Sort challenges by end_date desc so we pick the latest/future one if duplicates
        challenges_data.sort(key=lambda x: x["end_date"], reverse=True)
        challenge_map = {}
        for c in challenges_data:
            tid = c["exercise_type_id"]
            if tid not in challenge_map:
                challenge_map[tid] = c

        # Determine default exercise based on active challenges
        default_exercise_name = determine_default_exercise(challenges_data, exercise_types)

        # 2. Parse (Try fast numbers-only parser first)
        parsed_result = None
        entry_challenge_map = {}  # Map entry index -> challenge dict

        # Check for numbers-only multi-number input
        counts, parse_error = get_numbers_from_message(text)

        if parse_error:
            # Explicit error from fast parser (e.g. decimals)
            parsed_result = ParseResult(entries=[], is_valid=False, error_reason=parse_error)
        elif counts is not None:
            # Valid multi-number input. challenges_data is guaranteed non-empty
            # here (the handler returns early above when there are none).
            ordered_challenges = get_ordered_challenges(challenges_data)
            entries = []

            for i, count in enumerate(counts):
                if i >= len(ordered_challenges):
                    break

                challenge = ordered_challenges[i]
                # Find exercise type
                etype = next((et for et in exercise_types if et.id == challenge["exercise_type_id"]), None)

                if etype:
                    duration_seconds = count * 60 if etype.unit.lower() in {"minute", "minutes"} else None
                    entries.append(ExerciseEntry(
                        exercise_type_name=etype.name,
                        count=count,
                        duration_seconds=duration_seconds,
                        notes=None,
                        confidence=1.0
                    ))
                    # Explicitly map this entry index to this challenge
                    entry_challenge_map[len(entries) - 1] = challenge

            if not entries:
                parsed_result = ParseResult(
                    entries=[],
                    is_valid=False,
                    error_reason="Could not map numbers to active exercises."
                )
            else:
                parsed_result = ParseResult(entries=entries, is_valid=True)

        if not parsed_result:
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
        for i, entry in enumerate(parsed_result.entries):
            # Match exercise type
            etype = next(
                (et for et in exercise_types if et.name == entry.exercise_type_name), None
            )
            if not etype:
                continue  # Should not happen if AI follows constraints

            updated_exercise_ids.add(etype.id)

            # Find Challenge (prefer explicit map from fast parser, fallback to exercise type map)
            if i in entry_challenge_map:
                challenge = entry_challenge_map[i]
            else:
                challenge = challenge_map.get(etype.id)

            # Use Helper to get stats and message
            # Pass pre-fetched challenge to avoid duplicate query
            msg_part, stats = await get_exercise_stats_and_message(
                etype,
                challenge,
                today_local,
                added_count=entry.count,
                user_id=user.id,
            )

            # Store response map keyed by index or something unique?
            # Originally it was keyed by etype.id.
            # If we have multiple entries for same etype.id (e.g. 10 20 squats), response_map[id] gets overwritten.
            # However, logic below constructs final response from exercise_types list.
            # If same exercise type appears twice in entries, we should probably aggregate them or append messages?
            # Current structure assumes 1 message block per exercise type.
            # If I overwrite, I lose previous message.
            # I should append to response_map if exists.
            
            if etype.id in response_map:
                response_map[etype.id] += "\n" + msg_part
            else:
                response_map[etype.id] = msg_part

            # Insert Log
            log_data = {
                "user_id": user.id,
                "exercise_type_id": etype.id,
                "challenge_id": stats["challenge_id"],
                "date": today_local,
                "timestamp": datetime.now(TZ),
                "count": entry.count,
                "cumulative_total": stats["cumulative_total"],
                "day_number": stats["day_number"],
                "status": stats["status"],
                "raw_message": text,
                "duration_seconds": entry.duration_seconds,
                "notes": entry.notes,
            }
            await log_repo.create(log_data)
            await user_stats_repo.increment_total(
                etype.id,
                entry.count,
                today_local,
                user_id=user.id,
            )

            # Generate Witty Comment (using stats from helper).
            # Gated by the per-user is_workout_motivation_active setting: when
            # disabled, skip the LLM call and its fallback entirely so no
            # motivational line is appended. Evening reminders are unaffected.
            if challenge and user_settings.is_workout_motivation_active:
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
            msg_part, _ = await get_exercise_stats_and_message(
                etype,
                challenge,
                today_local,
                added_count=0,
                user_id=user.id,
            )
            response_map[etype.id] = msg_part

        # Check if all active challenges are complete for the day
        all_complete = await _check_all_challenges_complete(
            challenges_data,
            today_local,
            user_id=user.id,
        )

        # Final Response Assembly
        final_parts = []

        # Prepend daily completion indicator if all challenges are complete
        if all_complete:
            final_parts.append("✅ <b>Day Complete!</b>")
            final_parts.append("")  # Add blank line for spacing
            # Notify Habit Reward API (fire-and-forget, non-blocking)
            async def _notify_habit_reward():
                try:
                    await notify_habit_reward_if_complete(
                        today_local, user_id=user.id, chat_id=chat_id
                    )
                except Exception as e:
                    logger.warning(f"Habit reward notification failed: {e}")
            asyncio.create_task(_notify_habit_reward())

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


async def check_daily_reminders(hour: Optional[int] = None):
    """
    Checks active challenges and sends reminders.

    This function serves dual purpose:
    1. Legacy behavior (hour=None): Send simple "missing you" messages for challenges with no logs
    2. New behavior (hour in REMINDER_HOURS): Use evening reminder logic with combined message

    Args:
        hour: Optional reminder hour (must be in REMINDER_HOURS). If provided, uses evening reminder logic.
              If None, uses legacy simple reminder logic.
    """
    _ensure_orm()

    # If hour is specified, use new evening reminder logic
    if hour is not None:
        await send_evening_reminder(hour)
        return

    # Legacy behavior: simple reminder for challenges with no logs
    today_local = datetime.now(TZ).date()

    # Get chat_id from settings or env
    app_settings = await app_settings_repo.get_singleton()
    if not app_settings.is_reminder_active:
        logger.info("Reminders disabled, skipping legacy reminders")
        return

    challenges = await challenge_repo.get_current_active(today_local)

    target_chat_id = app_settings.telegram_chat_id
    if not target_chat_id:
        target_chat_id = settings.TARGET_CHAT_ID
        if not target_chat_id:
            logger.warning("No TARGET_CHAT_ID set for reminders.")
            return

    challenge_ids = [ch.id for ch in challenges]
    today_counts = await log_repo.get_today_counts_by_challenge_ids(
        challenge_ids, today_local
    )
    exception_map = await challenge_exception_day_repo.list_dates_for_challenges(
        challenge_ids
    )

    for ch in challenges:
        # Skip "missing you" reminders on rest days for this challenge.
        weekdays = _parse_weekdays_csv(getattr(ch, "exception_weekdays", "") or "")
        explicit_dates = exception_map.get(ch.id, set())
        exception_set = expand_exception_dates(
            ensure_date(ch.start_date),
            ensure_date(ch.end_date),
            weekdays,
            explicit_dates,
        )
        if today_local in exception_set:
            continue

        # Check if logged today
        today_count = today_counts.get(ch.id, 0)
        if today_count <= 0:
            ex_name = getattr(ch.exercise_type, "display_name", "exercise")
            emoji = getattr(ch.exercise_type, "emoji", "🏋️")
            msg = f"Hey, your {emoji} {ex_name} are missing you today! 🥺"
            await send_telegram_message(target_chat_id, msg)


async def compute_evening_reminder(
    today_local: date, reminder_hour: int
) -> Tuple[bool, Optional[str], int]:
    """
    Compute evening reminder message for incomplete challenges.

    Args:
        today_local: Current date in local timezone
        reminder_hour: Hour of reminder (must be in REMINDER_HOURS)

    Returns:
        Tuple of (should_send, message_html, incomplete_count)
        - should_send: True if there are incomplete challenges and reminder should be sent
        - message_html: HTML formatted message, or None if nothing to send
        - incomplete_count: Number of incomplete challenges
    """
    _ensure_orm()

    # Get active challenges for today
    challenges = await challenge_repo.get_current_active(today_local)
    if not challenges:
        return False, None, 0

    challenge_ids = [ch.id for ch in challenges]
    cumulative_counts = await log_repo.get_cumulative_counts_by_challenge_ids(
        challenge_ids, today_local
    )
    exception_map = await challenge_exception_day_repo.list_dates_for_challenges(
        challenge_ids
    )

    # Determine which challenges are NOT caught up (cumulative behind expected).
    # Challenges whose ``today_local`` is a rest day are skipped entirely.
    incomplete_challenges = []

    for ch in challenges:
        start_date = ensure_date(ch.start_date)
        end_date = ensure_date(ch.end_date)

        daily_target = ch.daily_target
        weekdays = _parse_weekdays_csv(getattr(ch, "exception_weekdays", "") or "")
        explicit_dates = exception_map.get(ch.id, set())

        effective_total_days, day_number, is_today_exception = _compute_effective_progress(
            start_date, end_date, today_local, weekdays, explicit_dates
        )
        if is_today_exception:
            continue

        expected = calculate_expected_progress(
            daily_target, day_number, max(1, effective_total_days)
        )
        cumulative_total = cumulative_counts.get(ch.id, 0)

        if cumulative_total < expected:
            deficit = math.ceil(expected - cumulative_total)
            incomplete_challenges.append({
                "exercise_name": ch.exercise_type.display_name,
                "emoji": ch.exercise_type.emoji,
                "unit": ch.exercise_type.unit,
                "cumulative_total": cumulative_total,
                "expected": math.ceil(expected),
                "deficit": deficit,
            })

    if not incomplete_challenges:
        return False, None, 0

    # Compute left challenges count and remaining totals by unit
    left_challenges_count = len(incomplete_challenges)

    # Group remaining work by unit (e.g., {"reps": 50, "minutes": 15})
    remaining_by_unit: dict[str, int] = {}
    for ch in incomplete_challenges:
        if ch["deficit"] > 0:
            unit = ch["unit"]
            remaining_by_unit[unit] = remaining_by_unit.get(unit, 0) + ch["deficit"]

    # Format remaining summary for LLM (e.g., "50 reps, 15 minutes")
    if remaining_by_unit:
        remaining_summary = ", ".join(f"{v} {k}" for k, v in remaining_by_unit.items())
    else:
        remaining_summary = "some exercises behind schedule"

    # Build cleaner challenge summaries for LLM context
    challenge_summaries = []
    for ch in incomplete_challenges:
        summary = (
            f"{ch['emoji']} {ch['exercise_name']}: "
            f"{ch['cumulative_total']}/{ch['expected']} {ch['unit']} "
            f"(need {ch['deficit']} more to catch up)"
        )
        challenge_summaries.append(summary)

    # Generate motivational message via LLM
    context = {
        "left_challenges_count": left_challenges_count,
        "remaining_summary": remaining_summary,
        "challenge_summaries": challenge_summaries,
        "reminder_hour": reminder_hour,
    }
    try:
        motivation = generate_reminder_motivation(context)
    except Exception as exc:
        logger.error(
            "Failed to generate reminder motivation, using safe fallback",
            exc_info=exc,
        )
        motivation = "Time to complete today's challenges! 💪"

    # Build HTML message
    header_time = f"{reminder_hour}:00"
    message_lines = [
        f"<b>🔔 Evening Reminder ({header_time})</b>",
        "",
    ]

    for ch in incomplete_challenges:
        unit_display = ch["unit"] if ch["deficit"] != 1 else ch["unit"].rstrip('s')
        message_lines.append(
            f"• {ch['emoji']} <b>{ch['exercise_name']}</b>: "
            f"{ch['cumulative_total']}/{ch['expected']} {ch['unit']} "
            f"(need {ch['deficit']} more {unit_display} to catch up)"
        )

    message_lines.append("")
    message_lines.append(f"<i>{motivation}</i>")

    message_html = "\n".join(message_lines)

    return True, message_html, left_challenges_count


async def send_evening_reminder(reminder_hour: int):
    """
    Send evening reminder at specified hour.

    Checks if reminder is enabled, if already sent today, and if there are incomplete challenges.
    Sends one combined message via Telegram if needed.

    Args:
        reminder_hour: Hour to send reminder (must be in REMINDER_HOURS)
    """
    _ensure_orm()

    # Best-effort data hygiene: clear expired is_active flags for all users.
    # Runs even when reminders are disabled. Fail open — never block reminders.
    try:
        await deactivate_expired_challenges()
    except Exception:
        # Best-effort hygiene; an expected, handled failure — warn (with trace)
        # rather than log at ERROR, since it never impacts reminder delivery.
        logger.warning(
            "Failed to deactivate expired challenges during reminder sweep",
            exc_info=True,
        )

    # Get settings
    app_settings = await app_settings_repo.get_singleton()

    # Check if reminders are active
    if not app_settings.is_reminder_active:
        logger.info(f"Reminders disabled, skipping {reminder_hour}:00 reminder")
        return

    # Check if we have a chat_id
    chat_id = app_settings.telegram_chat_id
    if not chat_id:
        # Fallback to env var if available
        chat_id = settings.TARGET_CHAT_ID
        if not chat_id:
            logger.warning("No telegram_chat_id configured for reminders")
            return

    # Get today in local timezone
    today_local = datetime.now(TZ).date()

    # Atomically claim this hour to avoid duplicate sends across workers
    claimed = await app_settings_repo.try_mark_hour_sent(today_local, reminder_hour)
    if not claimed:
        logger.info(f"Reminder for {reminder_hour}:00 already sent/claimed, skipping")
        return

    try:
        # Compute reminder message
        should_send, message_html, incomplete_count = await compute_evening_reminder(
            today_local, reminder_hour
        )

        if not should_send:
            logger.info(
                f"No incomplete challenges at {reminder_hour}:00, no reminder sent"
            )
            return

        # Send reminder
        logger.info(
            f"Sending {reminder_hour}:00 reminder: {incomplete_count} incomplete challenge(s)"
        )
        result = await send_telegram_message(chat_id, message_html, parse_mode="HTML")

        # If Telegram send failed, clear the claim to allow retry
        if result is None:
            await app_settings_repo.clear_hour_sent(today_local, reminder_hour)
            logger.warning(
                f"Telegram send failed for {reminder_hour}:00 reminder, will retry next run"
            )
        else:
            logger.info(f"Marked {reminder_hour}:00 reminder as sent")
    except Exception:
        await app_settings_repo.clear_hour_sent(today_local, reminder_hour)
        logger.exception(
            "Unexpected error during reminder computation/send; claim cleared"
        )
        raise


# =============================================================================
# Challenge creation flow (Telegram /challenge command)
# =============================================================================


_WEEKDAY_NAMES = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}


def _format_challenge_preview(parsed, challenge_data) -> str:
    """Format a challenge preview message for Telegram.

    Includes any exception (rest) days extracted from the prompt and uses
    the *effective* day count for the target_total so the preview cannot
    disagree with the eventual "Challenge Created" message.
    """
    total_days = (challenge_data.end_date - challenge_data.start_date).days + 1
    weekdays = list(challenge_data.exception_weekdays or [])
    explicit_dates = list(challenge_data.exception_dates or [])
    exception_set = expand_exception_dates(
        challenge_data.start_date,
        challenge_data.end_date,
        weekdays,
        explicit_dates,
    )
    effective_days = max(0, total_days - len(exception_set))
    target_total = challenge_data.daily_target * effective_days

    lines = [
        "📋 <b>New Challenge Preview</b>",
        "",
        f"📝 <b>Name:</b> {escape(parsed.challenge_name)}",
        f"🏋️ <b>Exercise:</b> {escape(parsed.exercise_type_name)}",
        f"📅 <b>Start:</b> {challenge_data.start_date}",
        f"📅 <b>End:</b> {challenge_data.end_date}",
        f"🗓 <b>Days:</b> {effective_days} active / {total_days} calendar",
        f"🎯 <b>Total target:</b> {target_total:,}",
        f"📊 <b>Daily target:</b> ~{challenge_data.daily_target:,}/day",
    ]
    if weekdays:
        names = ", ".join(_WEEKDAY_NAMES[w] for w in weekdays)
        lines.append(f"🏖️ <b>Rest weekdays:</b> {names}")
    if explicit_dates:
        date_strs = ", ".join(d.isoformat() for d in explicit_dates)
        lines.append(f"🏖️ <b>Rest dates:</b> {date_strs}")
    lines.append("")
    lines.append("Ready to create this challenge?")
    return "\n".join(lines)


CONFIRM_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "✅ Confirm", "callback_data": "confirm_challenge"},
            {"text": "❌ Cancel", "callback_data": "cancel_challenge"},
        ]
    ]
}


async def _handle_challenge_prompt(
    text: str, telegram_user_id: int, user_id: int, chat_id: int
) -> None:
    """Handle the user's natural language challenge description."""
    if not check_rate_limit(telegram_user_id):
        clear_flow(telegram_user_id)
        await send_telegram_message(
            chat_id,
            "⚠️ You've reached the limit of 10 challenge creations per hour. "
            "Please try again later.",
        )
        return

    # Run the same homoglyph/prompt-injection filter the REST endpoint
    # applies via ChallengePromptRequest. Without this, Telegram bypasses
    # the Pydantic validator entirely and jailbreak attempts reach the LLM.
    # Check happens BEFORE record_llm_call so a rejection does not
    # consume the user's hourly LLM budget.
    try:
        text = sanitize_llm_prompt(text)
    except ValueError:
        clear_flow(telegram_user_id)
        await send_telegram_message(
            chat_id,
            "❌ Your message contains patterns we can't process. "
            "Please rephrase and try again.",
        )
        return

    await send_chat_action(chat_id)
    record_llm_call(telegram_user_id)

    try:
        parsed, challenge_data = await validate_and_prepare_challenge(text, user_id)
    except LLMUnavailableError:
        clear_flow(telegram_user_id)
        await send_telegram_message(
            chat_id,
            "⚠️ AI service is temporarily unavailable. Please try again later.",
        )
        return
    except ExerciseTypeNotFoundError as e:
        clear_flow(telegram_user_id)
        available = ", ".join(e.available_names) if e.available_names else "none"
        await send_telegram_message(
            chat_id,
            f"❌ Exercise type '<b>{escape(e.exercise_type_name)}</b>' not found.\n\n"
            f"Your available types: {escape(available)}\n\n"
            "Send /challenge to try again.",
        )
        return
    except ValueError as e:
        clear_flow(telegram_user_id)
        await send_telegram_message(
            chat_id,
            f"❌ {escape(str(e))}\n\nSend /challenge to try again.",
        )
        return

    set_awaiting_confirm(telegram_user_id, parsed, challenge_data)

    preview = _format_challenge_preview(parsed, challenge_data)
    await send_telegram_message_with_keyboard(
        chat_id, preview, CONFIRM_KEYBOARD
    )


async def process_callback_query(
    callback_query_id: str,
    data: str,
    telegram_user_id: int,
    chat_id: int,
) -> None:
    """Handle inline button presses for the /challenge and /exception flows.

    Uses the flow ``kind`` discriminator so an in-flight ``/challenge`` cannot
    be confirmed by an ``/exception`` callback (or vice-versa).
    """
    _ensure_orm()

    flow = get_flow(telegram_user_id)

    if data in ("confirm_challenge", "cancel_challenge"):
        if (
            not flow
            or flow.kind != "challenge"
            or flow.step != "awaiting_confirm"
            or not flow.challenge_data
        ):
            await answer_callback_query(
                callback_query_id, "Session expired. Send /challenge to start again."
            )
            return

        target_chat_id = flow.chat_id

        if data == "confirm_challenge":
            try:
                user = await app_user_repo.get_by_telegram_user_id(telegram_user_id)
                if not user or not user.is_approved:
                    await answer_callback_query(callback_query_id, "User not found or not approved.")
                    clear_flow(telegram_user_id)
                    return

                result = await create_challenge(flow.challenge_data, user_id=user.id)
                clear_flow(telegram_user_id)

                # result.target_total is already computed against effective days,
                # so the success message cannot disagree with the preview.
                await send_telegram_message(
                    target_chat_id,
                    f"✅ <b>Challenge Created!</b>\n\n"
                    f"📝 <b>{escape(result.challenge_name)}</b>\n"
                    f"🎯 {result.target_total:,} total · ~{result.daily_target:,}/day\n"
                    f"📅 {result.start_date} → {result.end_date}\n\n"
                    "Good luck! 💪",
                )
                await answer_callback_query(callback_query_id, "Challenge created!")

            except Exception as e:
                clear_flow(telegram_user_id)
                logger.exception("Failed to create challenge: %s: %s", type(e).__name__, e)
                await send_telegram_message(
                    target_chat_id,
                    "❌ Failed to create challenge. Please try again later or contact support.",
                )
                await answer_callback_query(callback_query_id, "Error creating challenge.")

        else:  # cancel_challenge
            clear_flow(telegram_user_id)
            await send_telegram_message(
                target_chat_id, "❌ Challenge creation cancelled."
            )
            await answer_callback_query(callback_query_id, "Cancelled.")

    elif data in ("confirm_exception", "cancel_exception"):
        if (
            not flow
            or flow.kind != "exception"
            or flow.step != "awaiting_confirm"
            or not flow.exception_payload
        ):
            await answer_callback_query(
                callback_query_id,
                "Session expired. Send /exception add ... to start again.",
            )
            return

        target_chat_id = flow.chat_id

        if data == "confirm_exception":
            try:
                user = await app_user_repo.get_by_telegram_user_id(telegram_user_id)
                if not user or not user.is_approved:
                    await answer_callback_query(callback_query_id, "User not found or not approved.")
                    clear_flow(telegram_user_id)
                    return

                payload = flow.exception_payload
                challenge_id = payload["challenge_id"]

                # Apply weekday set if present (replace).
                if payload.get("weekdays"):
                    await set_exception_weekdays(
                        challenge_id, payload["weekdays"], user_id=user.id
                    )

                # Apply each one-off date — idempotent add() preserves any
                # existing rows that the user did not mention.
                added = 0
                for entry in payload.get("dates", []):
                    try:
                        await add_exception_day(
                            challenge_id,
                            entry["date"],
                            entry.get("reason") or "",
                            user_id=user.id,
                        )
                        added += 1
                    except ValueError as ve:
                        logger.warning("Skipping out-of-window exception date: %s", ve)

                clear_flow(telegram_user_id)
                await send_telegram_message(
                    target_chat_id,
                    f"✅ Exception days saved ({added} one-off + "
                    f"{len(payload.get('weekdays', []))} recurring weekday).",
                )
                await answer_callback_query(callback_query_id, "Saved.")
            except Exception as e:
                clear_flow(telegram_user_id)
                logger.exception("Failed to save exception days: %s: %s", type(e).__name__, e)
                await send_telegram_message(
                    target_chat_id,
                    "❌ Failed to save exception days. Please try again later.",
                )
                await answer_callback_query(callback_query_id, "Error saving exceptions.")

        else:  # cancel_exception
            clear_flow(telegram_user_id)
            await send_telegram_message(
                target_chat_id, "❌ Exception update cancelled."
            )
            await answer_callback_query(callback_query_id, "Cancelled.")

    else:
        await answer_callback_query(callback_query_id)


# =============================================================================
# /exception command — manage rest days
# =============================================================================


EXCEPTION_CONFIRM_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "✅ Confirm", "callback_data": "confirm_exception"},
            {"text": "❌ Cancel", "callback_data": "cancel_exception"},
        ]
    ]
}


_EXCEPTION_USAGE = (
    "🏖️ <b>/exception — manage rest days</b>\n\n"
    "Subcommands:\n"
    "• <code>/exception list</code> — show current rest days\n"
    "• <code>/exception add &lt;text&gt;</code> — add rest days (e.g. <i>weekends</i>, "
    "<i>Apr 20 Easter Monday</i>)\n"
    "• <code>/exception remove YYYY-MM-DD</code> — delete a single date\n"
    "• <code>/exception clear</code> — remove all rest days\n\n"
    "Operates on your default challenge."
)


async def _resolve_default_challenge(user_id: int):
    """Return the user's default challenge model, or None.

    Uses ``is_default=True`` per the plan — no disambiguation keyboard.
    """
    challenges = await challenge_repo.get_all(
        filters={"is_default": True}, user_id=user_id
    )
    return challenges[0] if challenges else None


def _format_exception_list(
    challenge,
    rows: List[Any],
) -> str:
    """Render the full set of recurring + one-off rest days for a challenge."""
    weekdays = _parse_weekdays_csv(getattr(challenge, "exception_weekdays", "") or "")
    explicit = [r.date for r in rows]
    exception_set = expand_exception_dates(
        challenge.start_date, challenge.end_date, weekdays, explicit
    )
    total_days = (challenge.end_date - challenge.start_date).days + 1
    effective_days = max(0, total_days - len(exception_set))

    lines = [
        "🏖️ <b>Rest days</b>",
        f"📝 {escape(challenge.challenge_name)}",
        f"📅 {challenge.start_date} → {challenge.end_date}",
        f"🗓 {effective_days} active / {total_days} calendar days",
        "",
    ]
    if weekdays:
        names = ", ".join(_WEEKDAY_NAMES[w] for w in weekdays)
        lines.append(f"🔁 <b>Recurring weekdays:</b> {names}")
    else:
        lines.append("🔁 <b>Recurring weekdays:</b> none")

    if rows:
        lines.append("")
        lines.append("📌 <b>One-off dates:</b>")
        for row in rows:
            line = f"• {row.date.isoformat()}"
            if row.reason:
                line += f" — {escape(row.reason)}"
            lines.append(line)
    else:
        lines.append("📌 <b>One-off dates:</b> none")

    return "\n".join(lines)


def _format_exception_preview(
    challenge,
    weekdays: List[int],
    dates: List[Dict[str, Any]],
) -> str:
    """Render the Confirm/Cancel preview for ``/exception add``."""
    # Combine the proposed weekday set with the existing one — set_exception_weekdays
    # is a REPLACE operation, but the preview should show what the user is choosing.
    new_weekdays = sorted(set(weekdays)) if weekdays else []

    # Compute effective days assuming the new state will be applied additively
    # over current one-off rows. We don't have the existing row set here; pass
    # only the proposed dates so the preview reflects the *delta* the user asked for.
    explicit = [d["date"] for d in dates]
    proposed_set = expand_exception_dates(
        challenge.start_date, challenge.end_date, new_weekdays, explicit
    )
    total_days = (challenge.end_date - challenge.start_date).days + 1
    effective_after = max(0, total_days - len(proposed_set))

    lines = [
        "🏖️ <b>Add rest days?</b>",
        f"📝 {escape(challenge.challenge_name)}",
        "",
    ]
    if new_weekdays:
        names = ", ".join(_WEEKDAY_NAMES[w] for w in new_weekdays)
        lines.append(f"🔁 <b>Recurring weekdays (replaces existing):</b> {names}")
    if dates:
        lines.append("📌 <b>One-off dates:</b>")
        for d in dates:
            line = f"• {d['date'].isoformat()}"
            if d.get("reason"):
                line += f" — {escape(d['reason'])}"
            lines.append(line)
    if not new_weekdays and not dates:
        lines.append("(nothing to add)")

    lines.append("")
    lines.append(
        f"🗓 New effective days: {effective_after} of {total_days} "
        f"(based on this change alone)"
    )
    lines.append("")
    lines.append("Apply these rest days?")
    return "\n".join(lines)


async def _handle_exception_command(
    text: str,
    telegram_user_id: int,
    user_id: int,
    chat_id: int,
) -> None:
    """Top-level dispatcher for the ``/exception`` Telegram command."""
    _ensure_orm()

    parts = text.split(maxsplit=2)
    # parts[0] = "/exception"
    sub = parts[1].lower() if len(parts) >= 2 else ""

    challenge = await _resolve_default_challenge(user_id)

    if sub == "":
        await send_telegram_message(chat_id, _EXCEPTION_USAGE)
        return

    if challenge is None:
        await send_telegram_message(
            chat_id,
            "❌ No default challenge found.\n\n"
            "Create one with <code>/challenge</code>, then mark it as default "
            "via the admin or API before using <code>/exception</code>.",
        )
        return

    if sub == "list":
        rows = await list_exception_days(challenge.id, user_id=user_id)
        # list_exception_days returns ChallengeExceptionDayOut, but
        # _format_exception_list expects objects with .date and .reason
        # — those attributes exist on the Out model too.
        await send_telegram_message(chat_id, _format_exception_list(challenge, rows))
        return

    if sub == "clear":
        await clear_exception_days(challenge.id, user_id=user_id)
        await send_telegram_message(
            chat_id, "✅ All rest days cleared for your default challenge."
        )
        return

    if sub == "remove":
        if len(parts) < 3:
            await send_telegram_message(
                chat_id,
                "❌ Usage: <code>/exception remove YYYY-MM-DD</code>",
            )
            return
        try:
            target_date = date.fromisoformat(parts[2].strip())
        except ValueError:
            await send_telegram_message(
                chat_id,
                f"❌ Invalid date '<code>{escape(parts[2])}</code>'. "
                "Expected ISO format YYYY-MM-DD.",
            )
            return
        removed = await remove_exception_day(
            challenge.id, target_date, user_id=user_id
        )
        if removed:
            await send_telegram_message(
                chat_id, f"✅ Removed rest day {target_date.isoformat()}."
            )
        else:
            await send_telegram_message(
                chat_id,
                f"ℹ️ No rest day on {target_date.isoformat()} to remove.",
            )
        return

    if sub == "add":
        if len(parts) < 3 or not parts[2].strip():
            await send_telegram_message(
                chat_id,
                "❌ Usage: <code>/exception add &lt;description&gt;</code>\n"
                "Example: <code>/exception add weekends</code>",
            )
            return
        await _handle_exception_prompt(
            parts[2], challenge, telegram_user_id, user_id, chat_id
        )
        return

    # Unknown subcommand
    await send_telegram_message(chat_id, _EXCEPTION_USAGE)


async def _handle_exception_prompt(
    text: str,
    challenge,
    telegram_user_id: int,
    user_id: int,
    chat_id: int,
) -> None:
    """LLM-parse free-text rest days and stage a Confirm/Cancel preview."""
    if not check_rate_limit(telegram_user_id):
        await send_telegram_message(
            chat_id,
            "⚠️ You've reached the limit of 10 AI calls per hour. "
            "Please try again later.",
        )
        return

    # Same homoglyph/prompt-injection filter ``/challenge`` uses — the
    # ``parse_exception_prompt`` system prompt has its own ignore-instructions
    # wording as a second layer, but we still want to bail out before the
    # LLM call (cheaper, keeps LLM budget intact, never sees jailbreak text).
    try:
        text = sanitize_llm_prompt(text)
    except ValueError:
        await send_telegram_message(
            chat_id,
            "❌ Your message contains patterns we can't process. "
            "Please rephrase and try again.",
        )
        return

    await send_chat_action(chat_id)
    record_llm_call(telegram_user_id)

    # Resolve relative phrases ("tomorrow", "next Friday") against the
    # configured app timezone, not the host's local time. Otherwise users in
    # non-UTC deployments can see "tomorrow" land on the wrong day around
    # local midnight.
    today_local = datetime.now(TZ).date()

    try:
        parsed = await parse_exception_prompt(
            text,
            challenge_window=(challenge.start_date, challenge.end_date),
            today=today_local,
        )
    except LLMUnavailableError:
        await send_telegram_message(
            chat_id,
            "⚠️ AI service is temporarily unavailable. Please try again later.",
        )
        return

    if not parsed.get("is_valid"):
        reason = parsed.get("error_reason") or "Could not parse rest days from your message."
        await send_telegram_message(
            chat_id,
            f"❌ {escape(str(reason))}\n\n"
            "Try something like <code>/exception add weekends</code> "
            "or <code>/exception add Apr 20 Easter Monday</code>.",
        )
        return

    raw_weekdays = parsed.get("exception_weekdays") or []
    weekdays: List[int] = []
    for w in raw_weekdays:
        try:
            iv = int(w)
            if 1 <= iv <= 7:
                weekdays.append(iv)
        except (TypeError, ValueError):
            continue
    weekdays = sorted(set(weekdays))

    raw_dates = parsed.get("exception_dates") or []
    dates_payload: List[Dict[str, Any]] = []
    for entry in raw_dates:
        if not isinstance(entry, dict):
            continue
        raw_date = entry.get("date")
        if not raw_date:
            continue
        try:
            d = date.fromisoformat(str(raw_date))
        except ValueError:
            continue
        # Drop out-of-window
        if not (challenge.start_date <= d <= challenge.end_date):
            continue
        dates_payload.append({"date": d, "reason": entry.get("reason") or ""})

    if not weekdays and not dates_payload:
        await send_telegram_message(
            chat_id,
            "❌ I couldn't extract any rest days from that. "
            "Try <code>/exception add weekends</code> "
            "or <code>/exception add Apr 20</code>.",
        )
        return

    start_exception_flow(
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        challenge_id=challenge.id,
        weekdays=weekdays,
        dates=dates_payload,
    )

    preview = _format_exception_preview(challenge, weekdays, dates_payload)
    await send_telegram_message_with_keyboard(
        chat_id, preview, EXCEPTION_CONFIRM_KEYBOARD
    )
