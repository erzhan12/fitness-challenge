"""Tests for /api/v1/stats endpoints."""

from unittest.mock import patch, Mock

from tests.api.conftest import create_mock_query


class TestGetExercisesStats:
    """Tests for GET /api/v1/stats/exercises."""

    def test_get_all_exercises_stats_success(
        self, client, mock_exercise_type_data, mock_challenge_data
    ):
        """Test successful retrieval of stats for all exercises."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()

            log_data = [{"count": 100}, {"count": 50}]

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
                    mock_table.select.return_value = create_mock_query(log_data)
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/stats/exercises")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_get_exercises_stats_empty(self, client):
        """Test stats when no exercises exist."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/stats/exercises")

            assert response.status_code == 200
            assert response.json() == []

    def test_get_exercises_stats_with_target_date(
        self, client, mock_exercise_type_data, mock_challenge_data
    ):
        """Test stats with specific target date."""
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
                    mock_table.select.return_value = create_mock_query([])
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/stats/exercises?target_date=2024-01-15")

            assert response.status_code == 200

    def test_get_exercises_stats_challenge_only_param(
        self, client, mock_exercise_type_data, mock_challenge_data
    ):
        """Test challenge_only filter parameter."""
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
                    mock_table.select.return_value = create_mock_query([])
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/stats/exercises?challenge_only=false")

            assert response.status_code == 200


class TestGetSingleExerciseStats:
    """Tests for GET /api/v1/stats/exercises/{exercise_type_id}."""

    def test_get_single_exercise_stats_success(
        self, client, mock_exercise_type_data, mock_challenge_data
    ):
        """Test successful retrieval of stats for single exercise."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()

            log_data = [{"count": 100}, {"count": 50}]

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
                    mock_table.select.return_value = create_mock_query(log_data)
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/stats/exercises/1")

            assert response.status_code == 200
            data = response.json()
            assert data["exercise_type_id"] == 1
            assert "cumulative_total" in data
            assert "status" in data

    def test_get_single_exercise_stats_fields(
        self, client, mock_exercise_type_data, mock_challenge_data
    ):
        """Test that all expected fields are present in response."""
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
                    mock_table.select.return_value = create_mock_query([])
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/stats/exercises/1")

            assert response.status_code == 200
            data = response.json()

            # Verify all expected fields
            expected_fields = [
                "exercise_type_id",
                "exercise_type_name",
                "exercise_type_emoji",
                "challenge_id",
                "challenge_name",
                "day_number",
                "total_days",
                "target_total",
                "daily_target",
                "today_total",
                "cumulative_total",
                "progress_percent",
                "status",
                "catch_up_reps",
            ]
            for field in expected_fields:
                assert field in data, f"Missing field: {field}"


class TestGetStatsSummary:
    """Tests for GET /api/v1/stats/summary."""

    def test_get_stats_summary_success(
        self, client, mock_exercise_type_data, mock_user_stats_data
    ):
        """Test successful retrieval of overall stats summary."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()

            user_stats_with_type = {
                **mock_user_stats_data,
                "exercise_types": mock_exercise_type_data,
            }

            log_dates = [{"date": "2024-01-15"}, {"date": "2024-01-16"}]

            def table_side_effect(table_name):
                mock_table = Mock()
                if table_name == "user_stats":
                    mock_table.select.return_value = create_mock_query(
                        [user_stats_with_type]
                    )
                elif table_name == "exercise_logs":
                    mock_table.select.return_value = create_mock_query(log_dates)
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/stats/summary")

            assert response.status_code == 200
            data = response.json()
            assert "total_reps_all_time" in data
            assert "total_active_days" in data
            assert "exercise_stats" in data

    def test_get_stats_summary_empty(self, client):
        """Test summary when no stats exist."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()
            mock_sb.table.return_value.select.return_value = create_mock_query([])
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/stats/summary")

            assert response.status_code == 200
            data = response.json()
            assert data["total_reps_all_time"] == 0
            assert data["total_active_days"] == 0
            assert data["exercise_stats"] == []

    def test_get_stats_summary_aggregation(
        self, client, mock_exercise_type_data, mock_exercise_type_data_2
    ):
        """Test that stats are properly aggregated across exercise types."""
        with patch("src.api.services.get_supabase") as mock_get_sb:
            mock_sb = Mock()

            user_stats = [
                {
                    **mock_exercise_type_data,
                    "id": 1,
                    "exercise_type_id": 1,
                    "all_time_total": 1000,
                    "best_daily_count": 50,
                    "current_streak": 5,
                    "longest_streak": 10,
                    "last_logged_date": "2024-01-15",
                    "exercise_types": mock_exercise_type_data,
                },
                {
                    **mock_exercise_type_data_2,
                    "id": 2,
                    "exercise_type_id": 2,
                    "all_time_total": 2000,
                    "best_daily_count": 100,
                    "current_streak": 3,
                    "longest_streak": 7,
                    "last_logged_date": "2024-01-14",
                    "exercise_types": mock_exercise_type_data_2,
                },
            ]

            log_dates = [
                {"date": "2024-01-15"},
                {"date": "2024-01-14"},
                {"date": "2024-01-13"},
            ]

            def table_side_effect(table_name):
                mock_table = Mock()
                if table_name == "user_stats":
                    mock_table.select.return_value = create_mock_query(user_stats)
                elif table_name == "exercise_logs":
                    mock_table.select.return_value = create_mock_query(log_dates)
                return mock_table

            mock_sb.table.side_effect = table_side_effect
            mock_get_sb.return_value = mock_sb

            response = client.get("/api/v1/stats/summary")

            assert response.status_code == 200
            data = response.json()
            assert data["total_reps_all_time"] == 3000  # 1000 + 2000
            assert data["total_active_days"] == 3  # 3 unique dates
            assert len(data["exercise_stats"]) == 2

