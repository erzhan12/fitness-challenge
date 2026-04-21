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
        description=(
            "Total target count for the challenge "
            "(computed: daily_target × effective_total_days, where "
            "effective_total_days subtracts exception days from the calendar span). "
            "Concrete example: 100 daily × 20 effective days = 2000 target_total, "
            "even if the calendar window is 30 days with 10 exception days."
        ),
        json_schema_extra={"readOnly": True},
    )
    daily_target: int = Field(..., description="Daily target count")
    challenge_name: str = Field(..., description="Name of the challenge")
    is_active: bool = Field(..., description="Whether the challenge is currently active")
    is_default: bool = Field(
        False, description="Whether this is the default challenge for number-only input"
    )

    # Exception (rest day) configuration
    exception_weekdays: List[int] = Field(
        default_factory=list,
        description="Recurring exception weekdays (ISO 1=Mon..7=Sun)",
    )
    exception_dates: List[dt.date] = Field(
        default_factory=list,
        description="One-off exception (rest) dates within the challenge window",
    )

    # Computed fields
    total_days: Optional[int] = Field(
        None,
        description="Calendar total number of days in the challenge",
        json_schema_extra={"readOnly": True},
    )
    effective_total_days: Optional[int] = Field(
        None,
        description=(
            "Total scheduled (non-exception) days in the challenge, used for "
            "target_total math. Equals total_days when there are no exceptions."
        ),
        json_schema_extra={"readOnly": True},
    )
    is_current: Optional[bool] = Field(
        None,
        description="Whether today falls within the challenge dates",
        json_schema_extra={"readOnly": True},
    )


def _validate_iso_weekdays(value: List[int]) -> List[int]:
    """Validate ISO weekday list (1..7), dedupe, sort ascending."""
    for w in value:
        if not (1 <= w <= 7):
            raise ValueError(
                f"exception_weekdays must contain ISO weekday ints 1..7; got {w}"
            )
    return sorted(set(value))


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
    exception_weekdays: List[int] = Field(
        default_factory=list,
        description="Recurring exception weekdays (ISO 1=Mon..7=Sun)",
        examples=[[6, 7]],
    )
    exception_dates: List[dt.date] = Field(
        default_factory=list,
        description="One-off exception dates; each must fall in [start_date, end_date]",
    )

    @field_validator("exception_weekdays")
    @classmethod
    def _check_weekdays(cls, v: List[int]) -> List[int]:
        return _validate_iso_weekdays(v)

    @model_validator(mode="after")
    def _check_exception_dates_in_window(self) -> "ExerciseChallengeCreate":
        if not self.exception_dates:
            return self
        # Dedupe + sort + window check
        deduped = sorted(set(self.exception_dates))
        for d in deduped:
            if not (self.start_date <= d <= self.end_date):
                raise ValueError(
                    f"exception_dates entry {d.isoformat()} is outside challenge window "
                    f"[{self.start_date.isoformat()}, {self.end_date.isoformat()}]"
                )
        # model_validator(mode='after') runs on the constructed instance —
        # mutate via direct attribute assignment.
        object.__setattr__(self, "exception_dates", deduped)
        return self


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
    exception_weekdays: Optional[List[int]] = Field(
        None,
        description="Recurring exception weekdays (ISO 1=Mon..7=Sun); replaces existing set",
    )
    exception_dates: Optional[List[dt.date]] = Field(
        None,
        description="One-off exception dates; replaces (NOT merges) the existing set",
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

    @field_validator("exception_weekdays")
    @classmethod
    def _check_weekdays(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is None:
            return v
        return _validate_iso_weekdays(v)

    @field_validator("exception_dates")
    @classmethod
    def _dedupe_exception_dates(
        cls, v: Optional[List[dt.date]]
    ) -> Optional[List[dt.date]]:
        # PATCH cannot enforce window membership without start_date/end_date,
        # which may be absent. The router/service must re-validate against the
        # current (or new) window before persisting.
        if v is None:
            return v
        return sorted(set(v))


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
        # Delegates to the shared helper so the Telegram handlers
        # (``_handle_challenge_prompt`` / ``_handle_exception_prompt``)
        # apply the exact same rules — see src/core/validators.py.
        from src.core.validators import sanitize_llm_prompt
        return sanitize_llm_prompt(v)


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
    exception_weekdays: Optional[List[int]] = Field(
        None,
        description="Recurring exception weekdays (ISO 1=Mon..7=Sun); empty/None = none",
    )
    exception_dates: Optional[List[dt.date]] = Field(
        None,
        description="Explicit one-off exception dates extracted from the prompt",
    )


# =============================================================================
# Challenge Exception Days
# =============================================================================


class ChallengeExceptionDayOut(BaseModel):
    """JSON representation of a one-off challenge exception (rest) day."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Unique identifier")
    challenge_id: int = Field(..., description="Owning challenge id")
    date: dt.date = Field(..., description="Exception date")
    reason: str = Field("", description="Optional reason / label")
    created_at: dt.datetime = Field(..., description="When this exception was added")


class ChallengeExceptionDayCreate(BaseModel):
    """Request model for adding a one-off exception day to a challenge."""

    date: dt.date = Field(
        ...,
        description="Exception date; must fall within the challenge window",
        examples=["2026-04-20"],
    )
    reason: Optional[str] = Field(
        None,
        description="Optional human-readable label",
        examples=["Easter Monday"],
        max_length=200,
    )


class ExceptionPromptDateEntry(BaseModel):
    """One date the LLM exception parser extracted from the user prompt."""

    date: dt.date = Field(..., description="Exception date")
    reason: Optional[str] = Field(
        None, description="Optional human-readable label extracted from the prompt"
    )


class ExceptionPromptParsed(BaseModel):
    """Intermediate model returned by ``parse_exception_prompt`` for /exception add."""

    is_valid: bool = Field(..., description="Whether the LLM successfully parsed the prompt")
    error_reason: Optional[str] = Field(
        None, description="Error reason when is_valid is False"
    )
    exception_weekdays: List[int] = Field(
        default_factory=list,
        description="Recurring exception weekdays the user mentioned (ISO 1..7)",
    )
    exception_dates: List[ExceptionPromptDateEntry] = Field(
        default_factory=list,
        description="One-off exception dates the user mentioned (with optional reason)",
    )

    @field_validator("exception_weekdays")
    @classmethod
    def _check_weekdays(cls, v: List[int]) -> List[int]:
        return _validate_iso_weekdays(v)


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
    day_number: int = Field(
        ...,
        description=(
            "Current day number counted across scheduled (non-rest) days only. "
            "On a rest day this is frozen at the count of scheduled days strictly "
            "before today, so the daily ring does not advance through exceptions."
        ),
    )
    total_days: int = Field(
        ...,
        description=(
            "Effective scheduled days in the challenge — calendar days minus "
            "exception (rest) days. NOTE: this differs from "
            "ExerciseChallengeOut.total_days, which is the calendar span. "
            "Clients that need the calendar span should read it from the "
            "challenge resource."
        ),
    )

    # Targets
    target_total: int = Field(
        ...,
        description=(
            "Total target across scheduled days "
            "(computed: daily_target × effective scheduled days, which "
            "excludes rest days). Equals 0 when every day in the window "
            "is a rest day."
        ),
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
        0,
        description=(
            "Number of reps needed to catch up (if behind). Always 0 on rest "
            "days because the daily ring is hidden when is_today_exception is True."
        ),
    )

    # Completion status
    is_daily_complete: bool = Field(
        default=False,
        description="True if cumulative progress is on track or ahead of expected progress for this challenge",
    )

    # Exception (rest) day flag
    is_today_exception: bool = Field(
        default=False,
        description=(
            "True when today is an exception (rest) day for this challenge. "
            "When True, the daily ring should be hidden in the Telegram stats card "
            "and the day_number is frozen at the previous scheduled day."
        ),
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

