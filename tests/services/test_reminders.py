"""Tests for evening reminder functionality."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core import setup_django

setup_django()

from app.services.workout_service import send_evening_reminder, compute_evening_reminder


class TestSendEveningReminder:
    """Tests for send_evening_reminder function."""

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


class TestComputeEveningReminder:
    """Tests for compute_evening_reminder function."""

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
    async def test_all_challenges_complete(self):
        """When all challenges are complete, returns (False, None, 0)."""
        mock_challenge = SimpleNamespace(
            id=1,
            exercise_type_id=1,
            exercise_type=SimpleNamespace(
                display_name="Push-ups",
                emoji="💪",
                unit="reps",
            ),
            daily_target=50,
        )

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=[mock_challenge])

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                # Today total meets target
                mock_log_repo.get_today_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 50}
                )

                should_send, message, count = await compute_evening_reminder(date.today(), 21)

                assert should_send is False
                assert message is None
                assert count == 0

    @pytest.mark.asyncio
    async def test_incomplete_challenge_with_target(self):
        """When a challenge with daily_target is incomplete, includes it in the message."""
        mock_challenge = SimpleNamespace(
            id=1,
            exercise_type_id=1,
            exercise_type=SimpleNamespace(
                display_name="Push-ups",
                emoji="💪",
                unit="reps",
            ),
            daily_target=50,
        )

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=[mock_challenge])

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                # Today total is less than target
                mock_log_repo.get_today_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 30}
                )

                with patch("app.services.workout_service.generate_reminder_motivation") as mock_llm:
                    mock_llm.return_value = "You can do it!"

                    should_send, message, count = await compute_evening_reminder(date.today(), 21)

                    assert should_send is True
                    assert count == 1
                    assert "Push-ups" in message
                    assert "30/50" in message
                    assert "need 20 more" in message

    @pytest.mark.asyncio
    async def test_incomplete_challenge_no_daily_target_zero_logged(self):
        """When challenge has no daily_target and today_total=0, it's incomplete."""
        mock_challenge = SimpleNamespace(
            id=1,
            exercise_type_id=1,
            exercise_type=SimpleNamespace(
                display_name="Yoga",
                emoji="🧘",
                unit="minutes",
            ),
            daily_target=None,  # No target
        )

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=[mock_challenge])

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                # Zero logged today
                mock_log_repo.get_today_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 0}
                )

                with patch("app.services.workout_service.generate_reminder_motivation") as mock_llm:
                    mock_llm.return_value = "Time for some yoga!"

                    should_send, message, count = await compute_evening_reminder(date.today(), 21)

                    assert should_send is True
                    assert count == 1
                    assert "Yoga" in message
                    assert "Not started today" in message

    @pytest.mark.asyncio
    async def test_complete_challenge_no_daily_target_some_logged(self):
        """When challenge has no daily_target but today_total>0, it's complete."""
        mock_challenge = SimpleNamespace(
            id=1,
            exercise_type_id=1,
            exercise_type=SimpleNamespace(
                display_name="Yoga",
                emoji="🧘",
                unit="minutes",
            ),
            daily_target=None,  # No target
        )

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=[mock_challenge])

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                # Some logged today - considered complete
                mock_log_repo.get_today_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 15}
                )

                should_send, message, count = await compute_evening_reminder(date.today(), 21)

                assert should_send is False
                assert message is None
                assert count == 0

    @pytest.mark.asyncio
    async def test_mixed_units_in_remaining_summary(self):
        """When challenges have different units, remaining_summary separates them."""
        mock_challenges = [
            SimpleNamespace(
                id=1,
                exercise_type_id=1,
                exercise_type=SimpleNamespace(
                    display_name="Push-ups",
                    emoji="💪",
                    unit="reps",
                ),
                daily_target=50,
            ),
            SimpleNamespace(
                id=2,
                exercise_type_id=2,
                exercise_type=SimpleNamespace(
                    display_name="Yoga",
                    emoji="🧘",
                    unit="minutes",
                ),
                daily_target=30,
            ),
        ]

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=mock_challenges)

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                # Both incomplete
                mock_log_repo.get_today_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 0, 2: 0}
                )

                with patch("app.services.workout_service.generate_reminder_motivation") as mock_llm:
                    mock_llm.return_value = "Let's go!"

                    # Capture what context is passed to LLM
                    def capture_context(ctx):
                        # Check that remaining_summary has both units
                        summary = ctx.get("remaining_summary", "")
                        assert "reps" in summary
                        assert "minutes" in summary
                        return "Let's go!"

                    mock_llm.side_effect = capture_context

                    should_send, message, count = await compute_evening_reminder(date.today(), 21)

                    assert should_send is True
                    assert count == 2

    @pytest.mark.asyncio
    async def test_mixed_complete_incomplete_challenges(self):
        """When some challenges are complete, only incomplete ones appear."""
        mock_challenges = [
            SimpleNamespace(
                id=1,
                exercise_type_id=1,
                exercise_type=SimpleNamespace(
                    display_name="Push-ups",
                    emoji="💪",
                    unit="reps",
                ),
                daily_target=10,
            ),
            SimpleNamespace(
                id=2,
                exercise_type_id=2,
                exercise_type=SimpleNamespace(
                    display_name="Squats",
                    emoji="🏋️",
                    unit="reps",
                ),
                daily_target=10,
            ),
        ]

        with patch("app.services.workout_service.challenge_repo") as mock_ch_repo:
            mock_ch_repo.get_current_active = AsyncMock(return_value=mock_challenges)

            with patch("app.services.workout_service.log_repo") as mock_log_repo:
                mock_log_repo.get_today_counts_by_challenge_ids = AsyncMock(
                    return_value={1: 10, 2: 3}
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
