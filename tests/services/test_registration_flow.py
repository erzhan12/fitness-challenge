"""Tests for Telegram registration flow controls."""

from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core import setup_django

setup_django()

from django.utils import timezone as django_timezone

import app.services.workout_service as workout_service
from app.services.workout_service import process_incoming_message
from src.core.models import AppUser as AppUserModel


async def _noop_keep_typing(chat_id, stop_event):
    return None


def _make_pending_user(last_attempt_at=None) -> AppUserModel:
    return AppUserModel(
        id=1,
        telegram_user_id=123456789,
        username="testuser",
        first_name="Test",
        timezone="Asia/Almaty",
        status="pending",
        created_at=datetime.now(dt_timezone.utc),
        last_registration_attempt_at=last_attempt_at,
    )


def _make_approved_user(telegram_user_id: int = 123456789) -> AppUserModel:
    return AppUserModel(
        id=1,
        telegram_user_id=telegram_user_id,
        username="superuser",
        first_name="Admin",
        timezone="Asia/Almaty",
        status="approved",
        created_at=datetime.now(dt_timezone.utc),
    )


def _make_target_user(telegram_user_id: int = 555555) -> AppUserModel:
    return AppUserModel(
        id=2,
        telegram_user_id=telegram_user_id,
        username="target",
        first_name="Target",
        timezone="Asia/Almaty",
        status="approved",
        created_at=datetime.now(dt_timezone.utc),
    )


@pytest.mark.asyncio
async def test_registration_closed_blocks_new_user():
    with patch(
        "app.services.workout_service.app_settings_repo.get_singleton",
        new_callable=AsyncMock,
    ) as mock_get_settings, patch(
        "app.services.workout_service.app_user_repo.get_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_user, patch(
        "app.services.workout_service.app_user_repo.get_or_create_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_or_create, patch(
        "app.services.workout_service.send_chat_action",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service.keep_typing",
        new=_noop_keep_typing,
    ), patch(
        "app.services.workout_service.send_telegram_message",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_get_settings.return_value = SimpleNamespace(is_registration_open=False)
        mock_get_user.return_value = None

        await process_incoming_message(
            text="hello",
            chat_id=42,
            telegram_user_id=123456789,
            first_name="Test",
            username="testuser",
        )

        mock_get_or_create.assert_not_called()
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limit_blocks_unapproved_user():
    now = django_timezone.now()
    user = _make_pending_user(last_attempt_at=now)

    with patch(
        "app.services.workout_service.app_settings_repo.get_singleton",
        new_callable=AsyncMock,
    ) as mock_get_settings, patch(
        "app.services.workout_service.app_user_repo.get_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_user, patch(
        "app.services.workout_service.app_user_repo.update",
        new_callable=AsyncMock,
    ) as mock_update, patch(
        "app.services.workout_service.user_settings_repo.update_chat_id",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service.send_chat_action",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service.keep_typing",
        new=_noop_keep_typing,
    ), patch(
        "app.services.workout_service.send_telegram_message",
        new_callable=AsyncMock,
    ) as mock_send, patch(
        "app.services.workout_service.timezone.now",
        return_value=now,
    ):
        mock_get_settings.return_value = SimpleNamespace(is_registration_open=True)
        mock_get_user.return_value = user

        await process_incoming_message(
            text="status",
            chat_id=42,
            telegram_user_id=123456789,
            first_name="Test",
            username="testuser",
        )

        mock_send.assert_called_once()
        mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_status_command_allowed_for_pending_user():
    now = django_timezone.now()
    user = _make_pending_user(last_attempt_at=None)

    with patch(
        "app.services.workout_service.app_settings_repo.get_singleton",
        new_callable=AsyncMock,
    ) as mock_get_settings, patch(
        "app.services.workout_service.app_user_repo.get_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_user, patch(
        "app.services.workout_service.app_user_repo.update",
        new_callable=AsyncMock,
    ) as mock_update, patch(
        "app.services.workout_service.user_settings_repo.update_chat_id",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service.send_chat_action",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service.keep_typing",
        new=_noop_keep_typing,
    ), patch(
        "app.services.workout_service.send_telegram_message",
        new_callable=AsyncMock,
    ) as mock_send, patch(
        "app.services.workout_service.timezone.now",
        return_value=now,
    ):
        mock_get_settings.return_value = SimpleNamespace(is_registration_open=True)
        mock_get_user.return_value = user

        await process_incoming_message(
            text="/status",
            chat_id=42,
            telegram_user_id=123456789,
            first_name="Test",
            username="testuser",
        )

        mock_update.assert_called_once()
        mock_send.assert_called_once()
        sent_text = mock_send.call_args.args[1]
        assert "Registration Status" in sent_text


@pytest.mark.asyncio
async def test_notify_superusers_on_new_registration():
    new_user = _make_pending_user()

    with patch(
        "app.services.workout_service.app_settings_repo.get_singleton",
        new_callable=AsyncMock,
    ) as mock_get_settings, patch(
        "app.services.workout_service.app_user_repo.get_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_user, patch(
        "app.services.workout_service.app_user_repo.get_or_create_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_or_create, patch(
        "app.services.workout_service.app_user_repo.update",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service.user_settings_repo.update_chat_id",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service.notify_superusers_of_new_registration",
        new_callable=AsyncMock,
    ) as mock_notify, patch(
        "app.services.workout_service.send_chat_action",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service.keep_typing",
        new=_noop_keep_typing,
    ), patch(
        "app.services.workout_service.send_telegram_message",
        new_callable=AsyncMock,
    ):
        mock_get_settings.return_value = SimpleNamespace(is_registration_open=True)
        mock_get_user.return_value = None
        mock_get_or_create.return_value = (new_user, True)

        await process_incoming_message(
            text="hello",
            chat_id=42,
            telegram_user_id=123456789,
            first_name="Test",
            username="testuser",
        )

        mock_notify.assert_called_once_with(new_user)


@pytest.mark.asyncio
async def test_update_chat_id_persisted_for_existing_user():
    user = _make_approved_user()

    with patch(
        "app.services.workout_service.app_settings_repo.get_singleton",
        new_callable=AsyncMock,
    ) as mock_get_settings, patch(
        "app.services.workout_service.app_user_repo.get_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_user, patch(
        "app.services.workout_service.user_settings_repo.update_chat_id",
        new_callable=AsyncMock,
    ) as mock_update_chat_id, patch(
        "app.services.workout_service.send_chat_action",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service.keep_typing",
        new=_noop_keep_typing,
    ), patch(
        "app.services.workout_service.send_telegram_message",
        new_callable=AsyncMock,
    ):
        mock_get_settings.return_value = SimpleNamespace(is_registration_open=True)
        mock_get_user.return_value = user

        await process_incoming_message(
            text="/status",
            chat_id=777,
            telegram_user_id=user.telegram_user_id,
            first_name=user.first_name,
            username=user.username,
        )

        mock_update_chat_id.assert_called_once_with(user.id, 777)


@pytest.mark.asyncio
async def test_approve_command_allows_superuser():
    superuser_id = 999
    superuser = _make_approved_user(telegram_user_id=superuser_id)
    target_user = _make_target_user(telegram_user_id=123456)
    target_settings = SimpleNamespace(telegram_chat_id=555)

    with patch(
        "app.services.workout_service.app_settings_repo.get_singleton",
        new_callable=AsyncMock,
    ) as mock_get_settings, patch(
        "app.services.workout_service.app_user_repo.get_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_user, patch(
        "app.services.workout_service.app_user_repo.approve_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_approve, patch(
        "app.services.workout_service.user_settings_repo.update_chat_id",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service.user_settings_repo.get_by_user_id",
        new_callable=AsyncMock,
    ) as mock_get_settings_by_user, patch(
        "app.services.workout_service.send_chat_action",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service.keep_typing",
        new=_noop_keep_typing,
    ), patch(
        "app.services.workout_service.send_telegram_message",
        new_callable=AsyncMock,
    ) as mock_send, patch.object(
        workout_service.settings,
        "SUPERUSER_TELEGRAM_IDS",
        [superuser_id],
    ):
        mock_get_settings.return_value = SimpleNamespace(is_registration_open=True)
        mock_get_user.return_value = superuser
        mock_approve.return_value = target_user
        mock_get_settings_by_user.return_value = target_settings

        await process_incoming_message(
            text="/approve 123456",
            chat_id=42,
            telegram_user_id=superuser_id,
            first_name=superuser.first_name,
            username=superuser.username,
        )

        mock_approve.assert_called_once_with(123456)
        assert mock_send.call_count >= 2
        assert any(call.args[0] == 555 for call in mock_send.call_args_list)


@pytest.mark.asyncio
async def test_reject_command_allows_superuser():
    superuser_id = 999
    superuser = _make_approved_user(telegram_user_id=superuser_id)
    target_user = _make_target_user(telegram_user_id=123456)
    target_settings = SimpleNamespace(telegram_chat_id=555)

    with patch(
        "app.services.workout_service.app_settings_repo.get_singleton",
        new_callable=AsyncMock,
    ) as mock_get_settings, patch(
        "app.services.workout_service.app_user_repo.get_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_user, patch(
        "app.services.workout_service.app_user_repo.reject_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_reject, patch(
        "app.services.workout_service.user_settings_repo.update_chat_id",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service.user_settings_repo.get_by_user_id",
        new_callable=AsyncMock,
    ) as mock_get_settings_by_user, patch(
        "app.services.workout_service.send_chat_action",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service.keep_typing",
        new=_noop_keep_typing,
    ), patch(
        "app.services.workout_service.send_telegram_message",
        new_callable=AsyncMock,
    ) as mock_send, patch.object(
        workout_service.settings,
        "SUPERUSER_TELEGRAM_IDS",
        [superuser_id],
    ):
        mock_get_settings.return_value = SimpleNamespace(is_registration_open=True)
        mock_get_user.return_value = superuser
        mock_reject.return_value = target_user
        mock_get_settings_by_user.return_value = target_settings

        await process_incoming_message(
            text="/reject 123456",
            chat_id=42,
            telegram_user_id=superuser_id,
            first_name=superuser.first_name,
            username=superuser.username,
        )

        mock_reject.assert_called_once_with(123456)
        assert mock_send.call_count >= 2
        assert any(call.args[0] == 555 for call in mock_send.call_args_list)
