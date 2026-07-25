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


def _fake_clock_datetime(clock: dict):
    """A datetime subclass whose now() reads a mutable {"now": datetime} dict.

    Lets tests advance a fake "current time" from inside a mocked
    asyncio.sleep, without ever real-sleeping.
    """

    class FakeClockDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock["now"]

    return FakeClockDateTime


def _advancing_sleep(clock: dict):
    async def fake_sleep(seconds):
        clock["now"] = clock["now"] + scheduler.timedelta(seconds=seconds)

    return AsyncMock(side_effect=fake_sleep)


def _patch_hours(hours):
    """Patch the repo call get_next_reminder_time() awaits, returning `hours`."""
    return patch(
        "src.core.repositories.user_settings_repo.get_distinct_active_reminder_hours",
        new=AsyncMock(return_value=hours),
    )


@pytest.mark.asyncio
async def test_get_next_reminder_time_before_default_hour_falls_back_to_default():
    fixed_now = datetime(2026, 1, 13, 20, 0, tzinfo=scheduler.TZ)
    with patch("app.services.reminder_scheduler.datetime", _fixed_datetime(fixed_now)):
        with _patch_hours([]):
            next_time, next_hour = await scheduler.get_next_reminder_time()

    assert next_hour == 21
    assert next_time.hour == 21
    assert next_time.date() == fixed_now.date()
    assert next_time.tzinfo == scheduler.TZ


@pytest.mark.asyncio
async def test_get_next_reminder_time_between_default_hours_falls_back_to_default():
    fixed_now = datetime(2026, 1, 13, 21, 30, tzinfo=scheduler.TZ)
    with patch("app.services.reminder_scheduler.datetime", _fixed_datetime(fixed_now)):
        with _patch_hours([]):
            next_time, next_hour = await scheduler.get_next_reminder_time()

    assert next_hour == 22
    assert next_time.hour == 22
    assert next_time.date() == fixed_now.date()


@pytest.mark.asyncio
async def test_get_next_reminder_time_after_all_default_hours_schedules_earliest_tomorrow():
    fixed_now = datetime(2026, 1, 13, 23, 30, tzinfo=scheduler.TZ)
    with patch("app.services.reminder_scheduler.datetime", _fixed_datetime(fixed_now)):
        with _patch_hours([]):
            next_time, next_hour = await scheduler.get_next_reminder_time()

    # DEFAULT_REMINDER_HOURS = [13, 21, 22]; all have passed today, so the
    # earliest hour tomorrow is 13, not 21.
    assert next_hour == 13
    assert next_time.hour == 13
    assert next_time.date() == fixed_now.date() + scheduler.timedelta(days=1)


@pytest.mark.asyncio
async def test_get_next_reminder_time_uses_user_hour_union():
    with _patch_hours([13, 21]):
        fixed_now = datetime(2026, 1, 13, 12, 0, tzinfo=scheduler.TZ)
        with patch("app.services.reminder_scheduler.datetime", _fixed_datetime(fixed_now)):
            next_time, next_hour = await scheduler.get_next_reminder_time()
        assert next_hour == 13
        assert next_time.hour == 13

        fixed_now = datetime(2026, 1, 13, 14, 0, tzinfo=scheduler.TZ)
        with patch("app.services.reminder_scheduler.datetime", _fixed_datetime(fixed_now)):
            next_time, next_hour = await scheduler.get_next_reminder_time()
        assert next_hour == 21
        assert next_time.hour == 21


@pytest.mark.asyncio
async def test_get_next_reminder_time_includes_hour_13():
    fixed_now = datetime(2026, 1, 13, 12, 30, tzinfo=scheduler.TZ)
    with patch("app.services.reminder_scheduler.datetime", _fixed_datetime(fixed_now)):
        with _patch_hours([]):
            next_time, next_hour = await scheduler.get_next_reminder_time()

    assert next_hour == 13
    assert next_time.hour == 13


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


@pytest.mark.asyncio
async def test_scheduler_reevaluates_when_earlier_hour_added_while_waiting():
    """Waiting toward 21:00 with union [21]; union grows to [14, 21] mid-wait.

    Asserts the scheduler retargets to 14:00 -- guarded by inspecting the
    real get_next_reminder_time()'s successive return values, without ever
    reaching a due send.
    """
    clock = {"now": datetime(2026, 1, 13, 12, 0, tzinfo=scheduler.TZ)}
    real_get_next_reminder_time = scheduler.get_next_reminder_time
    observed_targets = []

    async def spy_get_next_reminder_time():
        result = await real_get_next_reminder_time()
        observed_targets.append(result)
        return result

    hours_calls = {"n": 0}

    async def hours_side_effect():
        hours_calls["n"] += 1
        if hours_calls["n"] == 1:
            return [21]
        if hours_calls["n"] == 2:
            return [14, 21]
        raise StopScheduler

    with patch("app.services.reminder_scheduler.datetime", _fake_clock_datetime(clock)):
        with patch(
            "app.services.reminder_scheduler.asyncio.sleep",
            new=_advancing_sleep(clock),
        ):
            with patch(
                "src.core.repositories.user_settings_repo.get_distinct_active_reminder_hours",
                new=AsyncMock(side_effect=hours_side_effect),
            ):
                with patch(
                    "app.services.reminder_scheduler.get_next_reminder_time",
                    side_effect=spy_get_next_reminder_time,
                ):
                    with patch(
                        "app.services.reminder_scheduler.send_evening_reminder",
                        new=AsyncMock(),
                    ) as mock_send:
                        with pytest.raises(StopScheduler):
                            await scheduler.start_reminder_scheduler()

                        mock_send.assert_not_called()

    assert len(observed_targets) == 2
    assert observed_targets[0][1] == 21
    assert observed_targets[1][1] == 14
    assert observed_targets[1][0].hour == 14


@pytest.mark.asyncio
async def test_due_retargeted_hour_sent_exactly_once():
    """After retargeting to 14:00, the clock advances across 14:00 during a
    bounded sleep. send_evening_reminder(14) must fire exactly once --
    guarding both (a) recompute-before-send on the due tick, and (b)
    recompute-after-sleep that lands at/after 14:00 before checking the
    locked target (the strict `>` helper would then skip 14 and return 21).
    """
    clock = {"now": datetime(2026, 1, 13, 13, 0, tzinfo=scheduler.TZ)}

    hours_calls = {"n": 0}

    async def hours_side_effect():
        hours_calls["n"] += 1
        return [21] if hours_calls["n"] == 1 else [14, 21]

    with patch("app.services.reminder_scheduler.datetime", _fake_clock_datetime(clock)):
        with patch(
            "app.services.reminder_scheduler.asyncio.sleep",
            new=_advancing_sleep(clock),
        ):
            with patch(
                "src.core.repositories.user_settings_repo.get_distinct_active_reminder_hours",
                new=AsyncMock(side_effect=hours_side_effect),
            ):
                with patch(
                    "app.services.reminder_scheduler.send_evening_reminder",
                    new=AsyncMock(side_effect=StopScheduler),
                ) as mock_send:
                    with pytest.raises(StopScheduler):
                        await scheduler.start_reminder_scheduler()

    mock_send.assert_called_once_with(14)
    # The clock must have actually reached (not skipped past unnoticed) 14:00.
    assert clock["now"] >= datetime(2026, 1, 13, 14, 0, tzinfo=scheduler.TZ)


@pytest.mark.asyncio
async def test_scheduler_skips_stale_locked_target_across_midnight():
    """Locked target yesterday 21:00; clock jumps to today 08:00.

    Must not call send_evening_reminder (would claim today's slot), must log
    a warning, and must recompute a fresh target for today.
    """
    yesterday_21 = datetime(2026, 1, 12, 21, 0, tzinfo=scheduler.TZ)
    today_08 = datetime(2026, 1, 13, 8, 0, tzinfo=scheduler.TZ)
    today_13 = datetime(2026, 1, 13, 13, 0, tzinfo=scheduler.TZ)

    get_next_calls = {"n": 0}

    async def get_next_side_effect():
        get_next_calls["n"] += 1
        if get_next_calls["n"] == 1:
            return yesterday_21, 21
        if get_next_calls["n"] == 2:
            return today_13, 13
        raise StopScheduler

    with patch("app.services.reminder_scheduler.datetime", _fixed_datetime(today_08)):
        with patch(
            "app.services.reminder_scheduler.get_next_reminder_time",
            side_effect=get_next_side_effect,
        ):
            with patch(
                "app.services.reminder_scheduler.asyncio.sleep",
                new=AsyncMock(return_value=None),
            ):
                with patch(
                    "app.services.reminder_scheduler.send_evening_reminder",
                    new=AsyncMock(),
                ) as mock_send:
                    with patch("app.services.reminder_scheduler.logger") as mock_logger:
                        with pytest.raises(StopScheduler):
                            await scheduler.start_reminder_scheduler()

                        mock_send.assert_not_called()
                        assert mock_logger.warning.call_count >= 1
                        assert "Stale locked target" in mock_logger.warning.call_args[0][0]
                        assert get_next_calls["n"] == 3
