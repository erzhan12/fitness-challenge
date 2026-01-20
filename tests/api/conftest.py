"""Shared fixtures for API tests."""

import pytest
from datetime import date as dt_date, datetime as dt_datetime
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient

from src.core import setup_django

setup_django()

from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402
from src.core.models import (  # noqa: E402
    ExerciseType as ExerciseTypeModel,
    ExerciseChallenge as ExerciseChallengeModel,
    ExerciseLog as ExerciseLogModel,
    UserStats as UserStatsModel,
    AppUser as AppUserModel,
)


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


@pytest.fixture
def api_key():
    """Return the admin API key for authenticated requests."""
    return settings.ADMIN_API_KEY


@pytest.fixture
def auth_headers(api_key):
    """Return authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {api_key}"}


@pytest.fixture
def invalid_auth_headers():
    """Return authorization headers with invalid token."""
    return {"Authorization": "Bearer invalid-key-12345"}


@pytest.fixture
def test_telegram_user_id():
    """Return a test Telegram user ID."""
    return 123456789


@pytest.fixture
def user_context_headers(test_telegram_user_id):
    """Return headers with X-Telegram-User-Id for user context."""
    return {"X-Telegram-User-Id": str(test_telegram_user_id)}


@pytest.fixture
def auth_and_user_headers(auth_headers, user_context_headers):
    """Return combined auth and user context headers for write operations."""
    return {**auth_headers, **user_context_headers}


# =============================================================================
# Mock Data
# =============================================================================


@pytest.fixture
def mock_exercise_type_data():
    """Sample exercise type data."""
    return {
        "id": 1,
        "name": "pushups",
        "display_name": "Push-ups",
        "emoji": "💪",
        "unit": "reps",
        "aliases": ["push-up", "push up"],
        "is_active": True,
    }


@pytest.fixture
def mock_exercise_type_data_2():
    """Second sample exercise type data."""
    return {
        "id": 2,
        "name": "squats",
        "display_name": "Squats",
        "emoji": "🏋️",
        "unit": "reps",
        "aliases": ["squat"],
        "is_active": True,
    }


@pytest.fixture
def mock_challenge_data():
    """Sample challenge data."""
    return {
        "id": 1,
        "exercise_type_id": 1,
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "target_total": 1000,
        "daily_target": 33,
        "challenge_name": "January Push-up Challenge",
        "is_active": True,
    }


@pytest.fixture
def mock_log_data():
    """Sample log entry data."""
    return {
        "id": 123,
        "exercise_type_id": 1,
        "challenge_id": 1,
        "date": "2024-01-15",
        "timestamp": "2024-01-15T10:30:00+05:00",
        "count": 25,
        "cumulative_total": 250,
        "day_number": 15,
        "status": "on_track",
        "raw_message": "25 pushups",
        "duration_seconds": None,
        "notes": None,
    }


@pytest.fixture
def mock_user_stats_data():
    """Sample user stats data."""
    return {
        "id": 1,
        "exercise_type_id": 1,
        "all_time_total": 3000,
        "best_daily_count": 100,
        "current_streak": 7,
        "longest_streak": 14,
        "last_logged_date": "2024-01-15",
    }


@pytest.fixture
def mock_app_user_data(test_telegram_user_id):
    """Sample AppUser data."""
    return {
        "id": 1,
        "telegram_user_id": test_telegram_user_id,
        "username": "testuser",
        "first_name": "Test",
        "timezone": "Asia/Almaty",
        "status": "approved",
        "created_at": "2024-01-01T00:00:00+05:00",
        "approved_at": "2024-01-01T00:00:00+05:00",
    }


def _parse_date(value):
    if value is None or isinstance(value, dt_date):
        return value
    return dt_date.fromisoformat(value)


def _parse_datetime(value):
    if value is None or isinstance(value, dt_datetime):
        return value
    # Support "Z" suffix (Supabase-style) while still accepting offset-aware strings.
    return dt_datetime.fromisoformat(value.replace("Z", "+00:00"))


def make_exercise_type_model(data: dict) -> ExerciseTypeModel:
    return ExerciseTypeModel(
        id=data.get("id"),
        name=data["name"],
        display_name=data["display_name"],
        emoji=data["emoji"],
        unit=data.get("unit", "reps"),
        aliases=data.get("aliases", []),
        is_active=data.get("is_active", True),
    )


def make_challenge_model(data: dict, exercise_type: ExerciseTypeModel | None = None) -> ExerciseChallengeModel:
    model = ExerciseChallengeModel(
        id=data.get("id"),
        exercise_type_id=data["exercise_type_id"],
        start_date=_parse_date(data["start_date"]),
        end_date=_parse_date(data["end_date"]),
        target_total=data["target_total"],
        daily_target=data.get("daily_target"),
        challenge_name=data.get("challenge_name", ""),
        is_active=data.get("is_active", True),
        is_default=data.get("is_default", False),
    )
    if exercise_type is not None:
        model.exercise_type = exercise_type
    return model


def make_log_model(
    data: dict,
    exercise_type: ExerciseTypeModel | None = None,
    challenge: ExerciseChallengeModel | None = None,
) -> ExerciseLogModel:
    model = ExerciseLogModel(
        id=data.get("id"),
        exercise_type_id=data["exercise_type_id"],
        challenge_id=data.get("challenge_id"),
        date=_parse_date(data["date"]),
        timestamp=_parse_datetime(data["timestamp"]),
        count=data["count"],
        cumulative_total=data.get("cumulative_total"),
        day_number=data.get("day_number"),
        status=data.get("status"),
        raw_message=data.get("raw_message"),
        duration_seconds=data.get("duration_seconds"),
        notes=data.get("notes"),
    )
    if exercise_type is not None:
        model.exercise_type = exercise_type
    if challenge is not None:
        model.challenge = challenge
    return model


def make_user_stats_model(
    data: dict, exercise_type: ExerciseTypeModel | None = None
) -> UserStatsModel:
    model = UserStatsModel(
        id=data.get("id"),
        exercise_type_id=data["exercise_type_id"],
        all_time_total=data.get("all_time_total", 0),
        best_daily_count=data.get("best_daily_count", 0),
        current_streak=data.get("current_streak", 0),
        longest_streak=data.get("longest_streak", 0),
        last_logged_date=_parse_date(data.get("last_logged_date")),
    )
    if exercise_type is not None:
        model.exercise_type = exercise_type
    return model


def make_app_user_model(data: dict) -> AppUserModel:
    model = AppUserModel(
        id=data.get("id"),
        telegram_user_id=data["telegram_user_id"],
        username=data.get("username"),
        first_name=data.get("first_name"),
        timezone=data.get("timezone", "Asia/Almaty"),
        status=data.get("status", "approved"),
        created_at=_parse_datetime(data.get("created_at", "2024-01-01T00:00:00+05:00")),
        approved_at=_parse_datetime(data.get("approved_at")) if data.get("approved_at") else None,
    )
    return model


@pytest.fixture
def exercise_type_model(mock_exercise_type_data):
    return make_exercise_type_model(mock_exercise_type_data)


@pytest.fixture
def exercise_type_model_2(mock_exercise_type_data_2):
    return make_exercise_type_model(mock_exercise_type_data_2)


@pytest.fixture
def challenge_model(mock_challenge_data, exercise_type_model):
    return make_challenge_model(mock_challenge_data, exercise_type=exercise_type_model)


@pytest.fixture
def log_model(mock_log_data, exercise_type_model, challenge_model):
    return make_log_model(
        mock_log_data, exercise_type=exercise_type_model, challenge=challenge_model
    )


@pytest.fixture
def user_stats_model(mock_user_stats_data, exercise_type_model):
    return make_user_stats_model(mock_user_stats_data, exercise_type=exercise_type_model)


@pytest.fixture
def app_user_model(mock_app_user_data):
    return make_app_user_model(mock_app_user_data)


@pytest.fixture
def mock_repos(app_user_model):
    """Mock all repository instances used by src.api.services and security."""
    # Create a mock exercise type model for default returns
    default_exercise_type = make_exercise_type_model({
        "id": 1,
        "name": "pushups",
        "display_name": "Push-ups",
        "emoji": "💪",
        "unit": "reps",
        "aliases": ["push-up", "push up"],
        "is_active": True,
    })

    exercise_type_repo = Mock()
    exercise_type_repo.get_all = AsyncMock(return_value=[])
    exercise_type_repo.get_by_id = AsyncMock(return_value=default_exercise_type)  # Return default exercise type
    exercise_type_repo.get_by_name = AsyncMock(return_value=None)
    exercise_type_repo.create = AsyncMock(return_value=None)
    exercise_type_repo.update = AsyncMock(return_value=None)
    exercise_type_repo.get_by_ids = AsyncMock(return_value=[])

    challenge_repo = Mock()
    challenge_repo.get_all = AsyncMock(return_value=[])
    challenge_repo.get_by_id = AsyncMock(return_value=None)
    challenge_repo.get_active_for_type = AsyncMock(return_value=None)
    challenge_repo.get_current_active = AsyncMock(return_value=[])
    challenge_repo.create = AsyncMock(return_value=None)
    challenge_repo.update = AsyncMock(return_value=None)

    log_repo = Mock()
    log_repo.get_all = AsyncMock(return_value=([], 0))
    log_repo.get_by_id = AsyncMock(return_value=None)
    log_repo.get_cumulative_count = AsyncMock(return_value=0)
    log_repo.get_today_count = AsyncMock(return_value=0)
    log_repo.create = AsyncMock(return_value=None)
    log_repo.delete = AsyncMock(return_value=None)
    log_repo.get_last_log = AsyncMock(return_value=None)

    user_stats_repo = Mock()
    user_stats_repo.get_all = AsyncMock(return_value=[])
    user_stats_repo.get_by_exercise_type = AsyncMock(return_value=None)
    user_stats_repo.get_or_create = AsyncMock(return_value=None)
    user_stats_repo.update = AsyncMock(return_value=None)
    user_stats_repo.increment_total = AsyncMock(return_value=None)
    user_stats_repo.decrement_total = AsyncMock(return_value=None)
    user_stats_repo.sync_last_logged_date = AsyncMock(return_value=None)

    app_user_repo = Mock()
    app_user_repo.get_by_telegram_user_id = AsyncMock(return_value=app_user_model)
    app_user_repo.get_or_create_by_telegram_user_id = AsyncMock(return_value=(app_user_model, False))

    with patch("src.api.services.exercise_type_repo", exercise_type_repo), \
         patch("src.api.services.challenge_repo", challenge_repo), \
         patch("src.api.services.log_repo", log_repo), \
         patch("src.api.services.user_stats_repo", user_stats_repo), \
         patch("src.api.security.app_user_repo", app_user_repo):
        yield {
            "exercise_type": exercise_type_repo,
            "challenge": challenge_repo,
            "log": log_repo,
            "user_stats": user_stats_repo,
            "app_user": app_user_repo,
        }
