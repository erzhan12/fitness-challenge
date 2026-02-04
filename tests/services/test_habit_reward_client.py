"""Tests for Habit Reward API client and integration."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock, MagicMock

import httpx
import pytest

from src.core import setup_django

setup_django()


def _make_user_settings(api_key="test-api-key", habit_id=123, sent_date=None):
    """Create a mock UserSettings object with habit reward fields."""
    return SimpleNamespace(
        habit_reward_api_key=api_key,
        habit_reward_habit_id=habit_id,
        last_habit_reward_sent_date=sent_date,
        save=MagicMock(),
    )


class TestSendHabitCompletion:
    """Tests for send_habit_completion()."""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful API call returns response dict."""
        mock_settings = _make_user_settings()
        mock_api_response = {
            "habit_confirmed": True,
            "habit_name": "Fitness Challenge",
            "streak_count": 3,
            "got_reward": False,
            "total_weight_applied": 13.0,
            "reward": None,
            "cumulative_progress": None,
        }

        with patch(
            "app.services.habit_reward_client.user_settings_repo"
        ) as mock_repo:
            mock_repo.get_by_user_id = AsyncMock(return_value=mock_settings)

            with patch("app.services.habit_reward_client.settings") as mock_config:
                mock_config.HABIT_REWARD_BASE_URL = "https://api.example.com"

                with patch(
                    "app.services.habit_reward_client.httpx.AsyncClient"
                ) as mock_client_class:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.raise_for_status = MagicMock()
                    mock_response.json = MagicMock(return_value=mock_api_response)

                    mock_client = AsyncMock()
                    mock_client.post = AsyncMock(return_value=mock_response)
                    mock_client_class.return_value.__aenter__.return_value = (
                        mock_client
                    )

                    from app.services.habit_reward_client import (
                        send_habit_completion,
                    )

                    result = await send_habit_completion(1, date(2026, 1, 22))

                    assert result is not None
                    assert result["habit_confirmed"] is True
                    assert result["habit_name"] == "Fitness Challenge"
                    assert result["streak_count"] == 3
                    assert result["got_reward"] is False
                    mock_client.post.assert_called_once()
                    call_args = mock_client.post.call_args
                    # URL uses /v1/ prefix (not /api/v1/)
                    assert (
                        call_args[0][0]
                        == "https://api.example.com/v1/habits/123/complete"
                    )
                    # Auth uses X-API-Key header (not Bearer)
                    assert (
                        call_args[1]["headers"]["X-API-Key"] == "test-api-key"
                    )
                    assert "Authorization" not in call_args[1]["headers"]

    @pytest.mark.asyncio
    async def test_api_error_returns_none(self):
        """Test that HTTP error response returns None."""
        mock_settings = _make_user_settings()

        with patch(
            "app.services.habit_reward_client.user_settings_repo"
        ) as mock_repo:
            mock_repo.get_by_user_id = AsyncMock(return_value=mock_settings)

            with patch("app.services.habit_reward_client.settings") as mock_config:
                mock_config.HABIT_REWARD_BASE_URL = "https://api.example.com"

                with patch(
                    "app.services.habit_reward_client.httpx.AsyncClient"
                ) as mock_client_class:
                    mock_response = MagicMock()
                    mock_response.status_code = 401
                    mock_response.text = "Unauthorized"
                    mock_response.raise_for_status.side_effect = (
                        httpx.HTTPStatusError(
                            "401", request=MagicMock(), response=mock_response
                        )
                    )

                    mock_client = AsyncMock()
                    mock_client.post = AsyncMock(return_value=mock_response)
                    mock_client_class.return_value.__aenter__.return_value = (
                        mock_client
                    )

                    from app.services.habit_reward_client import (
                        send_habit_completion,
                    )

                    result = await send_habit_completion(1)

                    assert result is None

    @pytest.mark.asyncio
    async def test_network_error_returns_none(self):
        """Test that network errors return None."""
        mock_settings = _make_user_settings()

        with patch(
            "app.services.habit_reward_client.user_settings_repo"
        ) as mock_repo:
            mock_repo.get_by_user_id = AsyncMock(return_value=mock_settings)

            with patch("app.services.habit_reward_client.settings") as mock_config:
                mock_config.HABIT_REWARD_BASE_URL = "https://api.example.com"

                with patch(
                    "app.services.habit_reward_client.httpx.AsyncClient"
                ) as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client.post = AsyncMock(
                        side_effect=httpx.ConnectError("Connection failed")
                    )
                    mock_client_class.return_value.__aenter__.return_value = (
                        mock_client
                    )

                    from app.services.habit_reward_client import (
                        send_habit_completion,
                    )

                    result = await send_habit_completion(1)

                    assert result is None

    @pytest.mark.asyncio
    async def test_skips_when_no_user_settings(self):
        """Test that it skips and returns None when user has no settings."""
        with patch(
            "app.services.habit_reward_client.user_settings_repo"
        ) as mock_repo:
            mock_repo.get_by_user_id = AsyncMock(return_value=None)

            with patch(
                "app.services.habit_reward_client.httpx.AsyncClient"
            ) as mock_client_class:
                from app.services.habit_reward_client import send_habit_completion

                result = await send_habit_completion(1)

                assert result is None
                mock_client_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_api_key_empty(self):
        """Test that it skips when API key is empty."""
        mock_settings = _make_user_settings(api_key="", habit_id=123)

        with patch(
            "app.services.habit_reward_client.user_settings_repo"
        ) as mock_repo:
            mock_repo.get_by_user_id = AsyncMock(return_value=mock_settings)

            with patch(
                "app.services.habit_reward_client.httpx.AsyncClient"
            ) as mock_client_class:
                from app.services.habit_reward_client import send_habit_completion

                result = await send_habit_completion(1)

                assert result is None
                mock_client_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_habit_id_null(self):
        """Test that it skips when habit ID is null."""
        mock_settings = _make_user_settings(api_key="test-key", habit_id=None)

        with patch(
            "app.services.habit_reward_client.user_settings_repo"
        ) as mock_repo:
            mock_repo.get_by_user_id = AsyncMock(return_value=mock_settings)

            with patch(
                "app.services.habit_reward_client.httpx.AsyncClient"
            ) as mock_client_class:
                from app.services.habit_reward_client import send_habit_completion

                result = await send_habit_completion(1)

                assert result is None
                mock_client_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_includes_target_date_in_payload(self):
        """Test that completion_date is included as target_date in the payload."""
        mock_settings = _make_user_settings()

        with patch(
            "app.services.habit_reward_client.user_settings_repo"
        ) as mock_repo:
            mock_repo.get_by_user_id = AsyncMock(return_value=mock_settings)

            with patch("app.services.habit_reward_client.settings") as mock_config:
                mock_config.HABIT_REWARD_BASE_URL = "https://api.example.com"

                with patch(
                    "app.services.habit_reward_client.httpx.AsyncClient"
                ) as mock_client_class:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.raise_for_status = MagicMock()

                    mock_client = AsyncMock()
                    mock_client.post = AsyncMock(return_value=mock_response)
                    mock_client_class.return_value.__aenter__.return_value = (
                        mock_client
                    )

                    from app.services.habit_reward_client import (
                        send_habit_completion,
                    )

                    test_date = date(2026, 1, 15)
                    await send_habit_completion(1, test_date)

                    call_args = mock_client.post.call_args
                    # Field name is target_date (not date)
                    assert call_args[1]["json"] == {
                        "target_date": "2026-01-15"
                    }

    @pytest.mark.asyncio
    async def test_empty_payload_when_no_date(self):
        """Test that payload is empty dict {} when no date is provided.

        The Habit Reward API expects a JSON body even without target_date.
        """
        mock_settings = _make_user_settings()

        with patch(
            "app.services.habit_reward_client.user_settings_repo"
        ) as mock_repo:
            mock_repo.get_by_user_id = AsyncMock(return_value=mock_settings)

            with patch("app.services.habit_reward_client.settings") as mock_config:
                mock_config.HABIT_REWARD_BASE_URL = "https://api.example.com"

                with patch(
                    "app.services.habit_reward_client.httpx.AsyncClient"
                ) as mock_client_class:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.raise_for_status = MagicMock()

                    mock_client = AsyncMock()
                    mock_client.post = AsyncMock(return_value=mock_response)
                    mock_client_class.return_value.__aenter__.return_value = (
                        mock_client
                    )

                    from app.services.habit_reward_client import (
                        send_habit_completion,
                    )

                    await send_habit_completion(1)

                    call_args = mock_client.post.call_args
                    assert call_args[1]["json"] == {}


def _make_mock_challenge(id=1, start_date=date(2026, 1, 1), end_date=date(2026, 1, 31),
                         target_total=1000, daily_target=None):
    """Create a mock challenge object."""
    return SimpleNamespace(
        id=id,
        start_date=start_date,
        end_date=end_date,
        target_total=target_total,
        daily_target=daily_target,
    )


class TestNotifyHabitRewardIfComplete:
    """Integration tests for notify_habit_reward_if_complete() in workout_service."""

    @pytest.mark.asyncio
    async def test_returns_true_when_no_challenges(self):
        """When no active challenges, returns True without checking completion."""
        from app.services.workout_service import notify_habit_reward_if_complete

        with patch(
            "app.services.workout_service.challenge_repo"
        ) as mock_challenge_repo:
            mock_challenge_repo.get_current_active = AsyncMock(return_value=[])

            with patch(
                "app.services.workout_service.user_settings_repo"
            ) as mock_user_repo:
                with patch(
                    "app.services.workout_service.send_habit_completion",
                    new_callable=AsyncMock,
                ) as mock_send:
                    result = await notify_habit_reward_if_complete(
                        date(2026, 1, 22), user_id=1
                    )

                    assert result is True
                    # Should not try to claim or send when no challenges
                    mock_user_repo.try_claim_habit_reward_date.assert_not_called()
                    mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_true_when_not_all_complete(self):
        """When not all challenges complete, returns True without sending."""
        from app.services.workout_service import notify_habit_reward_if_complete

        mock_challenges = [_make_mock_challenge()]

        with patch(
            "app.services.workout_service.challenge_repo"
        ) as mock_challenge_repo:
            mock_challenge_repo.get_current_active = AsyncMock(
                return_value=mock_challenges
            )

            with patch(
                "app.services.workout_service._check_all_challenges_complete",
                new_callable=AsyncMock,
            ) as mock_check:
                mock_check.return_value = False  # Not all complete

                with patch(
                    "app.services.workout_service.user_settings_repo"
                ) as mock_user_repo:
                    with patch(
                        "app.services.workout_service.send_habit_completion",
                        new_callable=AsyncMock,
                    ) as mock_send:
                        result = await notify_habit_reward_if_complete(
                            date(2026, 1, 22), user_id=1
                        )

                        assert result is True
                        # Should check completion
                        mock_check.assert_awaited_once()
                        # Should NOT try to claim or send
                        mock_user_repo.try_claim_habit_reward_date.assert_not_called()
                        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_true_when_already_claimed(self):
        """When date already claimed, returns True without calling API."""
        from app.services.workout_service import notify_habit_reward_if_complete

        mock_challenges = [_make_mock_challenge()]

        with patch(
            "app.services.workout_service.challenge_repo"
        ) as mock_challenge_repo:
            mock_challenge_repo.get_current_active = AsyncMock(
                return_value=mock_challenges
            )

            with patch(
                "app.services.workout_service._check_all_challenges_complete",
                new_callable=AsyncMock,
            ) as mock_check:
                mock_check.return_value = True  # All complete

                with patch(
                    "app.services.workout_service.user_settings_repo"
                ) as mock_user_repo:
                    mock_user_repo.try_claim_habit_reward_date = AsyncMock(
                        return_value=False
                    )

                    with patch(
                        "app.services.workout_service.send_habit_completion",
                        new_callable=AsyncMock,
                    ) as mock_send:
                        result = await notify_habit_reward_if_complete(
                            date(2026, 1, 22), user_id=1
                        )

                        assert result is True
                        mock_user_repo.try_claim_habit_reward_date.assert_awaited_once_with(
                            1, date(2026, 1, 22)
                        )
                        # Should NOT call API since claim failed (already claimed)
                        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_on_successful_claim(self):
        """On successful claim and API call, returns True."""
        from app.services.workout_service import notify_habit_reward_if_complete

        mock_challenges = [_make_mock_challenge()]

        with patch(
            "app.services.workout_service.challenge_repo"
        ) as mock_challenge_repo:
            mock_challenge_repo.get_current_active = AsyncMock(
                return_value=mock_challenges
            )

            with patch(
                "app.services.workout_service._check_all_challenges_complete",
                new_callable=AsyncMock,
            ) as mock_check:
                mock_check.return_value = True  # All complete

                with patch(
                    "app.services.workout_service.user_settings_repo"
                ) as mock_user_repo:
                    mock_user_repo.try_claim_habit_reward_date = AsyncMock(
                        return_value=True
                    )

                    with patch(
                        "app.services.workout_service.send_habit_completion",
                        new_callable=AsyncMock,
                    ) as mock_send:
                        # API success returns response dict
                        mock_send.return_value = {
                            "habit_confirmed": True,
                            "habit_name": "Test Habit",
                            "streak_count": 5,
                            "got_reward": False,
                        }

                        result = await notify_habit_reward_if_complete(
                            date(2026, 1, 22), user_id=1
                        )

                        assert result is True
                        mock_send.assert_awaited_once_with(1, date(2026, 1, 22))
                        # Should NOT clear claim on success
                        mock_user_repo.clear_habit_reward_claim.assert_not_called()

    @pytest.mark.asyncio
    async def test_clears_claim_on_api_failure(self):
        """On API failure, clears claim and returns False."""
        from app.services.workout_service import notify_habit_reward_if_complete

        mock_challenges = [_make_mock_challenge()]

        with patch(
            "app.services.workout_service.challenge_repo"
        ) as mock_challenge_repo:
            mock_challenge_repo.get_current_active = AsyncMock(
                return_value=mock_challenges
            )

            with patch(
                "app.services.workout_service._check_all_challenges_complete",
                new_callable=AsyncMock,
            ) as mock_check:
                mock_check.return_value = True  # All complete

                with patch(
                    "app.services.workout_service.user_settings_repo"
                ) as mock_user_repo:
                    mock_user_repo.try_claim_habit_reward_date = AsyncMock(
                        return_value=True
                    )
                    mock_user_repo.clear_habit_reward_claim = AsyncMock()

                    with patch(
                        "app.services.workout_service.send_habit_completion",
                        new_callable=AsyncMock,
                    ) as mock_send:
                        mock_send.return_value = None  # API failure

                        result = await notify_habit_reward_if_complete(
                            date(2026, 1, 22), user_id=1
                        )

                        assert result is False
                        mock_send.assert_awaited_once_with(1, date(2026, 1, 22))
                        # Should clear claim on failure to allow retry
                        mock_user_repo.clear_habit_reward_claim.assert_awaited_once_with(
                            1, date(2026, 1, 22)
                        )

    @pytest.mark.asyncio
    async def test_returns_false_when_not_configured(self):
        """When send_habit_completion returns None (not configured), clears claim."""
        from app.services.workout_service import notify_habit_reward_if_complete

        mock_challenges = [_make_mock_challenge()]

        with patch(
            "app.services.workout_service.challenge_repo"
        ) as mock_challenge_repo:
            mock_challenge_repo.get_current_active = AsyncMock(
                return_value=mock_challenges
            )

            with patch(
                "app.services.workout_service._check_all_challenges_complete",
                new_callable=AsyncMock,
            ) as mock_check:
                mock_check.return_value = True  # All complete

                with patch(
                    "app.services.workout_service.user_settings_repo"
                ) as mock_user_repo:
                    mock_user_repo.try_claim_habit_reward_date = AsyncMock(
                        return_value=True
                    )
                    mock_user_repo.clear_habit_reward_claim = AsyncMock()

                    with patch(
                        "app.services.workout_service.send_habit_completion",
                        new_callable=AsyncMock,
                    ) as mock_send:
                        mock_send.return_value = None  # Not configured

                        result = await notify_habit_reward_if_complete(
                            date(2026, 1, 22), user_id=1
                        )

                        assert result is False
                        mock_user_repo.clear_habit_reward_claim.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_atomic_claim_prevents_duplicate_sends(self):
        """Atomic claim pattern prevents concurrent duplicate sends."""
        from app.services.workout_service import notify_habit_reward_if_complete

        mock_challenges = [_make_mock_challenge()]
        claim_count = 0

        async def mock_claim(uid, d):
            nonlocal claim_count
            # First call succeeds, subsequent calls fail (already claimed)
            if claim_count == 0:
                claim_count += 1
                return True
            return False

        with patch(
            "app.services.workout_service.challenge_repo"
        ) as mock_challenge_repo:
            mock_challenge_repo.get_current_active = AsyncMock(
                return_value=mock_challenges
            )

            with patch(
                "app.services.workout_service._check_all_challenges_complete",
                new_callable=AsyncMock,
            ) as mock_check:
                mock_check.return_value = True  # All complete

                with patch(
                    "app.services.workout_service.user_settings_repo"
                ) as mock_user_repo:
                    mock_user_repo.try_claim_habit_reward_date = AsyncMock(
                        side_effect=mock_claim
                    )

                    with patch(
                        "app.services.workout_service.send_habit_completion",
                        new_callable=AsyncMock,
                    ) as mock_send:
                        # API success returns response dict
                        mock_send.return_value = {
                            "habit_confirmed": True,
                            "habit_name": "Test Habit",
                            "streak_count": 5,
                            "got_reward": False,
                        }

                        # First call - should claim and send
                        result1 = await notify_habit_reward_if_complete(
                            date(2026, 1, 22), user_id=1
                        )
                        assert result1 is True
                        assert mock_send.await_count == 1

                        # Second call - claim fails, should not send
                        result2 = await notify_habit_reward_if_complete(
                            date(2026, 1, 22), user_id=1
                        )
                        assert result2 is True
                        # API should NOT be called again
                        assert mock_send.await_count == 1


class TestFormatHabitRewardMessage:
    """Tests for _format_habit_reward_message() formatter."""

    def test_format_no_reward(self):
        """Test message formatting when no reward is given."""
        from app.services.workout_service import _format_habit_reward_message

        response = {
            "habit_confirmed": True,
            "habit_name": "Fitness Challenge",
            "streak_count": 3,
            "got_reward": False,
            "reward": None,
        }

        message = _format_habit_reward_message(response)

        assert "✅ <b>Habit completed:</b> Fitness Challenge" in message
        assert "🔥🔥🔥 <b>Streak:</b> 3 days" in message
        assert "❌ No reward this time - keep going!" in message
        assert "🎁" not in message

    def test_format_with_reward(self):
        """Test message formatting when reward is given."""
        from app.services.workout_service import _format_habit_reward_message

        response = {
            "habit_confirmed": True,
            "habit_name": "Fitness Challenge",
            "streak_count": 5,
            "got_reward": True,
            "reward": {"name": "Ice Cream", "id": 1},
        }

        message = _format_habit_reward_message(response)

        assert "✅ <b>Habit completed:</b> Fitness Challenge" in message
        assert "🔥🔥🔥🔥🔥 <b>Streak:</b> 5 days" in message
        assert "🎁 <b>Reward:</b> Ice Cream" in message
        assert "❌" not in message

    def test_format_max_fire_emojis(self):
        """Test that fire emojis are capped at 5."""
        from app.services.workout_service import _format_habit_reward_message

        response = {
            "habit_confirmed": True,
            "habit_name": "Test",
            "streak_count": 100,
            "got_reward": False,
            "reward": None,
        }

        message = _format_habit_reward_message(response)

        # Should have exactly 5 fire emojis, not 100
        assert "🔥🔥🔥🔥🔥 <b>Streak:</b> 100 days" in message

    def test_format_single_day_streak(self):
        """Test formatting for streak of 1 day."""
        from app.services.workout_service import _format_habit_reward_message

        response = {
            "habit_confirmed": True,
            "habit_name": "Test",
            "streak_count": 1,
            "got_reward": False,
            "reward": None,
        }

        message = _format_habit_reward_message(response)

        assert "🔥 <b>Streak:</b> 1 days" in message


class TestNotifyHabitRewardTelegramNotification:
    """Tests for Telegram notification in notify_habit_reward_if_complete()."""

    @pytest.mark.asyncio
    async def test_sends_telegram_message_on_success(self):
        """When API succeeds and chat_id provided, sends Telegram message."""
        from app.services.workout_service import notify_habit_reward_if_complete

        mock_challenges = [_make_mock_challenge()]
        mock_api_response = {
            "habit_confirmed": True,
            "habit_name": "Fitness Challenge",
            "streak_count": 3,
            "got_reward": False,
            "reward": None,
        }

        with patch(
            "app.services.workout_service.challenge_repo"
        ) as mock_challenge_repo:
            mock_challenge_repo.get_current_active = AsyncMock(
                return_value=mock_challenges
            )

            with patch(
                "app.services.workout_service._check_all_challenges_complete",
                new_callable=AsyncMock,
            ) as mock_check:
                mock_check.return_value = True

                with patch(
                    "app.services.workout_service.user_settings_repo"
                ) as mock_user_repo:
                    mock_user_repo.try_claim_habit_reward_date = AsyncMock(
                        return_value=True
                    )

                    with patch(
                        "app.services.workout_service.send_habit_completion",
                        new_callable=AsyncMock,
                    ) as mock_send:
                        mock_send.return_value = mock_api_response

                        with patch(
                            "app.services.workout_service.send_telegram_message",
                            new_callable=AsyncMock,
                        ) as mock_telegram:
                            result = await notify_habit_reward_if_complete(
                                date(2026, 1, 22), user_id=1, chat_id=12345
                            )

                            assert result is True
                            mock_telegram.assert_awaited_once()
                            call_args = mock_telegram.call_args
                            assert call_args[0][0] == 12345  # chat_id
                            message = call_args[0][1]
                            assert "Fitness Challenge" in message
                            assert "Streak:" in message

    @pytest.mark.asyncio
    async def test_no_telegram_message_when_no_chat_id(self):
        """When chat_id not provided, no Telegram message sent."""
        from app.services.workout_service import notify_habit_reward_if_complete

        mock_challenges = [_make_mock_challenge()]
        mock_api_response = {
            "habit_confirmed": True,
            "habit_name": "Test",
            "streak_count": 1,
            "got_reward": False,
        }

        with patch(
            "app.services.workout_service.challenge_repo"
        ) as mock_challenge_repo:
            mock_challenge_repo.get_current_active = AsyncMock(
                return_value=mock_challenges
            )

            with patch(
                "app.services.workout_service._check_all_challenges_complete",
                new_callable=AsyncMock,
            ) as mock_check:
                mock_check.return_value = True

                with patch(
                    "app.services.workout_service.user_settings_repo"
                ) as mock_user_repo:
                    mock_user_repo.try_claim_habit_reward_date = AsyncMock(
                        return_value=True
                    )

                    with patch(
                        "app.services.workout_service.send_habit_completion",
                        new_callable=AsyncMock,
                    ) as mock_send:
                        mock_send.return_value = mock_api_response

                        with patch(
                            "app.services.workout_service.send_telegram_message",
                            new_callable=AsyncMock,
                        ) as mock_telegram:
                            # No chat_id provided
                            result = await notify_habit_reward_if_complete(
                                date(2026, 1, 22), user_id=1
                            )

                            assert result is True
                            mock_telegram.assert_not_awaited()


class TestUserSettingsRepositoryHabitReward:
    """Tests for atomic habit reward methods in UserSettingsRepository."""

    @pytest.mark.asyncio
    async def test_try_claim_returns_true_when_not_claimed(self):
        """try_claim_habit_reward_date returns True when date not yet claimed."""
        from src.core.repositories import UserSettingsRepository

        repo = UserSettingsRepository()

        mock_filter = MagicMock()
        mock_filter.exclude.return_value.update.return_value = 1  # 1 row updated

        with patch(
            "src.core.repositories.UserSettings.objects.get_or_create",
            return_value=(MagicMock(), False),
        ):
            with patch(
                "src.core.repositories.UserSettings.objects.filter",
                return_value=mock_filter,
            ):
                result = await repo.try_claim_habit_reward_date(1, date(2026, 1, 22))
                assert result is True

    @pytest.mark.asyncio
    async def test_try_claim_returns_false_when_already_claimed(self):
        """try_claim_habit_reward_date returns False when date already claimed."""
        from src.core.repositories import UserSettingsRepository

        repo = UserSettingsRepository()

        mock_filter = MagicMock()
        mock_filter.exclude.return_value.update.return_value = 0  # 0 rows updated

        with patch(
            "src.core.repositories.UserSettings.objects.get_or_create",
            return_value=(MagicMock(), False),
        ):
            with patch(
                "src.core.repositories.UserSettings.objects.filter",
                return_value=mock_filter,
            ):
                result = await repo.try_claim_habit_reward_date(1, date(2026, 1, 22))
                assert result is False

    @pytest.mark.asyncio
    async def test_clear_claim_returns_true_when_cleared(self):
        """clear_habit_reward_claim returns True when claim cleared."""
        from src.core.repositories import UserSettingsRepository

        repo = UserSettingsRepository()

        mock_filter = MagicMock()
        mock_filter.update.return_value = 1  # 1 row updated

        with patch(
            "src.core.repositories.UserSettings.objects.filter",
            return_value=mock_filter,
        ):
            result = await repo.clear_habit_reward_claim(1, date(2026, 1, 22))
            assert result is True

    @pytest.mark.asyncio
    async def test_clear_claim_returns_false_when_not_found(self):
        """clear_habit_reward_claim returns False when no matching claim."""
        from src.core.repositories import UserSettingsRepository

        repo = UserSettingsRepository()

        mock_filter = MagicMock()
        mock_filter.update.return_value = 0  # 0 rows updated

        with patch(
            "src.core.repositories.UserSettings.objects.filter",
            return_value=mock_filter,
        ):
            result = await repo.clear_habit_reward_claim(1, date(2026, 1, 22))
            assert result is False
