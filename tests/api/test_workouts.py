"""Tests for /api/v1/workouts endpoints."""

from unittest.mock import patch, Mock

from tests.api.conftest import create_mock_query
from app.models import ParseResult, ExerciseEntry


class TestParseWorkout:
    """Tests for POST /api/v1/workouts/parse."""

    def test_parse_workout_success(
        self, client, auth_headers, mock_exercise_type_data, mock_challenge_data
    ):
        """Test successful parsing of workout message."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()

            def table_side_effect(table_name):
                mock_table = Mock()
                if table_name == "exercise_types":
                    mock_table.select.return_value = create_mock_query(
                        [mock_exercise_type_data]
                    )
                elif table_name == "exercise_challenges":
                    mock_table.select.return_value = create_mock_query(
                        [mock_challenge_data]
                    )
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

            # Mock the parse_workout_message function
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
                    headers=auth_headers,
                )

                assert response.status_code == 200
                data = response.json()
                assert data["is_valid"] is True
                assert len(data["entries"]) == 1
                assert data["entries"][0]["exercise_type_name"] == "pushups"
                assert data["entries"][0]["count"] == 25
                assert data["entries"][0]["confidence"] == 0.95

    def test_parse_workout_multiple_exercises(
        self, client, auth_headers, mock_exercise_type_data, mock_exercise_type_data_2
    ):
        """Test parsing message with multiple exercises."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()

            def table_side_effect(table_name):
                mock_table = Mock()
                if table_name == "exercise_types":
                    mock_table.select.return_value = create_mock_query(
                        [mock_exercise_type_data, mock_exercise_type_data_2]
                    )
                elif table_name == "exercise_challenges":
                    mock_table.select.return_value = create_mock_query([])
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

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
                    headers=auth_headers,
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data["entries"]) == 2

    def test_parse_workout_invalid_message(self, client, auth_headers):
        """Test parsing an invalid/unrecognized workout message."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

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
                    headers=auth_headers,
                )

                assert response.status_code == 200
                data = response.json()
                assert data["is_valid"] is False
                assert data["error_reason"] is not None
                assert data["entries"] == []

    def test_parse_workout_unauthorized(self, client):
        """Test 401 when no API key provided."""
        response = client.post(
            "/api/v1/workouts/parse",
            json={"text": "25 pushups"},
        )

        assert response.status_code == 401

    def test_parse_workout_forbidden(self, client, invalid_auth_headers):
        """Test 403 when invalid API key provided."""
        response = client.post(
            "/api/v1/workouts/parse",
            json={"text": "25 pushups"},
            headers=invalid_auth_headers,
        )

        assert response.status_code == 403

    def test_parse_workout_missing_text(self, client, auth_headers):
        """Test 422 when text field is missing."""
        response = client.post(
            "/api/v1/workouts/parse",
            json={},
            headers=auth_headers,
        )

        assert response.status_code == 422

    def test_parse_workout_empty_text(self, client, auth_headers):
        """Test parsing empty text."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

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
                    headers=auth_headers,
                )

                # Empty string is valid input, parser should handle it
                assert response.status_code == 200

    def test_parse_workout_with_duration(
        self, client, auth_headers, mock_exercise_type_data
    ):
        """Test parsing workout with duration-based exercise."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()

            plank_type = {
                **mock_exercise_type_data,
                "id": 3,
                "name": "plank",
                "display_name": "Plank",
                "unit": "minutes",
            }

            def table_side_effect(table_name):
                mock_table = Mock()
                if table_name == "exercise_types":
                    mock_table.select.return_value = create_mock_query([plank_type])
                elif table_name == "exercise_challenges":
                    mock_table.select.return_value = create_mock_query([])
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

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
                    headers=auth_headers,
                )

                assert response.status_code == 200
                data = response.json()
                assert data["entries"][0]["duration_seconds"] == 120

    def test_parse_workout_response_format(
        self, client, auth_headers, mock_exercise_type_data
    ):
        """Test that response matches expected schema."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()

            def table_side_effect(table_name):
                mock_table = Mock()
                if table_name == "exercise_types":
                    mock_table.select.return_value = create_mock_query(
                        [mock_exercise_type_data]
                    )
                elif table_name == "exercise_challenges":
                    mock_table.select.return_value = create_mock_query([])
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

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
                    headers=auth_headers,
                )

                assert response.status_code == 200
                data = response.json()

                # Verify top-level structure
                assert "entries" in data
                assert "is_valid" in data
                assert "error_reason" in data

                # Verify entry structure
                entry = data["entries"][0]
                assert "exercise_type_name" in entry
                assert "count" in entry
                assert "duration_seconds" in entry
                assert "notes" in entry
                assert "confidence" in entry

