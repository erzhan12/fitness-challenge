from django.contrib import admin
from .models import ExerciseType, ExerciseChallenge, ExerciseLog, UserStats


@admin.register(ExerciseType)
class ExerciseTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "display_name", "emoji", "unit", "is_active"]
    list_filter = ["is_active", "unit"]
    search_fields = ["name", "display_name", "aliases"]
    list_editable = ["is_active"]
    ordering = ["name"]


@admin.register(ExerciseChallenge)
class ExerciseChallengeAdmin(admin.ModelAdmin):
    list_display = [
        "challenge_name",
        "exercise_type",
        "start_date",
        "end_date",
        "target_total",
        "daily_target",
        "is_active",
        "is_default",
    ]
    list_filter = ["is_active", "is_default", "start_date", "end_date"]
    search_fields = ["challenge_name", "exercise_type__name", "exercise_type__display_name"]
    list_editable = ["is_active", "is_default"]
    date_hierarchy = "start_date"
    ordering = ["-start_date"]
    raw_id_fields = ["exercise_type"]


@admin.register(ExerciseLog)
class ExerciseLogAdmin(admin.ModelAdmin):
    list_display = [
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
        "exercise_type",
        "status",
        "date",
        "timestamp",
    ]
    search_fields = [
        "exercise_type__name",
        "exercise_type__display_name",
        "challenge__challenge_name",
        "raw_message",
        "notes",
    ]
    date_hierarchy = "date"
    ordering = ["-timestamp"]
    raw_id_fields = ["exercise_type", "challenge"]
    readonly_fields = ["timestamp", "cumulative_total", "day_number", "status"]


@admin.register(UserStats)
class UserStatsAdmin(admin.ModelAdmin):
    list_display = [
        "exercise_type",
        "all_time_total",
        "best_daily_count",
        "current_streak",
        "longest_streak",
        "last_logged_date",
    ]
    list_filter = ["last_logged_date"]
    search_fields = ["exercise_type__name", "exercise_type__display_name"]
    ordering = ["-all_time_total"]
    raw_id_fields = ["exercise_type"]
    readonly_fields = [
        "all_time_total",
        "best_daily_count",
        "current_streak",
        "longest_streak",
        "last_logged_date",
    ]
