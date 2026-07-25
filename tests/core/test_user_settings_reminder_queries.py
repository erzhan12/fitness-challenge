"""UserSettings reminder query helpers (Feature 0022, Slice 3)."""

import pytest
from asgiref.sync import async_to_sync
from django.db import connection

from src.core.models import AppUser, UserSettings
from src.core.repositories import UserSettingsRepository


@pytest.fixture
def repo():
    return UserSettingsRepository()


@pytest.fixture
def get_users(repo):
    return async_to_sync(repo.get_users_for_reminder_hour)


@pytest.fixture
def get_distinct_hours(repo):
    return async_to_sync(repo.get_distinct_active_reminder_hours)


@pytest.fixture
def get_enabled_users(repo):
    return async_to_sync(repo.get_users_with_reminders_enabled)


def _make_user_settings(
    *,
    telegram_user_id: int,
    status: str = AppUser.Status.APPROVED,
    reminder_hours=None,
    is_reminder_active: bool = True,
    telegram_chat_id: int | None = 12345,
) -> UserSettings:
    user = AppUser.objects.create(
        telegram_user_id=telegram_user_id,
        first_name="Query",
        status=status,
    )
    kwargs = {
        "user": user,
        "is_reminder_active": is_reminder_active,
        "telegram_chat_id": telegram_chat_id,
    }
    if reminder_hours is not None:
        kwargs["reminder_hours"] = reminder_hours
    return UserSettings.objects.create(**kwargs)


@pytest.mark.django_db
def test_get_users_for_reminder_hour_excludes_empty_hours(get_users):
    empty = _make_user_settings(telegram_user_id=990023001, reminder_hours=[])
    _make_user_settings(telegram_user_id=990023002, reminder_hours=[13, 21])

    result = get_users(13)

    assert len(result) == 1
    assert result[0].user_id == empty.user_id + 1


@pytest.mark.django_db
def test_get_users_for_reminder_hour_excludes_unapproved(get_users):
    _make_user_settings(
        telegram_user_id=990023011,
        status=AppUser.Status.PENDING,
        reminder_hours=[13, 21],
    )
    approved = _make_user_settings(
        telegram_user_id=990023012,
        reminder_hours=[13, 21],
    )

    result = get_users(13)

    assert len(result) == 1
    assert result[0].user_id == approved.user_id


@pytest.mark.django_db
def test_get_users_for_reminder_hour_excludes_missing_hour(get_users):
    _make_user_settings(telegram_user_id=990023021, reminder_hours=[13, 21])

    result = get_users(22)

    assert result == []


@pytest.mark.django_db
def test_get_users_for_reminder_hour_matches_custom_hour(get_users):
    custom = _make_user_settings(telegram_user_id=990023031, reminder_hours=[8, 20])

    result = get_users(8)

    assert len(result) == 1
    assert result[0].user_id == custom.user_id


@pytest.mark.django_db
def test_get_distinct_active_reminder_hours_union(get_distinct_hours):
    _make_user_settings(telegram_user_id=990023041, reminder_hours=[13, 21])
    _make_user_settings(telegram_user_id=990023042, reminder_hours=[21, 22])

    assert get_distinct_hours() == [13, 21, 22]


@pytest.mark.django_db
def test_get_distinct_active_reminder_hours_excludes_unapproved(get_distinct_hours):
    _make_user_settings(
        telegram_user_id=990023051,
        status=AppUser.Status.PENDING,
        reminder_hours=[8, 9],
    )
    _make_user_settings(telegram_user_id=990023052, reminder_hours=[13, 21])

    assert get_distinct_hours() == [13, 21]


@pytest.mark.django_db
def test_get_users_with_reminders_enabled_excludes_empty_hours(get_enabled_users):
    """Real DB-backed check for the legacy (`hour=None`) path's opt-out query.

    `check_daily_reminders(hour=None)` relies on `get_users_with_reminders_enabled`
    to exclude `reminder_hours=[]` opt-outs. This must be verified against the
    real ORM/SQL filter, not a mocked repo return value.
    """
    empty = _make_user_settings(telegram_user_id=990023071, reminder_hours=[])
    enabled = _make_user_settings(telegram_user_id=990023072, reminder_hours=[13, 21])

    result = get_enabled_users()

    result_user_ids = {s.user_id for s in result}
    assert enabled.user_id in result_user_ids
    assert empty.user_id not in result_user_ids


@pytest.mark.django_db
def test_get_users_for_reminder_hour_works_on_sqlite(get_users):
    assert "sqlite" in connection.settings_dict["ENGINE"]

    custom = _make_user_settings(telegram_user_id=990023061, reminder_hours=[8, 20])
    _make_user_settings(telegram_user_id=990023062, reminder_hours=[13, 21])

    assert get_users(22) == []
    result = get_users(8)
    assert len(result) == 1
    assert result[0].user_id == custom.user_id
