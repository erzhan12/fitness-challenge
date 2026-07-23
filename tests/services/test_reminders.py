"""Tests for evening reminder functionality."""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core import setup_django

setup_django()

from app.services.workout_service import send_evening_reminder, compute_evening_reminder


class TestSendEveningReminder:
    """Tests for send_evening_reminder function."""

    @pytest.fixture(autouse=True)
    def _mock_deactivate_expired(self):
        """Hygiene sweep must not hit real challenge_repo in reminder tests."""
        with patch(
            "app.services.workout_service.deactivate_expired_challenges",
            new_callable=AsyncMock,
            return_value=0,
        ) as mock_deactivate:
            self.mock_deactivate_expired = mock_deactivate
            yield mock_deactivate

    @pytest.mark.asyncio
    async def test_send_reminder_disabled(self):
        """When is_reminder_active=False, no Telegram message should be sent."""
        mock_settings = SimpleNamespace(
            is_reminder_active=False,
            telegram_chat_id=123456789,
        )

        with patch("app.services.workout_service.app_settings_repo") as mock_repo:
            mock_repo.get_singleton = AsyncMock(return_value=mock_settings)

            with patch(
                "app.services.workout_service.send_telegram_message",
                new_callable=AsyncMock,
            ) as mock_send:
                await send_evening_reminder(21)

                # Should not send any message
                mock_send.assert_not_called()
                # Should not mark as sent
                mock_repo.try_mark_hour_sent.assert_not_called()
                # Hygiene sweep still runs before the disabled early-return
                self.mock_deactivate_expired.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_send_reminder_deactivate_failure_is_swallowed(self):
        """Hygiene sweep errors must not abort the reminder path."""
        mock_settings = SimpleNamespace(
            is_reminder_active=False,
            telegram_chat_id=123456789,
        )
        self.mock_deactivate_expired.side_effect = RuntimeError("db down")

        with patch("app.services.workout_service.app_settings_repo") as mock_repo:
            mock_repo.get_singleton = AsyncMock(return_value=mock_settings)

            with patch(
                "app.services.workout_service.send_telegram_message",
                new_callable=AsyncMock,
            ) as mock_send:
                await send_evening_reminder(21)

                mock_send.assert_not_called()
                mock_repo.get_singleton.assert_awaited()

    @pytest.mark.asyncio
    async def test_send_reminder_no_chat_id(self):
        """When no chat_id is configured, no message should be sent."""
        mock_settings = SimpleNamespace(
            is_reminder_active=True,
            telegram_chat_id=None,
        )

        with patch("app.services.workout_service.app_settings_repo") as mock_repo:
            mock_repo.get_singleton = AsyncMock(return_value=mock_settings)

            with patch("app.services.workout_service.settings") as mock_cfg:
                mock_cfg.TARGET_CHAT_ID = None  # No fallback either

                with patch(
                    "app.services.workout_service.send_telegram_message",
                    new_callable=AsyncMock,
                ) as mock_send:
                    await send_evening_reminder(21)

                    # Should not send any message
                    mock_send.assert_not_called()
                    mock_repo.try_mark_hour_sent.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_reminder_idempotency_already_sent(self):
        """When already sent today, should skip without re-sending."""
        mock_settings = SimpleNamespace(
            is_reminder_active=True,
            telegram_chat_id=123456789,
        )

        with patch("app.services.workout_service.app_settings_repo") as mock_repo:
            mock_repo.get_singleton = AsyncMock(return_value=mock_settings)
            mock_repo.try_mark_hour_sent = AsyncMock(return_value=False)  # Already sent

            with patch(
                "app.services.workout_service.send_telegram_message",
                new_callable=AsyncMock,
            ) as mock_send:
                await send_evening_reminder(21)

                # Should not send any message (already sent)
                mock_send.assert_not_called()
                # Should not mark again
                mock_repo.clear_hour_sent.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_reminder_all_complete(self):
        """When all challenges are complete, should mark as sent but not send message."""
        mock_settings = SimpleNamespace(
            is_reminder_active=True,
            telegram_chat_id=123456789,
        )

        with patch("app.services.workout_service.app_settings_repo") as mock_repo:
            mock_repo.get_singleton = AsyncMock(return_value=mock_settings)
            mock_repo.try_mark_hour_sent = AsyncMock(return_value=True)
            mock_repo.clear_hour_sent = AsyncMock()

            with patch(
                "app.services.workout_service.compute_evening_reminder",
                new_callable=AsyncMock,
            ) as mock_compute:
                # All complete - nothing to send
                mock_compute.return_value = (False, None, 0)

                with patch(
                    "app.services.workout_service.send_telegram_message",
                    new_callable=AsyncMock,
                ) as mock_send:
                    await send_evening_reminder(21)

                    # Should not send message (nothing incomplete)
                    mock_send.assert_not_called()
                    # Claim should be retained
                    mock_repo.try_mark_hour_sent.assert_called_once()
                    mock_repo.clear_hour_sent.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_reminder_incomplete_challenges(self):
        """When there are incomplete challenges, should send combined message."""
        mock_settings = SimpleNamespace(
            is_reminder_active=True,
            telegram_chat_id=123456789,
        )

        with patch("app.services.workout_service.app_settings_repo") as mock_repo:
            mock_repo.get_singleton = AsyncMock(return_value=mock_settings)
            mock_repo.try_mark_hour_sent = AsyncMock(return_value=True)
            mock_repo.clear_hour_sent = AsyncMock()

            with patch(
                "app.services.workout_service.compute_evening_reminder",
                new_callable=AsyncMock,
            ) as mock_compute:
                # 2 incomplete challenges
                mock_compute.return_value = (True, "<b>Test message</b>", 2)

                with patch(
                    "app.services.workout_service.send_telegram_message",
                    new_callable=AsyncMock,
                ) as mock_send:
                    mock_send.return_value = {"ok": True}  # Success

                    await send_evening_reminder(21)

                    # Should send the message
                    mock_send.assert_called_once()
                    call_args = mock_send.call_args
                    assert call_args[0][0] == 123456789  # chat_id
                    assert "<b>Test message</b>" in call_args[0][1]  # message

                    # Claim should remain
                    mock_repo.try_mark_hour_sent.assert_called_once()
                    mock_repo.clear_hour_sent.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_reminder_telegram_failure_not_marked(self):
        """When Telegram send fails, should NOT mark as sent (allows retry)."""
        mock_settings = SimpleNamespace(
            is_reminder_active=True,
            telegram_chat_id=123456789,
        )

        with patch("app.services.workout_service.app_settings_repo") as mock_repo:
            mock_repo.get_singleton = AsyncMock(return_value=mock_settings)
            mock_repo.try_mark_hour_sent = AsyncMock(return_value=True)
            mock_repo.clear_hour_sent = AsyncMock()

            with patch(
                "app.services.workout_service.compute_evening_reminder",
                new_callable=AsyncMock,
            ) as mock_compute:
                mock_compute.return_value = (True, "<b>Test message</b>", 2)

                with patch(
                    "app.services.workout_service.send_telegram_message",
                    new_callable=AsyncMock,
                ) as mock_send:
                    mock_send.return_value = None  # Failure - returns None

                    await send_evening_reminder(21)

                    # Should have attempted to send
                    mock_send.assert_called_once()
                    # Should clear claim to allow retry
                    mock_repo.clear_hour_sent.assert_called_once()


def _make_challenge(
    challenge_id,
    display_name,
    emoji,
    unit,
    daily_target,
    total_days=30,
    day_offset=10,
):
    """Helper to create a mock challenge for reminder tests.

    day_offset: how many days into the challenge we are (day_number).
    The challenge starts (day_offset - 1) days ago.
    """
    today = date.today()
    start_date = today - timedelta(days=day_offset - 1)
    end_date = start_date + timedelta(days=total_days - 1)
    return SimpleNamespace(
        id=challenge_id,
        exercise_type_id=challenge_id,
        exercise_type=SimpleNamespace(
            display_name=display_name,
            emoji=emoji,
            unit=unit,
        ),
        start_date=start_date,
        end_date=end_date,
        daily_target=daily_target,
    )


class TestComputeEveningReminder:
    """Tests for compute_evening_reminder function.

    Reminders use cumulative catch-up logic: a challenge is "incomplete"
    when cumulative_total < expected_progress (based on target and timeline).
    """

    @pytest.mark.asyncio
    async def test_no_active_challenges(self):
        """When there are no active challenges, returns (False, None, 0)."""
        with patch("app.services.workout_service.challenge_repo") as mock_repo:
            mock_repo.get_current_active = AsyncMock(return_value=[])

            should_send, message, count = await compute_evening_reminder(date.today(), 21)

            assert should_send is False
            assert message is None
            assert count == 0

    @pytest.mark.asyncio
    async def test_all_challenges_caught_up(self):
        """When all challenges are caught up on cumulative progress, returns (False, None, 0)."""
        # day 10 of 30, daily_target=50 → expected=500
        mock_challenge = _make_challenge(1, "Push-ups", "💪", "reps", 50)

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=[mock_challenge])

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                # Cumulative meets expected (500)
                mock_log_repo.get_cumulative_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 500}
                )

                should_send, message, count = await compute_evening_reminder(date.today(), 21)

                assert should_send is False
                assert message is None
                assert count == 0

    @pytest.mark.asyncio
    async def test_challenge_behind_cumulative_progress(self):
        """When cumulative_total < expected, challenge is included in reminder."""
        # day 10 of 30, daily_target=50 → expected=500
        mock_challenge = _make_challenge(1, "Push-ups", "💪", "reps", 50)

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=[mock_challenge])

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                # Cumulative is behind (400 < 500)
                mock_log_repo.get_cumulative_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 400}
                )

                with patch("app.services.workout_service.generate_reminder_motivation") as mock_llm:
                    mock_llm.return_value = "You can do it!"

                    should_send, message, count = await compute_evening_reminder(date.today(), 21)

                    assert should_send is True
                    assert count == 1
                    assert "Push-ups" in message
                    assert "400/500" in message
                    assert "need 100 more" in message
                    assert "catch up" in message

    @pytest.mark.asyncio
    async def test_challenge_with_small_daily_target_behind(self):
        """Challenge with daily_target=10 uses daily_target*day_number for expected."""
        # day 10 of 30, daily_target=10 → expected=100
        mock_challenge = _make_challenge(1, "Yoga", "🧘", "minutes", 10)

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=[mock_challenge])

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                # Cumulative is behind (50 < 100)
                mock_log_repo.get_cumulative_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 50}
                )

                with patch("app.services.workout_service.generate_reminder_motivation") as mock_llm:
                    mock_llm.return_value = "Time for some yoga!"

                    should_send, message, count = await compute_evening_reminder(date.today(), 21)

                    assert should_send is True
                    assert count == 1
                    assert "Yoga" in message
                    assert "50/100" in message
                    assert "need 50 more" in message

    @pytest.mark.asyncio
    async def test_challenge_with_small_daily_target_caught_up(self):
        """Challenge with daily_target=10 is caught up when cumulative >= expected."""
        # day 10 of 30, daily_target=10 → expected=100
        mock_challenge = _make_challenge(1, "Yoga", "🧘", "minutes", 10)

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=[mock_challenge])

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                # Cumulative meets expected (100 >= 100)
                mock_log_repo.get_cumulative_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 100}
                )

                should_send, message, count = await compute_evening_reminder(date.today(), 21)

                assert should_send is False
                assert message is None
                assert count == 0

    @pytest.mark.asyncio
    async def test_mixed_units_in_remaining_summary(self):
        """When challenges have different units, remaining_summary separates them."""
        # day 10 of 30: push-ups expected=500, yoga expected=100
        mock_challenges = [
            _make_challenge(1, "Push-ups", "💪", "reps", 50),
            _make_challenge(2, "Yoga", "🧘", "minutes", 10),
        ]

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=mock_challenges)

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                # Both behind
                mock_log_repo.get_cumulative_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 400, 2: 50}
                )

                with patch("app.services.workout_service.generate_reminder_motivation") as mock_llm:
                    def capture_context(ctx):
                        summary = ctx.get("remaining_summary", "")
                        assert "reps" in summary
                        assert "minutes" in summary
                        return "Let's go!"

                    mock_llm.side_effect = capture_context

                    should_send, message, count = await compute_evening_reminder(date.today(), 21)

                    assert should_send is True
                    assert count == 2

    @pytest.mark.asyncio
    async def test_mixed_caught_up_and_behind_challenges(self):
        """When some challenges are caught up, only behind ones appear in reminder."""
        # Both: day 10 of 30, daily_target=50 → expected=500
        mock_challenges = [
            _make_challenge(1, "Push-ups", "💪", "reps", 50),
            _make_challenge(2, "Squats", "🏋️", "reps", 50),
        ]

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=mock_challenges)

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                # Push-ups caught up (500 >= 500), squats behind (300 < 500)
                mock_log_repo.get_cumulative_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 500, 2: 300}
                )

                with patch("app.services.workout_service.generate_reminder_motivation") as mock_llm:
                    mock_llm.return_value = "Keep it up!"

                    should_send, message, count = await compute_evening_reminder(
                        date.today(), 21
                    )

                    assert should_send is True
                    assert count == 1
                    assert "Squats" in message
                    assert "Push-ups" not in message
                    assert "300/500" in message
                    assert "need 200 more" in message
