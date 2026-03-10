"""Tests for challenge_flow state management, expiry, and rate limiting."""

import time

import pytest

from src.core import setup_django

setup_django()

from app.services.challenge_flow import (
    FLOW_TTL_SECONDS,
    RATE_LIMIT_MAX_CALLS,
    start_flow,
    get_flow,
    set_awaiting_confirm,
    clear_flow,
    check_rate_limit,
    record_llm_call,
    _flows,
    _rate_limits,
)


@pytest.fixture(autouse=True)
def _clean_state():
    """Clear global state before each test."""
    _flows.clear()
    _rate_limits.clear()
    yield
    _flows.clear()
    _rate_limits.clear()


class TestFlowState:
    def test_start_and_get_flow(self):
        start_flow(111, chat_id=42)
        flow = get_flow(111)
        assert flow is not None
        assert flow.step == "awaiting_prompt"
        assert flow.chat_id == 42

    def test_get_flow_returns_none_for_unknown_user(self):
        assert get_flow(999) is None

    def test_clear_flow(self):
        start_flow(111, chat_id=42)
        clear_flow(111)
        assert get_flow(111) is None

    def test_clear_flow_noop_for_unknown_user(self):
        clear_flow(999)  # Should not raise

    def test_set_awaiting_confirm(self):
        from src.api.models import ChallengePromptParsed, ExerciseChallengeCreate
        from datetime import date

        start_flow(111, chat_id=42)

        parsed = ChallengePromptParsed(
            is_valid=True,
            exercise_type_name="pushups",
            start_date=date(2026, 3, 11),
            duration_days=30,
            target_total=1000,
            daily_target=34,
            challenge_name="1000 Pushups",
        )
        challenge_data = ExerciseChallengeCreate(
            exercise_type_id=1,
            start_date=date(2026, 3, 11),
            end_date=date(2026, 4, 9),
            daily_target=34,
            challenge_name="1000 Pushups",
            is_active=True,
            is_default=False,
        )

        set_awaiting_confirm(111, parsed, challenge_data)

        flow = get_flow(111)
        assert flow.step == "awaiting_confirm"
        assert flow.parsed_data == parsed
        assert flow.challenge_data == challenge_data

    def test_set_awaiting_confirm_noop_for_unknown_user(self):
        from src.api.models import ChallengePromptParsed, ExerciseChallengeCreate
        from datetime import date

        parsed = ChallengePromptParsed(
            is_valid=True,
            exercise_type_name="pushups",
            start_date=date(2026, 3, 11),
            duration_days=30,
            target_total=1000,
            daily_target=34,
            challenge_name="Test",
        )
        challenge_data = ExerciseChallengeCreate(
            exercise_type_id=1,
            start_date=date(2026, 3, 11),
            end_date=date(2026, 4, 9),
            daily_target=34,
            challenge_name="Test",
            is_active=True,
            is_default=False,
        )

        set_awaiting_confirm(999, parsed, challenge_data)
        assert get_flow(999) is None

    def test_start_flow_overwrites_existing(self):
        start_flow(111, chat_id=42)
        start_flow(111, chat_id=99)
        flow = get_flow(111)
        assert flow.chat_id == 99
        assert flow.step == "awaiting_prompt"


class TestFlowExpiry:
    def test_flow_expires_after_ttl(self):
        start_flow(111, chat_id=42)
        # Simulate time passing beyond TTL
        _flows[111].created_at = time.time() - FLOW_TTL_SECONDS - 1
        assert get_flow(111) is None

    def test_flow_not_expired_within_ttl(self):
        start_flow(111, chat_id=42)
        _flows[111].created_at = time.time() - FLOW_TTL_SECONDS + 10
        assert get_flow(111) is not None

    def test_expired_flow_is_cleaned_up(self):
        start_flow(111, chat_id=42)
        _flows[111].created_at = time.time() - FLOW_TTL_SECONDS - 1
        get_flow(111)  # Triggers cleanup
        assert 111 not in _flows


class TestRateLimit:
    def test_under_limit_returns_true(self):
        assert check_rate_limit(111) is True

    def test_at_limit_returns_false(self):
        for _ in range(RATE_LIMIT_MAX_CALLS):
            record_llm_call(111)
        assert check_rate_limit(111) is False

    def test_one_under_limit_returns_true(self):
        for _ in range(RATE_LIMIT_MAX_CALLS - 1):
            record_llm_call(111)
        assert check_rate_limit(111) is True

    def test_old_calls_expire(self):
        # Record max calls but make them old
        for _ in range(RATE_LIMIT_MAX_CALLS):
            record_llm_call(111)

        # Make all timestamps older than the window
        _rate_limits[111] = [time.time() - 3601 for _ in range(RATE_LIMIT_MAX_CALLS)]

        assert check_rate_limit(111) is True

    def test_record_initializes_list(self):
        record_llm_call(111)
        assert len(_rate_limits[111]) == 1

    def test_independent_per_user(self):
        for _ in range(RATE_LIMIT_MAX_CALLS):
            record_llm_call(111)
        assert check_rate_limit(111) is False
        assert check_rate_limit(222) is True
