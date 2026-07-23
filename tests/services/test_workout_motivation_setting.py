"""Tests for the per-user workout-log motivation toggle (feature 0021).

Exercises process_incoming_message() with an in-window challenge and a valid
parse, asserting that is_workout_motivation_active gates the LLM motivational
line appended to the Telegram reply. Reminders are out of scope and not tested
here.
"""

from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core import setup_django

setup_django()

from app.services.workout_service import process_incoming_message
from src.core.models import AppUser as AppUserModel

MOTIVATION_MARKER = "MOTIVATION_MARKER_1234"


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


def _base_patches(motivation_active: bool):
    """Base patch set with an explicit is_workout_motivation_active stub.

    The gate reads ``user_settings.is_workout_motivation_active``; a bare async
    mock would return a truthy Mock attribute and run the enabled path "by
    accident". We pin the flag with a real stub so assertions reflect behavior.
    """
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
            return_value=SimpleNamespace(
                is_workout_motivation_active=motivation_active
            ),
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


def _challenge_context():
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
    return challenge, etype


async def _run(motivation_active: bool):
    patches = _base_patches(motivation_active)
    challenge, etype = _challenge_context()

    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6] as mock_send,
        patches[7] as mock_list,
        patches[8],
        patches[9],
        patch(
            "app.services.workout_service.exercise_type_repo.get_by_ids",
            new_callable=AsyncMock,
            return_value=[etype],
        ),
        patch(
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
        ),
        patch(
            "app.services.workout_service.get_exercise_stats_and_message",
            new_callable=AsyncMock,
            return_value=(
                "<b>Push-ups</b> Day 5/30",
                {
                    "challenge_id": 1,
                    "cumulative_total": 25,
                    "day_number": 5,
                    "status": "on_track",
                    "today_total": 25,
                },
            ),
        ),
        patch(
            "app.services.workout_service.user_stats_repo.increment_total",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.workout_service._check_all_challenges_complete",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "app.services.workout_service.generate_motivational_response",
            return_value=MOTIVATION_MARKER,
        ) as mock_motivation,
        patch(
            "app.services.workout_service._to_app_exercise_type",
            side_effect=lambda t: t,
        ),
    ):
        mock_list.return_value = [challenge]

        await process_incoming_message(
            text="25 pushups",
            chat_id=42,
            telegram_user_id=123456789,
            first_name="Test",
            username="testuser",
        )

    sent_texts = [c.args[1] for c in mock_send.await_args_list]
    return mock_motivation, sent_texts


@pytest.mark.asyncio
async def test_motivation_enabled_appends_line():
    """Default-enabled: LLM called once, reply carries the motivational line."""
    mock_motivation, sent_texts = await _run(motivation_active=True)

    mock_motivation.assert_called_once()
    # Stats line present.
    assert any("Push-ups" in t for t in sent_texts)
    # Motivational suffix present, wrapped in <i>…</i> per assembly.
    assert any(f"<i>{MOTIVATION_MARKER}</i>" in t for t in sent_texts)


@pytest.mark.asyncio
async def test_motivation_disabled_skips_line_and_llm():
    """Disabled: no LLM call, no motivational line, no fallback string."""
    mock_motivation, sent_texts = await _run(motivation_active=False)

    mock_motivation.assert_not_called()
    # Stats line still present.
    assert any("Push-ups" in t for t in sent_texts)
    # No motivational marker and no hardcoded fallback.
    joined = " ".join(sent_texts)
    assert MOTIVATION_MARKER not in joined
    assert "Keep crushing it" not in joined
