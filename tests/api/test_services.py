"""Unit tests for challenge deactivation helpers (feature 0020)."""

from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.api import services as api_services
from src.api.services import TZ
from tests.api.conftest import make_challenge_model


@pytest.mark.asyncio
async def test_deactivate_expired_challenges_no_arg_uses_today(mock_repos):
    mock_repos["challenge"].deactivate_expired = AsyncMock(return_value=3)
    fixed_today = date(2026, 7, 23)

    with patch("src.api.services.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 7, 23, 12, 0, 0, tzinfo=TZ)
        count = await api_services.deactivate_expired_challenges(user_id=7)

    assert count == 3
    mock_repos["challenge"].deactivate_expired.assert_awaited_once_with(
        fixed_today, user_id=7
    )


@pytest.mark.asyncio
async def test_deactivate_expired_challenges_explicit_target_date(mock_repos):
    mock_repos["challenge"].deactivate_expired = AsyncMock(return_value=1)
    cutoff = date(2026, 1, 15)

    count = await api_services.deactivate_expired_challenges(
        target_date=cutoff, user_id=None
    )

    assert count == 1
    mock_repos["challenge"].deactivate_expired.assert_awaited_once_with(
        cutoff, user_id=None
    )


@pytest.mark.asyncio
async def test_list_current_active_challenges_sweeps_before_read(mock_repos):
    order: list[str] = []

    async def _track_deactivate(*args, **kwargs):
        order.append("deactivate")
        return 0

    async def _track_get(*args, **kwargs):
        order.append("get_current_active")
        return []

    mock_repos["challenge"].deactivate_expired = AsyncMock(side_effect=_track_deactivate)
    mock_repos["challenge"].get_current_active = AsyncMock(side_effect=_track_get)

    with patch(
        "src.api.services.deactivate_expired_challenges",
        new_callable=AsyncMock,
        side_effect=_track_deactivate,
    ) as mock_sweep:
        result = await api_services.list_current_active_challenges(
            target_date=date(2026, 7, 23), user_id=9
        )

    assert result == []
    assert order == ["deactivate", "get_current_active"]
    # Must not thread the display/target_date into the sweep.
    mock_sweep.assert_awaited_once_with(user_id=9)


@pytest.mark.asyncio
async def test_list_current_active_challenges_sweep_failure_is_swallowed(mock_repos):
    challenge_model = make_challenge_model(
        {
            "id": 1,
            "exercise_type_id": 1,
            "start_date": "2026-07-01",
            "end_date": "2026-07-31",
            "daily_target": 33,
            "challenge_name": "Pushups",
            "is_active": True,
            "is_default": False,
        }
    )
    mock_repos["challenge"].get_current_active = AsyncMock(
        return_value=[challenge_model]
    )

    with patch(
        "src.api.services.deactivate_expired_challenges",
        new_callable=AsyncMock,
        side_effect=RuntimeError("db down"),
    ):
        result = await api_services.list_current_active_challenges(user_id=1)

    assert len(result) == 1
    assert result[0]["id"] == 1


@pytest.mark.asyncio
async def test_list_current_active_challenges_forwards_user_id_to_sweep(mock_repos):
    mock_repos["challenge"].get_current_active = AsyncMock(return_value=[])

    with patch(
        "src.api.services.deactivate_expired_challenges",
        new_callable=AsyncMock,
        return_value=0,
    ) as mock_sweep:
        await api_services.list_current_active_challenges(user_id=55)

    mock_sweep.assert_awaited_once_with(user_id=55)
