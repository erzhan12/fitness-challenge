from django.db import models


class ExerciseType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    emoji = models.CharField(max_length=10)
    unit = models.CharField(max_length=20, default="reps")
    aliases = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "exercise_types"

    def __str__(self):
        return f"{self.emoji} {self.display_name}"


class ExerciseChallenge(models.Model):
    exercise_type = models.ForeignKey(
        ExerciseType,
        on_delete=models.CASCADE,
        related_name="challenges"
    )
    challenge_name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    target_total = models.IntegerField()
    daily_target = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "exercise_challenges"

    def __str__(self):
        return f"{self.challenge_name} ({self.start_date} - {self.end_date})"


class ExerciseLog(models.Model):
    exercise_type = models.ForeignKey(
        ExerciseType,
        on_delete=models.CASCADE,
        related_name="logs"
    )
    challenge = models.ForeignKey(
        ExerciseChallenge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs"
    )
    date = models.DateField()
    timestamp = models.DateTimeField()
    count = models.IntegerField()
    cumulative_total = models.IntegerField(null=True, blank=True)
    day_number = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, null=True, blank=True)
    raw_message = models.TextField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "exercise_logs"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.exercise_type.name}: {self.count} on {self.date}"


class UserStats(models.Model):
    exercise_type = models.OneToOneField(
        ExerciseType,
        on_delete=models.CASCADE,
        related_name="user_stats"
    )
    all_time_total = models.IntegerField(default=0)
    best_daily_count = models.IntegerField(default=0)
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_logged_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "user_stats"
        verbose_name_plural = "User stats"

    def __str__(self):
        return f"{self.exercise_type.name} stats: {self.all_time_total} total"
