from django.contrib import admin
from .models import (
    AppUser,
    UserSettings,
    ExerciseType,
    ExerciseChallenge,
    ChallengeExceptionDay,
    ExerciseLog,
    UserStats,
    AppSettings,
)


class UserSettingsInline(admin.StackedInline):
    """Inline for editing UserSettings on AppUser page."""
    model = UserSettings
    can_delete = False
    verbose_name_plural = "Settings"


@admin.register(AppUser)
class AppUserAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "telegram_user_id",
        "username",
        "first_name",
        "timezone",
        "status",
        "created_at",
        "approved_at",
    ]
    list_filter = ["status", "timezone", "created_at"]
    search_fields = ["telegram_user_id", "username", "first_name"]
    list_editable = ["status"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at"]
    inlines = [UserSettingsInline]

    actions = ["approve_users", "reject_users"]

    @admin.action(description="Approve selected users")
    def approve_users(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(status=AppUser.Status.PENDING).update(
            status=AppUser.Status.APPROVED,
            approved_at=timezone.now()
        )
        self.message_user(request, f"{updated} user(s) approved.")

    @admin.action(description="Reject selected users")
    def reject_users(self, request, queryset):
        updated = queryset.filter(status=AppUser.Status.PENDING).update(
            status=AppUser.Status.REJECTED
        )
        self.message_user(request, f"{updated} user(s) rejected.")


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "telegram_chat_id",
        "is_reminder_active",
        "habit_reward_habit_id",
        "last_reminder_21_date",
        "last_reminder_22_date",
        "last_reminder_23_date",
    ]
    list_filter = ["is_reminder_active"]
    search_fields = ["user__telegram_user_id", "user__username", "user__first_name"]
    list_editable = ["is_reminder_active"]
    raw_id_fields = ["user"]
    readonly_fields = [
        "last_reminder_21_date",
        "last_reminder_22_date",
        "last_reminder_23_date",
        "last_habit_reward_sent_date",
    ]


@admin.register(ExerciseType)
class ExerciseTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "display_name", "emoji", "unit", "user", "is_active"]
    list_filter = ["is_active", "unit", "user"]
    search_fields = ["name", "display_name", "aliases", "user__username", "user__first_name"]
    list_editable = ["is_active"]
    ordering = ["user", "name"]
    raw_id_fields = ["user"]


@admin.register(ExerciseChallenge)
class ExerciseChallengeAdmin(admin.ModelAdmin):
    list_display = [
        "challenge_name",
        "user",
        "exercise_type",
        "start_date",
        "end_date",
        "daily_target",
        "exception_weekdays",
        "is_active",
        "is_default",
    ]
    list_filter = ["is_active", "is_default", "user", "start_date", "end_date"]
    search_fields = [
        "challenge_name",
        "exercise_type__name",
        "exercise_type__display_name",
        "user__username",
        "user__first_name",
    ]
    list_editable = ["is_active", "is_default"]
    date_hierarchy = "start_date"
    ordering = ["user", "-start_date"]
    raw_id_fields = ["user", "exercise_type"]


@admin.register(ChallengeExceptionDay)
class ChallengeExceptionDayAdmin(admin.ModelAdmin):
    list_display = ["challenge", "date", "reason", "created_at"]
    list_filter = ["challenge", "date"]
    search_fields = [
        "challenge__challenge_name",
        "challenge__user__username",
        "reason",
    ]
    date_hierarchy = "date"
    raw_id_fields = ["challenge"]
    readonly_fields = ["created_at"]


@admin.register(ExerciseLog)
class ExerciseLogAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "exercise_type",
        "challenge",
        "date",
        "count",
        "cumulative_total",
        "day_number",
        "status",
        "timestamp",
    ]
    list_filter = [
        "user",
        "exercise_type",
        "status",
        "date",
        "timestamp",
    ]
    search_fields = [
        "exercise_type__name",
        "exercise_type__display_name",
        "challenge__challenge_name",
        "user__username",
        "user__first_name",
        "raw_message",
        "notes",
    ]
    date_hierarchy = "date"
    ordering = ["user", "-timestamp"]
    raw_id_fields = ["user", "exercise_type", "challenge"]
    readonly_fields = ["timestamp", "cumulative_total", "day_number", "status"]

    actions = ["change_user_to_user_2"]

    @admin.action(description="Change user_id to 2 for selected logs")
    def change_user_to_user_2(self, request, queryset):
        try:
            user_2 = AppUser.objects.get(id=2)
            updated = queryset.update(user=user_2)
            self.message_user(request, f"{updated} exercise log(s) updated to user_id=2.")
        except AppUser.DoesNotExist:
            self.message_user(request, "Error: User with id=2 does not exist.", level="error")


@admin.register(UserStats)
class UserStatsAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "exercise_type",
        "all_time_total",
        "best_daily_count",
        "current_streak",
        "longest_streak",
        "last_logged_date",
    ]
    list_filter = ["user", "last_logged_date"]
    search_fields = [
        "exercise_type__name",
        "exercise_type__display_name",
        "user__username",
        "user__first_name",
    ]
    ordering = ["user", "-all_time_total"]
    raw_id_fields = ["user", "exercise_type"]
    readonly_fields = [
        "all_time_total",
        "best_daily_count",
        "current_streak",
        "longest_streak",
        "last_logged_date",
    ]


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "is_registration_open",
        "is_reminder_active",
        "telegram_chat_id",
        "last_reminder_21_date",
        "last_reminder_22_date",
        "last_reminder_23_date",
    ]
    list_editable = ["is_registration_open", "is_reminder_active"]
    readonly_fields = [
        "last_reminder_21_date",
        "last_reminder_22_date",
        "last_reminder_23_date",
    ]

    def has_add_permission(self, request):
        """Prevent creating multiple settings instances (singleton pattern)."""
        return not AppSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deleting the settings instance."""
        return False
