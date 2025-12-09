"""Tests for API security and authentication."""

from unittest.mock import patch, Mock

from tests.api.conftest import create_mock_query


class TestAuthenticationRequired:
    """Tests for endpoints that require authentication."""

    # ==========================================================================
    # POST endpoints (all require auth)
    # ==========================================================================

    def test_create_exercise_requires_auth(self, client):
        """POST /exercises requires authentication."""
        response = client.post(
            "/api/v1/exercises",
            json={"name": "test", "display_name": "Test", "emoji": "🏋️"},
        )
        assert response.status_code == 401
        assert "Missing" in response.json()["detail"]

    def test_create_challenge_requires_auth(self, client):
        """POST /challenges requires authentication."""
        response = client.post(
            "/api/v1/challenges",
            json={
                "exercise_type_id": 1,
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "target_total": 1000,
                "challenge_name": "Test",
            },
        )
        assert response.status_code == 401

    def test_create_log_requires_auth(self, client):
        """POST /logs requires authentication."""
        response = client.post(
            "/api/v1/logs",
            json={"exercise_type_id": 1, "count": 25},
        )
        assert response.status_code == 401

    def test_parse_workout_requires_auth(self, client):
        """POST /workouts/parse requires authentication."""
        response = client.post(
            "/api/v1/workouts/parse",
            json={"text": "25 pushups"},
        )
        assert response.status_code == 401

    # ==========================================================================
    # PATCH endpoints (all require auth)
    # ==========================================================================

    def test_update_exercise_requires_auth(self, client):
        """PATCH /exercises/{id} requires authentication."""
        response = client.patch(
            "/api/v1/exercises/1",
            json={"display_name": "Updated"},
        )
        assert response.status_code == 401

    def test_update_challenge_requires_auth(self, client):
        """PATCH /challenges/{id} requires authentication."""
        response = client.patch(
            "/api/v1/challenges/1",
            json={"target_total": 1500},
        )
        assert response.status_code == 401

    # ==========================================================================
    # DELETE endpoints (all require auth)
    # ==========================================================================

    def test_delete_log_requires_auth(self, client):
        """DELETE /logs/{id} requires authentication."""
        response = client.delete("/api/v1/logs/123")
        assert response.status_code == 401


class TestInvalidAuthentication:
    """Tests for invalid API key scenarios."""

    def test_invalid_bearer_token(self, client):
        """Test with invalid Bearer token."""
        response = client.post(
            "/api/v1/exercises",
            json={"name": "test", "display_name": "Test", "emoji": "🏋️"},
            headers={"Authorization": "Bearer invalid-token-12345"},
        )
        assert response.status_code == 403
        assert "Invalid" in response.json()["detail"]

    def test_invalid_raw_token(self, client):
        """Test with invalid raw token (no Bearer prefix)."""
        response = client.post(
            "/api/v1/exercises",
            json={"name": "test", "display_name": "Test", "emoji": "🏋️"},
            headers={"Authorization": "invalid-token-12345"},
        )
        assert response.status_code == 403

    def test_empty_authorization_header(self, client):
        """Test with empty Authorization header."""
        response = client.post(
            "/api/v1/exercises",
            json={"name": "test", "display_name": "Test", "emoji": "🏋️"},
            headers={"Authorization": ""},
        )
        assert response.status_code == 401

    def test_whitespace_only_token(self, client):
        """Test with whitespace-only token."""
        response = client.post(
            "/api/v1/exercises",
            json={"name": "test", "display_name": "Test", "emoji": "🏋️"},
            headers={"Authorization": "Bearer    "},
        )
        assert response.status_code == 403


class TestValidAuthentication:
    """Tests for valid API key scenarios."""

    def test_bearer_token_format(self, client, api_key, mock_exercise_type_data):
        """Test with valid Bearer token format."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.insert.return_value = create_mock_query(
                [mock_exercise_type_data]
            )
            mock_get_sb.return_value = mock_sb

            response = client.post(
                "/api/v1/exercises",
                json={
                    "name": "test",
                    "display_name": "Test",
                    "emoji": "🏋️",
                    "unit": "reps",
                },
                headers={"Authorization": f"Bearer {api_key}"},
            )
            assert response.status_code == 201

    def test_raw_token_format(self, client, api_key, mock_exercise_type_data):
        """Test with raw token format (no Bearer prefix)."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.insert.return_value = create_mock_query(
                [mock_exercise_type_data]
            )
            mock_get_sb.return_value = mock_sb

            response = client.post(
                "/api/v1/exercises",
                json={
                    "name": "test",
                    "display_name": "Test",
                    "emoji": "🏋️",
                    "unit": "reps",
                },
                headers={"Authorization": api_key},
            )
            assert response.status_code == 201


class TestPublicEndpoints:
    """Tests for endpoints that don't require authentication."""

    def test_list_exercises_public(self, client):
        """GET /exercises is publicly accessible."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/exercises")
            assert response.status_code == 200

    def test_get_exercise_public(self, client, mock_exercise_type_data):
        """GET /exercises/{id} is publicly accessible."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [mock_exercise_type_data]
            )
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/exercises/1")
            assert response.status_code == 200

    def test_list_challenges_public(self, client):
        """GET /challenges is publicly accessible."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/challenges")
            assert response.status_code == 200

    def test_get_challenge_public(self, client, mock_challenge_data):
        """GET /challenges/{id} is publicly accessible."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [mock_challenge_data]
            )
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/challenges/1")
            assert response.status_code == 200

    def test_list_logs_public(self, client):
        """GET /logs is publicly accessible."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query(
                [], count=0
            )
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/logs")
            assert response.status_code == 200

    def test_get_log_public(self, client, mock_log_data, mock_exercise_type_data):
        """GET /logs/{id} is publicly accessible."""
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

    def test_stats_exercises_public(self, client):
        """GET /stats/exercises is publicly accessible."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/stats/exercises")
            assert response.status_code == 200

    def test_stats_summary_public(self, client):
        """GET /stats/summary is publicly accessible."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/stats/summary")
            assert response.status_code == 200

    def test_health_check_public(self, client):
        """GET / (health check) is publicly accessible."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestAdminJobsAuth:
    """Tests for admin jobs endpoint authentication."""

    def test_daily_reminder_requires_auth(self, client):
        """POST /jobs/daily-reminder requires authentication."""
        response = client.post("/jobs/daily-reminder")
        assert response.status_code == 403

    def test_daily_reminder_invalid_key(self, client):
        """POST /jobs/daily-reminder rejects invalid key."""
        response = client.post(
            "/jobs/daily-reminder",
            headers={"Authorization": "Bearer invalid-key"},
        )
        assert response.status_code == 403

