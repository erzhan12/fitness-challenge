"""Tests for /api/v1/challenges endpoints."""

from tests.api.conftest import make_challenge_model


class TestListChallenges:
    """Tests for GET /api/v1/challenges."""

    def test_list_challenges_success(self, client, mock_repos, challenge_model):
        """Test successful listing of challenges."""
        mock_repos["challenge"].get_all.return_value = [challenge_model]

        response = client.get("/api/v1/challenges")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["challenge_name"] == "January Push-up Challenge"
        assert data[0]["target_total"] == 1000

    def test_list_challenges_empty(self, client, mock_repos):
        """Test listing when no challenges exist."""
        mock_repos["challenge"].get_all.return_value = []

        response = client.get("/api/v1/challenges")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_challenges_filter_exercise_type(
        self, client, mock_repos, challenge_model
    ):
        """Test filtering by exercise type ID."""
        mock_repos["challenge"].get_all.return_value = [challenge_model]

        response = client.get("/api/v1/challenges?exercise_type_id=1")

        assert response.status_code == 200
        mock_repos["challenge"].get_all.assert_awaited_once_with(
            filters={"exercise_type_id": 1}
        )

    def test_list_challenges_filter_active(self, client, mock_repos, challenge_model):
        """Test filtering by active status."""
        mock_repos["challenge"].get_all.return_value = [challenge_model]

        response = client.get("/api/v1/challenges?is_active=true")

        assert response.status_code == 200
        mock_repos["challenge"].get_all.assert_awaited_once_with(filters={"is_active": True})

    def test_list_challenges_with_computed_fields(
        self, client, mock_repos, challenge_model
    ):
        """Test that computed fields (total_days, is_current) are included."""
        mock_repos["challenge"].get_all.return_value = [
            make_challenge_model(
                {
                    "id": 1,
                    "exercise_type_id": 1,
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                    "target_total": 1000,
                    "daily_target": 33,
                    "challenge_name": "January Push-up Challenge",
                    "is_active": True,
                }
            )
        ]

        response = client.get("/api/v1/challenges")

        assert response.status_code == 200
        data = response.json()
        assert "total_days" in data[0]
        assert "is_current" in data[0]
        # Jan 1 to Jan 31 = 31 days
        assert data[0]["total_days"] == 31


class TestGetChallenge:
    """Tests for GET /api/v1/challenges/{challenge_id}."""

    def test_get_challenge_success(self, client, mock_repos, challenge_model):
        """Test successful retrieval of single challenge."""
        mock_repos["challenge"].get_by_id.return_value = challenge_model

        response = client.get("/api/v1/challenges/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["challenge_name"] == "January Push-up Challenge"

    def test_get_challenge_not_found(self, client, mock_repos):
        """Test 404 when challenge doesn't exist."""
        mock_repos["challenge"].get_by_id.return_value = None

        response = client.get("/api/v1/challenges/999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestCreateChallenge:
    """Tests for POST /api/v1/challenges."""

    def test_create_challenge_success(
        self, client, auth_headers, mock_repos, mock_challenge_data
    ):
        """Test successful creation of challenge."""
        mock_repos["challenge"].create.return_value = make_challenge_model(mock_challenge_data)

        create_data = {
            "exercise_type_id": 1,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "target_total": 1000,
            "daily_target": 33,
            "challenge_name": "January Push-up Challenge",
        }

        response = client.post("/api/v1/challenges", json=create_data, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["challenge_name"] == "January Push-up Challenge"

    def test_create_challenge_unauthorized(self, client):
        """Test 401 when no API key provided."""
        create_data = {
            "exercise_type_id": 1,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "target_total": 1000,
            "challenge_name": "Test Challenge",
        }

        response = client.post("/api/v1/challenges", json=create_data)

        assert response.status_code == 401

    def test_create_challenge_forbidden(self, client, invalid_auth_headers):
        """Test 403 when invalid API key provided."""
        create_data = {
            "exercise_type_id": 1,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "target_total": 1000,
            "challenge_name": "Test Challenge",
        }

        response = client.post(
            "/api/v1/challenges", json=create_data, headers=invalid_auth_headers
        )

        assert response.status_code == 403

    def test_create_challenge_invalid_date_range(self, client, auth_headers):
        """Test 400 when end_date is before start_date."""
        create_data = {
            "exercise_type_id": 1,
            "start_date": "2024-01-31",
            "end_date": "2024-01-01",  # Before start
            "target_total": 1000,
            "challenge_name": "Invalid Challenge",
        }

        response = client.post(
            "/api/v1/challenges", json=create_data, headers=auth_headers
        )

        assert response.status_code == 400
        assert "end_date" in response.json()["detail"].lower()

    def test_create_challenge_invalid_data(self, client, auth_headers):
        """Test 422 when request body is invalid."""
        create_data = {"exercise_type_id": 1}  # Missing required fields

        response = client.post(
            "/api/v1/challenges", json=create_data, headers=auth_headers
        )

        assert response.status_code == 422

    def test_create_challenge_negative_target(self, client, auth_headers):
        """Test 422 when target_total is negative."""
        create_data = {
            "exercise_type_id": 1,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "target_total": -100,  # Invalid
            "challenge_name": "Invalid Challenge",
        }

        response = client.post(
            "/api/v1/challenges", json=create_data, headers=auth_headers
        )

        assert response.status_code == 422


class TestUpdateChallenge:
    """Tests for PATCH /api/v1/challenges/{challenge_id}."""

    def test_update_challenge_success(
        self, client, auth_headers, mock_repos, mock_challenge_data
    ):
        """Test successful update of challenge."""
        mock_repos["challenge"].get_by_id.return_value = make_challenge_model(mock_challenge_data)
        updated_data = {**mock_challenge_data, "target_total": 1500}
        mock_repos["challenge"].update.return_value = make_challenge_model(updated_data)

        update_data = {"target_total": 1500}

        response = client.patch("/api/v1/challenges/1", json=update_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["target_total"] == 1500

    def test_update_challenge_not_found(self, client, auth_headers, mock_repos):
        """Test 404 when challenge doesn't exist."""
        mock_repos["challenge"].get_by_id.return_value = None

        update_data = {"target_total": 1500}

        response = client.patch("/api/v1/challenges/999", json=update_data, headers=auth_headers)

        assert response.status_code == 404

    def test_update_challenge_invalid_date_range(
        self, client, auth_headers, mock_repos, mock_challenge_data
    ):
        """Test 400 when update creates invalid date range."""
        mock_repos["challenge"].get_by_id.return_value = make_challenge_model(mock_challenge_data)

        update_data = {"end_date": "2023-12-01"}  # Before existing start_date

        response = client.patch(
            "/api/v1/challenges/1", json=update_data, headers=auth_headers
        )

        assert response.status_code == 400

    def test_update_challenge_unauthorized(self, client):
        """Test 401 when no API key provided."""
        update_data = {"target_total": 1500}

        response = client.patch("/api/v1/challenges/1", json=update_data)

        assert response.status_code == 401
