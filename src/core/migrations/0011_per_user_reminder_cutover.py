"""Data cutover + destructive drops for per-user reminder hours (Slice 7).

Backfills ``UserSettings.reminder_hours`` / ``last_reminder_sent_dates`` from
the legacy ``AppSettings`` singleton (kill switch, telegram_chat_id,
per-hour idempotency dates), then drops the legacy columns from both
``UserSettings`` and ``AppSettings``. Never edit an applied ``0010`` in
place — this migration is additive-on-top, per the Feature 0022 rollout
plan (docs/features/0022_PLAN.md Phase 1).

Deploy safety: this migration is only safe to apply after the container
serving the old (pre-cutover) code has been stopped — the current deploy
already does stop-old -> migrate -> start-new (see plan doc), so no
additional maintenance drain is required today. If deploy ever becomes
multi-replica / migrate-while-old-code-still-running, split the
``RemoveField`` operations below into a later ``0012`` instead.

PRE-DEPLOY GATE: because deploy runs under ``set -eu`` (stop-old ->
migrate -> start-new), a ``ReminderCutoverBlocked`` raised below fails the
migration with no old container left to roll back to. Before deploying,
verify prod does not have a non-null ``AppSettings.telegram_chat_id`` with
no ``AppUser(telegram_user_id=0)`` — or apply one of the recovery paths in
the exception message first. See RULES.md > Evening Reminders System >
"Deploy — Migration 0011 pre-deploy gate".
"""

from django.db import migrations

DEFAULT_REMINDER_HOURS = [13, 21, 22]


class ReminderCutoverBlocked(Exception):
    """Raised when the global reminder chat id cannot be safely transferred.

    Only recovery paths that make a subsequent re-run of this migration
    succeed are listed in the message — see docs/features/0022_PLAN.md
    Phase 1 (0011 section) for the full policy.
    """


def cutover_reminders(apps, schema_editor):
    AppSettings = apps.get_model("core", "AppSettings")
    AppUser = apps.get_model("core", "AppUser")
    UserSettings = apps.get_model("core", "UserSettings")

    # Unconditional backfill: AddField(default=list-like) in 0010 already
    # materialized `[]` on every existing row, so a naive "set default where
    # missing" step would no-op. Only after this backfill is `[]` a
    # meaningful admin opt-out.
    UserSettings.objects.update(reminder_hours=list(DEFAULT_REMINDER_HOURS))

    try:
        app_settings = AppSettings.objects.get(id=1)
    except AppSettings.DoesNotExist:
        # No singleton: nothing to propagate/copy. Schema drops still proceed.
        return

    if not app_settings.is_reminder_active:
        UserSettings.objects.update(is_reminder_active=False)

    # Stable id from 0004_backfill_default_user — never key off mutable
    # `username` (0004 also skips creating this user when there was no
    # legacy exercise data, so it may be absent even on a used DB).
    default_user = AppUser.objects.filter(telegram_user_id=0).first()
    global_chat_id = app_settings.telegram_chat_id

    if global_chat_id is not None and default_user is None:
        raise ReminderCutoverBlocked(
            f"AppSettings.telegram_chat_id={global_chat_id} is set but no "
            "AppUser.telegram_user_id=0 exists to receive it. Migration 0011 "
            "stopped before dropping AppSettings.telegram_chat_id. To "
            "recover, either:\n"
            "  1. Create the legacy owner: insert AppUser(telegram_user_id=0, "
            "...) with UserSettings.telegram_chat_id="
            f"{global_chat_id}, then re-run this migration; or\n"
            "  2. Map to an existing approved user: set that user's "
            f"UserSettings.telegram_chat_id to {global_chat_id}, then set "
            "AppSettings.telegram_chat_id to NULL, then re-run this "
            "migration (a null global chat id skips the transfer so the "
            "drops proceed)."
        )

    if default_user is None:
        # No default user and nothing to transfer — safe to proceed to drops.
        return

    default_settings, _created = UserSettings.objects.get_or_create(user=default_user)

    if global_chat_id is not None and default_settings.telegram_chat_id != global_chat_id:
        # Stale/empty per-user chat id must not win over the live singleton.
        default_settings.telegram_chat_id = global_chat_id
        default_settings.save(update_fields=["telegram_chat_id"])

    sent_dates = {}
    for hour_key, value in (
        ("21", app_settings.last_reminder_21_date),
        ("22", app_settings.last_reminder_22_date),
        ("23", app_settings.last_reminder_23_date),
    ):
        if value is not None:
            sent_dates[hour_key] = value.isoformat()
    if sent_dates:
        default_settings.last_reminder_sent_dates = sent_dates
        default_settings.save(update_fields=["last_reminder_sent_dates"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_per_user_reminder_hours"),
    ]

    operations = [
        migrations.RunPython(cutover_reminders, migrations.RunPython.noop),
        migrations.RemoveField(model_name="usersettings", name="last_reminder_21_date"),
        migrations.RemoveField(model_name="usersettings", name="last_reminder_22_date"),
        migrations.RemoveField(model_name="usersettings", name="last_reminder_23_date"),
        migrations.RemoveField(model_name="appsettings", name="is_reminder_active"),
        migrations.RemoveField(model_name="appsettings", name="telegram_chat_id"),
        migrations.RemoveField(model_name="appsettings", name="last_reminder_21_date"),
        migrations.RemoveField(model_name="appsettings", name="last_reminder_22_date"),
        migrations.RemoveField(model_name="appsettings", name="last_reminder_23_date"),
    ]
