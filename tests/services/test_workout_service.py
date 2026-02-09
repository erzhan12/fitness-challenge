"""Tests for workout_service module."""

import asyncio
import math
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core import setup_django

setup_django()

from src.core.utils import (
    calculate_expected_progress,
    calculate_status_and_deficit,
    calculate_status,
    ensure_date,
)
from app.services.workout_service import (
    get_recent_logs,
    delete_log_entry,
    undo_last_log,
)

class TestProgressCalculations:
    """Test progress calculation functions."""

    def test_calculate_expected_progress_with_daily_target(self):
        """Test expected progress when daily target is set."""
        result = calculate_expected_progress(
            daily_target=25, day_number=5, total_days=30
        )
        assert result == 125  # 25 * 5

    def test_calculate_status_and_deficit_ahead(self):
        """Test status and deficit when user is ahead."""
        # daily_target=33, day 5 → expected = 165
        # cumulative=250, diff = 85 > threshold of 33 → ahead
        status, deficit = calculate_status_and_deficit(
            cumulative=250,
            daily_target=33,
            day_number=5,
            total_days=30,
        )
        assert status == "ahead"
        assert deficit == -85  # negative when ahead

    def test_calculate_status_and_deficit_on_track(self):
        """Test status and deficit when user is on track."""
        # daily_target=33, day 5 → expected = 165
        status, deficit = calculate_status_and_deficit(
            cumulative=167,
            daily_target=33,
            day_number=5,
            total_days=30,
        )
        assert status == "on_track"
        assert deficit == -2

    def test_calculate_status_and_deficit_behind(self):
        """Test status and deficit when user is behind."""
        # daily_target=33, day 5 → expected = 165
        status, deficit = calculate_status_and_deficit(
            cumulative=100,
            daily_target=33,
            day_number=5,
            total_days=30,
        )
        assert status == "behind"
        assert deficit == 65  # positive when behind

    def test_calculate_status_backward_compatibility(self):
        """Test that the backward compatibility wrapper works."""
        status = calculate_status(
            cumulative=100,
            daily_target=33,
            day_number=5,
            total_days=30,
        )
        assert status == "behind"


class TestCatchUpReps:
    """Test catch-up reps calculations from the manual test script."""

    def test_catch_up_ahead_should_not_show(self):
        """When ahead, catch-up should be 0."""
        # daily_target=33, day 5 → expected = 165
        status, deficit = calculate_status_and_deficit(
            cumulative=250,
            daily_target=33,
            day_number=5,
            total_days=30,
        )
        assert status == "ahead"
        assert deficit < 0  # negative when ahead

        catch_up_reps = 0
        if deficit > 0:
            catch_up_reps = math.ceil(deficit)
        assert catch_up_reps == 0

    def test_catch_up_on_track_should_not_show(self):
        """When on track (slightly ahead), catch-up should be 0."""
        # daily_target=33, day 5 → expected = 165
        status, deficit = calculate_status_and_deficit(
            cumulative=167,
            daily_target=33,
            day_number=5,
            total_days=30,
        )
        assert status == "on_track"

        catch_up_reps = 0
        if deficit > 0:
            catch_up_reps = math.ceil(deficit)
        assert catch_up_reps == 0

    def test_catch_up_behind(self):
        """When behind, should show catch-up."""
        # daily_target=33, day 5 → expected = 165
        status, deficit = calculate_status_and_deficit(
            cumulative=100,
            daily_target=33,
            day_number=5,
            total_days=30,
        )
        assert status == "behind"
        assert deficit > 0

        catch_up_reps = math.ceil(deficit)
        assert catch_up_reps == 65  # ceil(65)

    def test_catch_up_behind_with_small_daily_target(self):
        """When behind with daily target, should show catch-up."""
        status, deficit = calculate_status_and_deficit(
            cumulative=15,  # Expected: 25, deficit: 10
            daily_target=5,
            day_number=5,
            total_days=30,
        )
        assert status == "behind"
        assert deficit > 0

        catch_up_reps = math.ceil(deficit)
        assert catch_up_reps == 10

    def test_catch_up_slightly_behind_shows_deficit(self):
        """When slightly behind (positive deficit), should show catch-up."""
        # daily_target=33, day 5 → expected = 165
        status, deficit = calculate_status_and_deficit(
            cumulative=160,
            daily_target=33,
            day_number=5,
            total_days=30,
        )
        assert status == "on_track"  # within threshold
        assert deficit > 0

        catch_up_reps = math.ceil(deficit)
        assert catch_up_reps == 5


class TestIntegrationScenarios:
    """Test real-world scenarios to ensure the refactoring works correctly."""

    def test_exact_match_with_manual_test_script(self):
        """Verify our refactored code produces expected results."""
        test_cases = [
            # (cumulative, daily_target, day_number, total_days, expected_status, expected_catchup)
            (200, 33, 5, 30, "ahead", 0),        # expected=165, diff=35, threshold=33 → ahead (35 > 33)
            (167, 33, 5, 30, "on_track", 0),      # expected=165, diff=2 → on_track
            (100, 33, 5, 30, "behind", 65),        # expected=165, deficit=65
            (15, 5, 5, 30, "behind", 10),          # expected=25, deficit=10
            (160, 33, 5, 30, "on_track", 5),       # expected=165, deficit=5
            (250, 33, 5, 30, "ahead", 0),          # expected=165, diff=85 > 33 → ahead
        ]

        for (
            cumulative,
            daily_target,
            day_number,
            total_days,
            expected_status,
            expected_catchup,
        ) in test_cases:
            status, deficit = calculate_status_and_deficit(
                cumulative, daily_target, day_number, total_days
            )

            catch_up_reps = math.ceil(deficit) if deficit > 0 else 0

            assert status == expected_status, f"Failed for cumulative={cumulative}"
            assert catch_up_reps == expected_catchup, f"Failed catchup for cumulative={cumulative}"


class TestGetRecentLogs:
    """Test get_recent_logs function (repository-based)."""

    def test_get_recent_logs_success(self):
        log_1 = SimpleNamespace(
            id=1,
            count=20,
            date=date(2024, 1, 15),
            timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            raw_message="20 pushups",
            exercise_type=SimpleNamespace(display_name="Pushups", emoji="💪"),
        )
        log_2 = SimpleNamespace(
            id=2,
            count=30,
            date=date(2024, 1, 15),
            timestamp=datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc),
            raw_message="30 squats",
            exercise_type=SimpleNamespace(display_name="Squats", emoji="🏋️"),
        )

        with patch(
            "app.services.workout_service.log_repo.get_all",
            new=AsyncMock(return_value=([log_1, log_2], 2)),
        ) as get_all_mock:
            result = asyncio.run(get_recent_logs(12345, limit=5))

        assert "Recent Logs" in result
        assert "Pushups" in result
        assert "Squats" in result
        assert "<code>1</code>" in result
        assert "<code>2</code>" in result
        assert "/delete" in result
        get_all_mock.assert_awaited_once_with(limit=5, offset=0, user_id=12345)

    def test_get_recent_logs_empty(self):
        with patch(
            "app.services.workout_service.log_repo.get_all",
            new=AsyncMock(return_value=([], 0)),
        ) as get_all_mock:
            result = asyncio.run(get_recent_logs(12345))

        assert result == "No logs found."
        get_all_mock.assert_awaited_once_with(limit=5, offset=0, user_id=12345)

    def test_get_recent_logs_limit_is_respected(self):
        with patch(
            "app.services.workout_service.log_repo.get_all",
            new=AsyncMock(return_value=([], 0)),
        ) as get_all_mock:
            asyncio.run(get_recent_logs(12345, limit=3))

        get_all_mock.assert_awaited_once_with(limit=3, offset=0, user_id=12345)


class TestDeleteLogEntry:
    """Test delete_log_entry function (repository-based)."""

    def test_delete_log_entry_success_updates_stats_and_last_logged_date(self):
        log_entry = SimpleNamespace(
            id=123,
            exercise_type_id=1,
            count=20,
            date=date(2024, 1, 15),
            exercise_type=SimpleNamespace(display_name="Pushups", emoji="💪"),
        )
        with (
            patch(
                "app.services.workout_service.log_repo.get_by_id",
                new=AsyncMock(return_value=log_entry),
            ) as get_by_id_mock,
            patch(
                "app.services.workout_service.log_repo.delete",
                new=AsyncMock(return_value=log_entry),
            ) as delete_mock,
            patch(
                "app.services.workout_service.user_stats_repo.decrement_total",
                new=AsyncMock(),
            ) as decrement_mock,
            patch(
                "app.services.workout_service.user_stats_repo.sync_last_logged_date",
                new=AsyncMock(return_value=date(2024, 1, 14)),
            ) as sync_last_logged_date_mock,
        ):
            result = asyncio.run(delete_log_entry(123, 12345))

        assert "✅ Deleted log entry 123" in result
        assert "Pushups" in result
        assert "-20" in result
        assert "2024-01-15" in result
        get_by_id_mock.assert_awaited_once_with(123, user_id=12345)
        delete_mock.assert_awaited_once_with(123, user_id=12345)
        decrement_mock.assert_awaited_once_with(1, 20, user_id=12345)
        sync_last_logged_date_mock.assert_awaited_once_with(1, user_id=12345)

    def test_delete_log_entry_not_found(self):
        with (
            patch(
                "app.services.workout_service.log_repo.get_by_id",
                new=AsyncMock(return_value=None),
            ) as get_by_id_mock,
            patch(
                "app.services.workout_service.log_repo.delete",
                new=AsyncMock(),
            ) as delete_mock,
        ):
            result = asyncio.run(delete_log_entry(999, 12345))

        assert "not found" in result.lower()
        assert "999" in result
        get_by_id_mock.assert_awaited_once_with(999, user_id=12345)
        delete_mock.assert_not_awaited()

    def test_delete_log_entry_delete_failed(self):
        log_entry = SimpleNamespace(
            id=123,
            exercise_type_id=1,
            count=20,
            date=date(2024, 1, 15),
            exercise_type=SimpleNamespace(display_name="Pushups", emoji="💪"),
        )

        with (
            patch(
                "app.services.workout_service.log_repo.get_by_id",
                new=AsyncMock(return_value=log_entry),
            ),
            patch(
                "app.services.workout_service.log_repo.delete",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.workout_service.user_stats_repo.decrement_total",
                new=AsyncMock(),
            ) as decrement_mock,
        ):
            result = asyncio.run(delete_log_entry(123, 12345))

        assert "failed to delete" in result.lower()
        decrement_mock.assert_not_awaited()

    def test_delete_log_entry_sets_last_logged_date_none_when_no_remaining_logs(self):
        # Behavior for "no remaining logs" is internal to the repository method.
        # Ensure we still invoke it after a successful delete.
        log_entry = SimpleNamespace(
            id=123,
            exercise_type_id=1,
            count=20,
            date=date(2024, 1, 15),
            exercise_type=SimpleNamespace(display_name="Pushups", emoji="💪"),
        )

        with (
            patch(
                "app.services.workout_service.log_repo.get_by_id",
                new=AsyncMock(return_value=log_entry),
            ),
            patch(
                "app.services.workout_service.log_repo.delete",
                new=AsyncMock(return_value=log_entry),
            ),
            patch(
                "app.services.workout_service.user_stats_repo.decrement_total",
                new=AsyncMock(),
            ),
            patch(
                "app.services.workout_service.user_stats_repo.sync_last_logged_date",
                new=AsyncMock(return_value=None),
            ) as sync_last_logged_date_mock,
        ):
            asyncio.run(delete_log_entry(123, 12345))

        sync_last_logged_date_mock.assert_awaited_once_with(1, user_id=12345)


class TestUndoLastLog:
    """Test undo_last_log function (repository-based)."""

    def test_undo_last_log_success(self):
        log_entry = SimpleNamespace(id=123)

        with (
            patch(
                "app.services.workout_service.log_repo.get_all",
                new=AsyncMock(return_value=([log_entry], 1)),
            ) as get_all_mock,
            patch(
                "app.services.workout_service.delete_log_entry",
                new=AsyncMock(return_value="✅ Deleted log entry 123"),
            ) as delete_mock,
        ):
            result = asyncio.run(undo_last_log(12345))

        assert "Deleted log entry 123" in result
        get_all_mock.assert_awaited_once_with(limit=1, offset=0, user_id=12345)
        delete_mock.assert_awaited_once_with(123, 12345)

    def test_undo_last_log_no_logs(self):
        with patch(
            "app.services.workout_service.log_repo.get_all",
            new=AsyncMock(return_value=([], 0)),
        ) as get_all_mock:
            result = asyncio.run(undo_last_log(12345))

        assert "No logs found to undo" in result
        get_all_mock.assert_awaited_once_with(limit=1, offset=0, user_id=12345)


class TestEnsureDate:
    """Test ensure_date utility function."""

    def test_ensure_date_with_string(self):
        result = ensure_date("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_ensure_date_with_date_object(self):
        d = date(2024, 1, 15)
        result = ensure_date(d)
        assert result == d
