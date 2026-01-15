"""API-facing Pydantic models for REST endpoints.

These models are explicitly separated from Telegram-specific models
and HTML formatting to remain stable for future mobile/web clients.
"""

import datetime as dt
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Exercise Types
# =============================================================================


class ExerciseTypeOut(BaseModel):
    """JSON representation of an exercise type."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Unique identifier for the exercise type")
    name: str = Field(..., description="Internal name (e.g., 'pushups')")
    display_name: str = Field(..., description="Human-readable name (e.g., 'Push-ups')")
    emoji: str = Field(..., description="Emoji icon for the exercise")
    unit: str = Field(..., description="Unit of measurement (e.g., 'reps', 'minutes')")
    aliases: List[str] = Field(
        default_factory=list, description="Alternative names for parsing"
    )
    is_active: bool = Field(True, description="Whether the exercise type is active")


class ExerciseTypeCreate(BaseModel):
    """Request model for creating an exercise type."""

    name: str = Field(..., description="Internal name", examples=["pullups"])
    display_name: str = Field(
        ..., description="Human-readable name", examples=["Pull-ups"]
    )
    emoji: str = Field(..., description="Emoji icon", examples=["💪"])
    unit: str = Field("reps", description="Unit of measurement", examples=["reps"])
    aliases: List[str] = Field(
        default_factory=list,
        description="Alternative names",
        examples=[["pull-up", "pull up", "chin-up"]],
    )
    is_active: bool = Field(True, description="Whether the exercise type is active")


class ExerciseTypeUpdate(BaseModel):
    """Request model for updating an exercise type (partial update)."""

    display_name: Optional[str] = Field(None, description="Human-readable name")
    emoji: Optional[str] = Field(None, description="Emoji icon")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    aliases: Optional[List[str]] = Field(None, description="Alternative names")
    is_active: Optional[bool] = Field(None, description="Whether active")


# =============================================================================
# Challenges
# =============================================================================


class ExerciseChallengeOut(BaseModel):
    """JSON representation of a challenge."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Unique identifier for the challenge")
    exercise_type_id: int = Field(
        ..., description="ID of the associated exercise type"
    )
    start_date: dt.date = Field(..., description="Challenge start date")
    end_date: dt.date = Field(..., description="Challenge end date")
    target_total: int = Field(..., description="Total target count for the challenge")
    daily_target: Optional[int] = Field(None, description="Daily target count")
    challenge_name: str = Field(..., description="Name of the challenge")
    is_active: bool = Field(..., description="Whether the challenge is currently active")
    is_default: bool = Field(
        False, description="Whether this is the default challenge for number-only input"
    )

    # Computed fields
    total_days: Optional[int] = Field(
        None, description="Total number of days in the challenge"
    )
    is_current: Optional[bool] = Field(
        None, description="Whether today falls within the challenge dates"
    )


class ExerciseChallengeCreate(BaseModel):
    """Request model for creating a challenge."""

    exercise_type_id: int = Field(
        ..., description="ID of the associated exercise type", examples=[1]
    )
    start_date: dt.date = Field(
        ..., description="Challenge start date", examples=["2024-01-01"]
    )
    end_date: dt.date = Field(
        ..., description="Challenge end date", examples=["2024-01-31"]
    )
    target_total: int = Field(
        ..., description="Total target count", examples=[1000], ge=1
    )
    daily_target: Optional[int] = Field(
        None, description="Optional daily target", examples=[33], ge=1
    )
    challenge_name: str = Field(
        ..., description="Name of the challenge", examples=["January Push-up Challenge"]
    )
    is_active: bool = Field(True, description="Whether the challenge is active")
    is_default: bool = Field(
        False, description="Whether this is the default challenge"
    )


class ExerciseChallengeUpdate(BaseModel):
    """Request model for updating a challenge (partial update)."""

    start_date: Optional[dt.date] = Field(None, description="Challenge start date")
    end_date: Optional[dt.date] = Field(None, description="Challenge end date")
    target_total: Optional[int] = Field(None, description="Total target count", ge=1)
    daily_target: Optional[int] = Field(None, description="Daily target count", ge=1)
    challenge_name: Optional[str] = Field(None, description="Name of the challenge")
    is_active: Optional[bool] = Field(None, description="Whether active")
    is_default: Optional[bool] = Field(
        None, description="Whether this is the default challenge"
    )


# =============================================================================
# Exercise Logs
# =============================================================================


class ExerciseLogOut(BaseModel):
    """JSON representation of a log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Unique identifier for the log entry")
    exercise_type_id: int = Field(
        ..., description="ID of the associated exercise type"
    )
    challenge_id: Optional[int] = Field(
        None, description="ID of the associated challenge"
    )
    date: dt.date = Field(..., description="Date of the log entry")
    timestamp: dt.datetime = Field(..., description="Exact timestamp of the log")
    count: int = Field(..., description="Number of reps or minutes logged")
    cumulative_total: Optional[int] = Field(
        None, description="Cumulative total at time of logging"
    )
    day_number: Optional[int] = Field(
        None, description="Day number in the challenge"
    )
    status: Optional[str] = Field(
        None, description="Status at time of logging (ahead/on_track/behind)"
    )
    raw_message: Optional[str] = Field(
        None, description="Original message that created this log"
    )
    duration_seconds: Optional[int] = Field(
        None, description="Duration in seconds for time-based exercises"
    )
    notes: Optional[str] = Field(None, description="Additional notes")

    # Joined fields (optional, populated when including relations)
    exercise_type: Optional[ExerciseTypeOut] = Field(
        None, description="Associated exercise type details"
    )


class ExerciseLogCreate(BaseModel):
    """Request model for creating a log entry."""

    exercise_type_id: int = Field(
        ..., description="ID of the exercise type", examples=[1]
    )
    count: int = Field(..., description="Number of reps or minutes", examples=[25], ge=1)
    date: Optional[dt.date] = Field(
        None, description="Date of the log (defaults to today)", examples=["2024-01-15"]
    )
    duration_seconds: Optional[int] = Field(
        None, description="Duration in seconds for time-based exercises", ge=0
    )
    notes: Optional[str] = Field(
        None, description="Additional notes", examples=["Morning workout"]
    )
    raw_message: Optional[str] = Field(
        None, description="Original message text", examples=["25 pushups"]
    )


class ExerciseLogCreateResponse(BaseModel):
    """Response model for log creation including updated stats."""

    log: ExerciseLogOut = Field(..., description="The created log entry")
    stats: "ExerciseStatsOut" = Field(
        ..., description="Updated stats for the exercise"
    )


# =============================================================================
# Stats
# =============================================================================


class ExerciseStatsOut(BaseModel):
    """Summary stats for an exercise within a challenge context."""

    exercise_type_id: int = Field(..., description="ID of the exercise type")
    exercise_type_name: str = Field(..., description="Display name of the exercise")
    exercise_type_emoji: str = Field(..., description="Emoji for the exercise")

    # Challenge context
    challenge_id: Optional[int] = Field(None, description="ID of the active challenge")
    challenge_name: Optional[str] = Field(None, description="Name of the challenge")
    day_number: int = Field(..., description="Current day number in the challenge")
    total_days: int = Field(..., description="Total days in the challenge")

    # Targets
    target_total: int = Field(..., description="Total target for the challenge")
    daily_target: Optional[int] = Field(None, description="Daily target if set")

    # Progress
    today_total: int = Field(..., description="Total logged today")
    cumulative_total: int = Field(..., description="Cumulative total so far")
    progress_percent: float = Field(
        ..., description="Progress percentage (0-100)", ge=0, le=100
    )

    # Status
    status: str = Field(
        ..., description="Current status: 'ahead', 'on_track', or 'behind'"
    )
    catch_up_reps: int = Field(
        0, description="Number of reps needed to catch up (if behind)"
    )


class UserStatsOut(BaseModel):
    """User-level aggregated stats per exercise type."""

    model_config = ConfigDict(from_attributes=True)

    exercise_type_id: int = Field(..., description="ID of the exercise type")
    all_time_total: int = Field(..., description="All-time total count")
    best_daily_count: int = Field(0, description="Best single-day count")
    current_streak: int = Field(0, description="Current consecutive days streak")
    longest_streak: int = Field(0, description="Longest streak ever")
    last_logged_date: Optional[dt.date] = Field(None, description="Date of last log")

    # Joined fields (optional)
    exercise_type: Optional[ExerciseTypeOut] = Field(
        None, description="Associated exercise type details"
    )


class StatsSummaryOut(BaseModel):
    """Overall summary stats across all exercises."""

    total_reps_all_time: int = Field(
        ..., description="Total reps across all exercise types"
    )
    total_active_days: int = Field(
        ..., description="Number of days with any activity"
    )
    exercise_stats: List[UserStatsOut] = Field(
        ..., description="Per-exercise-type stats"
    )


# =============================================================================
# Parsing (optional API)
# =============================================================================


class ParseWorkoutRequest(BaseModel):
    """Request model for parsing workout text."""

    text: str = Field(
        ...,
        description="Raw workout message to parse",
        examples=["20 pushups and 30 squats"],
    )


class ParseWorkoutEntry(BaseModel):
    """A single parsed exercise entry."""

    exercise_type_name: str = Field(
        ..., description="Normalized exercise name", examples=["pushups"]
    )
    count: int = Field(..., description="Number of reps or minutes", examples=[20])
    duration_seconds: Optional[int] = Field(
        None, description="Duration in seconds for time-based"
    )
    notes: Optional[str] = Field(None, description="Additional context")
    confidence: float = Field(
        ..., description="Parser confidence (0-1)", examples=[0.95], ge=0, le=1
    )


class ParseWorkoutResponse(BaseModel):
    """Response model for workout parsing."""

    entries: List[ParseWorkoutEntry] = Field(
        ..., description="List of parsed exercise entries"
    )
    is_valid: bool = Field(..., description="Whether parsing was successful")
    error_reason: Optional[str] = Field(
        None, description="Error message if parsing failed"
    )


# =============================================================================
# Pagination
# =============================================================================


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    total: int = Field(..., description="Total number of items")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Current offset")
    has_more: bool = Field(..., description="Whether there are more items")


class PaginatedLogsResponse(BaseModel):
    """Paginated response for log listings."""

    data: List[ExerciseLogOut] = Field(..., description="List of log entries")
    pagination: PaginationMeta = Field(..., description="Pagination info")


# =============================================================================
# Settings
# =============================================================================


class SettingsOut(BaseModel):
    """JSON representation of app settings."""

    model_config = ConfigDict(from_attributes=True)

    is_reminder_active: bool = Field(
        ..., description="Whether evening reminders are enabled"
    )
    telegram_chat_id: Optional[int] = Field(
        None, description="Telegram chat ID for sending reminders"
    )


class SettingsUpdate(BaseModel):
    """Request model for updating app settings."""

    is_reminder_active: Optional[bool] = Field(
        None, description="Whether to enable or disable evening reminders"
    )


# =============================================================================
# Error Response
# =============================================================================


class ErrorResponse(BaseModel):
    """Standard error response format."""

    detail: str = Field(..., description="Human-readable error message")
    code: Optional[str] = Field(
        None, description="Machine-readable error code", examples=["NOT_FOUND"]
    )


# Rebuild models that have forward references
ExerciseLogCreateResponse.model_rebuild()

