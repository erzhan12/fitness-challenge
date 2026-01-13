"""Internal scheduler for evening reminders at 9pm, 10pm, and 11pm."""

import asyncio
import logging
from datetime import datetime, time, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from app.config import settings
from app.services.workout_service import send_evening_reminder

logger = logging.getLogger(__name__)
TZ = ZoneInfo(settings.TZ)

# Reminder hours (21:00, 22:00, 23:00)
REMINDER_HOURS = [21, 22, 23]


def get_next_reminder_time() -> tuple[datetime, int]:
    """
    Calculate the next scheduled reminder time.

    Returns:
        Tuple of (next_datetime, hour)
        - next_datetime: datetime of next reminder in local timezone
        - hour: hour of the reminder (21, 22, or 23)
    """
    now = datetime.now(TZ)
    today = now.date()

    # Check each reminder hour for today
    for hour in REMINDER_HOURS:
        reminder_time = datetime.combine(today, time(hour=hour, minute=0), tzinfo=TZ)
        if reminder_time > now:
            return reminder_time, hour

    # All reminders for today have passed, schedule first one for tomorrow
    tomorrow = today + timedelta(days=1)
    first_hour = REMINDER_HOURS[0]
    next_reminder = datetime.combine(tomorrow, time(hour=first_hour, minute=0), tzinfo=TZ)
    return next_reminder, first_hour


async def start_reminder_scheduler():
    """
    Background task that runs evening reminders at 9pm, 10pm, and 11pm.

    This runs continuously, calculating the next reminder time and sleeping until then.
    """
    logger.info("Starting evening reminder scheduler")

    while True:
        try:
            # Calculate next reminder time
            next_time, next_hour = get_next_reminder_time()
            now = datetime.now(TZ)
            sleep_seconds = (next_time - now).total_seconds()

            logger.info(
                f"Next reminder scheduled for {next_time.strftime('%Y-%m-%d %H:%M:%S %Z')} "
                f"(in {sleep_seconds/60:.1f} minutes)"
            )

            # Sleep until next reminder time
            await asyncio.sleep(sleep_seconds)

            # Send reminder
            logger.info(f"Triggering {next_hour}:00 reminder")
            try:
                await send_evening_reminder(next_hour)
            except Exception as e:
                logger.error(
                    f"Error sending {next_hour}:00 reminder: {type(e).__name__}: {str(e)}",
                    exc_info=True
                )

        except Exception as e:
            logger.error(
                f"Error in reminder scheduler: {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            # Sleep a bit before retrying to avoid tight error loop
            await asyncio.sleep(60)
