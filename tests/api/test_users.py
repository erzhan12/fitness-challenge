"""Tests for user registration endpoints."""

from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.core import setup_django

setup_django()

from src.core.models import AppUser as AppUserModel


def _make_user(telegram_user_id: int = 123456789) -> AppUserModel:
    return AppUserModel(
        id=1,
        telegram_user_id=telegram_user_id,
        username="testuser",
        first_name="Test",
        timezone="Asia/Almaty",
        status="pending",
        created_at=datetime.now(dt_timezone.utc),
    )


def _make_approved_user(telegram_user_id: int = 123456789) -> AppUserModel:
    return AppUserModel(
        id=1,
        telegram_user_id=telegram_user_id,
        username="testuser",
        first_name="Test",
        timezone="Asia/Almaty",
        status="approved",
        created_at=datetime.now(dt_timezone.utc),
    )


def test_register_user_closed(client):
    data = {
        "telegram_user_id": 123456789,
        "username": "testuser",
        "first_name": "Test",
        "timezone": "Asia/Almaty",
    }

    with patch(
        "src.api.routers.users.app_settings_repo.get_singleton",
        new_callable=AsyncMock,
    ) as mock_get_settings, patch(
        "src.api.routers.users.app_user_repo.get_or_create_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_or_create:
        mock_get_settings.return_value = SimpleNamespace(is_registration_open=False)

        response = client.post("/api/v1/users", json=data)

        assert response.status_code == 403
        mock_get_or_create.assert_not_called()


def test_register_user_open_creates_user(client):
    data = {
        "telegram_user_id": 123456789,
        "username": "testuser",
        "first_name": "Test",
        "timezone": "Asia/Almaty",
    }
    mock_user = _make_user()

    with patch(
        "src.api.routers.users.app_settings_repo.get_singleton",
        new_callable=AsyncMock,
    ) as mock_get_settings, patch(
        "src.api.routers.users.app_user_repo.get_or_create_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_or_create_user, patch(
        "src.api.routers.users.user_settings_repo.get_or_create",
        new_callable=AsyncMock,
    ) as mock_get_or_create_settings:
        mock_get_settings.return_value = SimpleNamespace(is_registration_open=True)
        mock_get_or_create_user.return_value = (mock_user, True)
        mock_get_or_create_settings.return_value = SimpleNamespace(id=1, user_id=1)

        response = client.post("/api/v1/users", json=data)

        assert response.status_code == 201
        payload = response.json()
        assert payload["telegram_user_id"] == data["telegram_user_id"]
        mock_get_or_create_settings.assert_called_once_with(mock_user.id)


def test_get_current_user_profile(client, user_context_headers):
    mock_user = _make_approved_user()
    mock_settings = SimpleNamespace(
        user_id=1,
        telegram_chat_id=987654321,
        is_reminder_active=True,
        is_workout_motivation_active=True,
    )

    with patch(
        "src.api.security.app_user_repo.get_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_user, patch(
        "src.api.routers.users.user_settings_repo.get_by_user_id",
        new_callable=AsyncMock,
    ) as mock_get_settings:
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_settings

        response = client.get("/api/v1/users/me", headers=user_context_headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["user"]["telegram_user_id"] == mock_user.telegram_user_id
        assert payload["settings"]["telegram_chat_id"] == 987654321
        assert payload["settings"]["is_workout_motivation_active"] is True


def test_update_current_user_settings_disable_workout_motivation(client, user_context_headers):
    """PATCH /me/settings must carry is_workout_motivation_active to the repo.

    Guards the documented per-user toggle surface: without this, forgetting the
    field on UserSettingsUpdate would be silently uncaught since
    model_dump(exclude_unset=True) drops absent fields.
    """
    mock_user = _make_approved_user()
    updated_settings = SimpleNamespace(
        user_id=1,
        telegram_chat_id=987654321,
        is_reminder_active=True,
        is_workout_motivation_active=False,
    )

    with patch(
        "src.api.security.app_user_repo.get_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_user, patch(
        "src.api.routers.users.user_settings_repo.get_or_create",
        new_callable=AsyncMock,
    ) as mock_get_or_create, patch(
        "src.api.routers.users.user_settings_repo.update",
        new_callable=AsyncMock,
    ) as mock_update:
        mock_get_user.return_value = mock_user
        mock_get_or_create.return_value = updated_settings
        mock_update.return_value = updated_settings

        response = client.patch(
            "/api/v1/users/me/settings",
            json={"is_workout_motivation_active": False},
            headers=user_context_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["is_workout_motivation_active"] is False
        # The flag must reach the repository update payload.
        update_arg = mock_update.call_args.args[1]
        assert update_arg["is_workout_motivation_active"] is False


def test_update_current_user_profile(client, user_context_headers):
    mock_user = _make_approved_user()
    updated_user = AppUserModel(
        id=1,
        telegram_user_id=mock_user.telegram_user_id,
        username="testuser",
        first_name="Updated",
        timezone="Asia/Almaty",
        status="approved",
        created_at=datetime.now(dt_timezone.utc),
    )

    with patch(
        "src.api.security.app_user_repo.get_by_telegram_user_id",
        new_callable=AsyncMock,
    ) as mock_get_user, patch(
        "src.api.routers.users.app_user_repo.update",
        new_callable=AsyncMock,
    ) as mock_update:
        mock_get_user.return_value = mock_user
        mock_update.return_value = updated_user

        response = client.patch(
            "/api/v1/users/me",
            json={"first_name": "Updated"},
            headers=user_context_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["first_name"] == "Updated"
