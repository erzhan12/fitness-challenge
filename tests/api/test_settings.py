"""Tests for settings API endpoints."""

import pytest
from unittest.mock import patch, AsyncMock, Mock
from src.core.models import UserSettings as UserSettingsModel, AppUser as AppUserModel


def _make_mock_user(telegram_user_id: int = 123456789) -> AppUserModel:
    """Create a mock approved user."""
    user = AppUserModel(
        id=1,
        telegram_user_id=telegram_user_id,
        username="testuser",
        first_name="Test",
        timezone="Asia/Almaty",
        status="approved",
    )
    return user


class TestGetSettings:
    """Tests for GET /api/v1/settings endpoint."""

    def test_get_settings_success(self, client, user_context_headers):
        """Test successful retrieval of settings."""
        # Mock the repository
        mock_settings = UserSettingsModel(
            user_id=1,
            is_reminder_active=True,
            telegram_chat_id=123456789,
        )
        mock_user = _make_mock_user()

        with patch("src.api.security.app_user_repo.get_by_telegram_user_id", new_callable=AsyncMock) as mock_get_user, \
             patch("src.api.services.user_settings_repo.get_or_create", new_callable=AsyncMock) as mock_get:
            mock_get_user.return_value = mock_user
            mock_get.return_value = mock_settings

            response = client.get("/api/v1/settings", headers=user_context_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["is_reminder_active"] is True
            assert data["telegram_chat_id"] == 123456789

    def test_get_settings_no_chat_id(self, client, user_context_headers):
        """Test settings retrieval when chat_id is not set."""
        mock_settings = UserSettingsModel(
            user_id=1,
            is_reminder_active=False,
            telegram_chat_id=None,
        )
        mock_user = _make_mock_user()

        with patch("src.api.security.app_user_repo.get_by_telegram_user_id", new_callable=AsyncMock) as mock_get_user, \
             patch("src.api.services.user_settings_repo.get_or_create", new_callable=AsyncMock) as mock_get:
            mock_get_user.return_value = mock_user
            mock_get.return_value = mock_settings

            response = client.get("/api/v1/settings", headers=user_context_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["is_reminder_active"] is False
            assert data["telegram_chat_id"] is None


class TestUpdateSettings:
    """Tests for PATCH /api/v1/settings endpoint."""

    def test_update_settings_enable_reminders(self, client, auth_and_user_headers):
        """Test enabling reminders."""
        mock_settings = UserSettingsModel(
            user_id=1,
            is_reminder_active=True,
            telegram_chat_id=123456789,
        )
        mock_user = _make_mock_user()

        with patch("src.api.security.app_user_repo.get_by_telegram_user_id", new_callable=AsyncMock) as mock_get_user, \
             patch("src.api.services.user_settings_repo.get_or_create", new_callable=AsyncMock) as mock_get_or_create, \
             patch("src.api.services.user_settings_repo.update", new_callable=AsyncMock) as mock_update:
            mock_get_user.return_value = mock_user
            mock_get_or_create.return_value = mock_settings
            mock_update.return_value = mock_settings

            response = client.patch(
                "/api/v1/settings",
                json={"is_reminder_active": True},
                headers=auth_and_user_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["is_reminder_active"] is True
            mock_update.assert_called_once()

    def test_update_settings_disable_reminders(self, client, auth_and_user_headers):
        """Test disabling reminders."""
        mock_settings = UserSettingsModel(
            user_id=1,
            is_reminder_active=False,
            telegram_chat_id=123456789,
        )
        mock_user = _make_mock_user()

        with patch("src.api.security.app_user_repo.get_by_telegram_user_id", new_callable=AsyncMock) as mock_get_user, \
             patch("src.api.services.user_settings_repo.get_or_create", new_callable=AsyncMock) as mock_get_or_create, \
             patch("src.api.services.user_settings_repo.update", new_callable=AsyncMock) as mock_update:
            mock_get_user.return_value = mock_user
            mock_get_or_create.return_value = mock_settings
            mock_update.return_value = mock_settings

            response = client.patch(
                "/api/v1/settings",
                json={"is_reminder_active": False},
                headers=auth_and_user_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["is_reminder_active"] is False

    def test_update_settings_unauthorized(self, client, invalid_auth_headers, user_context_headers):
        """Test update without valid API key returns 403."""
        response = client.patch(
            "/api/v1/settings",
            json={"is_reminder_active": True},
            headers={**invalid_auth_headers, **user_context_headers}
        )

        assert response.status_code == 403

    def test_update_settings_no_auth(self, client):
        """Test update without API key returns 401."""
        response = client.patch(
            "/api/v1/settings",
            json={"is_reminder_active": True}
        )

        assert response.status_code == 401

    def test_update_settings_empty_payload(self, client, auth_and_user_headers):
        """Test update with empty payload returns current settings."""
        mock_settings = UserSettingsModel(
            user_id=1,
            is_reminder_active=True,
            telegram_chat_id=123456789,
        )
        mock_user = _make_mock_user()

        with patch("src.api.security.app_user_repo.get_by_telegram_user_id", new_callable=AsyncMock) as mock_get_user, \
             patch("src.api.services.user_settings_repo.get_or_create", new_callable=AsyncMock) as mock_get:
            mock_get_user.return_value = mock_user
            mock_get.return_value = mock_settings

            response = client.patch(
                "/api/v1/settings",
                json={},
                headers=auth_and_user_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["is_reminder_active"] is True
