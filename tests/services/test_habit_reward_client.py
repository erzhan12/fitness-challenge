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
        """Test successful API call returns True."""
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

                    result = await send_habit_completion(1, date(2026, 1, 22))

                    assert result is True
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
    async def test_api_error_returns_false(self):
        """Test that HTTP error response returns False."""
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

                    assert result is False

    @pytest.mark.asyncio
    async def test_network_error_returns_false(self):
        """Test that network errors return False."""
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

                    assert result is False

    @pytest.mark.asyncio
    async def test_skips_when_no_user_settings(self):
        """Test that it skips and returns False when user has no settings."""
        with patch(
            "app.services.habit_reward_client.user_settings_repo"
        ) as mock_repo:
            mock_repo.get_by_user_id = AsyncMock(return_value=None)

            with patch(
                "app.services.habit_reward_client.httpx.AsyncClient"
            ) as mock_client_class:
                from app.services.habit_reward_client import send_habit_completion

                result = await send_habit_completion(1)

                assert result is False
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

                assert result is False
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

                assert result is False
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
    async def test_no_payload_when_no_date(self):
        """Test that payload is None when no date is provided."""
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
                    assert call_args[1]["json"] is None


class TestNotifyHabitRewardIfComplete:
    """Integration tests for notify_habit_reward_if_complete() in workout_service."""

    @pytest.mark.asyncio
    async def test_returns_true_when_already_sent_today(self):
        """When already sent today, returns True without calling API again."""
        from app.services.workout_service import notify_habit_reward_if_complete

        with patch(
            "app.services.workout_service.user_settings_repo"
        ) as mock_repo:
            mock_repo.check_habit_reward_sent = AsyncMock(return_value=True)

            with patch(
                "app.services.workout_service.send_habit_completion",
                new_callable=AsyncMock,
            ) as mock_send:
                result = await notify_habit_reward_if_complete(
                    date(2026, 1, 22), user_id=1
                )

                assert result is True
                mock_repo.check_habit_reward_sent.assert_awaited_once_with(
                    1, date(2026, 1, 22)
                )
                # Should NOT call API or mark again
                mock_send.assert_not_called()
                mock_repo.mark_habit_reward_sent.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_and_marks_on_success(self):
        """On successful API call, marks as sent and returns True."""
        from app.services.workout_service import notify_habit_reward_if_complete

        with patch(
            "app.services.workout_service.user_settings_repo"
        ) as mock_repo:
            mock_repo.check_habit_reward_sent = AsyncMock(return_value=False)
            mock_repo.mark_habit_reward_sent = AsyncMock()

            with patch(
                "app.services.workout_service.send_habit_completion",
                new_callable=AsyncMock,
            ) as mock_send:
                mock_send.return_value = True  # API success

                result = await notify_habit_reward_if_complete(
                    date(2026, 1, 22), user_id=1
                )

                assert result is True
                mock_send.assert_awaited_once_with(1, date(2026, 1, 22))
                mock_repo.mark_habit_reward_sent.assert_awaited_once_with(
                    1, date(2026, 1, 22)
                )

    @pytest.mark.asyncio
    async def test_does_not_mark_on_api_failure(self):
        """On API failure, does not mark as sent and returns False."""
        from app.services.workout_service import notify_habit_reward_if_complete

        with patch(
            "app.services.workout_service.user_settings_repo"
        ) as mock_repo:
            mock_repo.check_habit_reward_sent = AsyncMock(return_value=False)
            mock_repo.mark_habit_reward_sent = AsyncMock()

            with patch(
                "app.services.workout_service.send_habit_completion",
                new_callable=AsyncMock,
            ) as mock_send:
                mock_send.return_value = False  # API failure

                result = await notify_habit_reward_if_complete(
                    date(2026, 1, 22), user_id=1
                )

                assert result is False
                mock_send.assert_awaited_once_with(1, date(2026, 1, 22))
                # Should NOT mark as sent on failure
                mock_repo.mark_habit_reward_sent.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_when_not_configured(self):
        """When send_habit_completion returns False (not configured), returns False."""
        from app.services.workout_service import notify_habit_reward_if_complete

        with patch(
            "app.services.workout_service.user_settings_repo"
        ) as mock_repo:
            mock_repo.check_habit_reward_sent = AsyncMock(return_value=False)
            mock_repo.mark_habit_reward_sent = AsyncMock()

            with patch(
                "app.services.workout_service.send_habit_completion",
                new_callable=AsyncMock,
            ) as mock_send:
                mock_send.return_value = False  # Not configured

                result = await notify_habit_reward_if_complete(
                    date(2026, 1, 22), user_id=1
                )

                assert result is False
                mock_repo.mark_habit_reward_sent.assert_not_called()

    @pytest.mark.asyncio
    async def test_idempotency_prevents_duplicate_sends(self):
        """Multiple calls with same date only send once."""
        from app.services.workout_service import notify_habit_reward_if_complete

        call_count = 0

        async def mock_check(uid, d):
            nonlocal call_count
            # First call: not sent yet. Subsequent calls: already sent.
            if call_count == 0:
                return False
            return True

        async def mock_mark(uid, d):
            nonlocal call_count
            call_count += 1

        with patch(
            "app.services.workout_service.user_settings_repo"
        ) as mock_repo:
            mock_repo.check_habit_reward_sent = AsyncMock(
                side_effect=mock_check
            )
            mock_repo.mark_habit_reward_sent = AsyncMock(
                side_effect=mock_mark
            )

            with patch(
                "app.services.workout_service.send_habit_completion",
                new_callable=AsyncMock,
            ) as mock_send:
                mock_send.return_value = True

                # First call - should send
                result1 = await notify_habit_reward_if_complete(
                    date(2026, 1, 22), user_id=1
                )
                assert result1 is True
                assert mock_send.await_count == 1

                # Second call - should skip (already sent)
                result2 = await notify_habit_reward_if_complete(
                    date(2026, 1, 22), user_id=1
                )
                assert result2 is True
                # API should NOT be called again
                assert mock_send.await_count == 1


class TestUserSettingsRepositoryHabitReward:
    """Tests for habit reward methods in UserSettingsRepository."""

    @pytest.mark.asyncio
    async def test_check_habit_reward_sent_returns_false_when_not_sent(self):
        """check_habit_reward_sent returns False when field is None."""
        from src.core.repositories import UserSettingsRepository

        repo = UserSettingsRepository()

        mock_settings = _make_user_settings(sent_date=None)

        with patch(
            "src.core.repositories.UserSettings.objects.get_or_create",
            return_value=(mock_settings, False),
        ):
            result = await repo.check_habit_reward_sent(1, date(2026, 1, 22))
            assert result is False

    @pytest.mark.asyncio
    async def test_check_habit_reward_sent_returns_false_for_different_date(self):
        """check_habit_reward_sent returns False when field is different date."""
        from src.core.repositories import UserSettingsRepository

        repo = UserSettingsRepository()

        mock_settings = _make_user_settings(sent_date=date(2026, 1, 21))

        with patch(
            "src.core.repositories.UserSettings.objects.get_or_create",
            return_value=(mock_settings, False),
        ):
            result = await repo.check_habit_reward_sent(1, date(2026, 1, 22))
            assert result is False

    @pytest.mark.asyncio
    async def test_check_habit_reward_sent_returns_true_for_same_date(self):
        """check_habit_reward_sent returns True when field matches target date."""
        from src.core.repositories import UserSettingsRepository

        repo = UserSettingsRepository()

        mock_settings = _make_user_settings(sent_date=date(2026, 1, 22))

        with patch(
            "src.core.repositories.UserSettings.objects.get_or_create",
            return_value=(mock_settings, False),
        ):
            result = await repo.check_habit_reward_sent(1, date(2026, 1, 22))
            assert result is True

    @pytest.mark.asyncio
    async def test_mark_habit_reward_sent_updates_field(self):
        """mark_habit_reward_sent updates the field and saves."""
        from src.core.repositories import UserSettingsRepository

        repo = UserSettingsRepository()

        mock_settings = _make_user_settings(sent_date=None)

        with patch(
            "src.core.repositories.UserSettings.objects.get_or_create",
            return_value=(mock_settings, False),
        ):
            result = await repo.mark_habit_reward_sent(1, date(2026, 1, 22))

            assert mock_settings.last_habit_reward_sent_date == date(
                2026, 1, 22
            )
            mock_settings.save.assert_called_once_with(
                update_fields=["last_habit_reward_sent_date"]
            )
            assert result == mock_settings
