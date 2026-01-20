"""Tests for /api/v1/exercises endpoints."""

from tests.api.conftest import make_exercise_type_model


class TestListExercises:
    """Tests for GET /api/v1/exercises."""

    def test_list_exercises_success(self, client, mock_repos, exercise_type_model, user_context_headers):
        """Test successful listing of exercise types."""
        mock_repos["exercise_type"].get_all.return_value = [exercise_type_model]

        response = client.get("/api/v1/exercises", headers=user_context_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "pushups"
        assert data[0]["display_name"] == "Push-ups"
        assert data[0]["emoji"] == "💪"
        mock_repos["exercise_type"].get_all.assert_awaited_once_with(is_active=True, user_id=1)

    def test_list_exercises_empty(self, client, mock_repos, user_context_headers):
        """Test listing when no exercise types exist."""
        mock_repos["exercise_type"].get_all.return_value = []

        response = client.get("/api/v1/exercises", headers=user_context_headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_list_exercises_filter_active(self, client, mock_repos, exercise_type_model, user_context_headers):
        """Test filtering by active status."""
        mock_repos["exercise_type"].get_all.return_value = [exercise_type_model]

        response = client.get("/api/v1/exercises?is_active=true", headers=user_context_headers)

        assert response.status_code == 200
        mock_repos["exercise_type"].get_all.assert_awaited_once_with(is_active=True, user_id=1)

    def test_list_exercises_challenge_only(
        self, client, mock_repos, exercise_type_model, challenge_model, user_context_headers
    ):
        """Test filtering to only exercise types with active challenges."""
        mock_repos["exercise_type"].get_all.return_value = [exercise_type_model]
        mock_repos["challenge"].get_all.return_value = [challenge_model]

        response = client.get("/api/v1/exercises?challenge_only=true", headers=user_context_headers)

        assert response.status_code == 200
        assert len(response.json()) == 1
        mock_repos["challenge"].get_all.assert_awaited_once_with(filters={"is_active": True}, user_id=1)


class TestGetExercise:
    """Tests for GET /api/v1/exercises/{exercise_type_id}."""

    def test_get_exercise_success(self, client, mock_repos, exercise_type_model, user_context_headers):
        """Test successful retrieval of single exercise type."""
        mock_repos["exercise_type"].get_by_id.return_value = exercise_type_model

        response = client.get("/api/v1/exercises/1", headers=user_context_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "pushups"

    def test_get_exercise_not_found(self, client, mock_repos, user_context_headers):
        """Test 404 when exercise type doesn't exist."""
        mock_repos["exercise_type"].get_by_id.return_value = None

        response = client.get("/api/v1/exercises/999", headers=user_context_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestCreateExercise:
    """Tests for POST /api/v1/exercises."""

    def test_create_exercise_success(
        self, client, auth_and_user_headers, mock_repos, mock_exercise_type_data
    ):
        """Test successful creation of exercise type."""
        mock_repos["exercise_type"].create.return_value = make_exercise_type_model(
            mock_exercise_type_data
        )

        create_data = {
            "name": "pushups",
            "display_name": "Push-ups",
            "emoji": "💪",
            "unit": "reps",
            "aliases": ["push-up"],
        }

        response = client.post("/api/v1/exercises", json=create_data, headers=auth_and_user_headers)

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

    def test_create_exercise_forbidden(self, client, invalid_auth_headers, user_context_headers):
        """Test 403 when invalid API key provided."""
        create_data = {
            "name": "pushups",
            "display_name": "Push-ups",
            "emoji": "💪",
        }

        response = client.post(
            "/api/v1/exercises", json=create_data, headers={**invalid_auth_headers, **user_context_headers}
        )

        assert response.status_code == 403

    def test_create_exercise_invalid_data(self, client, auth_and_user_headers, mock_repos):
        """Test 422 when request body is invalid."""
        create_data = {"name": "pushups"}  # Missing required fields

        response = client.post(
            "/api/v1/exercises", json=create_data, headers=auth_and_user_headers
        )

        assert response.status_code == 422


class TestUpdateExercise:
    """Tests for PATCH /api/v1/exercises/{exercise_type_id}."""

    def test_update_exercise_success(
        self, client, auth_and_user_headers, mock_repos, mock_exercise_type_data
    ):
        """Test successful update of exercise type."""
        updated_data = {**mock_exercise_type_data, "display_name": "Updated Name"}
        mock_repos["exercise_type"].update.return_value = make_exercise_type_model(updated_data)

        update_data = {"display_name": "Updated Name"}

        response = client.patch("/api/v1/exercises/1", json=update_data, headers=auth_and_user_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Name"

    def test_update_exercise_not_found(self, client, auth_and_user_headers, mock_repos):
        """Test 404 when exercise type doesn't exist."""
        mock_repos["exercise_type"].update.return_value = None

        update_data = {"display_name": "Updated Name"}

        response = client.patch("/api/v1/exercises/999", json=update_data, headers=auth_and_user_headers)

        assert response.status_code == 404

    def test_update_exercise_unauthorized(self, client):
        """Test 401 when no API key provided."""
        update_data = {"display_name": "Updated Name"}

        response = client.patch("/api/v1/exercises/1", json=update_data)

        assert response.status_code == 401

    def test_update_exercise_partial(
        self, client, auth_and_user_headers, mock_repos, mock_exercise_type_data
    ):
        """Test partial update with only some fields."""
        updated = {**mock_exercise_type_data, "emoji": "🏋️"}
        mock_repos["exercise_type"].update.return_value = make_exercise_type_model(updated)

        update_data = {"emoji": "🏋️"}

        response = client.patch("/api/v1/exercises/1", json=update_data, headers=auth_and_user_headers)

        assert response.status_code == 200
