from datetime import date, datetime
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
from django.utils import timezone

from .models import (
    AppUser,
    UserSettings,
    ExerciseType,
    ExerciseChallenge,
    ExerciseLog,
    UserStats,
    AppSettings,
)
from .validators import validate_telegram_chat_id

# Import reminder hours constant
try:
    from app.constants import REMINDER_HOURS
except ImportError:
    # Fallback if app.constants not available (shouldn't happen in normal usage)
    REMINDER_HOURS = [21, 22, 23]


class AppUserRepository:
    """Repository for AppUser operations."""

    @sync_to_async
    def get_by_id(self, id: int) -> Optional[AppUser]:
        """Get user by ID."""
        try:
            return AppUser.objects.get(id=id)
        except AppUser.DoesNotExist:
            return None

    @sync_to_async
    def get_by_telegram_user_id(self, telegram_user_id: int) -> Optional[AppUser]:
        """Get user by Telegram user ID."""
        try:
            return AppUser.objects.get(telegram_user_id=telegram_user_id)
        except AppUser.DoesNotExist:
            return None

    @sync_to_async
    def get_by_telegram_user_ids(self, telegram_user_ids: List[int]) -> List[AppUser]:
        """Get users by Telegram user IDs."""
        if not telegram_user_ids:
            return []
        return list(
            AppUser.objects.select_related("settings").filter(
                telegram_user_id__in=telegram_user_ids
            )
        )

    @sync_to_async
    def get_all(
        self, status: Optional[str] = None, is_approved_only: bool = False
    ) -> List[AppUser]:
        """Get all users with optional filters."""
        queryset = AppUser.objects.all()
        if status is not None:
            queryset = queryset.filter(status=status)
        if is_approved_only:
            queryset = queryset.filter(status=AppUser.Status.APPROVED)
        return list(queryset.order_by("id"))

    @sync_to_async
    def create(self, data: dict) -> AppUser:
        """Create new user."""
        return AppUser.objects.create(**data)

    @sync_to_async
    def get_or_create_by_telegram_user_id(
        self,
        telegram_user_id: int,
        defaults: Optional[dict] = None
    ) -> Tuple[AppUser, bool]:
        """Get or create user by Telegram user ID.

        Returns:
            Tuple of (user, created) where created is True if a new user was created.
        """
        return AppUser.objects.get_or_create(
            telegram_user_id=telegram_user_id,
            defaults=defaults or {}
        )

    @sync_to_async
    def update(self, id: int, data: dict) -> Optional[AppUser]:
        """Update user by ID."""
        try:
            user = AppUser.objects.get(id=id)
            for key, value in data.items():
                setattr(user, key, value)
            user.save()
            return user
        except AppUser.DoesNotExist:
            return None

    @sync_to_async
    def approve(self, id: int) -> Optional[AppUser]:
        """Approve a user."""
        try:
            user = AppUser.objects.get(id=id)
            user.status = AppUser.Status.APPROVED
            user.approved_at = timezone.now()
            user.save(update_fields=["status", "approved_at"])
            return user
        except AppUser.DoesNotExist:
            return None

    @sync_to_async
    def reject(self, id: int) -> Optional[AppUser]:
        """Reject a user."""
        try:
            user = AppUser.objects.get(id=id)
            user.status = AppUser.Status.REJECTED
            user.save(update_fields=["status"])
            return user
        except AppUser.DoesNotExist:
            return None

    @sync_to_async
    def approve_by_telegram_user_id(self, telegram_user_id: int) -> Optional[AppUser]:
        """Approve a user by Telegram user ID."""
        try:
            user = AppUser.objects.get(telegram_user_id=telegram_user_id)
            user.status = AppUser.Status.APPROVED
            user.approved_at = timezone.now()
            user.save(update_fields=["status", "approved_at"])
            return user
        except AppUser.DoesNotExist:
            return None

    @sync_to_async
    def reject_by_telegram_user_id(self, telegram_user_id: int) -> Optional[AppUser]:
        """Reject a user by Telegram user ID."""
        try:
            user = AppUser.objects.get(telegram_user_id=telegram_user_id)
            user.status = AppUser.Status.REJECTED
            user.save(update_fields=["status"])
            return user
        except AppUser.DoesNotExist:
            return None


class UserSettingsRepository:
    """Repository for UserSettings operations (per-user settings)."""

    @staticmethod
    def _get_reminder_field_name(hour: int) -> str:
        """Get the field name for a reminder hour."""
        if hour not in REMINDER_HOURS:
            raise ValueError(
                f"Invalid hour: {hour}. Must be one of {REMINDER_HOURS}."
            )
        return f"last_reminder_{hour}_date"

    @sync_to_async
    def get_by_user_id(self, user_id: int) -> Optional[UserSettings]:
        """Get settings for user."""
        try:
            return UserSettings.objects.select_related("user").get(user_id=user_id)
        except UserSettings.DoesNotExist:
            return None

    @sync_to_async
    def get_or_create(self, user_id: int, defaults: Optional[dict] = None) -> UserSettings:
        """Get or create settings for user."""
        settings, created = UserSettings.objects.get_or_create(
            user_id=user_id,
            defaults=defaults or {}
        )
        return settings

    @sync_to_async
    def update(self, user_id: int, data: dict) -> Optional[UserSettings]:
        """Update settings for user."""
        try:
            settings = UserSettings.objects.get(user_id=user_id)
            for key, value in data.items():
                setattr(settings, key, value)
            settings.save()
            return settings
        except UserSettings.DoesNotExist:
            return None

    @sync_to_async
    def set_is_reminder_active(self, user_id: int, is_active: bool) -> UserSettings:
        """Set the is_reminder_active flag for user."""
        settings, created = UserSettings.objects.get_or_create(user_id=user_id)
        settings.is_reminder_active = is_active
        settings.save(update_fields=["is_reminder_active"])
        return settings

    @sync_to_async
    def update_chat_id(self, user_id: int, chat_id: int) -> UserSettings:
        """Update the telegram_chat_id for user."""
        validate_telegram_chat_id(chat_id)
        settings, created = UserSettings.objects.get_or_create(user_id=user_id)
        settings.telegram_chat_id = chat_id
        settings.save(update_fields=["telegram_chat_id"])
        return settings

    @sync_to_async
    def try_mark_hour_sent(self, user_id: int, target_date: date, hour: int) -> bool:
        """Atomically mark hour as sent if not already sent today for user.

        Returns:
            True if this call marked it (first to succeed).
            False if already marked.
        """
        field_name = self._get_reminder_field_name(hour)

        # Ensure settings exist
        UserSettings.objects.get_or_create(user_id=user_id)

        # Atomic conditional update
        updated = UserSettings.objects.filter(user_id=user_id).exclude(
            **{field_name: target_date}
        ).update(**{field_name: target_date})

        return updated > 0

    @sync_to_async
    def clear_hour_sent(self, user_id: int, target_date: date, hour: int) -> bool:
        """Clear the sent marker for the given hour on target_date for user."""
        field_name = self._get_reminder_field_name(hour)

        UserSettings.objects.get_or_create(user_id=user_id)
        updated = UserSettings.objects.filter(
            user_id=user_id, **{field_name: target_date}
        ).update(**{field_name: None})
        return updated > 0

    @sync_to_async
    def check_already_sent(self, user_id: int, target_date: date, hour: int) -> bool:
        """Check if reminder was already sent for the given hour on target_date for user."""
        field_name = self._get_reminder_field_name(hour)
        settings, created = UserSettings.objects.get_or_create(user_id=user_id)
        return getattr(settings, field_name) == target_date

    @sync_to_async
    def get_users_with_reminders_enabled(self) -> List[UserSettings]:
        """Get all user settings where reminders are enabled and user is approved."""
        return list(
            UserSettings.objects.select_related("user")
            .filter(
                is_reminder_active=True,
                telegram_chat_id__isnull=False,
                user__status=AppUser.Status.APPROVED
            )
            .order_by("user_id")
        )

    @sync_to_async
    def check_habit_reward_sent(self, user_id: int, target_date: date) -> bool:
        """Check if habit reward completion was already sent for target_date for user.

        Args:
            user_id: The AppUser ID
            target_date: The date to check

        Returns:
            True if already sent, False otherwise
        """
        settings, created = UserSettings.objects.get_or_create(user_id=user_id)
        return settings.last_habit_reward_sent_date == target_date

    @sync_to_async
    def mark_habit_reward_sent(self, user_id: int, target_date: date) -> UserSettings:
        """Mark that habit reward completion was sent for target_date for user.

        Should only be called after receiving a successful (200) response.

        Args:
            user_id: The AppUser ID
            target_date: The date to mark as sent

        Returns:
            Updated settings instance
        """
        settings, created = UserSettings.objects.get_or_create(user_id=user_id)
        settings.last_habit_reward_sent_date = target_date
        settings.save(update_fields=["last_habit_reward_sent_date"])
        return settings


class ExerciseTypeRepository:
    """Repository for ExerciseType operations."""

    @sync_to_async
    def get_all(
        self, is_active: Optional[bool] = None, user_id: Optional[int] = None
    ) -> List[ExerciseType]:
        """Get all exercise types, optionally filtered by is_active and user_id."""
        queryset = ExerciseType.objects.all()
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        return list(queryset.order_by("id"))

    @sync_to_async
    def get_by_id(
        self, id: int, user_id: Optional[int] = None
    ) -> Optional[ExerciseType]:
        """Get exercise type by ID, optionally verifying user ownership."""
        try:
            queryset = ExerciseType.objects.filter(id=id)
            if user_id is not None:
                queryset = queryset.filter(user_id=user_id)
            return queryset.get()
        except ExerciseType.DoesNotExist:
            return None

    @sync_to_async
    def get_by_name(
        self, name: str, user_id: Optional[int] = None
    ) -> Optional[ExerciseType]:
        """Get exercise type by name, optionally filtered by user_id."""
        try:
            queryset = ExerciseType.objects.filter(name=name)
            if user_id is not None:
                queryset = queryset.filter(user_id=user_id)
            return queryset.get()
        except ExerciseType.DoesNotExist:
            return None

    @sync_to_async
    def create(self, data: dict) -> ExerciseType:
        """Create new exercise type."""
        return ExerciseType.objects.create(**data)

    @sync_to_async
    def update(
        self, id: int, data: dict, user_id: Optional[int] = None
    ) -> Optional[ExerciseType]:
        """Update exercise type by ID, optionally verifying user ownership."""
        try:
            queryset = ExerciseType.objects.filter(id=id)
            if user_id is not None:
                queryset = queryset.filter(user_id=user_id)
            exercise_type = queryset.get()
            for key, value in data.items():
                setattr(exercise_type, key, value)
            exercise_type.save()
            return exercise_type
        except ExerciseType.DoesNotExist:
            return None

    @sync_to_async
    def get_by_ids(
        self, ids: List[int], user_id: Optional[int] = None
    ) -> List[ExerciseType]:
        """Get exercise types by list of IDs, optionally filtered by user_id."""
        queryset = ExerciseType.objects.filter(id__in=ids)
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)
        return list(queryset)


class ExerciseChallengeRepository:
    """Repository for ExerciseChallenge operations."""

    @sync_to_async
    def get_all(
        self, filters: Optional[dict] = None, user_id: Optional[int] = None
    ) -> List[ExerciseChallenge]:
        """Get all challenges with optional filters and user_id."""
        queryset = ExerciseChallenge.objects.select_related("exercise_type").all()

        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)

        if filters:
            if "exercise_type_id" in filters:
                queryset = queryset.filter(exercise_type_id=filters["exercise_type_id"])
            if "is_active" in filters:
                queryset = queryset.filter(is_active=filters["is_active"])
            if "is_default" in filters:
                queryset = queryset.filter(is_default=filters["is_default"])

        return list(queryset.order_by("id"))

    @sync_to_async
    def get_by_id(
        self, id: int, user_id: Optional[int] = None
    ) -> Optional[ExerciseChallenge]:
        """Get challenge by ID, optionally verifying user ownership."""
        try:
            queryset = ExerciseChallenge.objects.select_related("exercise_type").filter(id=id)
            if user_id is not None:
                queryset = queryset.filter(user_id=user_id)
            return queryset.get()
        except ExerciseChallenge.DoesNotExist:
            return None

    @sync_to_async
    def get_active_for_type(
        self, exercise_type_id: int, target_date: date, user_id: Optional[int] = None
    ) -> Optional[ExerciseChallenge]:
        """Get active challenge for exercise type on target date."""
        queryset = ExerciseChallenge.objects.select_related("exercise_type").filter(
            exercise_type_id=exercise_type_id,
            is_active=True,
            start_date__lte=target_date,
            end_date__gte=target_date,
        )
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)
        return queryset.first()

    @sync_to_async
    def get_current_active(
        self, target_date: date, user_id: Optional[int] = None
    ) -> List[ExerciseChallenge]:
        """Get all active challenges for target date."""
        queryset = ExerciseChallenge.objects.select_related("exercise_type").filter(
            is_active=True,
            start_date__lte=target_date,
            end_date__gte=target_date,
        )
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)
        return list(queryset.order_by("id"))

    @sync_to_async
    def create(self, data: dict) -> ExerciseChallenge:
        """Create new challenge."""
        return ExerciseChallenge.objects.create(**data)

    @sync_to_async
    def update(
        self, id: int, data: dict, user_id: Optional[int] = None
    ) -> Optional[ExerciseChallenge]:
        """Update challenge by ID, optionally verifying user ownership."""
        try:
            queryset = ExerciseChallenge.objects.filter(id=id)
            if user_id is not None:
                queryset = queryset.filter(user_id=user_id)
            challenge = queryset.get()
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
        self,
        filters: Optional[dict] = None,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[int] = None,
    ) -> Tuple[List[ExerciseLog], int]:
        """Get all logs with pagination and optional filters."""
        queryset = ExerciseLog.objects.select_related("exercise_type", "challenge").all()

        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)

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
    def get_by_id(
        self, id: int, user_id: Optional[int] = None
    ) -> Optional[ExerciseLog]:
        """Get log by ID, optionally verifying user ownership."""
        try:
            queryset = ExerciseLog.objects.select_related("exercise_type", "challenge").filter(id=id)
            if user_id is not None:
                queryset = queryset.filter(user_id=user_id)
            return queryset.get()
        except ExerciseLog.DoesNotExist:
            return None

    @sync_to_async
    def get_cumulative_count(
        self,
        exercise_type_id: int,
        challenge_id: Optional[int] = None,
        up_to_date: Optional[date] = None,
        user_id: Optional[int] = None,
    ) -> int:
        """Get cumulative count for exercise type."""
        queryset = ExerciseLog.objects.filter(exercise_type_id=exercise_type_id)

        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)

        if challenge_id is not None:
            queryset = queryset.filter(challenge_id=challenge_id)

        if up_to_date is not None:
            queryset = queryset.filter(date__lte=up_to_date)

        result = queryset.aggregate(total=Sum("count"))
        return result["total"] or 0

    @sync_to_async
    def get_cumulative_counts_by_challenge_ids(
        self,
        challenge_ids: List[int],
        up_to_date: Optional[date] = None,
        user_id: Optional[int] = None,
    ) -> dict[int, int]:
        """Get per-challenge cumulative totals up to an optional date."""
        if not challenge_ids:
            return {}

        queryset = ExerciseLog.objects.filter(challenge_id__in=challenge_ids)
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)
        if up_to_date is not None:
            queryset = queryset.filter(date__lte=up_to_date)

        rows = queryset.values("challenge_id").annotate(total=Sum("count"))
        return {row["challenge_id"]: row["total"] or 0 for row in rows}

    @sync_to_async
    def get_today_count(
        self,
        exercise_type_id: int,
        date: date,
        challenge_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> int:
        """Get count for specific date."""
        queryset = ExerciseLog.objects.filter(
            exercise_type_id=exercise_type_id,
            date=date,
        )

        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)

        if challenge_id is not None:
            queryset = queryset.filter(challenge_id=challenge_id)

        result = queryset.aggregate(total=Sum("count"))
        return result["total"] or 0

    @sync_to_async
    def get_today_counts_by_challenge_ids(
        self,
        challenge_ids: List[int],
        target_date: date,
        user_id: Optional[int] = None,
    ) -> dict[int, int]:
        """Get per-challenge totals for a specific date."""
        if not challenge_ids:
            return {}

        queryset = ExerciseLog.objects.filter(challenge_id__in=challenge_ids, date=target_date)
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)

        rows = queryset.values("challenge_id").annotate(total=Sum("count"))
        return {row["challenge_id"]: row["total"] or 0 for row in rows}

    @sync_to_async
    def create(self, data: dict) -> ExerciseLog:
        """Create new log entry."""
        return ExerciseLog.objects.create(**data)

    @sync_to_async
    def delete(self, id: int, user_id: Optional[int] = None) -> Optional[ExerciseLog]:
        """Delete log by ID, optionally verifying user ownership."""
        try:
            queryset = ExerciseLog.objects.filter(id=id)
            if user_id is not None:
                queryset = queryset.filter(user_id=user_id)
            log = queryset.get()
            log.delete()
            return log
        except ExerciseLog.DoesNotExist:
            return None

    @sync_to_async
    def get_last_log(
        self, exercise_type_id: int, user_id: Optional[int] = None
    ) -> Optional[ExerciseLog]:
        """Get the most recent log for exercise type."""
        queryset = ExerciseLog.objects.filter(exercise_type_id=exercise_type_id)
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)
        return queryset.order_by("-timestamp").first()


class UserStatsRepository:
    """Repository for UserStats operations.

    Note: With multi-user support, stats are now per (user_id, exercise_type_id).
    The user_id parameter is optional for backward compatibility but should be
    provided for proper user-scoped operations.
    """

    @sync_to_async
    def get_all(self, user_id: Optional[int] = None) -> List[UserStats]:
        """Get all user stats, optionally filtered by user_id."""
        queryset = UserStats.objects.select_related("exercise_type")
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)
        return list(queryset.all())

    @sync_to_async
    def get_by_exercise_type(
        self, exercise_type_id: int, user_id: Optional[int] = None
    ) -> Optional[UserStats]:
        """Get user stats for exercise type, optionally filtered by user_id."""
        try:
            queryset = UserStats.objects.select_related("exercise_type").filter(
                exercise_type_id=exercise_type_id
            )
            if user_id is not None:
                queryset = queryset.filter(user_id=user_id)
            return queryset.get()
        except UserStats.DoesNotExist:
            return None
        except UserStats.MultipleObjectsReturned:
            # This can happen during migration when user_id is null
            # Return the first one (backward compat)
            return queryset.first()

    @sync_to_async
    def get_or_create(
        self, exercise_type_id: int, user_id: Optional[int] = None
    ) -> UserStats:
        """Get or create user stats for exercise type.

        When user_id is provided, creates/retrieves stats for that specific user.
        """
        filter_kwargs = {"exercise_type_id": exercise_type_id}
        if user_id is not None:
            filter_kwargs["user_id"] = user_id

        stats, created = UserStats.objects.get_or_create(**filter_kwargs)
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
    def increment_total(
        self, exercise_type_id: int, count: int, log_date: date, user_id: Optional[int] = None
    ):
        """Increment all-time total for exercise type."""
        filter_kwargs = {"exercise_type_id": exercise_type_id}
        if user_id is not None:
            filter_kwargs["user_id"] = user_id

        stats, created = UserStats.objects.get_or_create(**filter_kwargs)
        stats.all_time_total += count
        stats.last_logged_date = log_date
        stats.save()

    @sync_to_async
    def decrement_total(
        self, exercise_type_id: int, count: int, user_id: Optional[int] = None
    ):
        """Decrement all-time total for exercise type."""
        try:
            queryset = UserStats.objects.filter(exercise_type_id=exercise_type_id)
            if user_id is not None:
                queryset = queryset.filter(user_id=user_id)
            stats = queryset.get()
            stats.all_time_total = max(0, stats.all_time_total - count)
            stats.save()
        except UserStats.DoesNotExist:
            pass
        except UserStats.MultipleObjectsReturned:
            # Backward compat: update first matching row
            stats = queryset.first()
            if stats:
                stats.all_time_total = max(0, stats.all_time_total - count)
                stats.save()

    @sync_to_async
    def sync_last_logged_date(
        self, exercise_type_id: int, user_id: Optional[int] = None
    ) -> Optional[date]:
        """Recompute last_logged_date from remaining logs for the exercise type.

        This is used after deletions so both API and Telegram flows stay consistent.
        Returns the updated last_logged_date (or None if stats row/logs are missing).
        """
        try:
            queryset = UserStats.objects.filter(exercise_type_id=exercise_type_id)
            if user_id is not None:
                queryset = queryset.filter(user_id=user_id)
            stats = queryset.get()
        except UserStats.DoesNotExist:
            return None
        except UserStats.MultipleObjectsReturned:
            stats = queryset.first()
            if not stats:
                return None

        # Filter logs by user_id if provided
        log_queryset = ExerciseLog.objects.filter(exercise_type_id=exercise_type_id)
        if user_id is not None:
            log_queryset = log_queryset.filter(user_id=user_id)

        last_log = log_queryset.order_by("-timestamp").first()
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
app_user_repo = AppUserRepository()
user_settings_repo = UserSettingsRepository()
exercise_type_repo = ExerciseTypeRepository()
challenge_repo = ExerciseChallengeRepository()
log_repo = ExerciseLogRepository()
user_stats_repo = UserStatsRepository()
app_settings_repo = AppSettingsRepository()
