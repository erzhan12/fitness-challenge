"""Add exception-day support to ExerciseChallenge.

Adds:
1. ``ExerciseChallenge.exception_weekdays`` — canonical CSV of ISO weekday
   ints (1=Mon..7=Sun) marking recurring rest days. Empty string = none.
2. New ``ChallengeExceptionDay`` model — one-off rest dates attached to a
   challenge, unique on (challenge, date).

No data backfill: existing challenges keep ``exception_weekdays=""`` and
zero exception-day rows. Their behavior is bit-for-bit identical to before.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_remove_target_total'),
    ]

    operations = [
        migrations.AddField(
            model_name='exercisechallenge',
            name='exception_weekdays',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.CreateModel(
            name='ChallengeExceptionDay',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('reason', models.CharField(blank=True, default='', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('challenge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exception_days', to='core.exercisechallenge')),
            ],
            options={
                'db_table': 'challenge_exception_days',
                'ordering': ['date'],
                'indexes': [models.Index(fields=['challenge', 'date'], name='challenge_e_challen_2fda5e_idx')],
                'unique_together': {('challenge', 'date')},
            },
        ),
    ]
