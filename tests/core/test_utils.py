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
        assert calculate_expected_progress(50, 10, 30) == 500

    def test_day_one(self):
        assert calculate_expected_progress(10, 1, 30) == 10

    def test_last_day(self):
        assert calculate_expected_progress(10, 30, 30) == 300

    def test_large_daily_target(self):
        assert calculate_expected_progress(100, 5, 30) == 500


class TestCalculateStatusAndDeficit:
    """Tests for calculate_status_and_deficit."""

    def test_ahead(self):
        # cumulative=600, expected=500 (daily_target=50, day 10)
        # diff=100, threshold=50, 100 > 50 → ahead
        status, deficit = calculate_status_and_deficit(600, 50, 10, 30)
        assert status == "ahead"
        assert deficit == -100  # negative = ahead

    def test_on_track(self):
        # cumulative=500, expected=500
        # diff=0, threshold=50, not > 50, not < -50 → on_track
        status, deficit = calculate_status_and_deficit(500, 50, 10, 30)
        assert status == "on_track"
        assert deficit == 0

    def test_behind(self):
        # cumulative=400, expected=500
        # diff=-100, threshold=50, -100 < -50 → behind
        status, deficit = calculate_status_and_deficit(400, 50, 10, 30)
        assert status == "behind"
        assert deficit == 100  # positive = behind

    def test_slightly_behind_is_on_track(self):
        # cumulative=470, expected=500
        # diff=-30, threshold=50, -30 is not < -50 → on_track
        status, deficit = calculate_status_and_deficit(470, 50, 10, 30)
        assert status == "on_track"
        assert deficit == 30

    def test_slightly_ahead_is_on_track(self):
        # cumulative=530, expected=500
        # diff=30, threshold=50, 30 is not > 50 → on_track
        status, deficit = calculate_status_and_deficit(530, 50, 10, 30)
        assert status == "on_track"
        assert deficit == -30


class TestCalculateStatus:
    """Tests for calculate_status backward compatibility wrapper."""

    def test_returns_string_only(self):
        status = calculate_status(500, 50, 10, 30)
        assert isinstance(status, str)
        assert status == "on_track"

    def test_ahead(self):
        assert calculate_status(600, 50, 10, 30) == "ahead"

    def test_behind(self):
        assert calculate_status(400, 50, 10, 30) == "behind"


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
