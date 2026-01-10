from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ExerciseType",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                ("display_name", models.CharField(max_length=100)),
                ("emoji", models.CharField(max_length=10)),
                ("unit", models.CharField(default="reps", max_length=20)),
                ("aliases", models.JSONField(default=list)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "exercise_types",
            },
        ),
        migrations.CreateModel(
            name="ExerciseChallenge",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("challenge_name", models.CharField(max_length=200)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("target_total", models.IntegerField()),
                ("daily_target", models.IntegerField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                (
                    "exercise_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="challenges",
                        to="core.exercisetype",
                    ),
                ),
            ],
            options={
                "db_table": "exercise_challenges",
            },
        ),
        migrations.CreateModel(
            name="ExerciseLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date", models.DateField()),
                ("timestamp", models.DateTimeField()),
                ("count", models.IntegerField()),
                ("cumulative_total", models.IntegerField(blank=True, null=True)),
                ("day_number", models.IntegerField(blank=True, null=True)),
                ("status", models.CharField(blank=True, max_length=20, null=True)),
                ("raw_message", models.TextField(blank=True, null=True)),
                ("duration_seconds", models.IntegerField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, null=True)),
                (
                    "challenge",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="logs",
                        to="core.exercisechallenge",
                    ),
                ),
                (
                    "exercise_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs",
                        to="core.exercisetype",
                    ),
                ),
            ],
            options={
                "db_table": "exercise_logs",
                "ordering": ["-timestamp"],
            },
        ),
        migrations.CreateModel(
            name="UserStats",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("all_time_total", models.IntegerField(default=0)),
                ("best_daily_count", models.IntegerField(default=0)),
                ("current_streak", models.IntegerField(default=0)),
                ("longest_streak", models.IntegerField(default=0)),
                ("last_logged_date", models.DateField(blank=True, null=True)),
                (
                    "exercise_type",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_stats",
                        to="core.exercisetype",
                    ),
                ),
            ],
            options={
                "db_table": "user_stats",
                "verbose_name_plural": "User stats",
            },
        ),
    ]

