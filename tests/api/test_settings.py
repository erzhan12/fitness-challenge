"""Tests for settings API endpoints."""

import pytest
from unittest.mock import patch, AsyncMock
from src.core.models import AppSettings as AppSettingsModel


class TestGetSettings:
    """Tests for GET /api/v1/settings endpoint."""

    def test_get_settings_success(self, client):
        """Test successful retrieval of settings."""
        # Mock the repository
        mock_settings = AppSettingsModel(
            id=1,
            is_reminder_active=True,
            telegram_chat_id=123456789,
        )

        with patch("src.api.services.app_settings_repo.get_singleton", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_settings

            response = client.get("/api/v1/settings")

            assert response.status_code == 200
            data = response.json()
            assert data["is_reminder_active"] is True
            assert data["telegram_chat_id"] == 123456789

    def test_get_settings_no_chat_id(self, client):
        """Test settings retrieval when chat_id is not set."""
        mock_settings = AppSettingsModel(
            id=1,
            is_reminder_active=False,
            telegram_chat_id=None,
        )

        with patch("src.api.services.app_settings_repo.get_singleton", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_settings

            response = client.get("/api/v1/settings")

            assert response.status_code == 200
            data = response.json()
            assert data["is_reminder_active"] is False
            assert data["telegram_chat_id"] is None


class TestUpdateSettings:
    """Tests for PATCH /api/v1/settings endpoint."""

    def test_update_settings_enable_reminders(self, client, auth_headers):
        """Test enabling reminders."""
        mock_settings = AppSettingsModel(
            id=1,
            is_reminder_active=True,
            telegram_chat_id=123456789,
        )

        with patch("src.api.services.app_settings_repo.update", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_settings

            response = client.patch(
                "/api/v1/settings",
                json={"is_reminder_active": True},
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["is_reminder_active"] is True
            mock_update.assert_called_once()

    def test_update_settings_disable_reminders(self, client, auth_headers):
        """Test disabling reminders."""
        mock_settings = AppSettingsModel(
            id=1,
            is_reminder_active=False,
            telegram_chat_id=123456789,
        )

        with patch("src.api.services.app_settings_repo.update", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_settings

            response = client.patch(
                "/api/v1/settings",
                json={"is_reminder_active": False},
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["is_reminder_active"] is False

    def test_update_settings_unauthorized(self, client, invalid_auth_headers):
        """Test update without valid API key returns 403."""
        response = client.patch(
            "/api/v1/settings",
            json={"is_reminder_active": True},
            headers=invalid_auth_headers
        )

        assert response.status_code == 403

    def test_update_settings_no_auth(self, client):
        """Test update without API key returns 401."""
        response = client.patch(
            "/api/v1/settings",
            json={"is_reminder_active": True}
        )

        assert response.status_code == 401

    def test_update_settings_empty_payload(self, client, auth_headers):
        """Test update with empty payload returns current settings."""
        mock_settings = AppSettingsModel(
            id=1,
            is_reminder_active=True,
            telegram_chat_id=123456789,
        )

        with patch("src.api.services.app_settings_repo.get_singleton", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_settings

            response = client.patch(
                "/api/v1/settings",
                json={},
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["is_reminder_active"] is True
