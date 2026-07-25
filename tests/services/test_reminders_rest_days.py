"""Direct rest-day branch tests for reminder/Habit Reward paths.

Three functions in ``app.services.workout_service`` honor exception
(rest) days via the same ``if is_today_exception: continue`` pattern.
A regression that flipped any of those ``continue``s would silently
break Habit Reward gating and reminder UX.

For ``_check_all_challenges_complete``, ``continue`` still means a
rest-day challenge never *blocks* Habit Reward, but a day on which
*every* challenge rests returns ``False`` (not a vacuous ``True``) —
there is no scheduled work to complete. Evening-reminder /
daily-reminder functions keep the older "today is a rest day → no work
happens" outcome.

Each test below pins the rest-day branch and a negative control (no
rest day → work happens), so the test fails fast if either branch
breaks. The autouse fixture in ``tests/services/conftest.py`` patches
``challenge_exception_day_repo`` on the workout_service module; tests
override ``list_dates_for_challenges`` per-call to mark today as a
one-off rest day. This avoids the need to freeze
``datetime.now(TZ).date()`` — ``check_daily_reminders`` reads it
internally.
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


def _make_user_settings(user_id, telegram_chat_id=123456789, is_reminder_active=True):
    return SimpleNamespace(
        user_id=user_id,
        telegram_chat_id=telegram_chat_id,
        is_reminder_active=is_reminder_active,
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
    """``_check_all_challenges_complete``: a rest-day challenge never
    *blocks* Habit Reward, but an all-rest day is not completable and
    returns ``False``.
    """

    @pytest.mark.asyncio
    async def test_returns_false_when_all_challenges_are_rest_days(
        self, _mock_challenge_exception_day_repo
    ):
        today_local = datetime.now(TZ).date()
        challenge_dict = {
            "id": 1,
            "start_date": today_local - timedelta(days=5),
            "end_date": today_local + timedelta(days=5),
            "daily_target": 50,
            # Recurring weekday exclusion (issue #29 repro path via
            # `_parse_weekdays_csv` / `expand_exception_dates`).
            "exception_weekdays": str(today_local.isoweekday()),
        }
        # Explicit dates stay at the autouse `{}` default — rest day comes
        # from the recurring CSV only.

        with patch("app.services.workout_service.log_repo") as mock_log_repo:
            # Banked ahead on a rest day: only `scheduled_seen` → False can
            # discriminate; `{1: 0}` would also fail if the continue branch
            # were lost (`0 < expected`).
            mock_log_repo.get_cumulative_counts_by_challenge_ids = AsyncMock(
                return_value={1: 1000}
            )

            result = await _check_all_challenges_complete([challenge_dict], today_local)

        assert result is False, (
            "An all-rest day has no scheduled work, so it is not a completable "
            "day; vacuous True would incorrectly fire Habit Reward / Day Complete."
        )

    @pytest.mark.asyncio
    async def test_negative_control_returns_false_without_rest_day(
        self, _mock_challenge_exception_day_repo
    ):
        """Negative control: same fixture, no exception → must return False.

        Pins the ordinary behind-schedule path: with no rest day the
        challenge is scheduled, so ``scheduled_seen`` is True and the
        ``cumulative_total < expected`` check is what returns False.

        Note this control does not by itself isolate the rest-day branch —
        both it and the all-rest test return ``False``. What discriminates
        is the banked ``{1: 1000}`` in the all-rest test above: that value
        clears ``expected``, so only ``scheduled_seen`` staying False can
        produce ``False`` there.
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

    @pytest.mark.asyncio
    async def test_returns_true_when_one_challenge_rests_and_other_is_on_track(
        self, _mock_challenge_exception_day_repo
    ):
        today_local = datetime.now(TZ).date()
        rest_challenge = {
            "id": 1,
            "start_date": today_local - timedelta(days=5),
            "end_date": today_local + timedelta(days=5),
            "daily_target": 50,
            "exception_weekdays": "",
        }
        scheduled_challenge = {
            "id": 2,
            "start_date": today_local - timedelta(days=5),
            "end_date": today_local + timedelta(days=5),
            "daily_target": 10,
            "exception_weekdays": "",
        }
        _mock_challenge_exception_day_repo.list_dates_for_challenges = AsyncMock(
            return_value={1: {today_local}}
        )

        with patch("app.services.workout_service.log_repo") as mock_log_repo:
            # day_number=6 → expected = 10 * 6 = 60; 100 >= 60 → on track
            mock_log_repo.get_cumulative_counts_by_challenge_ids = AsyncMock(
                return_value={1: 0, 2: 100}
            )

            result = await _check_all_challenges_complete(
                [rest_challenge, scheduled_challenge], today_local
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_one_challenge_rests_and_other_is_behind(
        self, _mock_challenge_exception_day_repo
    ):
        today_local = datetime.now(TZ).date()
        rest_challenge = {
            "id": 1,
            "start_date": today_local - timedelta(days=5),
            "end_date": today_local + timedelta(days=5),
            "daily_target": 50,
            "exception_weekdays": "",
        }
        scheduled_challenge = {
            "id": 2,
            "start_date": today_local - timedelta(days=5),
            "end_date": today_local + timedelta(days=5),
            "daily_target": 10,
            "exception_weekdays": "",
        }
        _mock_challenge_exception_day_repo.list_dates_for_challenges = AsyncMock(
            return_value={1: {today_local}}
        )

        with patch("app.services.workout_service.log_repo") as mock_log_repo:
            # day_number=6 → expected = 60; 0 < 60 → behind
            mock_log_repo.get_cumulative_counts_by_challenge_ids = AsyncMock(
                return_value={1: 0, 2: 0}
            )

            result = await _check_all_challenges_complete(
                [rest_challenge, scheduled_challenge], today_local
            )

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
                    today_local, 21, user_id=1
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
                        today_local, 21, user_id=1
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

        user = _make_user_settings(1, telegram_chat_id=123456789)

        with patch("app.services.workout_service.user_settings_repo") as mock_us_repo:
            mock_us_repo.get_users_with_reminders_enabled = AsyncMock(
                return_value=[user]
            )

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

        user = _make_user_settings(1, telegram_chat_id=123456789)

        with patch("app.services.workout_service.user_settings_repo") as mock_us_repo:
            mock_us_repo.get_users_with_reminders_enabled = AsyncMock(
                return_value=[user]
            )

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
        assert mock_send.call_args.args[0] == 123456789


class TestCheckDailyRemindersLegacyPerUser:
    """``check_daily_reminders(hour=None)`` iterates per-user settings."""

    @pytest.mark.asyncio
    async def test_legacy_iterates_per_user_with_own_chat_id(
        self, _mock_challenge_exception_day_repo
    ):
        today_local = datetime.now(TZ).date()
        challenge_a = _make_rest_aware_challenge(1, 50, today_local)
        challenge_b = _make_rest_aware_challenge(2, 30, today_local)
        user_a = _make_user_settings(1, telegram_chat_id=111)
        user_b = _make_user_settings(2, telegram_chat_id=222)

        with patch("app.services.workout_service.user_settings_repo") as mock_us_repo:
            mock_us_repo.get_users_with_reminders_enabled = AsyncMock(
                return_value=[user_a, user_b]
            )

            with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
                async def active_for_user(today, user_id):
                    if user_id == 1:
                        return [challenge_a]
                    if user_id == 2:
                        return [challenge_b]
                    return []

                mock_ch_repo.get_current_active = AsyncMock(side_effect=active_for_user)

                with patch("app.services.workout_service.log_repo") as mock_log_repo:
                    mock_log_repo.get_today_counts_by_challenge_ids = AsyncMock(
                        return_value={1: 0, 2: 0}
                    )

                    with patch(
                        "app.services.workout_service.send_telegram_message",
                        new_callable=AsyncMock,
                    ) as mock_send:
                        await check_daily_reminders(hour=None)

        assert mock_send.await_count == 2
        sent_chat_ids = {c.args[0] for c in mock_send.call_args_list}
        assert sent_chat_ids == {111, 222}

    @pytest.mark.asyncio
    async def test_legacy_scopes_challenges_per_user_id(
        self, _mock_challenge_exception_day_repo
    ):
        today_local = datetime.now(TZ).date()
        user_a = _make_user_settings(1, telegram_chat_id=111)
        user_b = _make_user_settings(2, telegram_chat_id=222)

        with patch("app.services.workout_service.user_settings_repo") as mock_us_repo:
            mock_us_repo.get_users_with_reminders_enabled = AsyncMock(
                return_value=[user_a, user_b]
            )

            with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
                mock_ch_repo.get_current_active = AsyncMock(return_value=[])

                with patch(
                    "app.services.workout_service.send_telegram_message",
                    new_callable=AsyncMock,
                ):
                    await check_daily_reminders(hour=None)

        assert mock_ch_repo.get_current_active.await_count == 2
        user_ids = {
            c.kwargs.get("user_id") or c.args[1]
            for c in mock_ch_repo.get_current_active.call_args_list
        }
        assert user_ids == {1, 2}
        for call in mock_ch_repo.get_current_active.call_args_list:
            assert call.args[0] == today_local

    @pytest.mark.asyncio
    async def test_legacy_no_target_chat_id_fallback(
        self, _mock_challenge_exception_day_repo
    ):
        user = _make_user_settings(1, telegram_chat_id=None)

        with patch("app.services.workout_service.user_settings_repo") as mock_us_repo:
            mock_us_repo.get_users_with_reminders_enabled = AsyncMock(
                return_value=[user]
            )

            with patch("app.services.workout_service.settings") as mock_cfg:
                mock_cfg.TARGET_CHAT_ID = 999999

                with patch(
                    "app.services.workout_service.send_telegram_message",
                    new_callable=AsyncMock,
                ) as mock_send:
                    await check_daily_reminders(hour=None)

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_legacy_skips_user_without_telegram_chat_id(
        self, _mock_challenge_exception_day_repo
    ):
        user = _make_user_settings(1, telegram_chat_id=None)

        with patch("app.services.workout_service.user_settings_repo") as mock_us_repo:
            mock_us_repo.get_users_with_reminders_enabled = AsyncMock(
                return_value=[user]
            )

            with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
                mock_ch_repo.get_current_active = AsyncMock()

                with patch(
                    "app.services.workout_service.send_telegram_message",
                    new_callable=AsyncMock,
                ) as mock_send:
                    await check_daily_reminders(hour=None)

        mock_ch_repo.get_current_active.assert_not_called()
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_legacy_skips_user_with_empty_reminder_hours(
        self, _mock_challenge_exception_day_repo
    ):
        with patch("app.services.workout_service.user_settings_repo") as mock_us_repo:
            mock_us_repo.get_users_with_reminders_enabled = AsyncMock(return_value=[])

            with patch(
                "app.services.workout_service.send_telegram_message",
                new_callable=AsyncMock,
            ) as mock_send:
                await check_daily_reminders(hour=None)

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_legacy_skips_inactive_user(
        self, _mock_challenge_exception_day_repo
    ):
        with patch("app.services.workout_service.user_settings_repo") as mock_us_repo:
            mock_us_repo.get_users_with_reminders_enabled = AsyncMock(return_value=[])

            with patch(
                "app.services.workout_service.send_telegram_message",
                new_callable=AsyncMock,
            ) as mock_send:
                await check_daily_reminders(hour=None)

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_legacy_skips_unapproved_user(
        self, _mock_challenge_exception_day_repo
    ):
        with patch("app.services.workout_service.user_settings_repo") as mock_us_repo:
            mock_us_repo.get_users_with_reminders_enabled = AsyncMock(return_value=[])

            with patch(
                "app.services.workout_service.send_telegram_message",
                new_callable=AsyncMock,
            ) as mock_send:
                await check_daily_reminders(hour=None)

        mock_send.assert_not_called()
