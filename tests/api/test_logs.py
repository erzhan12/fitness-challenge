"""Tests for /api/v1/logs endpoints."""

from unittest.mock import patch, Mock

from tests.api.conftest import create_mock_query


class TestListLogs:
    """Tests for GET /api/v1/logs."""

    def test_list_logs_success(self, client, mock_log_data, mock_exercise_type_data):
        """Test successful listing of logs."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            log_with_type = {
                **mock_log_data,
                "exercise_types": mock_exercise_type_data,
            }
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [log_with_type], count=1
            )
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/logs")

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert "pagination" in data
            assert len(data["data"]) == 1
            assert data["data"][0]["count"] == 25

    def test_list_logs_empty(self, client):
        """Test listing when no logs exist."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [], count=0
            )
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/logs")

            assert response.status_code == 200
            data = response.json()
            assert data["data"] == []
            assert data["pagination"]["total"] == 0

    def test_list_logs_filter_exercise_type(self, client, mock_log_data):
        """Test filtering by exercise type ID."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_query = create_mock_query([mock_log_data], count=1)
            mock_sb.table.return_value.select.return_value = mock_query
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/logs?exercise_type_id=1")

            assert response.status_code == 200
            mock_query.eq.assert_called()

    def test_list_logs_filter_challenge(self, client, mock_log_data):
        """Test filtering by challenge ID."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_query = create_mock_query([mock_log_data], count=1)
            mock_sb.table.return_value.select.return_value = mock_query
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/logs?challenge_id=1")

            assert response.status_code == 200

    def test_list_logs_filter_date_range(self, client, mock_log_data):
        """Test filtering by date range."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_query = create_mock_query([mock_log_data], count=1)
            mock_sb.table.return_value.select.return_value = mock_query
            mock_get_sb.return_value = mock_sb

            response = client.get(
                "/api/v1/logs?date_from=2024-01-01&date_to=2024-01-31"
            )

            assert response.status_code == 200

    def test_list_logs_pagination(self, client, mock_log_data):
        """Test pagination parameters."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_query = create_mock_query([mock_log_data], count=100)
            mock_sb.table.return_value.select.return_value = mock_query
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/logs?limit=10&offset=20")

            assert response.status_code == 200
            data = response.json()
            assert data["pagination"]["limit"] == 10
            assert data["pagination"]["offset"] == 20

    def test_list_logs_includes_exercise_type(
        self, client, mock_log_data, mock_exercise_type_data
    ):
        """Test that exercise type details are included in response."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            log_with_type = {
                **mock_log_data,
                "exercise_types": mock_exercise_type_data,
            }
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [log_with_type], count=1
            )
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/logs")

            assert response.status_code == 200
            data = response.json()
            assert data["data"][0]["exercise_type"] is not None
            assert data["data"][0]["exercise_type"]["name"] == "pushups"


class TestGetLog:
    """Tests for GET /api/v1/logs/{log_id}."""

    def test_get_log_success(self, client, mock_log_data, mock_exercise_type_data):
        """Test successful retrieval of single log."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            log_with_type = {
                **mock_log_data,
                "exercise_types": mock_exercise_type_data,
            }
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [log_with_type]
            )
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/logs/123")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 123
            assert data["count"] == 25

    def test_get_log_not_found(self, client):
        """Test 404 when log doesn't exist."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/logs/999")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()


class TestCreateLog:
    """Tests for POST /api/v1/logs."""

    def test_create_log_success(
        self,
        client,
        auth_headers,
        mock_log_data,
        mock_exercise_type_data,
        mock_challenge_data,
    ):
        """Test successful creation of log entry."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()

            # Track table calls
            call_count = [0]

            def table_side_effect(table_name):
                call_count[0] += 1
                mock_table = Mock()

                if table_name == "exercise_types":
                    mock_table.select.return_value = create_mock_query(
                        [mock_exercise_type_data]
                    )
                elif table_name == "exercise_challenges":
                    mock_table.select.return_value = create_mock_query(
                        [mock_challenge_data]
                    )
                elif table_name == "exercise_logs":
                    mock_table.select.return_value = create_mock_query([mock_log_data])
                    mock_table.insert.return_value = create_mock_query([mock_log_data])
                elif table_name == "user_stats":
                    mock_table.select.return_value = create_mock_query([])
                    mock_table.insert.return_value = create_mock_query([])

                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

            create_data = {
                "exercise_type_id": 1,
                "count": 25,
                "notes": "Morning workout",
            }

            response = client.post(
                "/api/v1/logs", json=create_data, headers=auth_headers
            )

            assert response.status_code == 201
            data = response.json()
            assert "log" in data
            assert "stats" in data
            assert data["log"]["count"] == 25

    def test_create_log_unauthorized(self, client):
        """Test 401 when no API key provided."""
        create_data = {
            "exercise_type_id": 1,
            "count": 25,
        }

        response = client.post("/api/v1/logs", json=create_data)

        assert response.status_code == 401

    def test_create_log_forbidden(self, client, invalid_auth_headers):
        """Test 403 when invalid API key provided."""
        create_data = {
            "exercise_type_id": 1,
            "count": 25,
        }

        response = client.post(
            "/api/v1/logs", json=create_data, headers=invalid_auth_headers
        )

        assert response.status_code == 403

    def test_create_log_exercise_not_found(self, client, auth_headers):
        """Test 404 when exercise type doesn't exist."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            create_data = {
                "exercise_type_id": 999,
                "count": 25,
            }

            response = client.post(
                "/api/v1/logs", json=create_data, headers=auth_headers
            )

            assert response.status_code == 404

    def test_create_log_invalid_count(self, client, auth_headers):
        """Test 422 when count is invalid (zero or negative)."""
        create_data = {
            "exercise_type_id": 1,
            "count": 0,  # Invalid - must be >= 1
        }

        response = client.post(
            "/api/v1/logs", json=create_data, headers=auth_headers
        )

        assert response.status_code == 422

    def test_create_log_with_date(
        self,
        client,
        auth_headers,
        mock_log_data,
        mock_exercise_type_data,
        mock_challenge_data,
    ):
        """Test creating log with explicit date."""
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
                elif table_name == "exercise_logs":
                    mock_table.select.return_value = create_mock_query([mock_log_data])
                    mock_table.insert.return_value = create_mock_query([mock_log_data])
                elif table_name == "user_stats":
                    mock_table.select.return_value = create_mock_query([])
                    mock_table.insert.return_value = create_mock_query([])
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

            create_data = {
                "exercise_type_id": 1,
                "count": 25,
                "date": "2024-01-10",
            }

            response = client.post(
                "/api/v1/logs", json=create_data, headers=auth_headers
            )

            assert response.status_code == 201


class TestDeleteLog:
    """Tests for DELETE /api/v1/logs/{log_id}."""

    def test_delete_log_success(
        self,
        client,
        auth_headers,
        mock_log_data,
        mock_exercise_type_data,
        mock_user_stats_data,
    ):
        """Test successful deletion of log entry."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()

            def table_side_effect(table_name):
                mock_table = Mock()
                if table_name == "exercise_logs":
                    log_with_type = {
                        **mock_log_data,
                        "exercise_types": mock_exercise_type_data,
                    }
                    mock_table.select.return_value = create_mock_query([log_with_type])
                    mock_table.delete.return_value = create_mock_query([mock_log_data])
                elif table_name == "exercise_types":
                    mock_table.select.return_value = create_mock_query(
                        [mock_exercise_type_data]
                    )
                elif table_name == "exercise_challenges":
                    mock_table.select.return_value = create_mock_query([])
                elif table_name == "user_stats":
                    mock_table.select.return_value = create_mock_query(
                        [mock_user_stats_data]
                    )
                    mock_table.update.return_value = create_mock_query([])
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

            response = client.delete("/api/v1/logs/123", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert "log" in data
            assert "stats" in data

    def test_delete_log_not_found(self, client, auth_headers):
        """Test 404 when log doesn't exist."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            response = client.delete("/api/v1/logs/999", headers=auth_headers)

            assert response.status_code == 404

    def test_delete_log_unauthorized(self, client):
        """Test 401 when no API key provided."""
        response = client.delete("/api/v1/logs/123")

        assert response.status_code == 401

    def test_delete_log_forbidden(self, client, invalid_auth_headers):
        """Test 403 when invalid API key provided."""
        response = client.delete("/api/v1/logs/123", headers=invalid_auth_headers)

        assert response.status_code == 403

