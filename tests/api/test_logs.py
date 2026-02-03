"""Tests for /api/v1/logs endpoints."""

from datetime import date
from unittest.mock import AsyncMock, patch

from src.api.models import ExerciseStatsOut


class TestListLogs:
    """Tests for GET /api/v1/logs."""

    def test_list_logs_success(self, client, mock_repos, log_model, user_context_headers):
        """Test successful listing of logs."""
        mock_repos["log"].get_all.return_value = ([log_model], 1)

        response = client.get("/api/v1/logs", headers=user_context_headers)

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["count"] == 25

    def test_list_logs_empty(self, client, mock_repos, user_context_headers):
        """Test listing when no logs exist."""
        mock_repos["log"].get_all.return_value = ([], 0)

        response = client.get("/api/v1/logs", headers=user_context_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["pagination"]["total"] == 0

    def test_list_logs_filter_exercise_type(self, client, mock_repos, user_context_headers):
        """Test filtering by exercise type ID."""
        mock_repos["log"].get_all.return_value = ([], 0)

        response = client.get("/api/v1/logs?exercise_type_id=1", headers=user_context_headers)

        assert response.status_code == 200
        mock_repos["log"].get_all.assert_awaited_once_with(
            filters={"exercise_type_id": 1}, limit=50, offset=0, user_id=1
        )

    def test_list_logs_filter_challenge(self, client, mock_repos, user_context_headers):
        """Test filtering by challenge ID."""
        mock_repos["log"].get_all.return_value = ([], 0)

        response = client.get("/api/v1/logs?challenge_id=1", headers=user_context_headers)

        assert response.status_code == 200
        mock_repos["log"].get_all.assert_awaited_once_with(
            filters={"challenge_id": 1}, limit=50, offset=0, user_id=1
        )

    def test_list_logs_filter_date_range(self, client, mock_repos, user_context_headers):
        """Test filtering by date range."""
        mock_repos["log"].get_all.return_value = ([], 0)

        response = client.get("/api/v1/logs?date_from=2024-01-01&date_to=2024-01-31", headers=user_context_headers)

        assert response.status_code == 200
        mock_repos["log"].get_all.assert_awaited_once_with(
            filters={
                "date_from": date(2024, 1, 1),
                "date_to": date(2024, 1, 31),
            },
            limit=50,
            offset=0,
            user_id=1,
        )

    def test_list_logs_pagination(self, client, mock_repos, user_context_headers):
        """Test pagination parameters."""
        mock_repos["log"].get_all.return_value = ([], 100)

        response = client.get("/api/v1/logs?limit=10&offset=20", headers=user_context_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["limit"] == 10
        assert data["pagination"]["offset"] == 20

    def test_list_logs_includes_exercise_type(
        self, client, mock_repos, log_model, user_context_headers
    ):
        """Test that exercise type details are included in response."""
        mock_repos["log"].get_all.return_value = ([log_model], 1)

        response = client.get("/api/v1/logs", headers=user_context_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["data"][0]["exercise_type"] is not None
        assert data["data"][0]["exercise_type"]["name"] == "pushups"


class TestGetLog:
    """Tests for GET /api/v1/logs/{log_id}."""

    def test_get_log_success(self, client, mock_repos, log_model, user_context_headers):
        """Test successful retrieval of single log."""
        mock_repos["log"].get_by_id.return_value = log_model

        response = client.get("/api/v1/logs/123", headers=user_context_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 123
        assert data["count"] == 25

    def test_get_log_not_found(self, client, mock_repos, user_context_headers):
        """Test 404 when log doesn't exist."""
        mock_repos["log"].get_by_id.return_value = None

        response = client.get("/api/v1/logs/999", headers=user_context_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestCreateLog:
    """Tests for POST /api/v1/logs."""

    def test_create_log_success(
        self,
        client,
        auth_and_user_headers,
        mock_repos,
        log_model,
        exercise_type_model,
        challenge_model,
    ):
        """Test successful creation of log entry."""
        mock_repos["exercise_type"].get_by_id.return_value = exercise_type_model
        mock_repos["challenge"].get_active_for_type.return_value = challenge_model
        mock_repos["log"].create.return_value = log_model

        stats_out = ExerciseStatsOut(
            exercise_type_id=1,
            exercise_type_name="Push-ups",
            exercise_type_emoji="💪",
            challenge_id=1,
            challenge_name="January Push-up Challenge",
            day_number=15,
            total_days=31,
            target_total=1000,
            daily_target=33,
            today_total=25,
            cumulative_total=275,
            progress_percent=27.5,
            status="on_track",
            catch_up_reps=0,
        )

        with patch(
            "src.api.services.compute_exercise_stats",
            new=AsyncMock(return_value=stats_out),
        ):
            create_data = {
                "exercise_type_id": 1,
                "count": 25,
                "notes": "Morning workout",
            }

            response = client.post("/api/v1/logs", json=create_data, headers=auth_and_user_headers)

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

    def test_create_log_forbidden(self, client, invalid_auth_headers, user_context_headers):
        """Test 403 when invalid API key provided."""
        create_data = {
            "exercise_type_id": 1,
            "count": 25,
        }

        response = client.post(
            "/api/v1/logs", json=create_data, headers={**invalid_auth_headers, **user_context_headers}
        )

        assert response.status_code == 403

    def test_create_log_exercise_not_found(self, client, auth_and_user_headers, mock_repos):
        """Test 404 when exercise type doesn't exist."""
        mock_repos["exercise_type"].get_by_id.return_value = None

        create_data = {
            "exercise_type_id": 999,
            "count": 25,
        }

        response = client.post("/api/v1/logs", json=create_data, headers=auth_and_user_headers)

        assert response.status_code == 404

    def test_create_log_invalid_count(self, client, auth_and_user_headers, mock_repos):
        """Test 422 when count is invalid (zero or negative)."""
        create_data = {
            "exercise_type_id": 1,
            "count": 0,  # Invalid - must be >= 1
        }

        response = client.post(
            "/api/v1/logs", json=create_data, headers=auth_and_user_headers
        )

        assert response.status_code == 422

    def test_create_log_with_date(
        self,
        client,
        auth_and_user_headers,
        mock_repos,
        log_model,
        exercise_type_model,
        challenge_model,
    ):
        """Test creating log with explicit date."""
        mock_repos["exercise_type"].get_by_id.return_value = exercise_type_model
        mock_repos["challenge"].get_active_for_type.return_value = challenge_model
        mock_repos["log"].create.return_value = log_model

        stats_out = ExerciseStatsOut(
            exercise_type_id=1,
            exercise_type_name="Push-ups",
            exercise_type_emoji="💪",
            challenge_id=1,
            challenge_name="January Push-up Challenge",
            day_number=10,
            total_days=31,
            target_total=1000,
            daily_target=33,
            today_total=25,
            cumulative_total=275,
            progress_percent=27.5,
            status="on_track",
            catch_up_reps=0,
        )

        with patch(
            "src.api.services.compute_exercise_stats",
            new=AsyncMock(return_value=stats_out),
        ):
            create_data = {
                "exercise_type_id": 1,
                "count": 25,
                "date": "2024-01-10",
            }

            response = client.post("/api/v1/logs", json=create_data, headers=auth_and_user_headers)

            assert response.status_code == 201

    def test_create_log_triggers_habit_reward_check(
        self,
        client,
        auth_and_user_headers,
        mock_repos,
        log_model,
        exercise_type_model,
        challenge_model,
    ):
        """Test that POST /api/v1/logs triggers habit reward notification."""
        mock_repos["exercise_type"].get_by_id.return_value = exercise_type_model
        mock_repos["challenge"].get_active_for_type.return_value = challenge_model
        mock_repos["log"].create.return_value = log_model

        stats_out = ExerciseStatsOut(
            exercise_type_id=1,
            exercise_type_name="Push-ups",
            exercise_type_emoji="💪",
            challenge_id=1,
            challenge_name="January Push-up Challenge",
            day_number=15,
            total_days=31,
            target_total=1000,
            daily_target=33,
            today_total=25,
            cumulative_total=275,
            progress_percent=27.5,
            status="on_track",
            catch_up_reps=0,
        )

        with patch(
            "src.api.services.compute_exercise_stats",
            new=AsyncMock(return_value=stats_out),
        ):
            with patch(
                "app.services.workout_service.notify_habit_reward_if_complete",
                new_callable=AsyncMock,
            ) as mock_notify:
                mock_notify.return_value = True

                create_data = {
                    "exercise_type_id": 1,
                    "count": 25,
                }

                response = client.post(
                    "/api/v1/logs", json=create_data, headers=auth_and_user_headers
                )

                assert response.status_code == 201

                # Give the background task a moment to run
                import asyncio
                import time
                time.sleep(0.1)

                # Verify habit reward notification was triggered
                mock_notify.assert_called_once()
                call_args = mock_notify.call_args
                assert call_args[0][0] == log_model.date  # First positional arg is date
                assert call_args[1]["user_id"] == 1  # user_id kwarg


class TestDeleteLog:
    """Tests for DELETE /api/v1/logs/{log_id}."""

    def test_delete_log_success(
        self,
        client,
        auth_and_user_headers,
        mock_repos,
        log_model,
    ):
        """Test successful deletion of log entry."""
        mock_repos["log"].get_by_id.return_value = log_model
        mock_repos["log"].delete.return_value = log_model

        stats_out = ExerciseStatsOut(
            exercise_type_id=1,
            exercise_type_name="Push-ups",
            exercise_type_emoji="💪",
            challenge_id=1,
            challenge_name="January Push-up Challenge",
            day_number=15,
            total_days=31,
            target_total=1000,
            daily_target=33,
            today_total=0,
            cumulative_total=250,
            progress_percent=25.0,
            status="on_track",
            catch_up_reps=0,
        )

        with patch(
            "src.api.services.compute_exercise_stats",
            new=AsyncMock(return_value=stats_out),
        ):
            response = client.delete("/api/v1/logs/123", headers=auth_and_user_headers)

            assert response.status_code == 200
            data = response.json()
            assert "log" in data
            assert "stats" in data
            mock_repos["user_stats"].sync_last_logged_date.assert_awaited_once_with(1, user_id=1)

    def test_delete_log_not_found(self, client, auth_and_user_headers, mock_repos):
        """Test 404 when log doesn't exist."""
        mock_repos["log"].get_by_id.return_value = None

        response = client.delete("/api/v1/logs/999", headers=auth_and_user_headers)

        assert response.status_code == 404

    def test_delete_log_unauthorized(self, client):
        """Test 401 when no API key provided."""
        response = client.delete("/api/v1/logs/123")

        assert response.status_code == 401

    def test_delete_log_forbidden(self, client, invalid_auth_headers, user_context_headers):
        """Test 403 when invalid API key provided."""
        response = client.delete("/api/v1/logs/123", headers={**invalid_auth_headers, **user_context_headers})

        assert response.status_code == 403
