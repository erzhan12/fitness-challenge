"""Tests for /api/v1/stats endpoints."""

from datetime import date
from unittest.mock import AsyncMock, patch

from src.api.models import ExerciseStatsOut
from tests.api.conftest import make_exercise_type_model, make_log_model, make_user_stats_model


class TestGetExercisesStats:
    """Tests for GET /api/v1/stats/exercises."""

    def test_get_all_exercises_stats_success(
        self, client, mock_repos, exercise_type_model, challenge_model, user_context_headers
    ):
        mock_repos["exercise_type"].get_all.return_value = [exercise_type_model]
        mock_repos["challenge"].get_all.return_value = [challenge_model]

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
            today_total=50,
            cumulative_total=495,
            progress_percent=49.5,
            status="on_track",
            catch_up_reps=0,
        )

        with patch(
            "src.api.services.compute_exercise_stats",
            new=AsyncMock(return_value=stats_out),
        ):
            response = client.get("/api/v1/stats/exercises", headers=user_context_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_exercises_stats_empty(self, client, mock_repos, user_context_headers):
        mock_repos["exercise_type"].get_all.return_value = []
        response = client.get("/api/v1/stats/exercises", headers=user_context_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_get_exercises_stats_with_target_date(
        self, client, mock_repos, exercise_type_model, challenge_model, user_context_headers
    ):
        mock_repos["exercise_type"].get_all.return_value = [exercise_type_model]
        mock_repos["challenge"].get_all.return_value = [challenge_model]

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
            cumulative_total=0,
            progress_percent=0.0,
            status="behind",
            catch_up_reps=1,
        )

        compute_mock = AsyncMock(return_value=stats_out)
        with patch("src.api.services.compute_exercise_stats", new=compute_mock):
            response = client.get("/api/v1/stats/exercises?target_date=2024-01-15", headers=user_context_headers)

        assert response.status_code == 200
        compute_mock.assert_awaited()

    def test_get_exercises_stats_challenge_only_param(
        self, client, mock_repos, exercise_type_model, user_context_headers
    ):
        mock_repos["exercise_type"].get_all.return_value = [exercise_type_model]

        stats_out = ExerciseStatsOut(
            exercise_type_id=1,
            exercise_type_name="Push-ups",
            exercise_type_emoji="💪",
            challenge_id=None,
            challenge_name=None,
            day_number=1,
            total_days=30,
            target_total=1000,
            daily_target=33,
            today_total=0,
            cumulative_total=0,
            progress_percent=0.0,
            status="behind",
            catch_up_reps=1,
        )

        with patch(
            "src.api.services.compute_exercise_stats",
            new=AsyncMock(return_value=stats_out),
        ):
            response = client.get("/api/v1/stats/exercises?challenge_only=false", headers=user_context_headers)

        assert response.status_code == 200


class TestGetSingleExerciseStats:
    """Tests for GET /api/v1/stats/exercises/{exercise_type_id}."""

    # TODO: Uncomment after migrations are set up in CI
    # def test_get_single_exercise_stats_success(self, client):
    #     stats_out = ExerciseStatsOut(
    #         exercise_type_id=1,
    #         exercise_type_name="Push-ups",
    #         exercise_type_emoji="💪",
    #         challenge_id=1,
    #         challenge_name="January Push-up Challenge",
    #         day_number=15,
    #         total_days=31,
    #         target_total=1000,
    #         daily_target=33,
    #         today_total=50,
    #         cumulative_total=495,
    #         progress_percent=49.5,
    #         status="on_track",
    #         catch_up_reps=0,
    #     )
    #
    #     with patch(
    #         "src.api.services.compute_exercise_stats",
    #         new=AsyncMock(return_value=stats_out),
    #     ):
    #         response = client.get("/api/v1/stats/exercises/1")
    #
    #     assert response.status_code == 200
    #     data = response.json()
    #     assert data["exercise_type_id"] == 1
    #     assert "cumulative_total" in data
    #     assert "status" in data

    # TODO: Uncomment after migrations are set up in CI
    # def test_get_single_exercise_stats_fields(self, client):
    #     stats_out = ExerciseStatsOut(
    #         exercise_type_id=1,
    #         exercise_type_name="Push-ups",
    #         exercise_type_emoji="💪",
    #         challenge_id=1,
    #         challenge_name="January Push-up Challenge",
    #         day_number=15,
    #         total_days=31,
    #         target_total=1000,
    #         daily_target=33,
    #         today_total=0,
    #         cumulative_total=0,
    #         progress_percent=0.0,
    #         status="behind",
    #         catch_up_reps=1,
    #     )
    #
    #     with patch(
    #         "src.api.services.compute_exercise_stats",
    #         new=AsyncMock(return_value=stats_out),
    #     ):
    #         response = client.get("/api/v1/stats/exercises/1")
    #
    #     assert response.status_code == 200
    #     data = response.json()
    #
    #     expected_fields = [
    #         "exercise_type_id",
    #         "exercise_type_name",
    #         "exercise_type_emoji",
    #         "challenge_id",
    #         "challenge_name",
    #         "day_number",
    #         "total_days",
    #         "target_total",
    #         "daily_target",
    #         "today_total",
    #         "cumulative_total",
    #         "progress_percent",
    #         "status",
    #         "catch_up_reps",
    #     ]
    #     for field in expected_fields:
    #         assert field in data, f"Missing field: {field}"


class TestGetStatsSummary:
    """Tests for GET /api/v1/stats/summary."""

    def test_get_stats_summary_success(
        self, client, mock_repos, mock_user_stats_data, exercise_type_model, user_context_headers
    ):
        stats_model = make_user_stats_model(mock_user_stats_data, exercise_type=exercise_type_model)
        mock_repos["user_stats"].get_all.return_value = [stats_model]

        log1 = make_log_model(
            {
                "id": 1,
                "exercise_type_id": 1,
                "challenge_id": 1,
                "date": "2024-01-15",
                "timestamp": "2024-01-15T10:30:00+05:00",
                "count": 25,
            }
        )
        log2 = make_log_model(
            {
                "id": 2,
                "exercise_type_id": 1,
                "challenge_id": 1,
                "date": "2024-01-16",
                "timestamp": "2024-01-16T10:30:00+05:00",
                "count": 10,
            }
        )
        mock_repos["log"].get_all.return_value = ([log1, log2], 2)

        response = client.get("/api/v1/stats/summary", headers=user_context_headers)

        assert response.status_code == 200
        data = response.json()
        assert "total_reps_all_time" in data
        assert "total_active_days" in data
        assert "exercise_stats" in data

    def test_get_stats_summary_empty(self, client, mock_repos, user_context_headers):
        mock_repos["user_stats"].get_all.return_value = []
        mock_repos["log"].get_all.return_value = ([], 0)

        response = client.get("/api/v1/stats/summary", headers=user_context_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_reps_all_time"] == 0
        assert data["total_active_days"] == 0
        assert data["exercise_stats"] == []

    def test_get_stats_summary_aggregation(
        self, client, mock_repos, mock_exercise_type_data, mock_exercise_type_data_2, user_context_headers
    ):
        ex1 = make_exercise_type_model(mock_exercise_type_data)
        ex2 = make_exercise_type_model(mock_exercise_type_data_2)

        stats1 = make_user_stats_model(
            {
                "id": 1,
                "exercise_type_id": 1,
                "all_time_total": 1000,
                "best_daily_count": 50,
                "current_streak": 5,
                "longest_streak": 10,
                "last_logged_date": "2024-01-15",
            },
            exercise_type=ex1,
        )
        stats2 = make_user_stats_model(
            {
                "id": 2,
                "exercise_type_id": 2,
                "all_time_total": 2000,
                "best_daily_count": 100,
                "current_streak": 3,
                "longest_streak": 7,
                "last_logged_date": "2024-01-14",
            },
            exercise_type=ex2,
        )

        mock_repos["user_stats"].get_all.return_value = [stats1, stats2]

        log_dates = [
            ("2024-01-15", "2024-01-15T10:00:00+05:00"),
            ("2024-01-14", "2024-01-14T10:00:00+05:00"),
            ("2024-01-13", "2024-01-13T10:00:00+05:00"),
        ]
        logs = []
        for i, (d, ts) in enumerate(log_dates, start=1):
            logs.append(
                make_log_model(
                    {
                        "id": i,
                        "exercise_type_id": 1,
                        "challenge_id": 1,
                        "date": d,
                        "timestamp": ts,
                        "count": 1,
                    }
                )
            )
        mock_repos["log"].get_all.return_value = (logs, len(logs))

        response = client.get("/api/v1/stats/summary", headers=user_context_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_reps_all_time"] == 3000
        assert data["total_active_days"] == 3
        assert len(data["exercise_stats"]) == 2

