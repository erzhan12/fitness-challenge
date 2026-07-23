"""Tests for empty in-window challenge handling in process_incoming_message (feature 0020)."""

from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core import setup_django

setup_django()

from app.services.workout_service import process_incoming_message
from src.core.models import AppUser as AppUserModel

NO_ACTIVE_CHALLENGES_MSG = (
    "No active challenges right now. Create one with /challenge "
    "or extend an existing challenge's dates."
)


async def _noop_keep_typing(chat_id, stop_event):
    return None


def _make_approved_user() -> AppUserModel:
    return AppUserModel(
        id=1,
        telegram_user_id=123456789,
        username="testuser",
        first_name="Test",
        timezone="Asia/Almaty",
        status="approved",
        created_at=datetime.now(dt_timezone.utc),
    )


def _base_patches():
    return [
        patch(
            "app.services.workout_service.app_settings_repo.get_singleton",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(is_registration_open=True),
        ),
        patch(
            "app.services.workout_service.app_user_repo.get_by_telegram_user_id",
            new_callable=AsyncMock,
            return_value=_make_approved_user(),
        ),
        patch(
            "app.services.workout_service.user_settings_repo.update_chat_id",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.workout_service.send_chat_action",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.workout_service.keep_typing",
            new=_noop_keep_typing,
        ),
        patch(
            "app.services.workout_service.get_flow",
            return_value=None,
        ),
        patch(
            "app.services.workout_service.send_telegram_message",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.workout_service.list_current_active_challenges",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.workout_service.log_repo.create",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.workout_service.get_exercise_types",
            new_callable=AsyncMock,
        ),
    ]


@pytest.mark.asyncio
async def test_process_incoming_no_active_challenges_sends_message_and_skips_log():
    patches = _base_patches()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
         patches[6] as mock_send, patches[7] as mock_list, patches[8] as mock_create, \
         patches[9] as mock_get_types:
        mock_list.return_value = []

        await process_incoming_message(
            text="25 pushups",
            chat_id=42,
            telegram_user_id=123456789,
            first_name="Test",
            username="testuser",
        )

        mock_send.assert_awaited()
        sent_text = mock_send.await_args.args[1]
        assert sent_text == NO_ACTIVE_CHALLENGES_MSG
        mock_create.assert_not_awaited()
        mock_get_types.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_incoming_with_challenge_does_not_use_all_types_fallback():
    """When an in-window challenge exists, do not fall back to get_exercise_types()."""
    patches = _base_patches()
    challenge = {
        "id": 1,
        "exercise_type_id": 1,
        "start_date": "2026-07-01",
        "end_date": "2026-07-31",
        "daily_target": 33,
        "challenge_name": "Pushups",
        "is_active": True,
        "is_default": True,
    }
    etype = SimpleNamespace(
        id=1,
        name="pushups",
        display_name="Push-ups",
        emoji="💪",
        unit="reps",
        aliases=["push-up"],
        is_active=True,
    )

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
         patches[6] as mock_send, patches[7] as mock_list, patches[8], \
         patches[9] as mock_get_types, patch(
        "app.services.workout_service.exercise_type_repo.get_by_ids",
        new_callable=AsyncMock,
        return_value=[etype],
    ), patch(
        "app.services.workout_service.parse_workout_message",
        return_value=SimpleNamespace(
            is_valid=True,
            error_reason=None,
            entries=[
                SimpleNamespace(
                    exercise_type_name="pushups",
                    count=25,
                    duration_seconds=None,
                    notes=None,
                    confidence=0.9,
                )
            ],
        ),
    ), patch(
        "app.services.workout_service.get_exercise_stats_and_message",
        new_callable=AsyncMock,
        return_value=("<b>Push-ups</b> Day 5/30", {"challenge_id": 1, "cumulative_total": 25, "day_number": 5, "status": "on_track", "today_total": 25}),
    ), patch(
        "app.services.workout_service.user_stats_repo.increment_total",
        new_callable=AsyncMock,
    ), patch(
        "app.services.workout_service._check_all_challenges_complete",
        new_callable=AsyncMock,
        return_value=False,
    ), patch(
        "app.services.workout_service.generate_motivational_response",
        return_value="Nice!",
    ), patch(
        "app.services.workout_service._to_app_exercise_type",
        side_effect=lambda t: t,
    ):
        mock_list.return_value = [challenge]

        await process_incoming_message(
            text="25 pushups",
            chat_id=42,
            telegram_user_id=123456789,
            first_name="Test",
            username="testuser",
        )

        mock_get_types.assert_not_awaited()
        # Reply should mention the challenged exercise, not invent Day 1/30 · 990
        sent_texts = [c.args[1] for c in mock_send.await_args_list]
        assert any("Push-ups" in t or "pushups" in t.lower() for t in sent_texts)
