"""Smoke test for pytest-django in-memory SQLite harness."""

import pytest
from django.conf import settings
from django.db import connection

from src.core.models import AppUser


@pytest.mark.django_db
def test_django_db_uses_isolated_in_memory_sqlite():
    disk_db_path = str(settings.BASE_DIR / "data" / "db.sqlite3")

    user = AppUser.objects.create(telegram_user_id=999001, first_name="Harness")
    fetched = AppUser.objects.get(pk=user.pk)
    assert fetched.first_name == "Harness"

    db_settings = connection.settings_dict
    assert "sqlite" in db_settings["ENGINE"]

    runtime_name = str(db_settings.get("NAME", ""))
    assert runtime_name != disk_db_path
    assert not runtime_name.endswith("data/db.sqlite3")

    configured_name = settings.DATABASES["default"].get("NAME")
    assert configured_name == ":memory:" or "mode=memory" in runtime_name
