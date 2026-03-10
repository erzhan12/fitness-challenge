"""Tests for /challenge Telegram command, prompt handling, and callback queries."""

from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.core import setup_django

setup_django()

from src.core.models import AppUser as AppUserModel
from src.api.models import (
    ChallengePromptParsed,
    ExerciseChallengeCreate,
    ExerciseChallengeOut,
)
from app.services.challenge_flow import (
    _flows,
    _rate_limits,
    start_flow,
    set_awaiting_confirm,
    RATE_LIMIT_MAX_CALLS,
)
from app.services.workout_service import (
    process_callback_query,
    _handle_challenge_prompt,
    _format_challenge_preview,
)
from app.services.openai_service import LLMUnavailableError
from src.api.services import ExerciseTypeNotFoundError


@pytest.fixture(autouse=True)
def _clean_state():
    _flows.clear()
    _rate_limits.clear()
    yield
    _flows.clear()
    _rate_limits.clear()


def _make_parsed():
    return ChallengePromptParsed(
        is_valid=True,
        exercise_type_name="pushups",
        start_date=date(2026, 3, 11),
        duration_days=30,
        target_total=1000,
        daily_target=34,
        challenge_name="1000 Pushups Challenge",
    )


def _make_challenge_data():
    return ExerciseChallengeCreate(
        exercise_type_id=1,
        start_date=date(2026, 3, 11),
        end_date=date(2026, 4, 9),
        daily_target=34,
        challenge_name="1000 Pushups Challenge",
        is_active=True,
        is_default=False,
    )


def _make_challenge_out():
    return ExerciseChallengeOut(
        id=1,
        exercise_type_id=1,
        start_date=date(2026, 3, 11),
        end_date=date(2026, 4, 9),
        target_total=1020,
        daily_target=34,
        challenge_name="1000 Pushups Challenge",
        is_active=True,
        is_default=False,
        total_days=30,
        is_current=True,
    )


def _make_approved_user(telegram_user_id=111):
    return AppUserModel(
        id=1,
        telegram_user_id=telegram_user_id,
        username="testuser",
        first_name="Test",
        timezone="Asia/Almaty",
        status="approved",
        created_at=datetime.now(dt_timezone.utc),
    )


def _make_unapproved_user(telegram_user_id=111):
    return AppUserModel(
        id=1,
        telegram_user_id=telegram_user_id,
        username="testuser",
        first_name="Test",
        timezone="Asia/Almaty",
        status="pending",
        created_at=datetime.now(dt_timezone.utc),
    )


# ─── _format_challenge_preview ───────────────────────────────────────────


class TestFormatPreview:
    def test_includes_name_and_targets(self):
        parsed = _make_parsed()
        data = _make_challenge_data()
        result = _format_challenge_preview(parsed, data)
        assert "1000 Pushups Challenge" in result
        assert "pushups" in result
        assert "2026-03-11" in result
        assert "2026-04-09" in result
        assert "~34/day" in result

    def test_escapes_html(self):
        parsed = _make_parsed()
        parsed.challenge_name = "<b>Hacked</b>"
        data = _make_challenge_data()
        result = _format_challenge_preview(parsed, data)
        assert "<b>Hacked</b>" not in result
        assert "&lt;b&gt;Hacked&lt;/b&gt;" in result


# ─── _handle_challenge_prompt ────────────────────────────────────────────


class TestHandleChallengePrompt:
    @pytest.mark.asyncio
    async def test_happy_path_sends_preview_with_keyboard(self):
        start_flow(111, chat_id=42)

        with patch(
            "app.services.workout_service.send_chat_action", new_callable=AsyncMock
        ), patch(
            "app.services.workout_service.validate_and_prepare_challenge",
            new_callable=AsyncMock,
            return_value=(_make_parsed(), _make_challenge_data()),
        ), patch(
            "app.services.workout_service.send_telegram_message_with_keyboard",
            new_callable=AsyncMock,
        ) as mock_send_kb:
            await _handle_challenge_prompt("100 pushups in 30 days", 111, 1, 42)

            mock_send_kb.assert_called_once()
            args = mock_send_kb.call_args
            assert "New Challenge Preview" in args[0][1]
            assert args[0][0] == 42  # chat_id

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        start_flow(111, chat_id=42)
        # Exhaust rate limit
        _rate_limits[111] = [1e18] * RATE_LIMIT_MAX_CALLS

        with patch(
            "app.services.workout_service.send_telegram_message",
            new_callable=AsyncMock,
        ) as mock_send:
            await _handle_challenge_prompt("100 pushups", 111, 1, 42)

            mock_send.assert_called_once()
            assert "limit" in mock_send.call_args[0][1].lower()
            # Flow should be cleared
            assert 111 not in _flows

    @pytest.mark.asyncio
    async def test_llm_unavailable_clears_flow(self):
        start_flow(111, chat_id=42)

        with patch(
            "app.services.workout_service.send_chat_action", new_callable=AsyncMock
        ), patch(
            "app.services.workout_service.validate_and_prepare_challenge",
            new_callable=AsyncMock,
            side_effect=LLMUnavailableError("timeout"),
        ), patch(
            "app.services.workout_service.send_telegram_message",
            new_callable=AsyncMock,
        ) as mock_send:
            await _handle_challenge_prompt("100 pushups", 111, 1, 42)

            mock_send.assert_called_once()
            assert "unavailable" in mock_send.call_args[0][1].lower()
            assert 111 not in _flows

    @pytest.mark.asyncio
    async def test_exercise_type_not_found(self):
        start_flow(111, chat_id=42)

        with patch(
            "app.services.workout_service.send_chat_action", new_callable=AsyncMock
        ), patch(
            "app.services.workout_service.validate_and_prepare_challenge",
            new_callable=AsyncMock,
            side_effect=ExerciseTypeNotFoundError("running", ["pushups", "squats"]),
        ), patch(
            "app.services.workout_service.send_telegram_message",
            new_callable=AsyncMock,
        ) as mock_send:
            await _handle_challenge_prompt("100 running", 111, 1, 42)

            mock_send.assert_called_once()
            msg = mock_send.call_args[0][1]
            assert "running" in msg
            assert "pushups, squats" in msg
            assert 111 not in _flows

    @pytest.mark.asyncio
    async def test_validation_error_clears_flow(self):
        start_flow(111, chat_id=42)

        with patch(
            "app.services.workout_service.send_chat_action", new_callable=AsyncMock
        ), patch(
            "app.services.workout_service.validate_and_prepare_challenge",
            new_callable=AsyncMock,
            side_effect=ValueError("Duration too long"),
        ), patch(
            "app.services.workout_service.send_telegram_message",
            new_callable=AsyncMock,
        ) as mock_send:
            await _handle_challenge_prompt("invalid prompt", 111, 1, 42)

            mock_send.assert_called_once()
            assert "Duration too long" in mock_send.call_args[0][1]
            assert 111 not in _flows


# ─── process_callback_query ──────────────────────────────────────────────


class TestProcessCallbackQuery:
    @pytest.mark.asyncio
    async def test_confirm_happy_path(self):
        start_flow(111, chat_id=42)
        set_awaiting_confirm(111, _make_parsed(), _make_challenge_data())

        with patch(
            "app.services.workout_service.app_user_repo.get_by_telegram_user_id",
            new_callable=AsyncMock,
            return_value=_make_approved_user(),
        ), patch(
            "app.services.workout_service.create_challenge",
            new_callable=AsyncMock,
            return_value=_make_challenge_out(),
        ) as mock_create, patch(
            "app.services.workout_service.send_telegram_message",
            new_callable=AsyncMock,
        ) as mock_send, patch(
            "app.services.workout_service.answer_callback_query",
            new_callable=AsyncMock,
        ) as mock_answer:
            await process_callback_query("cb123", "confirm_challenge", 111, 42)

            mock_create.assert_called_once()
            mock_send.assert_called_once()
            assert "Challenge Created" in mock_send.call_args[0][1]
            # Messages sent to original flow chat_id (42)
            assert mock_send.call_args[0][0] == 42
            mock_answer.assert_called_once_with("cb123", "Challenge created!")
            assert 111 not in _flows

    @pytest.mark.asyncio
    async def test_confirm_uses_flow_chat_id_not_callback_chat_id(self):
        """Ensure messages go to the chat where /challenge was started."""
        start_flow(111, chat_id=42)
        set_awaiting_confirm(111, _make_parsed(), _make_challenge_data())

        with patch(
            "app.services.workout_service.app_user_repo.get_by_telegram_user_id",
            new_callable=AsyncMock,
            return_value=_make_approved_user(),
        ), patch(
            "app.services.workout_service.create_challenge",
            new_callable=AsyncMock,
            return_value=_make_challenge_out(),
        ), patch(
            "app.services.workout_service.send_telegram_message",
            new_callable=AsyncMock,
        ) as mock_send, patch(
            "app.services.workout_service.answer_callback_query",
            new_callable=AsyncMock,
        ):
            # Pass a different chat_id (99) to simulate callback from different context
            await process_callback_query("cb123", "confirm_challenge", 111, 99)

            # Should use flow.chat_id (42), NOT the callback chat_id (99)
            assert mock_send.call_args[0][0] == 42

    @pytest.mark.asyncio
    async def test_confirm_expired_session(self):
        # No flow started
        with patch(
            "app.services.workout_service.answer_callback_query",
            new_callable=AsyncMock,
        ) as mock_answer:
            await process_callback_query("cb123", "confirm_challenge", 111, 42)

            mock_answer.assert_called_once_with(
                "cb123", "Session expired. Send /challenge to start again."
            )

    @pytest.mark.asyncio
    async def test_confirm_wrong_step(self):
        start_flow(111, chat_id=42)  # step = "awaiting_prompt", not "awaiting_confirm"

        with patch(
            "app.services.workout_service.answer_callback_query",
            new_callable=AsyncMock,
        ) as mock_answer:
            await process_callback_query("cb123", "confirm_challenge", 111, 42)

            mock_answer.assert_called_once_with(
                "cb123", "Session expired. Send /challenge to start again."
            )

    @pytest.mark.asyncio
    async def test_confirm_unapproved_user(self):
        start_flow(111, chat_id=42)
        set_awaiting_confirm(111, _make_parsed(), _make_challenge_data())

        with patch(
            "app.services.workout_service.app_user_repo.get_by_telegram_user_id",
            new_callable=AsyncMock,
            return_value=_make_unapproved_user(),
        ), patch(
            "app.services.workout_service.answer_callback_query",
            new_callable=AsyncMock,
        ) as mock_answer:
            await process_callback_query("cb123", "confirm_challenge", 111, 42)

            mock_answer.assert_called_once_with("cb123", "User not found or not approved.")
            assert 111 not in _flows

    @pytest.mark.asyncio
    async def test_confirm_user_not_found(self):
        start_flow(111, chat_id=42)
        set_awaiting_confirm(111, _make_parsed(), _make_challenge_data())

        with patch(
            "app.services.workout_service.app_user_repo.get_by_telegram_user_id",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.services.workout_service.answer_callback_query",
            new_callable=AsyncMock,
        ) as mock_answer:
            await process_callback_query("cb123", "confirm_challenge", 111, 42)

            mock_answer.assert_called_once_with("cb123", "User not found or not approved.")
            assert 111 not in _flows

    @pytest.mark.asyncio
    async def test_confirm_create_exception(self):
        start_flow(111, chat_id=42)
        set_awaiting_confirm(111, _make_parsed(), _make_challenge_data())

        with patch(
            "app.services.workout_service.app_user_repo.get_by_telegram_user_id",
            new_callable=AsyncMock,
            return_value=_make_approved_user(),
        ), patch(
            "app.services.workout_service.create_challenge",
            new_callable=AsyncMock,
            side_effect=ValueError("DB error"),
        ), patch(
            "app.services.workout_service.send_telegram_message",
            new_callable=AsyncMock,
        ) as mock_send, patch(
            "app.services.workout_service.answer_callback_query",
            new_callable=AsyncMock,
        ) as mock_answer:
            await process_callback_query("cb123", "confirm_challenge", 111, 42)

            assert "Failed to create challenge" in mock_send.call_args[0][1]
            mock_answer.assert_called_once_with("cb123", "Error creating challenge.")
            assert 111 not in _flows

    @pytest.mark.asyncio
    async def test_cancel_happy_path(self):
        start_flow(111, chat_id=42)
        set_awaiting_confirm(111, _make_parsed(), _make_challenge_data())

        with patch(
            "app.services.workout_service.send_telegram_message",
            new_callable=AsyncMock,
        ) as mock_send, patch(
            "app.services.workout_service.answer_callback_query",
            new_callable=AsyncMock,
        ) as mock_answer:
            await process_callback_query("cb123", "cancel_challenge", 111, 42)

            mock_send.assert_called_once()
            assert "cancelled" in mock_send.call_args[0][1].lower()
            # Uses flow.chat_id
            assert mock_send.call_args[0][0] == 42
            mock_answer.assert_called_once_with("cb123", "Cancelled.")
            assert 111 not in _flows

    @pytest.mark.asyncio
    async def test_cancel_expired_session(self):
        # No flow exists
        with patch(
            "app.services.workout_service.answer_callback_query",
            new_callable=AsyncMock,
        ) as mock_answer:
            await process_callback_query("cb123", "cancel_challenge", 111, 42)

            mock_answer.assert_called_once_with(
                "cb123", "Session expired. Send /challenge to start again."
            )

    @pytest.mark.asyncio
    async def test_unknown_callback_data(self):
        with patch(
            "app.services.workout_service.answer_callback_query",
            new_callable=AsyncMock,
        ) as mock_answer:
            await process_callback_query("cb123", "unknown_action", 111, 42)

            mock_answer.assert_called_once_with("cb123")
