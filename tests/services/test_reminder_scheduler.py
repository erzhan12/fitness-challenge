"""Tests for reminder scheduler timing and resilience."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.services import reminder_scheduler as scheduler


class StopScheduler(BaseException):
    """Sentinel exception to stop the infinite scheduler loop in tests."""


def _fixed_datetime(fixed_now: datetime):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    return FixedDateTime


def test_get_next_reminder_time_before_9pm():
    fixed_now = datetime(2026, 1, 13, 20, 0, tzinfo=scheduler.TZ)
    with patch("app.services.reminder_scheduler.datetime", _fixed_datetime(fixed_now)):
        next_time, next_hour = scheduler.get_next_reminder_time()

    assert next_hour == 21
    assert next_time.hour == 21
    assert next_time.date() == fixed_now.date()
    assert next_time.tzinfo == scheduler.TZ


def test_get_next_reminder_time_between_9_and_10pm():
    fixed_now = datetime(2026, 1, 13, 21, 30, tzinfo=scheduler.TZ)
    with patch("app.services.reminder_scheduler.datetime", _fixed_datetime(fixed_now)):
        next_time, next_hour = scheduler.get_next_reminder_time()

    assert next_hour == 22
    assert next_time.hour == 22
    assert next_time.date() == fixed_now.date()


def test_get_next_reminder_time_after_11pm():
    fixed_now = datetime(2026, 1, 13, 23, 30, tzinfo=scheduler.TZ)
    with patch("app.services.reminder_scheduler.datetime", _fixed_datetime(fixed_now)):
        next_time, next_hour = scheduler.get_next_reminder_time()

    assert next_hour == 21
    assert next_time.hour == 21
    assert next_time.date() == fixed_now.date() + scheduler.timedelta(days=1)


@pytest.mark.asyncio
async def test_start_reminder_scheduler_logs_send_error():
    fixed_now = datetime(2026, 1, 13, 21, 0, tzinfo=scheduler.TZ)

    with patch("app.services.reminder_scheduler.datetime", _fixed_datetime(fixed_now)):
        with patch(
            "app.services.reminder_scheduler.get_next_reminder_time",
            side_effect=[(fixed_now, 21), StopScheduler],
        ):
            with patch(
                "app.services.reminder_scheduler.asyncio.sleep",
                new=AsyncMock(return_value=None),
            ):
                with patch(
                    "app.services.reminder_scheduler.send_evening_reminder",
                    new=AsyncMock(side_effect=RuntimeError("boom")),
                ) as mock_send:
                    with patch("app.services.reminder_scheduler.logger") as mock_logger:
                        with pytest.raises(StopScheduler):
                            await scheduler.start_reminder_scheduler()

                        mock_send.assert_awaited_once()
                        assert mock_logger.error.call_count == 1
                        assert (
                            "Error sending 21:00 reminder"
                            in mock_logger.error.call_args[0][0]
                        )
