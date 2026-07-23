"""Repository-level tests for ExerciseChallengeRepository.deactivate_expired.

Option B from feature 0020: assert query construction via spies on
``ExerciseChallenge.objects.filter`` / queryset ``.update`` (no pytest-django).
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.core import setup_django

setup_django()

from src.core.repositories import ExerciseChallengeRepository


@pytest.mark.asyncio
async def test_deactivate_expired_filters_active_before_reference_date():
    repo = ExerciseChallengeRepository()
    mock_qs = MagicMock()
    mock_qs.update.return_value = 2

    with patch("src.core.repositories.ExerciseChallenge.objects") as mock_objects:
        mock_objects.filter.return_value = mock_qs
        count = await repo.deactivate_expired(date(2026, 7, 23))

    mock_objects.filter.assert_called_once_with(
        is_active=True,
        end_date__lt=date(2026, 7, 23),
    )
    mock_qs.update.assert_called_once_with(is_active=False, is_default=False)
    assert count == 2


@pytest.mark.asyncio
async def test_deactivate_expired_scopes_by_user_id_when_provided():
    repo = ExerciseChallengeRepository()
    mock_qs = MagicMock()
    mock_filtered = MagicMock()
    mock_filtered.update.return_value = 1
    mock_qs.filter.return_value = mock_filtered

    with patch("src.core.repositories.ExerciseChallenge.objects") as mock_objects:
        mock_objects.filter.return_value = mock_qs
        count = await repo.deactivate_expired(date(2026, 7, 23), user_id=42)

    mock_objects.filter.assert_called_once_with(
        is_active=True,
        end_date__lt=date(2026, 7, 23),
    )
    mock_qs.filter.assert_called_once_with(user_id=42)
    mock_filtered.update.assert_called_once_with(is_active=False, is_default=False)
    assert count == 1


@pytest.mark.asyncio
async def test_deactivate_expired_without_user_id_does_not_scope():
    repo = ExerciseChallengeRepository()
    mock_qs = MagicMock()
    mock_qs.update.return_value = 0

    with patch("src.core.repositories.ExerciseChallenge.objects") as mock_objects:
        mock_objects.filter.return_value = mock_qs
        count = await repo.deactivate_expired(date(2026, 1, 1), user_id=None)

    mock_qs.filter.assert_not_called()
    assert count == 0
