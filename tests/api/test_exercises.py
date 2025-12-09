"""Tests for /api/v1/exercises endpoints."""

from unittest.mock import patch, Mock

from tests.api.conftest import create_mock_query


class TestListExercises:
    """Tests for GET /api/v1/exercises."""

    def test_list_exercises_success(self, client, mock_exercise_type_data):
        """Test successful listing of exercise types."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [mock_exercise_type_data]
            )
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/exercises")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "pushups"
            assert data[0]["display_name"] == "Push-ups"
            assert data[0]["emoji"] == "💪"

    def test_list_exercises_empty(self, client):
        """Test listing when no exercise types exist."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/exercises")

            assert response.status_code == 200
            assert response.json() == []

    def test_list_exercises_filter_active(self, client, mock_exercise_type_data):
        """Test filtering by active status."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_query = create_mock_query([mock_exercise_type_data])
            mock_sb.table.return_value.select.return_value = mock_query
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/exercises?is_active=true")

            assert response.status_code == 200
            mock_query.eq.assert_called()

    def test_list_exercises_challenge_only(
        self, client, mock_exercise_type_data, mock_challenge_data
    ):
        """Test filtering to only exercise types with active challenges."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()

            # First call returns exercise types
            exercise_query = create_mock_query([mock_exercise_type_data])
            # Second call returns challenges
            challenge_query = create_mock_query([mock_challenge_data])

            call_count = [0]

            def table_side_effect(table_name):
                mock_table = Mock()
                call_count[0] += 1
                if table_name == "exercise_types":
                    mock_table.select.return_value = exercise_query
                elif table_name == "exercise_challenges":
                    mock_table.select.return_value = challenge_query
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/exercises?challenge_only=true")

            assert response.status_code == 200


class TestGetExercise:
    """Tests for GET /api/v1/exercises/{exercise_type_id}."""

    def test_get_exercise_success(self, client, mock_exercise_type_data):
        """Test successful retrieval of single exercise type."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [mock_exercise_type_data]
            )
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/exercises/1")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["name"] == "pushups"

    def test_get_exercise_not_found(self, client):
        """Test 404 when exercise type doesn't exist."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/exercises/999")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()


class TestCreateExercise:
    """Tests for POST /api/v1/exercises."""

    def test_create_exercise_success(
        self, client, auth_headers, mock_exercise_type_data
    ):
        """Test successful creation of exercise type."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.insert.return_value = create_mock_query(
                [mock_exercise_type_data]
            )
            mock_get_sb.return_value = mock_sb

            create_data = {
                "name": "pushups",
                "display_name": "Push-ups",
                "emoji": "💪",
                "unit": "reps",
                "aliases": ["push-up"],
            }

            response = client.post(
                "/api/v1/exercises", json=create_data, headers=auth_headers
            )

            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "pushups"

    def test_create_exercise_unauthorized(self, client):
        """Test 401 when no API key provided."""
        create_data = {
            "name": "pushups",
            "display_name": "Push-ups",
            "emoji": "💪",
        }

        response = client.post("/api/v1/exercises", json=create_data)

        assert response.status_code == 401

    def test_create_exercise_forbidden(self, client, invalid_auth_headers):
        """Test 403 when invalid API key provided."""
        create_data = {
            "name": "pushups",
            "display_name": "Push-ups",
            "emoji": "💪",
        }

        response = client.post(
            "/api/v1/exercises", json=create_data, headers=invalid_auth_headers
        )

        assert response.status_code == 403

    def test_create_exercise_invalid_data(self, client, auth_headers):
        """Test 422 when request body is invalid."""
        create_data = {"name": "pushups"}  # Missing required fields

        response = client.post(
            "/api/v1/exercises", json=create_data, headers=auth_headers
        )

        assert response.status_code == 422


class TestUpdateExercise:
    """Tests for PATCH /api/v1/exercises/{exercise_type_id}."""

    def test_update_exercise_success(
        self, client, auth_headers, mock_exercise_type_data
    ):
        """Test successful update of exercise type."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            updated_data = {**mock_exercise_type_data, "display_name": "Updated Name"}
            mock_sb.table.return_value.update.return_value = create_mock_query(
                [updated_data]
            )
            mock_get_sb.return_value = mock_sb

            update_data = {"display_name": "Updated Name"}

            response = client.patch(
                "/api/v1/exercises/1", json=update_data, headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["display_name"] == "Updated Name"

    def test_update_exercise_not_found(self, client, auth_headers):
        """Test 404 when exercise type doesn't exist."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.update.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            update_data = {"display_name": "Updated Name"}

            response = client.patch(
                "/api/v1/exercises/999", json=update_data, headers=auth_headers
            )

            assert response.status_code == 404

    def test_update_exercise_unauthorized(self, client):
        """Test 401 when no API key provided."""
        update_data = {"display_name": "Updated Name"}

        response = client.patch("/api/v1/exercises/1", json=update_data)

        assert response.status_code == 401

    def test_update_exercise_partial(self, client, auth_headers, mock_exercise_type_data):
        """Test partial update with only some fields."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            # When no update data, it should return existing record
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [mock_exercise_type_data]
            )
            mock_sb.table.return_value.update.return_value = create_mock_query(
                [mock_exercise_type_data]
            )
            mock_get_sb.return_value = mock_sb

            update_data = {"emoji": "🏋️"}

            response = client.patch(
                "/api/v1/exercises/1", json=update_data, headers=auth_headers
            )

            assert response.status_code == 200

