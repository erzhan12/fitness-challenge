"""Django admin smoke tests for per-user reminder settings (Feature 0022, Slice 8)."""

import pytest
from django.core.exceptions import ValidationError

from src.core.admin import AppSettingsAdmin, UserSettingsAdmin
from src.core.models import AppSettings, AppUser, UserSettings


@pytest.mark.django_db
def test_user_settings_admin_reminder_field_visibility():
    assert "reminder_hours" in UserSettingsAdmin.list_display
    assert "last_reminder_sent_dates" in UserSettingsAdmin.readonly_fields
    assert "reminder_hours" not in UserSettingsAdmin.readonly_fields
    assert "last_reminder_21_date" not in UserSettingsAdmin.readonly_fields


def test_app_settings_admin_registration_only():
    assert AppSettingsAdmin.list_display == ["id", "is_registration_open"]
    assert AppSettingsAdmin.list_editable == ["is_registration_open"]
    assert not hasattr(AppSettingsAdmin, "readonly_fields") or not getattr(
        AppSettingsAdmin, "readonly_fields", None
    )


@pytest.mark.django_db
def test_user_settings_clean_rejects_invalid_reminder_hours():
    user = AppUser.objects.create(telegram_user_id=990022008, first_name="Admin")
    settings = UserSettings.objects.create(user=user, reminder_hours=[13, 21, 22])
    settings.reminder_hours = [25]
    with pytest.raises(ValidationError):
        settings.full_clean()
