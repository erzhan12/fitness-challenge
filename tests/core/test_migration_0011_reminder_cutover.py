"""Migration 0011 data cutover + destructive drops (Feature 0022, Slice 7).

Harness (required, not a normal ``django_db`` seed): the test database is
already migrated to latest by the pytest-django session setup, so after
``0011`` ships, legacy ``AppSettings`` reminder columns / per-user
``last_reminder_*_date`` no longer exist on the current model registry.
Every test here:

1. Uses ``@pytest.mark.django_db(transaction=True)``.
2. Drives the schema with Django's ``MigrationExecutor`` — rolling back to
   (or landing on) ``0010`` only, then seeding via the **historical** app
   registry (``executor.loader.project_state(("core", "0010")).apps``).
3. Migrates forward to ``0011``, then asserts via the **current** models
   (post-``0011`` registry).
4. Never seeds dropped columns through the current model registry.
"""

from datetime import date

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from src.core.models import AppUser, UserSettings

CORE = "core"
TARGET_0010 = "0010_per_user_reminder_hours"
TARGET_0011 = "0011_per_user_reminder_cutover"


def _migrate_to(target: str) -> None:
    """Drive the ``core`` app to the given migration node via a fresh executor."""
    MigrationExecutor(connection).migrate([(CORE, target)])


def _apps_at(target: str):
    """Historical app registry as of the given migration node."""
    return MigrationExecutor(connection).loader.project_state((CORE, target)).apps


def _reset_to_0010() -> None:
    """Land the schema on 0010 regardless of the session's initial state."""
    _migrate_to(TARGET_0010)


@pytest.fixture(autouse=True)
def _restore_head_schema_after_test():
    """Guarantee the shared in-memory DB is back at head after each test.

    Failure-path tests intentionally leave the schema at 0010 (rolled back
    atomically) with a blocking singleton chat id; this restores head so
    unrelated tests/fixtures relying on the full schema are unaffected.
    """
    yield
    leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
    try:
        MigrationExecutor(connection).migrate(leaves)
    except Exception:
        # A failure-path test left AppSettings.telegram_chat_id set with no
        # legacy owner (0011 blocks in that state by design) — clear it via
        # the historical 0010 registry so the schema can climb back to head.
        apps_0010 = _apps_at(TARGET_0010)
        AppSettings0010 = apps_0010.get_model(CORE, "AppSettings")
        AppSettings0010.objects.filter(id=1).update(telegram_chat_id=None)
        MigrationExecutor(connection).migrate(leaves)


@pytest.mark.django_db(transaction=True)
def test_backfills_default_user_idempotency_and_hours():
    _reset_to_0010()
    apps_0010 = _apps_at(TARGET_0010)
    AppUser0010 = apps_0010.get_model(CORE, "AppUser")
    UserSettings0010 = apps_0010.get_model(CORE, "UserSettings")
    AppSettings0010 = apps_0010.get_model(CORE, "AppSettings")

    default_user = AppUser0010.objects.create(telegram_user_id=0, first_name="Legacy")
    UserSettings0010.objects.create(user=default_user)
    AppSettings0010.objects.create(
        id=1,
        last_reminder_21_date=date(2026, 7, 20),
        last_reminder_22_date=date(2026, 7, 21),
    )

    _migrate_to(TARGET_0011)

    settings = UserSettings.objects.get(user__telegram_user_id=0)
    assert settings.last_reminder_sent_dates == {"21": "2026-07-20", "22": "2026-07-21"}
    assert settings.reminder_hours == [13, 21, 22]


@pytest.mark.django_db(transaction=True)
def test_all_existing_rows_get_default_hours_not_empty_list():
    _reset_to_0010()
    apps_0010 = _apps_at(TARGET_0010)
    AppUser0010 = apps_0010.get_model(CORE, "AppUser")
    UserSettings0010 = apps_0010.get_model(CORE, "UserSettings")

    for i, hours in enumerate(([], [13, 21, 22], [9])):
        user = AppUser0010.objects.create(telegram_user_id=1000 + i, first_name=f"U{i}")
        UserSettings0010.objects.create(user=user, reminder_hours=hours)

    _migrate_to(TARGET_0011)

    for settings in UserSettings.objects.all():
        assert settings.reminder_hours == [13, 21, 22]


@pytest.mark.django_db(transaction=True)
def test_propagates_global_kill_switch_when_inactive():
    _reset_to_0010()
    apps_0010 = _apps_at(TARGET_0010)
    AppUser0010 = apps_0010.get_model(CORE, "AppUser")
    UserSettings0010 = apps_0010.get_model(CORE, "UserSettings")
    AppSettings0010 = apps_0010.get_model(CORE, "AppSettings")

    AppSettings0010.objects.create(id=1, is_reminder_active=False)
    for i in range(3):
        user = AppUser0010.objects.create(telegram_user_id=2000 + i, first_name=f"U{i}")
        UserSettings0010.objects.create(user=user, is_reminder_active=True)

    _migrate_to(TARGET_0011)

    assert UserSettings.objects.count() == 3
    for settings in UserSettings.objects.all():
        assert settings.is_reminder_active is False


@pytest.mark.django_db(transaction=True)
def test_copies_singleton_telegram_chat_id_to_default_user():
    _reset_to_0010()
    apps_0010 = _apps_at(TARGET_0010)
    AppUser0010 = apps_0010.get_model(CORE, "AppUser")
    UserSettings0010 = apps_0010.get_model(CORE, "UserSettings")
    AppSettings0010 = apps_0010.get_model(CORE, "AppSettings")

    default_user = AppUser0010.objects.create(telegram_user_id=0, first_name="Legacy")
    UserSettings0010.objects.create(user=default_user, telegram_chat_id=None)
    AppSettings0010.objects.create(id=1, telegram_chat_id=999)

    _migrate_to(TARGET_0011)

    settings = UserSettings.objects.get(user__telegram_user_id=0)
    assert settings.telegram_chat_id == 999


@pytest.mark.django_db(transaction=True)
def test_fresh_db_no_singleton_still_migrates():
    _reset_to_0010()
    apps_0010 = _apps_at(TARGET_0010)
    AppUser0010 = apps_0010.get_model(CORE, "AppUser")
    UserSettings0010 = apps_0010.get_model(CORE, "UserSettings")

    user = AppUser0010.objects.create(telegram_user_id=5555, first_name="Solo")
    UserSettings0010.objects.create(user=user)

    _migrate_to(TARGET_0011)

    settings = UserSettings.objects.get(user__telegram_user_id=5555)
    assert settings.reminder_hours == [13, 21, 22]


@pytest.mark.django_db(transaction=True)
def test_non_null_global_chat_without_legacy_user_fails():
    _reset_to_0010()
    apps_0010 = _apps_at(TARGET_0010)
    AppSettings0010 = apps_0010.get_model(CORE, "AppSettings")
    AppSettings0010.objects.create(id=1, telegram_chat_id=555)

    with pytest.raises(Exception, match="telegram_chat_id"):
        _migrate_to(TARGET_0011)

    # Migration failed atomically: schema/data rolled back to 0010, so the
    # global chat id must still be intact (not dropped).
    apps_0010_after = _apps_at(TARGET_0010)
    AppSettings0010_after = apps_0010_after.get_model(CORE, "AppSettings")
    assert AppSettings0010_after.objects.get(id=1).telegram_chat_id == 555


@pytest.mark.django_db(transaction=True)
def test_recovery_after_clearing_global_chat_succeeds():
    _reset_to_0010()
    apps_0010 = _apps_at(TARGET_0010)
    AppUser0010 = apps_0010.get_model(CORE, "AppUser")
    UserSettings0010 = apps_0010.get_model(CORE, "UserSettings")
    AppSettings0010 = apps_0010.get_model(CORE, "AppSettings")

    approved_user = AppUser0010.objects.create(telegram_user_id=42, first_name="Approved")
    approved_settings = UserSettings0010.objects.create(user=approved_user)
    AppSettings0010.objects.create(id=1, telegram_chat_id=555)

    with pytest.raises(Exception, match="telegram_chat_id"):
        _migrate_to(TARGET_0011)

    # Operator recovery: map the chat id onto the approved user, then null
    # out the global field (still at 0010 — rolled back atomically).
    apps_0010_fix = _apps_at(TARGET_0010)
    UserSettings0010_fix = apps_0010_fix.get_model(CORE, "UserSettings")
    AppSettings0010_fix = apps_0010_fix.get_model(CORE, "AppSettings")

    settings_row = UserSettings0010_fix.objects.get(pk=approved_settings.pk)
    settings_row.telegram_chat_id = 555
    settings_row.save(update_fields=["telegram_chat_id"])

    app_settings_row = AppSettings0010_fix.objects.get(id=1)
    app_settings_row.telegram_chat_id = None
    app_settings_row.save(update_fields=["telegram_chat_id"])

    _migrate_to(TARGET_0011)

    settings = UserSettings.objects.get(user__telegram_user_id=42)
    assert settings.telegram_chat_id == 555
    assert settings.reminder_hours == [13, 21, 22]


@pytest.mark.django_db(transaction=True)
def test_recovery_after_creating_legacy_user_succeeds():
    _reset_to_0010()
    apps_0010 = _apps_at(TARGET_0010)
    AppSettings0010 = apps_0010.get_model(CORE, "AppSettings")
    AppSettings0010.objects.create(id=1, telegram_chat_id=777)

    with pytest.raises(Exception, match="telegram_chat_id"):
        _migrate_to(TARGET_0011)

    # Operator recovery: create the legacy owner (telegram_user_id=0) with
    # the singleton's chat id (still at 0010 — rolled back atomically).
    apps_0010_fix = _apps_at(TARGET_0010)
    AppUser0010_fix = apps_0010_fix.get_model(CORE, "AppUser")
    UserSettings0010_fix = apps_0010_fix.get_model(CORE, "UserSettings")

    default_user = AppUser0010_fix.objects.create(telegram_user_id=0, first_name="Legacy")
    UserSettings0010_fix.objects.create(user=default_user, telegram_chat_id=777)

    _migrate_to(TARGET_0011)

    settings = UserSettings.objects.get(user__telegram_user_id=0)
    assert settings.telegram_chat_id == 777


@pytest.mark.django_db(transaction=True)
def test_upgrade_from_0010_to_0011():
    _reset_to_0010()
    apps_0010 = _apps_at(TARGET_0010)
    AppUser0010 = apps_0010.get_model(CORE, "AppUser")
    UserSettings0010 = apps_0010.get_model(CORE, "UserSettings")
    AppSettings0010 = apps_0010.get_model(CORE, "AppSettings")

    default_user = AppUser0010.objects.create(telegram_user_id=0, first_name="Legacy")
    UserSettings0010.objects.create(user=default_user, reminder_hours=[9])
    AppSettings0010.objects.create(id=1, is_reminder_active=True)

    _migrate_to(TARGET_0011)

    settings = UserSettings.objects.get(user__telegram_user_id=0)
    assert settings.reminder_hours == [13, 21, 22]

    # Guards the "amended 0010 in place" mistake: legacy columns must be
    # gone from the *current* model registry, reached via a distinct 0011.
    user_settings_field_names = {f.name for f in UserSettings._meta.get_fields()}
    assert "last_reminder_21_date" not in user_settings_field_names
    assert "last_reminder_22_date" not in user_settings_field_names
    assert "last_reminder_23_date" not in user_settings_field_names

    from src.core.models import AppSettings as CurrentAppSettings

    app_settings_field_names = {f.name for f in CurrentAppSettings._meta.get_fields()}
    assert "is_reminder_active" not in app_settings_field_names
    assert "telegram_chat_id" not in app_settings_field_names
