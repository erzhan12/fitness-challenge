"""Shared fixtures for API tests."""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


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


# =============================================================================
# Supabase Mocking Helpers
# =============================================================================


def create_mock_query(data, count=None):
    """Create a mock Supabase query chain."""
    mock_response = Mock()
    mock_response.data = data
    mock_response.count = count if count is not None else len(data)

    mock_query = Mock()
    mock_query.execute.return_value = mock_response
    mock_query.eq.return_value = mock_query
    mock_query.neq.return_value = mock_query
    mock_query.gt.return_value = mock_query
    mock_query.gte.return_value = mock_query
    mock_query.lt.return_value = mock_query
    mock_query.lte.return_value = mock_query
    mock_query.in_.return_value = mock_query
    mock_query.is_.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.range.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.insert.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.delete.return_value = mock_query

    return mock_query


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    mock_sb = Mock()

    def table_factory(table_name):
        mock_table = Mock()
        mock_table.select.return_value = create_mock_query([])
        mock_table.insert.return_value = create_mock_query([])
        mock_table.update.return_value = create_mock_query([])
        mock_table.delete.return_value = create_mock_query([])
        return mock_table

    mock_sb.table.side_effect = table_factory
    return mock_sb


@pytest.fixture
def patch_supabase(mock_supabase):
    """Patch the get_supabase function to return mock client."""
    with patch("app.dependencies.get_supabase", return_value=mock_supabase):
        with patch("src.api.services.get_supabase", return_value=mock_supabase):
            yield mock_supabase

