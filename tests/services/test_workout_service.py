"""Tests for workout_service module."""

import pytest
import math
from unittest.mock import Mock, patch
from app.services.workout_service import (
    calculate_expected_progress,
    calculate_status_and_deficit,
    calculate_status,
    get_recent_logs,
    delete_log_entry,
    undo_last_log,
)


class TestProgressCalculations:
    """Test progress calculation functions."""

    def test_calculate_expected_progress_with_daily_target(self):
        """Test expected progress when daily target is set."""
        result = calculate_expected_progress(
            target_total=750, day_number=5, total_days=30, daily_target=25
        )
        assert result == 125  # 25 * 5

    def test_calculate_expected_progress_without_daily_target(self):
        """Test expected progress when daily target is not set."""
        result = calculate_expected_progress(
            target_total=1000, day_number=5, total_days=30, daily_target=None
        )
        assert result == pytest.approx(166.67, 0.01)  # (1000/30) * 5

    def test_calculate_status_and_deficit_ahead(self):
        """Test status and deficit when user is ahead."""
        status, deficit = calculate_status_and_deficit(
            cumulative=200,  # Expected: 166.67
            target_total=1000,
            day_number=5,
            total_days=30,
            daily_target=None,
        )
        assert status == "ahead"
        assert deficit == pytest.approx(-33.33, 0.01)  # negative when ahead

    def test_calculate_status_and_deficit_on_track(self):
        """Test status and deficit when user is on track."""
        status, deficit = calculate_status_and_deficit(
            cumulative=167,  # Expected: 166.67
            target_total=1000,
            day_number=5,
            total_days=30,
            daily_target=None,
        )
        assert status == "on_track"
        assert deficit == pytest.approx(-0.333, 0.01)

    def test_calculate_status_and_deficit_behind(self):
        """Test status and deficit when user is behind."""
        status, deficit = calculate_status_and_deficit(
            cumulative=100,  # Expected: 166.67
            target_total=1000,
            day_number=5,
            total_days=30,
            daily_target=None,
        )
        assert status == "behind"
        assert deficit == pytest.approx(66.67, 0.01)  # positive when behind

    def test_calculate_status_backward_compatibility(self):
        """Test that the backward compatibility wrapper works."""
        status = calculate_status(
            cumulative=100,
            target_total=1000,
            day_number=5,
            total_days=30,
            daily_target=None,
        )
        assert status == "behind"


class TestCatchUpReps:
    """Test catch-up reps calculations from the manual test script."""

    def test_catch_up_ahead_should_not_show(self):
        """When ahead, catch-up should be 0."""
        status, deficit = calculate_status_and_deficit(
            cumulative=200,  # Expected: 166.67, ahead by 33.33
            target_total=1000,
            day_number=5,
            total_days=30,
            daily_target=None,
        )
        assert status == "ahead"
        assert deficit < 0  # negative when ahead

        # Catch-up calculation
        catch_up_reps = 0
        if status == "behind" and deficit > 0:
            catch_up_reps = math.ceil(deficit)
        assert catch_up_reps == 0

    def test_catch_up_on_track_should_not_show(self):
        """When on track, catch-up should be 0."""
        status, deficit = calculate_status_and_deficit(
            cumulative=167,  # ~5.57/day for 30 days = 167
            target_total=1000,
            day_number=5,
            total_days=30,
            daily_target=None,
        )
        assert status == "on_track"

        # Catch-up calculation
        catch_up_reps = 0
        if status == "behind" and deficit > 0:
            catch_up_reps = math.ceil(deficit)
        assert catch_up_reps == 0

    def test_catch_up_behind_no_daily_target(self):
        """When behind without daily target, should show catch-up."""
        status, deficit = calculate_status_and_deficit(
            cumulative=100,  # Expected: 166.67, deficit: 66.67
            target_total=1000,
            day_number=5,
            total_days=30,
            daily_target=None,
        )
        assert status == "behind"
        assert deficit > 0

        # Catch-up calculation
        catch_up_reps = 0
        if status == "behind" and deficit > 0:
            catch_up_reps = math.ceil(deficit)
        assert catch_up_reps == 67  # ceil(66.67)

    def test_catch_up_behind_with_daily_target(self):
        """When behind with daily target, should show catch-up."""
        status, deficit = calculate_status_and_deficit(
            cumulative=15,  # Expected: 25, deficit: 10
            target_total=750,
            day_number=5,
            total_days=30,
            daily_target=5,
        )
        assert status == "behind"
        assert deficit > 0

        # Catch-up calculation
        catch_up_reps = 0
        if status == "behind" and deficit > 0:
            catch_up_reps = math.ceil(deficit)
        assert catch_up_reps == 10  # ceil(10)

    def test_catch_up_slightly_behind_within_threshold(self):
        """When slightly behind but within threshold, should not show catch-up."""
        status, deficit = calculate_status_and_deficit(
            cumulative=160,  # Expected: 166.67, deficit: 6.67 (within 8.33 threshold)
            target_total=1000,
            day_number=5,
            total_days=30,
            daily_target=None,
        )
        assert status == "on_track"  # Within threshold

        # Catch-up calculation
        catch_up_reps = 0
        if status == "behind" and deficit > 0:
            catch_up_reps = math.ceil(deficit)
        assert catch_up_reps == 0


class TestIntegrationScenarios:
    """Test real-world scenarios to ensure the refactoring works correctly."""

    def test_exact_match_with_manual_test_script(self):
        """Verify our refactored code produces same results as manual test script."""
        test_cases = [
            # (cumulative, target_total, day_number, total_days, daily_target, expected_status, expected_catchup)
            (200, 1000, 5, 30, None, "ahead", 0),
            (167, 1000, 5, 30, None, "on_track", 0),
            (100, 1000, 5, 30, None, "behind", 67),
            (15, 750, 5, 30, 5, "behind", 10),
            (160, 1000, 5, 30, None, "on_track", 0),
        ]

        for (
            cumulative,
            target_total,
            day_number,
            total_days,
            daily_target,
            expected_status,
            expected_catchup,
        ) in test_cases:
            status, deficit = calculate_status_and_deficit(
                cumulative, target_total, day_number, total_days, daily_target
            )

            catch_up_reps = 0
            if status == "behind" and deficit > 0:
                catch_up_reps = math.ceil(deficit)

            assert status == expected_status
            assert catch_up_reps == expected_catchup


class TestGetRecentLogs:
    """Test get_recent_logs function."""

    @pytest.mark.asyncio
    @patch("app.services.workout_service.get_supabase")
    async def test_get_recent_logs_success(self, mock_get_supabase):
        """Test successful retrieval of recent logs."""
        # Mock Supabase response
        mock_sb = Mock()
        mock_table = Mock()
        mock_query = Mock()

        mock_logs_data = [
            {
                "id": 1,
                "exercise_type_id": 1,
                "count": 20,
                "date": "2024-01-15",
                "timestamp": "2024-01-15T10:30:00+00:00",
                "raw_message": "20 pushups",
                "exercise_types": {"display_name": "Pushups", "emoji": "💪"},
            },
            {
                "id": 2,
                "exercise_type_id": 2,
                "count": 30,
                "date": "2024-01-15",
                "timestamp": "2024-01-15T11:00:00+00:00",
                "raw_message": "30 squats",
                "exercise_types": {"display_name": "Squats", "emoji": "🏋️"},
            },
        ]

        mock_response = Mock()
        mock_response.data = mock_logs_data
        mock_query.execute.return_value = mock_response
        mock_query.limit.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_table.select.return_value = mock_query
        mock_sb.table.return_value = mock_table
        mock_get_supabase.return_value = mock_sb

        result = await get_recent_logs(12345, limit=5)

        assert "Recent Logs" in result
        assert "Pushups" in result
        assert "Squats" in result
        assert "20" in result
        assert "30" in result
        assert "<code>1</code>" in result
        assert "<code>2</code>" in result
        assert "/delete" in result

    @pytest.mark.asyncio
    @patch("app.services.workout_service.get_supabase")
    async def test_get_recent_logs_empty(self, mock_get_supabase):
        """Test when no logs are found."""
        mock_sb = Mock()
        mock_table = Mock()
        mock_query = Mock()

        mock_response = Mock()
        mock_response.data = []
        mock_query.execute.return_value = mock_response
        mock_query.limit.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_table.select.return_value = mock_query
        mock_sb.table.return_value = mock_table
        mock_get_supabase.return_value = mock_sb

        result = await get_recent_logs(12345)

        assert result == "No logs found."

    @pytest.mark.asyncio
    @patch("app.services.workout_service.get_supabase")
    async def test_get_recent_logs_limit(self, mock_get_supabase):
        """Test that limit parameter is respected."""
        mock_sb = Mock()
        mock_table = Mock()
        mock_query = Mock()

        mock_response = Mock()
        mock_response.data = [
            {
                "id": i,
                "exercise_type_id": 1,
                "count": 10,
                "date": "2024-01-15",
                "timestamp": "2024-01-15T10:00:00+00:00",
                "raw_message": "test",
                "exercise_types": {"display_name": "Test", "emoji": "🏋️"},
            }
            for i in range(10)
        ]
        mock_query.execute.return_value = mock_response
        mock_query.limit.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_table.select.return_value = mock_query
        mock_sb.table.return_value = mock_table
        mock_get_supabase.return_value = mock_sb

        await get_recent_logs(12345, limit=3)

        # Verify limit was called with 3
        mock_query.limit.assert_called_with(3)


class TestDeleteLogEntry:
    """Test delete_log_entry function."""

    def _create_mock_query_chain(self, execute_return_value):
        """Helper to create a mock query chain."""
        mock_query = Mock()
        mock_response = Mock()
        mock_response.data = execute_return_value
        mock_query.execute.return_value = mock_response
        mock_query.eq.return_value = mock_query
        mock_query.gt.return_value = mock_query
        mock_query.lt.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.delete.return_value = mock_query
        mock_query.update.return_value = mock_query
        return mock_query, mock_response

    @pytest.mark.asyncio
    @patch("app.services.workout_service.get_supabase")
    async def test_delete_log_entry_success(self, mock_get_supabase):
        """Test successful deletion of a log entry."""
        mock_sb = Mock()

        def create_query_chain(response_data):
            """Create a query chain that returns the given response."""
            query = Mock()
            response = Mock()
            response.data = response_data
            query.execute.return_value = response
            query.eq.return_value = query
            query.gt.return_value = query
            query.lt.return_value = query
            query.order.return_value = query
            query.limit.return_value = query
            query.select.return_value = query
            query.delete.return_value = query
            query.update.return_value = query
            return query

        # Responses in order of execution
        responses = [
            [
                {
                    "id": 123,
                    "exercise_type_id": 1,
                    "count": 20,
                    "challenge_id": None,
                    "date": "2024-01-15",
                }
            ],  # Get log
            [{"display_name": "Pushups", "emoji": "💪"}],  # Get exercise type
            [{"id": 123}],  # Delete response
            [{"id": 1, "exercise_type_id": 1, "all_time_total": 100}],  # Get stats
            [],  # Later logs (empty)
            [],  # Same date logs (empty)
            [{"date": "2024-01-14"}],  # Previous logs
        ]

        query_index = [0]

        def execute_side_effect():
            idx = query_index[0]
            query_index[0] += 1
            response = Mock()
            response.data = responses[idx] if idx < len(responses) else []
            return response

        # Create tables
        mock_log_table = Mock()
        mock_ex_table = Mock()
        mock_stats_table = Mock()

        # Setup query chains - all return same query object but execute returns different data
        log_query = create_query_chain([])
        log_query.execute.side_effect = execute_side_effect

        ex_query = create_query_chain([])
        ex_query.execute.side_effect = execute_side_effect

        stats_query = create_query_chain([])
        stats_query.execute.side_effect = execute_side_effect

        mock_log_table.select.return_value = log_query
        mock_log_table.delete.return_value = log_query
        mock_ex_table.select.return_value = ex_query
        mock_stats_table.select.return_value = stats_query
        mock_stats_table.update.return_value = stats_query

        def table_side_effect(table_name):
            if table_name == "exercise_logs":
                return mock_log_table
            elif table_name == "exercise_types":
                return mock_ex_table
            elif table_name == "user_stats":
                return mock_stats_table
            return Mock()

        mock_sb.table.side_effect = table_side_effect
        mock_get_supabase.return_value = mock_sb

        result = await delete_log_entry(123, 12345)

        assert "Deleted log entry 123" in result
        assert "Pushups" in result
        assert "-20" in result
        assert "2024-01-15" in result

    @pytest.mark.asyncio
    @patch("app.services.workout_service.get_supabase")
    async def test_delete_log_entry_not_found(self, mock_get_supabase):
        """Test deletion when log entry doesn't exist."""
        mock_sb = Mock()
        mock_table = Mock()
        mock_query = Mock()

        mock_response = Mock()
        mock_response.data = []
        mock_query.execute.return_value = mock_response
        mock_query.eq.return_value = mock_query
        mock_table.select.return_value = mock_query
        mock_sb.table.return_value = mock_table
        mock_get_supabase.return_value = mock_sb

        result = await delete_log_entry(999, 12345)

        assert "not found" in result
        assert "999" in result

    @pytest.mark.asyncio
    @patch("app.services.workout_service.get_supabase")
    async def test_delete_log_entry_updates_stats(self, mock_get_supabase):
        """Test that user_stats are updated correctly when deleting."""
        mock_sb = Mock()

        # Track execute calls
        query_index = [0]

        # Responses in order: log, ex_type, delete, stats, later, same_date, prev
        responses = [
            [
                {
                    "id": 123,
                    "exercise_type_id": 1,
                    "count": 20,
                    "challenge_id": None,
                    "date": "2024-01-15",
                }
            ],
            [{"display_name": "Pushups", "emoji": "💪"}],
            [{"id": 123}],
            [{"id": 1, "exercise_type_id": 1, "all_time_total": 100}],
            [],
            [],
            [{"date": "2024-01-14"}],
        ]

        def execute_side_effect():
            idx = query_index[0]
            query_index[0] += 1
            response = Mock()
            response.data = responses[idx] if idx < len(responses) else []
            return response

        # Create query chains
        def create_query():
            query = Mock()
            query.execute.side_effect = execute_side_effect
            query.eq.return_value = query
            query.gt.return_value = query
            query.lt.return_value = query
            query.order.return_value = query
            query.limit.return_value = query
            query.select.return_value = query
            query.delete.return_value = query
            query.update.return_value = query
            return query

        mock_log_table = Mock()
        mock_ex_table = Mock()
        mock_stats_table = Mock()

        log_query = create_query()
        ex_query = create_query()
        stats_query = create_query()

        mock_log_table.select.return_value = log_query
        mock_log_table.delete.return_value = log_query
        mock_ex_table.select.return_value = ex_query
        mock_stats_table.select.return_value = stats_query
        mock_stats_table.update.return_value = stats_query

        def table_side_effect(table_name):
            if table_name == "exercise_logs":
                return mock_log_table
            elif table_name == "exercise_types":
                return mock_ex_table
            elif table_name == "user_stats":
                return mock_stats_table
            return Mock()

        mock_sb.table.side_effect = table_side_effect
        mock_get_supabase.return_value = mock_sb

        await delete_log_entry(123, 12345)

        # Verify update was called on user_stats
        assert mock_stats_table.update.called


class TestUndoLastLog:
    """Test undo_last_log function."""

    @pytest.mark.asyncio
    @patch("app.services.workout_service.get_supabase")
    @patch("app.services.workout_service.delete_log_entry")
    async def test_undo_last_log_success(
        self, mock_delete_log_entry, mock_get_supabase
    ):
        """Test successful undo of last log."""
        mock_sb = Mock()
        mock_table = Mock()
        mock_query = Mock()

        mock_response = Mock()
        mock_response.data = [{"id": 123}]
        mock_query.execute.return_value = mock_response
        mock_query.limit.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_table.select.return_value = mock_query
        mock_sb.table.return_value = mock_table
        mock_get_supabase.return_value = mock_sb

        mock_delete_log_entry.return_value = "✅ Deleted log entry 123"

        result = await undo_last_log(12345)

        assert "Deleted log entry 123" in result
        mock_delete_log_entry.assert_called_once_with(123, 12345)

    @pytest.mark.asyncio
    @patch("app.services.workout_service.get_supabase")
    async def test_undo_last_log_no_logs(self, mock_get_supabase):
        """Test undo when no logs exist."""
        mock_sb = Mock()
        mock_table = Mock()
        mock_query = Mock()

        mock_response = Mock()
        mock_response.data = []
        mock_query.execute.return_value = mock_response
        mock_query.limit.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_table.select.return_value = mock_query
        mock_sb.table.return_value = mock_table
        mock_get_supabase.return_value = mock_sb

        result = await undo_last_log(12345)

        assert "No logs found to undo" in result
