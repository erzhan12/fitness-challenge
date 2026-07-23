"""Add per-user toggle for workout-log motivational messages.

Adds ``UserSettings.is_workout_motivation_active`` (default True). Gates the
LLM motivational line appended to workout-log Telegram replies. Evening
reminder motivation is unaffected.

No data backfill: Django applies ``default=True`` to existing rows, so current
users keep the pre-feature behavior (motivation enabled).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_add_exception_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="is_workout_motivation_active",
            field=models.BooleanField(default=True),
        ),
    ]
