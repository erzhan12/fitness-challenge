"""Remove target_total from ExerciseChallenge; make daily_target required.

Steps:
1. Backfill daily_target = ceil(target_total / total_days) where daily_target IS NULL
2. Make daily_target non-nullable
3. Remove target_total column
"""

import logging
import math
from django.db import migrations, models

logger = logging.getLogger(__name__)


def backfill_daily_target(apps, schema_editor):
    """For challenges where daily_target is NULL, compute it from target_total."""
    ExerciseChallenge = apps.get_model("core", "ExerciseChallenge")
    for challenge in ExerciseChallenge.objects.filter(daily_target__isnull=True):
        total_days = (challenge.end_date - challenge.start_date).days + 1
        if total_days > 0 and challenge.target_total > 0:
            challenge.daily_target = math.ceil(challenge.target_total / total_days)
        else:
            logger.warning(
                f"Challenge {challenge.id}: Invalid data (total_days={total_days}, "
                f"target_total={challenge.target_total}). Using fallback daily_target=1"
            )
            challenge.daily_target = 1
        challenge.save(update_fields=["daily_target"])


def reverse_backfill(apps, schema_editor):
    """No-op reverse — we can't un-derive daily_target."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_add_habit_reward_tracking"),
    ]

    operations = [
        # 1. Backfill daily_target for rows where it's NULL
        migrations.RunPython(backfill_daily_target, reverse_backfill),
        # 2. Make daily_target non-nullable
        migrations.AlterField(
            model_name="exercisechallenge",
            name="daily_target",
            field=models.IntegerField(),
        ),
        # 3. Remove target_total column
        migrations.RemoveField(
            model_name="exercisechallenge",
            name="target_total",
        ),
    ]
