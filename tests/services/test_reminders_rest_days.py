"""Direct rest-day branch tests for reminder/Habit Reward paths.

Three functions in ``app.services.workout_service`` honor exception
(rest) days via the same ``if is_today_exception: continue`` pattern,
but none of the rest-day branch was exercised by a test before this
file. A regression that flipped any of those ``continue``s would
silently break Habit Reward gating and reminder UX.

Each test below pins both the rest-day branch (today is a rest day →
no work happens) and a negative control (no rest day → work happens),
so the test fails fast if either branch breaks. The autouse fixture in
``tests/services/conftest.py`` patches ``challenge_exception_day_repo``
on the workout_service module; tests override
``list_dates_for_challenges`` per-call to mark today as a one-off rest
day. This avoids the need to freeze ``datetime.now(TZ).date()`` —
``check_daily_reminders`` reads it internally.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core import setup_django

setup_django()

from app.services.workout_service import (  # noqa: E402
    TZ,
    _check_all_challenges_complete,
    check_daily_reminders,
    compute_evening_reminder,
)


def _make_rest_aware_challenge(
    challenge_id: int,
    daily_target: int,
    today_local,
    weekdays_csv: str = "",
):
    """Build a SimpleNamespace challenge whose window contains today_local.

    Mirrors the shape consumed by ``compute_evening_reminder`` and
    ``check_daily_reminders`` (attribute access on ``.exercise_type``,
    ``.start_date``, ``.end_date``, ``.daily_target``,
    ``.exception_weekdays``).
    """
    return SimpleNamespace(
        id=challenge_id,
        exercise_type_id=challenge_id,
        exercise_type=SimpleNamespace(
            display_name="Push-ups",
            emoji="💪",
            unit="reps",
        ),
        start_date=today_local - timedelta(days=5),
        end_date=today_local + timedelta(days=5),
        daily_target=daily_target,
        exception_weekdays=weekdays_csv,
    )


class TestCheckAllChallengesCompleteRestDay:
    """``_check_all_challenges_complete`` must skip rest-day challenges so
    they cannot block Habit Reward."""

    @pytest.mark.asyncio
    async def test_returns_true_when_today_is_rest_day(
        self, _mock_challenge_exception_day_repo
    ):
        today_local = datetime.now(TZ).date()
        challenge_dict = {
            "id": 1,
            "start_date": today_local - timedelta(days=5),
            "end_date": today_local + timedelta(days=5),
            "daily_target": 50,
            "exception_weekdays": "",
        }
        # Today is a one-off rest day for this challenge.
        _mock_challenge_exception_day_repo.list_dates_for_challenges = AsyncMock(
            return_value={1: {today_local}}
        )

        with patch("app.services.workout_service.log_repo") as mock_log_repo:
            mock_log_repo.get_cumulative_counts_by_challenge_ids = AsyncMock(
                return_value={1: 0}  # zero progress would normally fail
            )

            result = await _check_all_challenges_complete([challenge_dict], today_local)

        assert result is True, (
            "Rest day must short-circuit to True regardless of cumulative progress; "
            "if this fails, the `if is_today_exception: continue` branch is gone."
        )

    @pytest.mark.asyncio
    async def test_negative_control_returns_false_without_rest_day(
        self, _mock_challenge_exception_day_repo
    ):
        """Negative control: same fixture, no exception → must return False.

        This proves the rest-day branch (not some unrelated short-circuit)
        is what made the previous test return True.
        """
        today_local = datetime.now(TZ).date()
        challenge_dict = {
            "id": 1,
            "start_date": today_local - timedelta(days=5),
            "end_date": today_local + timedelta(days=5),
            "daily_target": 50,
            "exception_weekdays": "",
        }
        # No exceptions: list_dates_for_challenges already returns {} from
        # the autouse fixture, so we don't need to override it here.

        with patch("app.services.workout_service.log_repo") as mock_log_repo:
            mock_log_repo.get_cumulative_counts_by_challenge_ids = AsyncMock(
                return_value={1: 0}
            )

            result = await _check_all_challenges_complete([challenge_dict], today_local)

        assert result is False


class TestComputeEveningReminderRestDay:
    """``compute_evening_reminder`` must filter rest-day challenges out of
    the incomplete list so they never appear in the evening reminder."""

    @pytest.mark.asyncio
    async def test_skips_rest_day_challenge(
        self, _mock_challenge_exception_day_repo
    ):
        today_local = datetime.now(TZ).date()
        challenge = _make_rest_aware_challenge(
            challenge_id=1, daily_target=50, today_local=today_local
        )
        _mock_challenge_exception_day_repo.list_dates_for_challenges = AsyncMock(
            return_value={1: {today_local}}
        )

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=[challenge])

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                mock_log_repo.get_cumulative_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 0}  # zero progress would normally trigger
                )

                should_send, message, count = await compute_evening_reminder(
                    today_local, 21
                )

        assert should_send is False
        assert message is None
        assert count == 0

    @pytest.mark.asyncio
    async def test_negative_control_includes_challenge_when_not_rest_day(
        self, _mock_challenge_exception_day_repo
    ):
        """Same fixture, no exception → challenge SHOULD be flagged incomplete.

        Pins that the previous test's behavior is caused specifically by
        ``is_today_exception``, not by some other filter.
        """
        today_local = datetime.now(TZ).date()
        challenge = _make_rest_aware_challenge(
            challenge_id=1, daily_target=50, today_local=today_local
        )
        # No rest day — autouse fixture default {} is fine.

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=[challenge])

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                mock_log_repo.get_cumulative_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 0}
                )

                with patch(
                    "app.services.workout_service.generate_reminder_motivation"
                ) as mock_llm:
                    mock_llm.return_value = "You can do it!"

                    should_send, message, count = await compute_evening_reminder(
                        today_local, 21
                    )

        assert should_send is True
        assert count == 1
        assert message is not None


class TestCheckDailyRemindersLegacyRestDay:
    """``check_daily_reminders(hour=None)`` (legacy "missing you" branch)
    must not send the per-challenge nudge on rest days."""

    @pytest.mark.asyncio
    async def test_legacy_branch_skips_rest_day_challenge(
        self, _mock_challenge_exception_day_repo
    ):
        today_local = datetime.now(TZ).date()
        challenge = _make_rest_aware_challenge(
            challenge_id=1, daily_target=50, today_local=today_local
        )
        # Mark today as a one-off rest day for this challenge.
        _mock_challenge_exception_day_repo.list_dates_for_challenges = AsyncMock(
            return_value={1: {today_local}}
        )

        mock_settings = SimpleNamespace(
            is_reminder_active=True,
            telegram_chat_id=123456789,
        )

        with patch("app.services.workout_service.app_settings_repo") as mock_app_repo:
            mock_app_repo.get_singleton = AsyncMock(return_value=mock_settings)

            with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
                mock_ch_repo.get_current_active = AsyncMock(return_value=[challenge])

                with patch("app.services.workout_service.log_repo") as mock_log_repo:
                    mock_log_repo.get_today_counts_by_challenge_ids = AsyncMock(
                        return_value={1: 0}  # would normally trigger "missing you"
                    )

                    with patch(
                        "app.services.workout_service.send_telegram_message",
                        new_callable=AsyncMock,
                    ) as mock_send:
                        await check_daily_reminders(hour=None)

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_negative_control_legacy_branch_sends_when_not_rest_day(
        self, _mock_challenge_exception_day_repo
    ):
        """Same fixture, no exception → "missing you" message SHOULD send."""
        today_local = datetime.now(TZ).date()
        challenge = _make_rest_aware_challenge(
            challenge_id=1, daily_target=50, today_local=today_local
        )
        # No rest day — autouse fixture default {} is fine.

        mock_settings = SimpleNamespace(
            is_reminder_active=True,
            telegram_chat_id=123456789,
        )

        with patch("app.services.workout_service.app_settings_repo") as mock_app_repo:
            mock_app_repo.get_singleton = AsyncMock(return_value=mock_settings)

            with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
                mock_ch_repo.get_current_active = AsyncMock(return_value=[challenge])

                with patch("app.services.workout_service.log_repo") as mock_log_repo:
                    mock_log_repo.get_today_counts_by_challenge_ids = AsyncMock(
                        return_value={1: 0}
                    )

                    with patch(
                        "app.services.workout_service.send_telegram_message",
                        new_callable=AsyncMock,
                    ) as mock_send:
                        await check_daily_reminders(hour=None)

        mock_send.assert_called_once()
