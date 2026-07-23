"""Unit tests for challenge deactivation helpers (feature 0020)."""

from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.api import services as api_services
from src.api.services import TZ


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
async def test_list_current_active_challenges_does_not_sweep_on_read(mock_repos):
    """The hot read path must NOT run the deactivation sweep (perf).

    ``get_current_active`` already excludes expired challenges by date window,
    so clearing ``is_active`` is left to the evening reminder sweep instead of
    a DB write on every workout parse/log.
    """
    mock_repos["challenge"].get_current_active = AsyncMock(return_value=[])

    with patch(
        "src.api.services.deactivate_expired_challenges",
        new_callable=AsyncMock,
    ) as mock_sweep:
        result = await api_services.list_current_active_challenges(
            target_date=date(2026, 7, 23), user_id=9
        )

    assert result == []
    mock_sweep.assert_not_awaited()
