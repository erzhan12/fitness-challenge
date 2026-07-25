"""Add per-user reminder hours and JSON idempotency map (additive only).

Adds ``UserSettings.reminder_hours`` (default [13, 21, 22]) and
``UserSettings.last_reminder_sent_dates`` (default {}). Legacy
``last_reminder_{21,22,23}_date`` columns are unchanged until 0011.
"""

from django.db import migrations, models

import src.core.models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_add_workout_motivation_setting"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="reminder_hours",
            field=models.JSONField(default=src.core.models.default_reminder_hours),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="last_reminder_sent_dates",
            field=models.JSONField(
                default=src.core.models.default_empty_reminder_sent_dates
            ),
        ),
    ]
