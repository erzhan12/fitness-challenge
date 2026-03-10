"""API-facing Pydantic models for REST endpoints.

These models are explicitly separated from Telegram-specific models
and HTML formatting to remain stable for future mobile/web clients.
"""

import datetime as dt
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


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
    target_total: int = Field(
        ...,
        description="Total target count for the challenge (computed: daily_target × total_days)",
        json_schema_extra={"readOnly": True},
    )
    daily_target: int = Field(..., description="Daily target count")
    challenge_name: str = Field(..., description="Name of the challenge")
    is_active: bool = Field(..., description="Whether the challenge is currently active")
    is_default: bool = Field(
        False, description="Whether this is the default challenge for number-only input"
    )

    # Computed fields
    total_days: Optional[int] = Field(
        None,
        description="Total number of days in the challenge",
        json_schema_extra={"readOnly": True},
    )
    is_current: Optional[bool] = Field(
        None,
        description="Whether today falls within the challenge dates",
        json_schema_extra={"readOnly": True},
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
    daily_target: int = Field(
        ..., description="Daily target count", examples=[33], ge=1
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
    daily_target: Optional[int] = Field(None, description="Daily target count", ge=1)
    challenge_name: Optional[str] = Field(None, description="Name of the challenge")
    is_active: Optional[bool] = Field(None, description="Whether active")
    is_default: Optional[bool] = Field(
        None, description="Whether this is the default challenge"
    )

    @model_validator(mode="before")
    @classmethod
    def reject_null_daily_target(cls, data):
        """Reject explicit null values for daily_target in PATCH requests.

        Since daily_target is now required in the DB, we must prevent users
        from explicitly setting it to null via API updates.
        """
        if isinstance(data, dict) and "daily_target" in data and data["daily_target"] is None:
            raise ValueError("daily_target cannot be null")
        return data


# =============================================================================
# Challenge from Prompt
# =============================================================================


class ChallengePromptRequest(BaseModel):
    """Request model for creating a challenge from a natural language prompt."""

    text: str = Field(
        ...,
        description="Natural language description of the challenge",
        examples=["pushups challenge for 30 days starting tomorrow, 2000 reps total"],
        min_length=5,
        max_length=500,
    )

    @field_validator("text")
    @classmethod
    def validate_safe_input(cls, v: str) -> str:
        import re
        import unicodedata
        v = v.strip()
        # Normalize Unicode (e.g. fullwidth chars, accented lookalikes)
        decomposed = unicodedata.normalize("NFKD", v)
        # Map common homoglyphs (Cyrillic/Greek lookalikes) and leet-speak to Latin
        _homoglyph_map = str.maketrans(
            "аеорсухіјёАВЕНІКМОРСТХοеіа0134578",
            "aeopcyxijëABEHIKMOPCTXoeiaoieastb",
        )
        transliterated = decomposed.translate(_homoglyph_map)
        # Strip non-Latin-alpha (removes digits, zero-width chars, symbols)
        # then collapse any resulting gaps so "ign0re" → "ignore" not "ign re"
        words = transliterated.split()
        cleaned_words = [re.sub(r"[^a-zA-Z:\[\]]", "", w).lower() for w in words]
        normalized = " ".join(w for w in cleaned_words if w)
        suspicious_patterns = [
            "ignore previous", "ignore all", "ignore above",
            "disregard prior", "disregard previous",
            "forget everything", "forget above",
            "neglect above",
            "system:", "assistant:", "[inst]",
            "you are now",
        ]
        for pattern in suspicious_patterns:
            if pattern in normalized:
                raise ValueError("Invalid input format")
        return v


class ChallengePromptParsed(BaseModel):
    """Intermediate model representing what the LLM extracted from the prompt."""

    is_valid: bool = Field(..., description="Whether the LLM successfully parsed the prompt")
    error_reason: Optional[str] = Field(None, description="Error reason if is_valid is False")
    exercise_type_name: Optional[str] = Field(
        None, description="Matched exercise type name (internal name)"
    )
    start_date: Optional[dt.date] = Field(None, description="Challenge start date")
    duration_days: Optional[int] = Field(None, description="Number of days", ge=1)
    target_total: Optional[int] = Field(
        None, description="Total reps/units for the full challenge", ge=1
    )
    daily_target: Optional[int] = Field(
        None, description="Daily reps/units target", ge=1
    )
    challenge_name: Optional[str] = Field(None, description="Name for the challenge")


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
    target_total: int = Field(
        ...,
        description="Total target for the challenge (computed: daily_target × total_days)",
        json_schema_extra={"readOnly": True},
    )
    daily_target: int = Field(..., description="Daily target count")

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

    # Completion status
    is_daily_complete: bool = Field(
        default=False,
        description="True if cumulative progress is on track or ahead of expected progress for this challenge",
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
# Users
# =============================================================================


class UserOut(BaseModel):
    """JSON representation of a user."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Unique identifier for the user")
    telegram_user_id: int = Field(..., description="Telegram user ID")
    username: Optional[str] = Field(None, description="Telegram username")
    first_name: Optional[str] = Field(None, description="User's first name")
    timezone: str = Field(..., description="User's timezone")
    status: str = Field(..., description="User status: pending, approved, or rejected")
    created_at: dt.datetime = Field(..., description="Account creation timestamp")
    approved_at: Optional[dt.datetime] = Field(None, description="Approval timestamp")


class UserCreate(BaseModel):
    """Request model for creating/registering a user."""

    telegram_user_id: int = Field(
        ..., description="Telegram user ID", examples=[123456789]
    )
    username: Optional[str] = Field(
        None, description="Telegram username", examples=["john_doe"]
    )
    first_name: Optional[str] = Field(
        None, description="User's first name", examples=["John"]
    )
    timezone: str = Field(
        "Asia/Almaty", description="User's timezone", examples=["Asia/Almaty"]
    )


class UserUpdate(BaseModel):
    """Request model for updating a user profile."""

    username: Optional[str] = Field(None, description="Telegram username")
    first_name: Optional[str] = Field(None, description="User's first name")
    timezone: Optional[str] = Field(None, description="User's timezone")


class UserSettingsOut(BaseModel):
    """JSON representation of user settings."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(..., description="User ID")
    telegram_chat_id: Optional[int] = Field(
        None, description="Telegram chat ID for sending messages"
    )
    is_reminder_active: bool = Field(
        ..., description="Whether evening reminders are enabled"
    )
    habit_reward_api_key: str = Field(
        "", description="API key for Habit Reward integration"
    )
    habit_reward_habit_id: Optional[int] = Field(
        None, description="Habit ID to mark as complete in Habit Reward"
    )


class UserSettingsUpdate(BaseModel):
    """Request model for updating user settings."""

    is_reminder_active: Optional[bool] = Field(
        None, description="Whether to enable or disable evening reminders"
    )
    telegram_chat_id: Optional[int] = Field(
        None, description="Telegram chat ID"
    )
    habit_reward_api_key: Optional[str] = Field(
        None, description="API key for Habit Reward integration"
    )
    habit_reward_habit_id: Optional[int] = Field(
        None, description="Habit ID to mark as complete in Habit Reward"
    )


class UserWithSettingsOut(BaseModel):
    """User profile with settings."""

    user: UserOut = Field(..., description="User profile")
    settings: Optional[UserSettingsOut] = Field(None, description="User settings")


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

