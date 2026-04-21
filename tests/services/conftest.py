"""Shared fixtures for tests/services/.

The reminder/habit-reward consumers in ``app.services.workout_service`` query
``challenge_exception_day_repo`` (added in feature 0018). The existing tests
patch ``challenge_repo`` and ``log_repo`` per-test but never touch the new
exception-day repo, which means without this fixture the real Django
``sync_to_async`` repo runs against an unmigrated SQLite test DB.

This autouse fixture replaces the module-level reference with a Mock that
returns "no exception days" by default, so existing reminder/habit tests
keep their original semantics. Tests that need exception data can still
override the mock per-test.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch


@pytest.fixture(autouse=True)
def _mock_challenge_exception_day_repo():
    """Patch the challenge_exception_day_repo used by app.services.workout_service.

    Default behavior: no exceptions for any challenge — preserves the
    pre-feature-0018 baseline math used by existing reminder tests.
    """
    repo = Mock()
    repo.list_for_challenge = AsyncMock(return_value=[])
    repo.list_dates_for_challenges = AsyncMock(return_value={})
    repo.add = AsyncMock(return_value=(None, False))
    repo.remove = AsyncMock(return_value=False)
    repo.replace_dates = AsyncMock(return_value=[])

    with patch(
        "app.services.workout_service.challenge_exception_day_repo", repo
    ):
        yield repo
