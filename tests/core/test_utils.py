"""Comprehensive tests for src/core/utils.py shared utility functions."""

from datetime import date

import pytest

from src.core.utils import (
    calculate_expected_progress,
    calculate_status_and_deficit,
    calculate_status,
    ensure_date,
    expand_exception_dates,
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


class TestExpandExceptionDates:
    """Tests for expand_exception_dates — see feature 0018."""

    def test_empty_inputs(self):
        # No weekdays, no dates → empty set
        start = date(2026, 1, 1)
        end = date(2026, 1, 10)
        assert expand_exception_dates(start, end, [], []) == set()

    def test_weekends_only_two_week_window_starting_monday(self):
        # 2026-01-05 is a Monday. Two-week window → 4 weekend days.
        start = date(2026, 1, 5)
        end = date(2026, 1, 18)
        result = expand_exception_dates(start, end, [6, 7], [])
        assert result == {
            date(2026, 1, 10),  # Sat
            date(2026, 1, 11),  # Sun
            date(2026, 1, 17),  # Sat
            date(2026, 1, 18),  # Sun
        }

    def test_explicit_dates_only_in_window(self):
        start = date(2026, 1, 1)
        end = date(2026, 1, 31)
        explicit = [date(2026, 1, 10), date(2026, 1, 20)]
        assert expand_exception_dates(start, end, [], explicit) == set(explicit)

    def test_explicit_dates_outside_window_dropped(self):
        start = date(2026, 1, 1)
        end = date(2026, 1, 10)
        explicit = [
            date(2025, 12, 25),  # before window
            date(2026, 1, 5),    # in window
            date(2026, 2, 1),    # after window
        ]
        assert expand_exception_dates(start, end, [], explicit) == {date(2026, 1, 5)}

    def test_weekday_and_explicit_overlap_deduped(self):
        # 2026-01-10 is a Saturday — also in explicit list. Set unions cleanly.
        start = date(2026, 1, 5)
        end = date(2026, 1, 18)
        result = expand_exception_dates(
            start, end, [6, 7], [date(2026, 1, 10), date(2026, 1, 14)]
        )
        # Wednesday Jan 14 is added on top of the 4 weekend days.
        assert date(2026, 1, 14) in result
        assert len(result) == 5

    def test_single_day_window_exception_match(self):
        d = date(2026, 1, 10)  # Saturday
        assert expand_exception_dates(d, d, [6, 7], []) == {d}

    def test_single_day_window_no_match(self):
        d = date(2026, 1, 12)  # Monday
        assert expand_exception_dates(d, d, [6, 7], []) == set()

    def test_all_exception_window_returns_full_window(self):
        # Every weekday → every day in a Mon..Sun stretch is an exception
        start = date(2026, 1, 5)  # Mon
        end = date(2026, 1, 11)   # Sun
        result = expand_exception_dates(start, end, [1, 2, 3, 4, 5, 6, 7], [])
        assert len(result) == 7

    def test_inverted_window_returns_empty(self):
        # start > end is degenerate; helper must not loop forever
        assert expand_exception_dates(date(2026, 2, 1), date(2026, 1, 1), [6, 7], []) == set()
