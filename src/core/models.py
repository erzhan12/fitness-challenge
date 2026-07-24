from django.db import models

from .validators import (
    normalize_exception_weekdays,
    normalize_reminder_hours,
    validate_timezone_field,
)


def default_reminder_hours() -> list:
    """Return a new default reminder schedule for UserSettings.reminder_hours."""
    return [13, 21, 22]


def default_empty_reminder_sent_dates() -> dict:
    """Return a new empty idempotency map for UserSettings.last_reminder_sent_dates."""
    return {}


class AppUser(models.Model):
    """Application user model for multi-user support.

    Separate from Django's auth.User to avoid custom auth migrations.
    Users are identified by their Telegram user ID.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    telegram_user_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=100, null=True, blank=True)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    timezone = models.CharField(
        max_length=50,
        default="Asia/Almaty",
        validators=[validate_timezone_field],
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    last_registration_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "app_users"

    def __str__(self):
        name = self.first_name or self.username or str(self.telegram_user_id)
        return f"{name} ({self.status})"

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED


class UserSettings(models.Model):
    """Per-user settings for reminders and preferences.

    One-to-one relationship with AppUser.
    """
    user = models.OneToOneField(
        AppUser,
        on_delete=models.CASCADE,
        related_name="settings"
    )
    telegram_chat_id = models.BigIntegerField(null=True, blank=True)
    is_reminder_active = models.BooleanField(default=True)
    # Toggles the LLM motivational line appended to workout-log Telegram
    # replies. Does NOT affect evening reminder motivation.
    is_workout_motivation_active = models.BooleanField(default=True)

    reminder_hours = models.JSONField(default=default_reminder_hours)
    last_reminder_sent_dates = models.JSONField(
        default=default_empty_reminder_sent_dates
    )

    # Idempotency: track last date each reminder was sent (per-user)
    last_reminder_21_date = models.DateField(null=True, blank=True)
    last_reminder_22_date = models.DateField(null=True, blank=True)
    last_reminder_23_date = models.DateField(null=True, blank=True)

    # Habit Reward Integration (per-user)
    habit_reward_api_key = models.CharField(max_length=255, blank=True, default="")
    habit_reward_habit_id = models.IntegerField(null=True, blank=True)
    last_habit_reward_sent_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "user_settings"
        verbose_name_plural = "User settings"

    def clean(self):
        super().clean()
        self.reminder_hours = normalize_reminder_hours(self.reminder_hours)

    def save(self, *args, **kwargs):
        self.reminder_hours = normalize_reminder_hours(self.reminder_hours)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Settings for {self.user}"


class ExerciseType(models.Model):
    user = models.ForeignKey(
        AppUser,
        on_delete=models.CASCADE,
        related_name="exercise_types",
        null=True,  # Nullable for migration; will be made required after backfill
        blank=True,
        db_index=True
    )
    name = models.CharField(max_length=100)  # Unique per user, not globally
    display_name = models.CharField(max_length=100)
    emoji = models.CharField(max_length=10)
    unit = models.CharField(max_length=20, default="reps")
    aliases = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "exercise_types"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_exercise_type_per_user"
            )
        ]

    def __str__(self):
        return f"{self.emoji} {self.display_name}"


class ExerciseChallenge(models.Model):
    user = models.ForeignKey(
        AppUser,
        on_delete=models.CASCADE,
        related_name="challenges",
        null=True,  # Nullable for migration; will be made required after backfill
        blank=True,
        db_index=True
    )
    exercise_type = models.ForeignKey(
        ExerciseType,
        on_delete=models.CASCADE,
        related_name="challenges"
    )
    challenge_name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    daily_target = models.IntegerField()
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    # Recurring exception weekdays as canonical CSV of ISO ints (1=Mon..7=Sun).
    # Empty string means no recurring exceptions. See ``normalize_exception_weekdays``.
    exception_weekdays = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        db_table = "exercise_challenges"

    def save(self, *args, **kwargs):
        # Normalize the CSV on every save so the DB always holds canonical
        # form (sorted, deduped, validated). Raises ValueError on bad input.
        self.exception_weekdays = normalize_exception_weekdays(self.exception_weekdays)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.challenge_name} ({self.start_date} - {self.end_date})"


class ChallengeExceptionDay(models.Model):
    """One-off exception (rest) day attached to a challenge.

    Combined with ``ExerciseChallenge.exception_weekdays`` to compute the
    full exception set for stats math. The challenge's daily target does not
    apply on these days, but logs may still be recorded and bank reps toward
    the cumulative total.
    """

    challenge = models.ForeignKey(
        ExerciseChallenge,
        on_delete=models.CASCADE,
        related_name="exception_days",
    )
    date = models.DateField()
    reason = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "challenge_exception_days"
        unique_together = [("challenge", "date")]
        indexes = [models.Index(fields=["challenge", "date"])]
        ordering = ["date"]

    def __str__(self):
        return f"{self.challenge_id} rest day on {self.date}"


class ExerciseLog(models.Model):
    user = models.ForeignKey(
        AppUser,
        on_delete=models.CASCADE,
        related_name="logs",
        null=True,  # Nullable for migration; will be made required after backfill
        blank=True,
        db_index=True
    )
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
    """Per-user stats for each exercise type.

    Changed from OneToOne(ExerciseType) to (user, exercise_type) for multi-user support.
    """
    user = models.ForeignKey(
        AppUser,
        on_delete=models.CASCADE,
        related_name="stats",
        null=True,  # Nullable for migration; will be made required after backfill
        blank=True,
        db_index=True
    )
    exercise_type = models.ForeignKey(
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
        constraints = [
            models.UniqueConstraint(
                fields=["user", "exercise_type"],
                name="unique_stats_per_user_exercise"
            )
        ]

    def __str__(self):
        user_name = self.user.first_name if self.user else "Unknown"
        return f"{user_name} - {self.exercise_type.name}: {self.all_time_total} total"


class AppSettings(models.Model):
    """Application settings (singleton pattern for single-user app).

    Stores reminder preferences and idempotency tracking for evening reminders.
    Future-proofed for multi-user by keeping extensible schema.
    """
    is_registration_open = models.BooleanField(default=True)
    is_reminder_active = models.BooleanField(default=True)
    telegram_chat_id = models.BigIntegerField(null=True, blank=True)

    # Idempotency: track last date each reminder was sent
    last_reminder_21_date = models.DateField(null=True, blank=True)
    last_reminder_22_date = models.DateField(null=True, blank=True)
    last_reminder_23_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "app_settings"
        verbose_name_plural = "App settings"

    def __str__(self):
        return f"App Settings (reminders: {'ON' if self.is_reminder_active else 'OFF'})"
