"""Unit tests for compute_exercise_stats exception-day math (feature 0018).

These exercise the in-process function (no FastAPI client) so we can assert
on the precise effective_day_number / target_total / is_today_exception
behavior added in feature 0018.
"""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from src.api.services import compute_exercise_stats


@pytest.fixture
def fake_etype():
    return {
        "id": 1,
        "name": "pushups",
        "display_name": "Push-ups",
        "emoji": "💪",
        "unit": "reps",
    }


def _make_challenge(
    *,
    start: str,
    end: str,
    daily_target: int,
    exception_weekdays: str = "",
    exception_dates_set=None,
):
    """Build a challenge dict in the shape compute_exercise_stats expects.

    Setting ``_exception_dates`` exercises the bulk N+1-avoidance code path
    so we don't have to mock challenge_exception_day_repo.list_for_challenge.
    """
    return {
        "id": 1,
        "challenge_name": "Test Challenge",
        "start_date": start,
        "end_date": end,
        "daily_target": daily_target,
        "exception_weekdays": exception_weekdays,
        "_exception_dates": exception_dates_set or set(),
    }


@pytest.mark.asyncio
async def test_no_exceptions_baseline(mock_repos, fake_etype):
    """Sanity: no exceptions ⇒ effective_total_days == calendar."""
    mock_repos["log"].get_cumulative_count = AsyncMock(return_value=100)
    mock_repos["log"].get_today_count = AsyncMock(return_value=10)

    challenge = _make_challenge(
        start="2026-04-01", end="2026-04-30", daily_target=10
    )

    stats = await compute_exercise_stats(
        exercise_type_id=1,
        target_date=date(2026, 4, 10),
        etype=fake_etype,
        challenge=challenge,
        user_id=1,
    )

    assert stats.total_days == 30
    assert stats.target_total == 300
    assert stats.day_number == 10
    assert stats.is_today_exception is False


@pytest.mark.asyncio
async def test_today_is_weekend_freezes_day_number(mock_repos, fake_etype):
    """When today is a recurring weekend, day_number freezes at the prior weekday."""
    mock_repos["log"].get_cumulative_count = AsyncMock(return_value=200)
    mock_repos["log"].get_today_count = AsyncMock(return_value=0)

    # Window: Mon Apr 6 .. Sun Apr 19, 2026 (14 days, 4 weekend days)
    # Today: Sat Apr 11 → exception → frozen at Friday Apr 10 (day 5 of effective)
    challenge = _make_challenge(
        start="2026-04-06",
        end="2026-04-19",
        daily_target=20,
        exception_weekdays="6,7",
    )

    stats = await compute_exercise_stats(
        exercise_type_id=1,
        target_date=date(2026, 4, 11),  # Sat
        etype=fake_etype,
        challenge=challenge,
        user_id=1,
    )

    # 14 calendar - 4 weekends = 10 effective
    assert stats.total_days == 10
    assert stats.target_total == 200
    # Today (Sat) is exception → frozen at the count of weekdays Mon..Fri = 5
    assert stats.day_number == 5
    assert stats.is_today_exception is True
    # No daily-ring penalty on a rest day
    assert stats.is_daily_complete is True
    assert stats.catch_up_reps == 0


@pytest.mark.asyncio
async def test_starts_on_rest_day(mock_repos, fake_etype):
    """If day 1 is itself a rest day, effective_day_number is 0 (no early-behind)."""
    mock_repos["log"].get_cumulative_count = AsyncMock(return_value=0)
    mock_repos["log"].get_today_count = AsyncMock(return_value=0)

    # Window starts on a Sat with weekends as exceptions; today == start.
    challenge = _make_challenge(
        start="2026-04-11",  # Sat
        end="2026-04-30",
        daily_target=20,
        exception_weekdays="6,7",
    )

    stats = await compute_exercise_stats(
        exercise_type_id=1,
        target_date=date(2026, 4, 11),
        etype=fake_etype,
        challenge=challenge,
        user_id=1,
    )

    # day_number 0 → no expected work yet → catch_up_reps 0
    assert stats.day_number == 0
    assert stats.is_today_exception is True
    assert stats.catch_up_reps == 0


@pytest.mark.asyncio
async def test_banked_weekend_logs_count_toward_cumulative(mock_repos, fake_etype):
    """Logs on a rest day still bump cumulative_total — daily ring stays hidden."""
    # Cumulative includes 200 banked on the weekend.
    mock_repos["log"].get_cumulative_count = AsyncMock(return_value=350)
    mock_repos["log"].get_today_count = AsyncMock(return_value=200)

    challenge = _make_challenge(
        start="2026-04-06",
        end="2026-04-19",
        daily_target=20,
        exception_weekdays="6,7",
    )

    stats = await compute_exercise_stats(
        exercise_type_id=1,
        target_date=date(2026, 4, 11),  # Sat (rest)
        etype=fake_etype,
        challenge=challenge,
        user_id=1,
    )

    assert stats.cumulative_total == 350
    assert stats.today_total == 200
    assert stats.is_today_exception is True
    # Status math uses effective_total_days; 350 > expected ⇒ ahead.
    assert stats.status == "ahead"


@pytest.mark.asyncio
async def test_all_exception_window_no_divide_by_zero(mock_repos, fake_etype):
    """An all-exception window yields target_total == 0 without crashing."""
    mock_repos["log"].get_cumulative_count = AsyncMock(return_value=0)
    mock_repos["log"].get_today_count = AsyncMock(return_value=0)

    # Mon..Sun with all 7 weekdays marked → every day is an exception
    challenge = _make_challenge(
        start="2026-04-06",
        end="2026-04-12",
        daily_target=20,
        exception_weekdays="1,2,3,4,5,6,7",
    )

    stats = await compute_exercise_stats(
        exercise_type_id=1,
        target_date=date(2026, 4, 9),  # Thu
        etype=fake_etype,
        challenge=challenge,
        user_id=1,
    )

    assert stats.total_days == 0
    assert stats.target_total == 0
    assert stats.is_today_exception is True
    # Progress percent should be 0 (no target_total to divide by) — not NaN.
    assert stats.progress_percent == 0


@pytest.mark.asyncio
async def test_explicit_one_off_date_skipped(mock_repos, fake_etype):
    """A single explicit exception date freezes day_number on that day."""
    mock_repos["log"].get_cumulative_count = AsyncMock(return_value=80)
    mock_repos["log"].get_today_count = AsyncMock(return_value=0)

    # Window Apr 1..30, only one explicit rest day Apr 15
    challenge = _make_challenge(
        start="2026-04-01",
        end="2026-04-30",
        daily_target=10,
        exception_dates_set={date(2026, 4, 15)},
    )

    stats = await compute_exercise_stats(
        exercise_type_id=1,
        target_date=date(2026, 4, 15),
        etype=fake_etype,
        challenge=challenge,
        user_id=1,
    )

    # 30 - 1 explicit = 29 effective
    assert stats.total_days == 29
    assert stats.target_total == 290
    # Today is the rest day → frozen at Apr 14 (day 14 of effective)
    assert stats.day_number == 14
    assert stats.is_today_exception is True
