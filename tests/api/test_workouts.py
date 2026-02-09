"""Tests for /api/v1/workouts endpoints."""

from unittest.mock import patch

from app.models import ExerciseEntry, ParseResult
from tests.api.conftest import make_challenge_model, make_exercise_type_model


class TestParseWorkout:
    """Tests for POST /api/v1/workouts/parse."""

    def test_parse_workout_success(
        self, client, auth_and_user_headers, mock_repos, exercise_type_model, challenge_model
    ):
        mock_repos["exercise_type"].get_all.return_value = [exercise_type_model]
        mock_repos["challenge"].get_all.return_value = [challenge_model]
        mock_repos["challenge"].get_current_active.return_value = [challenge_model]

        mock_result = ParseResult(
            entries=[
                ExerciseEntry(
                    exercise_type_name="pushups",
                    count=25,
                    duration_seconds=None,
                    notes=None,
                    confidence=0.95,
                )
            ],
            is_valid=True,
            error_reason=None,
        )

        with patch(
            "src.api.routers.workouts.parse_workout_message",
            return_value=mock_result,
        ):
            response = client.post(
                "/api/v1/workouts/parse",
                json={"text": "25 pushups"},
                headers=auth_and_user_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert len(data["entries"]) == 1
        assert data["entries"][0]["exercise_type_name"] == "pushups"
        assert data["entries"][0]["count"] == 25
        assert data["entries"][0]["confidence"] == 0.95

    def test_parse_workout_multiple_exercises(
        self,
        client,
        auth_and_user_headers,
        mock_repos,
        exercise_type_model,
        exercise_type_model_2,
    ):
        # Force fallback from challenge-only -> all active types.
        mock_repos["challenge"].get_all.return_value = []
        mock_repos["exercise_type"].get_all.return_value = [
            exercise_type_model,
            exercise_type_model_2,
        ]
        mock_repos["challenge"].get_current_active.return_value = []

        mock_result = ParseResult(
            entries=[
                ExerciseEntry(
                    exercise_type_name="pushups",
                    count=20,
                    duration_seconds=None,
                    notes=None,
                    confidence=0.95,
                ),
                ExerciseEntry(
                    exercise_type_name="squats",
                    count=30,
                    duration_seconds=None,
                    notes=None,
                    confidence=0.92,
                ),
            ],
            is_valid=True,
            error_reason=None,
        )

        with patch(
            "src.api.routers.workouts.parse_workout_message",
            return_value=mock_result,
        ):
            response = client.post(
                "/api/v1/workouts/parse",
                json={"text": "20 pushups and 30 squats"},
                headers=auth_and_user_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) == 2

    def test_parse_workout_invalid_message(self, client, auth_and_user_headers, mock_repos):
        mock_repos["exercise_type"].get_all.return_value = []
        mock_repos["challenge"].get_all.return_value = []
        mock_repos["challenge"].get_current_active.return_value = []

        mock_result = ParseResult(
            entries=[],
            is_valid=False,
            error_reason="Could not understand the workout message",
        )

        with patch(
            "src.api.routers.workouts.parse_workout_message",
            return_value=mock_result,
        ):
            response = client.post(
                "/api/v1/workouts/parse",
                json={"text": "random gibberish"},
                headers=auth_and_user_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert data["error_reason"] is not None
        assert data["entries"] == []

    def test_parse_workout_unauthorized(self, client):
        response = client.post("/api/v1/workouts/parse", json={"text": "25 pushups"})
        assert response.status_code == 401

    def test_parse_workout_forbidden(self, client, invalid_auth_headers, user_context_headers):
        response = client.post(
            "/api/v1/workouts/parse",
            json={"text": "25 pushups"},
            headers={**invalid_auth_headers, **user_context_headers},
        )
        assert response.status_code == 403

    def test_parse_workout_missing_text(self, client, auth_and_user_headers, mock_repos):
        response = client.post("/api/v1/workouts/parse", json={}, headers=auth_and_user_headers)
        assert response.status_code == 422

    def test_parse_workout_empty_text(self, client, auth_and_user_headers, mock_repos):
        mock_repos["exercise_type"].get_all.return_value = []
        mock_repos["challenge"].get_all.return_value = []
        mock_repos["challenge"].get_current_active.return_value = []

        mock_result = ParseResult(
            entries=[],
            is_valid=False,
            error_reason="Empty message",
        )

        with patch(
            "src.api.routers.workouts.parse_workout_message",
            return_value=mock_result,
        ):
            response = client.post(
                "/api/v1/workouts/parse",
                json={"text": ""},
                headers=auth_and_user_headers,
            )

        # Empty string is valid input, parser should handle it
        assert response.status_code == 200

    def test_parse_workout_with_duration(
        self, client, auth_and_user_headers, mock_repos, mock_exercise_type_data
    ):
        plank_type = {
            **mock_exercise_type_data,
            "id": 3,
            "name": "plank",
            "display_name": "Plank",
            "unit": "minutes",
        }
        mock_repos["challenge"].get_all.return_value = []
        mock_repos["exercise_type"].get_all.return_value = [make_exercise_type_model(plank_type)]
        mock_repos["challenge"].get_current_active.return_value = []

        mock_result = ParseResult(
            entries=[
                ExerciseEntry(
                    exercise_type_name="plank",
                    count=2,
                    duration_seconds=120,
                    notes="morning routine",
                    confidence=0.90,
                )
            ],
            is_valid=True,
            error_reason=None,
        )

        with patch(
            "src.api.routers.workouts.parse_workout_message",
            return_value=mock_result,
        ):
            response = client.post(
                "/api/v1/workouts/parse",
                json={"text": "2 min plank"},
                headers=auth_and_user_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["entries"][0]["duration_seconds"] == 120

    def test_parse_workout_response_format(
        self, client, auth_and_user_headers, mock_repos, exercise_type_model
    ):
        mock_repos["exercise_type"].get_all.return_value = [exercise_type_model]
        mock_repos["challenge"].get_all.return_value = []
        mock_repos["challenge"].get_current_active.return_value = []

        mock_result = ParseResult(
            entries=[
                ExerciseEntry(
                    exercise_type_name="pushups",
                    count=25,
                    duration_seconds=None,
                    notes="test notes",
                    confidence=0.95,
                )
            ],
            is_valid=True,
            error_reason=None,
        )

        with patch(
            "src.api.routers.workouts.parse_workout_message",
            return_value=mock_result,
        ):
            response = client.post(
                "/api/v1/workouts/parse",
                json={"text": "25 pushups"},
                headers=auth_and_user_headers,
            )

        assert response.status_code == 200
        data = response.json()

        assert "entries" in data
        assert "is_valid" in data
        assert "error_reason" in data

        entry = data["entries"][0]
        assert "exercise_type_name" in entry
        assert "count" in entry
        assert "duration_seconds" in entry
        assert "notes" in entry
        assert "confidence" in entry

    def test_parse_workout_multi_number_mapping(
        self,
        client,
        auth_and_user_headers,
        mock_repos,
        exercise_type_model,
        exercise_type_model_2,
    ):
        challenge_1 = make_challenge_model(
            {
                "id": 10,
                "exercise_type_id": 1,
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "daily_target": 33,
                "challenge_name": "Default Pushups",
                "is_active": True,
                "is_default": True,
            }
        )
        challenge_2 = make_challenge_model(
            {
                "id": 20,
                "exercise_type_id": 2,
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "daily_target": 33,
                "challenge_name": "Squats Challenge",
                "is_active": True,
                "is_default": False,
            }
        )

        mock_repos["exercise_type"].get_all.return_value = [
            exercise_type_model,
            exercise_type_model_2,
        ]
        mock_repos["challenge"].get_all.return_value = [challenge_1, challenge_2]
        mock_repos["challenge"].get_current_active.return_value = [challenge_1, challenge_2]

        with patch("src.api.routers.workouts.parse_workout_message") as mock_parse_llm:
            response = client.post(
                "/api/v1/workouts/parse",
                json={"text": "50 30"},
                headers=auth_and_user_headers,
            )

        assert response.status_code == 200
        data = response.json()

        assert len(data["entries"]) == 2
        assert data["entries"][0]["exercise_type_name"] == "pushups"
        assert data["entries"][0]["count"] == 50
        assert data["entries"][1]["exercise_type_name"] == "squats"
        assert data["entries"][1]["count"] == 30

        mock_parse_llm.assert_not_called()

