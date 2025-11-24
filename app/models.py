from typing import List, Optional
from datetime import date
from pydantic import BaseModel, Field

# --- OpenAI Parsing Models ---


class ExerciseEntry(BaseModel):
    exercise_type_name: str = Field(
        ...,
        description="The normalized name of the exercise (e.g., 'pushups', 'plank')",
    )
    count: int = Field(..., description="Number of reps or minutes")
    duration_seconds: Optional[int] = Field(
        None, description="Total seconds for time-based exercises"
    )
    notes: Optional[str] = Field(None, description="Context or notes from the user")
    confidence: float = Field(..., description="Confidence score between 0 and 1")


class ParseResult(BaseModel):
    entries: List[ExerciseEntry]
    is_valid: bool
    error_reason: Optional[str] = None


# --- Telegram Webhook Models (Minimal) ---


class TelegramUser(BaseModel):
    id: int
    first_name: str
    username: Optional[str] = None


class TelegramChat(BaseModel):
    id: int
    type: str


class TelegramMessage(BaseModel):
    message_id: int
    from_: Optional[TelegramUser] = Field(None, alias="from")
    chat: TelegramChat
    date: int
    text: Optional[str] = None


class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[TelegramMessage] = None


# --- Database/Application Models ---


class ExerciseType(BaseModel):
    id: int
    name: str
    display_name: str
    emoji: str
    unit: str
    aliases: List[str]


class ExerciseChallenge(BaseModel):
    id: int
    exercise_type_id: int
    start_date: date
    end_date: date
    target_total: int
    daily_target: Optional[int]
    challenge_name: str
    is_active: bool


class UserStats(BaseModel):
    exercise_type_id: int
    all_time_total: int
    best_daily_count: int
    current_streak: int
    longest_streak: int
    last_logged_date: Optional[date]
