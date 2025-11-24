"""Tests for workout_service module."""

import pytest
import math
from app.services.workout_service import (
    calculate_expected_progress,
    calculate_status_and_deficit,
    calculate_status,
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
