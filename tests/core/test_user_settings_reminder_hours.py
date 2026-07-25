"""UserSettings.reminder_hours validation and defaults (Feature 0022, Slice 1)."""

import pytest
from django.core.exceptions import ValidationError

from src.core.models import AppUser, UserSettings


@pytest.fixture
def user_settings(db):
    user = AppUser.objects.create(telegram_user_id=990022001, first_name="Reminder")
    return UserSettings.objects.create(user=user)


@pytest.mark.django_db
def test_default_reminder_hours_on_create(user_settings):
    assert user_settings.reminder_hours == [13, 21, 22]


@pytest.mark.django_db
def test_empty_reminder_hours_allowed(user_settings):
    user_settings.reminder_hours = []
    user_settings.save()
    user_settings.refresh_from_db()
    assert user_settings.reminder_hours == []


@pytest.mark.django_db
@pytest.mark.parametrize("invalid_hours", [[25], ["21"]])
def test_invalid_hour_rejected(user_settings, invalid_hours):
    user_settings.reminder_hours = invalid_hours
    with pytest.raises(ValidationError):
        user_settings.save()


@pytest.mark.django_db
def test_reminder_hours_normalized_sorted_unique(user_settings):
    user_settings.reminder_hours = [22, 13, 21, 21]
    user_settings.save()
    user_settings.refresh_from_db()
    assert user_settings.reminder_hours == [13, 21, 22]


@pytest.mark.django_db
def test_reminder_hours_rejects_list_longer_than_24(user_settings):
    user_settings.reminder_hours = list(range(25))  # 0..24 — 25 items
    with pytest.raises(ValidationError):
        user_settings.save()
