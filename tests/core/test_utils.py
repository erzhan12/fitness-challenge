"""Comprehensive tests for src/core/utils.py shared utility functions."""

from datetime import date

import pytest

from src.core.utils import (
    calculate_expected_progress,
    calculate_status_and_deficit,
    calculate_status,
    ensure_date,
)


class TestCalculateExpectedProgress:
    """Tests for calculate_expected_progress."""

    def test_with_daily_target(self):
        # daily_target=50, day 10 → 500
        assert calculate_expected_progress(1500, 10, 30, 50) == 500

    def test_without_daily_target(self):
        # 1500 / 30 * 10 = 500.0
        assert calculate_expected_progress(1500, 10, 30, None) == 500.0

    def test_without_daily_target_fractional(self):
        # 100 / 3 * 1 ≈ 33.33
        result = calculate_expected_progress(100, 1, 3, None)
        assert abs(result - 33.333) < 0.01

    def test_day_one(self):
        assert calculate_expected_progress(300, 1, 30, 10) == 10

    def test_last_day(self):
        assert calculate_expected_progress(300, 30, 30, 10) == 300

    def test_zero_total_days_returns_zero(self):
        """Division by zero guard: total_days=0 should return 0.0."""
        assert calculate_expected_progress(1500, 10, 0, None) == 0.0

    def test_negative_total_days_returns_zero(self):
        """Negative total_days should also return 0.0."""
        assert calculate_expected_progress(1500, 10, -5, None) == 0.0

    def test_zero_total_days_with_daily_target(self):
        """When daily_target is set, total_days doesn't matter."""
        assert calculate_expected_progress(1500, 10, 0, 50) == 500

    def test_daily_target_zero_falls_through(self):
        """daily_target=0 is falsy, should use target_total/total_days."""
        assert calculate_expected_progress(300, 10, 30, 0) == 100.0


class TestCalculateStatusAndDeficit:
    """Tests for calculate_status_and_deficit."""

    def test_ahead(self):
        # cumulative=600, expected=500 (daily_target=50, day 10)
        # diff=100, threshold=50, 100 > 50 → ahead
        status, deficit = calculate_status_and_deficit(600, 1500, 10, 30, 50)
        assert status == "ahead"
        assert deficit == -100  # negative = ahead

    def test_on_track(self):
        # cumulative=500, expected=500
        # diff=0, threshold=50, not > 50, not < -50 → on_track
        status, deficit = calculate_status_and_deficit(500, 1500, 10, 30, 50)
        assert status == "on_track"
        assert deficit == 0

    def test_behind(self):
        # cumulative=400, expected=500
        # diff=-100, threshold=50, -100 < -50 → behind
        status, deficit = calculate_status_and_deficit(400, 1500, 10, 30, 50)
        assert status == "behind"
        assert deficit == 100  # positive = behind

    def test_slightly_behind_is_on_track(self):
        # cumulative=470, expected=500
        # diff=-30, threshold=50, -30 is not < -50 → on_track
        status, deficit = calculate_status_and_deficit(470, 1500, 10, 30, 50)
        assert status == "on_track"
        assert deficit == 30

    def test_slightly_ahead_is_on_track(self):
        # cumulative=530, expected=500
        # diff=30, threshold=50, 30 is not > 50 → on_track
        status, deficit = calculate_status_and_deficit(530, 1500, 10, 30, 50)
        assert status == "on_track"
        assert deficit == -30

    def test_zero_total_days_no_daily_target(self):
        """With total_days=0 and no daily_target, threshold defaults to 1."""
        status, deficit = calculate_status_and_deficit(10, 300, 5, 0, None)
        # expected=0.0 (guarded), diff=10, threshold=1, 10 > 1 → ahead
        assert status == "ahead"
        assert deficit == -10

    def test_without_daily_target(self):
        # target_total=300, total_days=30, day 10 → expected=100
        # cumulative=100, diff=0, threshold=10 (300/30) → on_track
        status, deficit = calculate_status_and_deficit(100, 300, 10, 30, None)
        assert status == "on_track"
        assert deficit == 0


class TestCalculateStatus:
    """Tests for calculate_status backward compatibility wrapper."""

    def test_returns_string_only(self):
        status = calculate_status(500, 1500, 10, 30, 50)
        assert isinstance(status, str)
        assert status == "on_track"

    def test_ahead(self):
        assert calculate_status(600, 1500, 10, 30, 50) == "ahead"

    def test_behind(self):
        assert calculate_status(400, 1500, 10, 30, 50) == "behind"


class TestEnsureDate:
    """Tests for ensure_date utility function."""

    def test_with_iso_string(self):
        result = ensure_date("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_with_date_object(self):
        d = date(2024, 1, 15)
        result = ensure_date(d)
        assert result is d

    def test_invalid_string_raises_value_error(self):
        with pytest.raises(ValueError):
            ensure_date("not-a-date")

    def test_none_passes_through(self):
        # ensure_date doesn't guard against None — callers are responsible
        result = ensure_date(None)
        assert result is None
