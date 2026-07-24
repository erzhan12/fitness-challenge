"""Internal scheduler for evening reminders across per-user reminder hours."""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from app.config import settings
from app.constants import DEFAULT_REMINDER_HOURS
from app.services.workout_service import send_evening_reminder
from src.core.repositories import user_settings_repo

logger = logging.getLogger(__name__)
TZ = ZoneInfo(settings.TZ)
HEARTBEAT_INTERVAL_SECONDS = 60

last_scheduler_heartbeat: Optional[datetime] = None


def _update_heartbeat() -> None:
    global last_scheduler_heartbeat
    last_scheduler_heartbeat = datetime.now(TZ)


async def get_next_reminder_time() -> tuple[datetime, int]:
    """
    Calculate the next scheduled reminder time from the union of active
    per-user reminder hours (any hour 0-23, not fixed to 9/10/11pm).

    Falls back to DEFAULT_REMINDER_HOURS for sleep timing only when no
    active user schedules exist yet -- send_evening_reminder() is a no-op
    when it finds no matching users for that hour, so this never causes a
    spurious send.

    Returns:
        Tuple of (next_datetime, hour)
        - next_datetime: datetime of next reminder in local timezone
        - hour: hour of the reminder
    """
    now = datetime.now(TZ)
    today = now.date()

    active_hours = await user_settings_repo.get_distinct_active_reminder_hours()
    hours = sorted(set(active_hours)) if active_hours else sorted(set(DEFAULT_REMINDER_HOURS))

    # Check each candidate hour for today (strict > now).
    for hour in hours:
        reminder_time = datetime.combine(today, time(hour=hour, minute=0), tzinfo=TZ)
        if reminder_time > now:
            return reminder_time, hour

    # All candidate hours for today have passed, schedule the earliest one tomorrow.
    tomorrow = today + timedelta(days=1)
    first_hour = hours[0]
    next_reminder = datetime.combine(tomorrow, time(hour=first_hour, minute=0), tzinfo=TZ)
    return next_reminder, first_hour


async def start_reminder_scheduler():
    """
    Background task that runs evening reminders across the union of active
    per-user reminder hours.

    Maintains a single "locked" target (current_target_time, current_hour) at
    a time. The locked target is checked for due-ness before any
    configuration re-read, so a re-evaluation can never recompute past (and
    thereby skip) a due or already-locked hour:

    1. If the locked target is due (now >= current_target_time), send it,
       then compute a fresh locked target.
    2. Otherwise sleep one bounded step (HEARTBEAT_INTERVAL_SECONDS).
    3. After the sleep: if now is now due, loop back and send the existing
       locked target (do not re-read config first). Otherwise, only then
       re-evaluate configuration; if an earlier hour is now available,
       retarget to it.
    """
    logger.info("Starting evening reminder scheduler")

    current_target_time: Optional[datetime] = None
    current_hour: Optional[int] = None

    while True:
        try:
            _update_heartbeat()

            if current_target_time is None:
                current_target_time, current_hour = await get_next_reminder_time()
                logger.info(
                    f"Next reminder scheduled for "
                    f"{current_target_time.strftime('%Y-%m-%d %H:%M:%S %Z')} "
                    f"(hour {current_hour})"
                )

            now = datetime.now(TZ)

            if now >= current_target_time:
                logger.info(f"Triggering {current_hour}:00 reminder")
                try:
                    await send_evening_reminder(current_hour)
                except Exception as e:
                    logger.error(
                        f"Error sending {current_hour}:00 reminder: {type(e).__name__}: {str(e)}",
                        exc_info=True,
                    )
                # Fresh target only after the locked one has been sent.
                current_target_time, current_hour = await get_next_reminder_time()
                continue

            sleep_seconds = min(
                HEARTBEAT_INTERVAL_SECONDS,
                (current_target_time - now).total_seconds(),
            )
            await asyncio.sleep(max(0.0, sleep_seconds))

            _update_heartbeat()
            now = datetime.now(TZ)
            if now >= current_target_time:
                # Due: loop back to the top and send the locked target
                # unchanged -- do not re-read configuration first.
                continue

            # Still future: only now safe to re-evaluate for an earlier hour.
            new_target_time, new_hour = await get_next_reminder_time()
            if new_target_time < current_target_time:
                logger.info(
                    f"Retargeting reminder from {current_hour}:00 to {new_hour}:00 "
                    f"({new_target_time.strftime('%Y-%m-%d %H:%M:%S %Z')})"
                )
                current_target_time, current_hour = new_target_time, new_hour

        except Exception as e:
            logger.error(
                f"Error in reminder scheduler: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            # Force a fresh recompute after backoff, in case the failure was
            # due to a stale/invalid locked target.
            current_target_time = None
            current_hour = None
            await asyncio.sleep(60)
