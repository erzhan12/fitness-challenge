"""Tests for /api/v1/challenges endpoints."""

from unittest.mock import patch, Mock

from tests.api.conftest import create_mock_query


class TestListChallenges:
    """Tests for GET /api/v1/challenges."""

    def test_list_challenges_success(self, client, mock_challenge_data):
        """Test successful listing of challenges."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [mock_challenge_data]
            )
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/challenges")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["challenge_name"] == "January Push-up Challenge"
            assert data[0]["target_total"] == 1000

    def test_list_challenges_empty(self, client):
        """Test listing when no challenges exist."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/challenges")

            assert response.status_code == 200
            assert response.json() == []

    def test_list_challenges_filter_exercise_type(self, client, mock_challenge_data):
        """Test filtering by exercise type ID."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_query = create_mock_query([mock_challenge_data])
            mock_sb.table.return_value.select.return_value = mock_query
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/challenges?exercise_type_id=1")

            assert response.status_code == 200
            mock_query.eq.assert_called()

    def test_list_challenges_filter_active(self, client, mock_challenge_data):
        """Test filtering by active status."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_query = create_mock_query([mock_challenge_data])
            mock_sb.table.return_value.select.return_value = mock_query
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/challenges?is_active=true")

            assert response.status_code == 200

    def test_list_challenges_with_computed_fields(self, client, mock_challenge_data):
        """Test that computed fields (total_days, is_current) are included."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [mock_challenge_data]
            )
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/challenges")

            assert response.status_code == 200
            data = response.json()
            assert "total_days" in data[0]
            assert "is_current" in data[0]
            # Jan 1 to Jan 31 = 31 days
            assert data[0]["total_days"] == 31


class TestGetChallenge:
    """Tests for GET /api/v1/challenges/{challenge_id}."""

    def test_get_challenge_success(self, client, mock_challenge_data):
        """Test successful retrieval of single challenge."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [mock_challenge_data]
            )
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/challenges/1")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["challenge_name"] == "January Push-up Challenge"

    def test_get_challenge_not_found(self, client):
        """Test 404 when challenge doesn't exist."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/challenges/999")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()


class TestCreateChallenge:
    """Tests for POST /api/v1/challenges."""

    def test_create_challenge_success(self, client, auth_headers, mock_challenge_data):
        """Test successful creation of challenge."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.insert.return_value = create_mock_query(
                [mock_challenge_data]
            )
            mock_get_sb.return_value = mock_sb

            create_data = {
                "exercise_type_id": 1,
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "target_total": 1000,
                "daily_target": 33,
                "challenge_name": "January Push-up Challenge",
            }

            response = client.post(
                "/api/v1/challenges", json=create_data, headers=auth_headers
            )

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

    def test_update_challenge_success(self, client, auth_headers, mock_challenge_data):
        """Test successful update of challenge."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            # get_challenge call
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [mock_challenge_data]
            )
            # update call
            updated_data = {**mock_challenge_data, "target_total": 1500}
            mock_sb.table.return_value.update.return_value = create_mock_query(
                [updated_data]
            )
            mock_get_sb.return_value = mock_sb

            update_data = {"target_total": 1500}

            response = client.patch(
                "/api/v1/challenges/1", json=update_data, headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["target_total"] == 1500

    def test_update_challenge_not_found(self, client, auth_headers):
        """Test 404 when challenge doesn't exist."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            update_data = {"target_total": 1500}

            response = client.patch(
                "/api/v1/challenges/999", json=update_data, headers=auth_headers
            )

            assert response.status_code == 404

    def test_update_challenge_invalid_date_range(
        self, client, auth_headers, mock_challenge_data
    ):
        """Test 400 when update creates invalid date range."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [mock_challenge_data]
            )
            mock_get_sb.return_value = mock_sb

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

