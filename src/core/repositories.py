from datetime import date
from typing import List, Optional, Tuple
from asgiref.sync import sync_to_async

# NOTE: This module is used both from Django management commands and from
# standalone (e.g. FastAPI) contexts. In the standalone case, Django may not be
# configured yet at import time.
from django.conf import settings as django_settings

if not django_settings.configured:
    from src.core import setup_django

    setup_django()

from django.db.models import Sum

from .models import ExerciseType, ExerciseChallenge, ExerciseLog, UserStats, AppSettings
from .validators import validate_telegram_chat_id

# Import reminder hours constant
try:
    from app.constants import REMINDER_HOURS
except ImportError:
    # Fallback if app.constants not available (shouldn't happen in normal usage)
    REMINDER_HOURS = [21, 22, 23]


class ExerciseTypeRepository:
    """Repository for ExerciseType operations."""

    @sync_to_async
    def get_all(self, is_active: Optional[bool] = None) -> List[ExerciseType]:
        """Get all exercise types, optionally filtered by is_active."""
        queryset = ExerciseType.objects.all()
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        return list(queryset.order_by("id"))

    @sync_to_async
    def get_by_id(self, id: int) -> Optional[ExerciseType]:
        """Get exercise type by ID."""
        try:
            return ExerciseType.objects.get(id=id)
        except ExerciseType.DoesNotExist:
            return None

    @sync_to_async
    def get_by_name(self, name: str) -> Optional[ExerciseType]:
        """Get exercise type by name."""
        try:
            return ExerciseType.objects.get(name=name)
        except ExerciseType.DoesNotExist:
            return None

    @sync_to_async
    def create(self, data: dict) -> ExerciseType:
        """Create new exercise type."""
        return ExerciseType.objects.create(**data)

    @sync_to_async
    def update(self, id: int, data: dict) -> Optional[ExerciseType]:
        """Update exercise type by ID."""
        try:
            exercise_type = ExerciseType.objects.get(id=id)
            for key, value in data.items():
                setattr(exercise_type, key, value)
            exercise_type.save()
            return exercise_type
        except ExerciseType.DoesNotExist:
            return None

    @sync_to_async
    def get_by_ids(self, ids: List[int]) -> List[ExerciseType]:
        """Get exercise types by list of IDs."""
        return list(ExerciseType.objects.filter(id__in=ids))


class ExerciseChallengeRepository:
    """Repository for ExerciseChallenge operations."""

    @sync_to_async
    def get_all(self, filters: Optional[dict] = None) -> List[ExerciseChallenge]:
        """Get all challenges with optional filters."""
        queryset = ExerciseChallenge.objects.select_related("exercise_type").all()

        if filters:
            if "exercise_type_id" in filters:
                queryset = queryset.filter(exercise_type_id=filters["exercise_type_id"])
            if "is_active" in filters:
                queryset = queryset.filter(is_active=filters["is_active"])
            if "is_default" in filters:
                queryset = queryset.filter(is_default=filters["is_default"])

        return list(queryset.order_by("id"))

    @sync_to_async
    def get_by_id(self, id: int) -> Optional[ExerciseChallenge]:
        """Get challenge by ID."""
        try:
            return ExerciseChallenge.objects.select_related("exercise_type").get(id=id)
        except ExerciseChallenge.DoesNotExist:
            return None

    @sync_to_async
    def get_active_for_type(
        self, exercise_type_id: int, target_date: date
    ) -> Optional[ExerciseChallenge]:
        """Get active challenge for exercise type on target date."""
        return (
            ExerciseChallenge.objects.select_related("exercise_type")
            .filter(
                exercise_type_id=exercise_type_id,
                is_active=True,
                start_date__lte=target_date,
                end_date__gte=target_date,
            )
            .first()
        )

    @sync_to_async
    def get_current_active(self, target_date: date) -> List[ExerciseChallenge]:
        """Get all active challenges for target date."""
        return list(
            ExerciseChallenge.objects.select_related("exercise_type").filter(
                is_active=True,
                start_date__lte=target_date,
                end_date__gte=target_date,
            ).order_by("id")
        )

    @sync_to_async
    def create(self, data: dict) -> ExerciseChallenge:
        """Create new challenge."""
        return ExerciseChallenge.objects.create(**data)

    @sync_to_async
    def update(self, id: int, data: dict) -> Optional[ExerciseChallenge]:
        """Update challenge by ID."""
        try:
            challenge = ExerciseChallenge.objects.get(id=id)
            for key, value in data.items():
                setattr(challenge, key, value)
            challenge.save()
            return challenge
        except ExerciseChallenge.DoesNotExist:
            return None


class ExerciseLogRepository:
    """Repository for ExerciseLog operations."""

    @sync_to_async
    def get_all(
        self, filters: Optional[dict] = None, limit: int = 50, offset: int = 0
    ) -> Tuple[List[ExerciseLog], int]:
        """Get all logs with pagination and optional filters."""
        queryset = ExerciseLog.objects.select_related("exercise_type", "challenge").all()

        if filters:
            if "exercise_type_id" in filters:
                queryset = queryset.filter(exercise_type_id=filters["exercise_type_id"])
            if "challenge_id" in filters:
                queryset = queryset.filter(challenge_id=filters["challenge_id"])
            if "date" in filters:
                queryset = queryset.filter(date=filters["date"])
            if "date_from" in filters:
                queryset = queryset.filter(date__gte=filters["date_from"])
            if "date_to" in filters:
                queryset = queryset.filter(date__lte=filters["date_to"])

        total_count = queryset.count()
        logs = list(queryset.order_by("-timestamp")[offset:offset + limit])

        return logs, total_count

    @sync_to_async
    def get_by_id(self, id: int) -> Optional[ExerciseLog]:
        """Get log by ID."""
        try:
            return ExerciseLog.objects.select_related("exercise_type", "challenge").get(id=id)
        except ExerciseLog.DoesNotExist:
            return None

    @sync_to_async
    def get_cumulative_count(
        self,
        exercise_type_id: int,
        challenge_id: Optional[int] = None,
        up_to_date: Optional[date] = None,
    ) -> int:
        """Get cumulative count for exercise type."""
        queryset = ExerciseLog.objects.filter(exercise_type_id=exercise_type_id)

        if challenge_id is not None:
            queryset = queryset.filter(challenge_id=challenge_id)

        if up_to_date is not None:
            queryset = queryset.filter(date__lte=up_to_date)

        result = queryset.aggregate(total=Sum("count"))
        return result["total"] or 0

    @sync_to_async
    def get_today_count(
        self, exercise_type_id: int, date: date, challenge_id: Optional[int] = None
    ) -> int:
        """Get count for specific date."""
        queryset = ExerciseLog.objects.filter(
            exercise_type_id=exercise_type_id,
            date=date,
        )

        if challenge_id is not None:
            queryset = queryset.filter(challenge_id=challenge_id)

        result = queryset.aggregate(total=Sum("count"))
        return result["total"] or 0

    @sync_to_async
    def get_today_counts_by_challenge_ids(
        self, challenge_ids: List[int], target_date: date
    ) -> dict[int, int]:
        """Get per-challenge totals for a specific date."""
        if not challenge_ids:
            return {}

        rows = (
            ExerciseLog.objects.filter(challenge_id__in=challenge_ids, date=target_date)
            .values("challenge_id")
            .annotate(total=Sum("count"))
        )

        return {row["challenge_id"]: row["total"] or 0 for row in rows}

    @sync_to_async
    def create(self, data: dict) -> ExerciseLog:
        """Create new log entry."""
        return ExerciseLog.objects.create(**data)

    @sync_to_async
    def delete(self, id: int) -> Optional[ExerciseLog]:
        """Delete log by ID."""
        try:
            log = ExerciseLog.objects.get(id=id)
            log.delete()
            return log
        except ExerciseLog.DoesNotExist:
            return None

    @sync_to_async
    def get_last_log(self, exercise_type_id: int) -> Optional[ExerciseLog]:
        """Get the most recent log for exercise type."""
        return ExerciseLog.objects.filter(
            exercise_type_id=exercise_type_id
        ).order_by("-timestamp").first()


class UserStatsRepository:
    """Repository for UserStats operations."""

    @sync_to_async
    def get_all(self) -> List[UserStats]:
        """Get all user stats."""
        return list(UserStats.objects.select_related("exercise_type").all())

    @sync_to_async
    def get_by_exercise_type(self, exercise_type_id: int) -> Optional[UserStats]:
        """Get user stats for exercise type."""
        try:
            return UserStats.objects.select_related("exercise_type").get(
                exercise_type_id=exercise_type_id
            )
        except UserStats.DoesNotExist:
            return None

    @sync_to_async
    def get_or_create(self, exercise_type_id: int) -> UserStats:
        """Get or create user stats for exercise type."""
        stats, created = UserStats.objects.get_or_create(
            exercise_type_id=exercise_type_id
        )
        return stats

    @sync_to_async
    def update(self, id: int, data: dict) -> UserStats:
        """Update user stats by ID."""
        stats = UserStats.objects.get(id=id)
        for key, value in data.items():
            setattr(stats, key, value)
        stats.save()
        return stats

    @sync_to_async
    def increment_total(self, exercise_type_id: int, count: int, log_date: date):
        """Increment all-time total for exercise type."""
        stats, created = UserStats.objects.get_or_create(
            exercise_type_id=exercise_type_id
        )
        stats.all_time_total += count
        stats.last_logged_date = log_date
        stats.save()

    @sync_to_async
    def decrement_total(self, exercise_type_id: int, count: int):
        """Decrement all-time total for exercise type."""
        try:
            stats = UserStats.objects.get(exercise_type_id=exercise_type_id)
            stats.all_time_total = max(0, stats.all_time_total - count)
            stats.save()
        except UserStats.DoesNotExist:
            pass

    @sync_to_async
    def sync_last_logged_date(self, exercise_type_id: int) -> Optional[date]:
        """Recompute last_logged_date from remaining logs for the exercise type.

        This is used after deletions so both API and Telegram flows stay consistent.
        Returns the updated last_logged_date (or None if stats row/logs are missing).
        """
        try:
            stats = UserStats.objects.get(exercise_type_id=exercise_type_id)
        except UserStats.DoesNotExist:
            return None

        last_log = (
            ExerciseLog.objects.filter(exercise_type_id=exercise_type_id)
            .order_by("-timestamp")
            .first()
        )
        stats.last_logged_date = last_log.date if last_log else None
        stats.save(update_fields=["last_logged_date"])
        return stats.last_logged_date


class AppSettingsRepository:
    """Repository for AppSettings operations (singleton pattern)."""

    @staticmethod
    def _get_reminder_field_name(hour: int) -> str:
        """Get the field name for a reminder hour.
        
        Args:
            hour: The reminder hour (must be in REMINDER_HOURS)
            
        Returns:
            Field name like "last_reminder_21_date"
            
        Raises:
            ValueError: If hour is not in REMINDER_HOURS
        """
        if hour not in REMINDER_HOURS:
            raise ValueError(
                f"Invalid hour: {hour}. Must be one of {REMINDER_HOURS}."
            )
        return f"last_reminder_{hour}_date"

    @sync_to_async
    def get_singleton(self) -> AppSettings:
        """Get or create the singleton AppSettings instance."""
        settings, created = AppSettings.objects.get_or_create(id=1)
        return settings

    @sync_to_async
    def set_is_reminder_active(self, is_active: bool) -> AppSettings:
        """Set the is_reminder_active flag."""
        settings, created = AppSettings.objects.get_or_create(id=1)
        settings.is_reminder_active = is_active
        settings.save(update_fields=["is_reminder_active"])
        return settings

    @sync_to_async
    def update_chat_id(self, chat_id: int) -> AppSettings:
        """Update the telegram_chat_id."""
        validate_telegram_chat_id(chat_id)
        settings, created = AppSettings.objects.get_or_create(id=1)
        settings.telegram_chat_id = chat_id
        settings.save(update_fields=["telegram_chat_id"])
        return settings

    @sync_to_async
    def mark_hour_sent(self, target_date: date, hour: int) -> AppSettings:
        """Mark that a reminder was sent for the given hour on target_date.

        Args:
            target_date: The date the reminder was sent
            hour: The hour (must be in REMINDER_HOURS)

        Returns:
            Updated settings instance
        """
        field_name = self._get_reminder_field_name(hour)
        settings, created = AppSettings.objects.get_or_create(id=1)
        setattr(settings, field_name, target_date)
        settings.save(update_fields=[field_name])
        return settings

    @sync_to_async
    def check_already_sent(self, target_date: date, hour: int) -> bool:
        """Check if reminder was already sent for the given hour on target_date.

        Args:
            target_date: The date to check
            hour: The hour (must be in REMINDER_HOURS)

        Returns:
            True if already sent, False otherwise
        """
        field_name = self._get_reminder_field_name(hour)
        settings, created = AppSettings.objects.get_or_create(id=1)
        return getattr(settings, field_name) == target_date

    @sync_to_async
    def try_mark_hour_sent(self, target_date: date, hour: int) -> bool:
        """Atomically mark hour as sent if not already sent today.

        This is race-condition safe: uses a conditional update that only
        succeeds if the field doesn't already match the target date.

        Args:
            target_date: The date to mark as sent
            hour: The hour (must be in REMINDER_HOURS)

        Returns:
            True if this call marked it (first to succeed).
            False if already marked (another worker got there first).
        """
        field_name = self._get_reminder_field_name(hour)

        # Ensure the singleton exists
        AppSettings.objects.get_or_create(id=1)

        # Atomic conditional update: only update if field != target_date
        # This excludes rows where the field already equals target_date
        updated = AppSettings.objects.filter(id=1).exclude(
            **{field_name: target_date}
        ).update(**{field_name: target_date})

        return updated > 0  # True if we were first to mark it

    @sync_to_async
    def clear_hour_sent(self, target_date: date, hour: int) -> bool:
        """Clear the sent marker for the given hour on target_date.

        This is used to roll back a pre-claim if the send fails.

        Args:
            target_date: The date to clear
            hour: The hour (must be in REMINDER_HOURS)

        Returns:
            True if a row was updated, False otherwise.
        """
        field_name = self._get_reminder_field_name(hour)

        AppSettings.objects.get_or_create(id=1)
        updated = AppSettings.objects.filter(id=1, **{field_name: target_date}).update(
            **{field_name: None}
        )
        return updated > 0

    @sync_to_async
    def update(self, data: dict) -> AppSettings:
        """Update settings with arbitrary fields."""
        settings, created = AppSettings.objects.get_or_create(id=1)
        for key, value in data.items():
            setattr(settings, key, value)
        settings.save()
        return settings


# Module-level singleton instances
exercise_type_repo = ExerciseTypeRepository()
challenge_repo = ExerciseChallengeRepository()
log_repo = ExerciseLogRepository()
user_stats_repo = UserStatsRepository()
app_settings_repo = AppSettingsRepository()
