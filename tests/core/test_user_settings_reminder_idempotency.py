"""UserSettings JSON idempotency (Feature 0022, Slice 2)."""

import threading
from datetime import date

import pytest
from asgiref.sync import async_to_sync

from src.core.models import AppUser, UserSettings
from src.core.repositories import UserSettingsRepository


@pytest.fixture
def user_settings(db):
    user = AppUser.objects.create(telegram_user_id=990022002, first_name="Idempotency")
    return UserSettings.objects.create(user=user)


@pytest.fixture
def repo():
    return UserSettingsRepository()


@pytest.fixture
def mark(repo):
    return async_to_sync(repo.try_mark_hour_sent)


@pytest.fixture
def clear(repo):
    return async_to_sync(repo.clear_hour_sent)


@pytest.mark.django_db
def test_try_mark_hour_sent_first_wins(user_settings, mark):
    today = date(2026, 7, 25)
    assert mark(user_settings.user_id, today, 21) is True
    user_settings.refresh_from_db()
    assert user_settings.last_reminder_sent_dates["21"] == today.isoformat()


@pytest.mark.django_db
def test_try_mark_hour_sent_second_skipped(user_settings, mark):
    today = date(2026, 7, 25)
    assert mark(user_settings.user_id, today, 21) is True
    assert mark(user_settings.user_id, today, 21) is False


@pytest.mark.django_db(transaction=True)
def test_try_mark_hour_sent_concurrent_second_loses(user_settings, mark):
    today = date(2026, 7, 25)
    user_id = user_settings.user_id
    results = []
    barrier = threading.Barrier(2)

    def worker():
        from django.db import connections

        connections.close_all()
        barrier.wait()
        results.append(mark(user_id, today, 21))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == [False, True]


@pytest.mark.django_db
def test_clear_hour_sent_on_failure(user_settings, mark, clear):
    today = date(2026, 7, 25)
    assert mark(user_settings.user_id, today, 21) is True
    assert clear(user_settings.user_id, today, 21) is True
    assert mark(user_settings.user_id, today, 21) is True


@pytest.mark.django_db
def test_stale_hour_key_ignored_for_different_hour(user_settings, mark):
    today = date(2026, 7, 25)
    user_settings.last_reminder_sent_dates = {"23": today.isoformat()}
    user_settings.save(update_fields=["last_reminder_sent_dates"])
    assert mark(user_settings.user_id, today, 21) is True


@pytest.mark.django_db
def test_try_mark_hour_sent_preserves_other_hour_keys(user_settings, mark):
    today = date(2026, 7, 25)
    assert mark(user_settings.user_id, today, 13) is True
    assert mark(user_settings.user_id, today, 21) is True
    user_settings.refresh_from_db()
    assert user_settings.last_reminder_sent_dates == {
        "13": today.isoformat(),
        "21": today.isoformat(),
    }
