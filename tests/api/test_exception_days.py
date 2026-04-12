"""Tests for /api/v1/challenges/{id}/exception-days endpoints (feature 0018)."""

from datetime import date, datetime, timezone
from types import SimpleNamespace

from tests.api.conftest import make_challenge_model


def _exception_row(challenge_id: int, exc_date: date, reason: str = ""):
    """Build a SimpleNamespace standing in for a ChallengeExceptionDay model row.

    The router only touches ``.id``, ``.date``, ``.reason`` and ``.created_at``,
    so we don't need a real Django model instance.
    """
    return SimpleNamespace(
        id=hash((challenge_id, exc_date.toordinal())) & 0xFFFFFF,
        challenge_id=challenge_id,
        date=exc_date,
        reason=reason,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )


class TestListExceptionDays:
    """GET /api/v1/challenges/{id}/exception-days."""

    def test_list_returns_rows_ordered(
        self, client, mock_repos, mock_challenge_data, user_context_headers
    ):
        """GET returns the rows from the repo (no auth header required)."""
        # Owner check goes through the repo's user_id filter, simulated here.
        mock_repos["challenge_exception_day"].list_for_challenge.return_value = [
            _exception_row(1, date(2026, 4, 18), "Travel"),
            _exception_row(1, date(2026, 4, 25), ""),
        ]

        response = client.get(
            "/api/v1/challenges/1/exception-days", headers=user_context_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["date"] == "2026-04-18"
        assert data[0]["reason"] == "Travel"
        assert data[1]["date"] == "2026-04-25"
        assert data[1]["reason"] == ""

    def test_list_empty(self, client, mock_repos, user_context_headers):
        mock_repos["challenge_exception_day"].list_for_challenge.return_value = []

        response = client.get(
            "/api/v1/challenges/1/exception-days", headers=user_context_headers
        )

        assert response.status_code == 200
        assert response.json() == []


class TestCreateExceptionDay:
    """POST /api/v1/challenges/{id}/exception-days."""

    def test_post_in_window_succeeds(
        self,
        client,
        mock_repos,
        mock_challenge_data,
        auth_and_user_headers,
    ):
        """An in-window date is added idempotently and returns 201."""
        challenge = make_challenge_model(
            {**mock_challenge_data, "start_date": "2026-04-01", "end_date": "2026-04-30"}
        )
        mock_repos["challenge"].get_by_id.return_value = challenge
        new_row = _exception_row(1, date(2026, 4, 20), "Easter")
        mock_repos["challenge_exception_day"].add.return_value = (new_row, True)

        response = client.post(
            "/api/v1/challenges/1/exception-days",
            json={"date": "2026-04-20", "reason": "Easter"},
            headers=auth_and_user_headers,
        )

        assert response.status_code == 201
        body = response.json()
        assert body["date"] == "2026-04-20"
        assert body["reason"] == "Easter"
        # The repo's add() must have been called with the parsed date.
        mock_repos["challenge_exception_day"].add.assert_awaited_once()

    def test_post_out_of_window_returns_400(
        self,
        client,
        mock_repos,
        mock_challenge_data,
        auth_and_user_headers,
    ):
        """Dates outside the challenge window are rejected with 400."""
        challenge = make_challenge_model(
            {**mock_challenge_data, "start_date": "2026-04-01", "end_date": "2026-04-30"}
        )
        mock_repos["challenge"].get_by_id.return_value = challenge

        response = client.post(
            "/api/v1/challenges/1/exception-days",
            json={"date": "2026-05-15"},
            headers=auth_and_user_headers,
        )

        assert response.status_code == 400
        assert "outside" in response.json()["detail"].lower()
        # And we never called the repo for the out-of-window add.
        mock_repos["challenge_exception_day"].add.assert_not_awaited()

    def test_post_idempotent_duplicate(
        self,
        client,
        mock_repos,
        mock_challenge_data,
        auth_and_user_headers,
    ):
        """A repeated POST for the same date returns 201 (idempotent add)."""
        challenge = make_challenge_model(
            {**mock_challenge_data, "start_date": "2026-04-01", "end_date": "2026-04-30"}
        )
        mock_repos["challenge"].get_by_id.return_value = challenge
        existing = _exception_row(1, date(2026, 4, 20), "Easter")
        # add() returns (row, created=False) on duplicates
        mock_repos["challenge_exception_day"].add.return_value = (existing, False)

        response = client.post(
            "/api/v1/challenges/1/exception-days",
            json={"date": "2026-04-20", "reason": "Easter"},
            headers=auth_and_user_headers,
        )

        assert response.status_code == 201
        assert response.json()["date"] == "2026-04-20"

    def test_post_unknown_challenge_returns_404(
        self, client, mock_repos, auth_and_user_headers
    ):
        mock_repos["challenge"].get_by_id.return_value = None

        response = client.post(
            "/api/v1/challenges/999/exception-days",
            json={"date": "2026-04-20"},
            headers=auth_and_user_headers,
        )

        assert response.status_code == 404

    def test_post_requires_api_key(self, client, user_context_headers):
        """POST without API key is rejected with 401 — write endpoint is protected."""
        response = client.post(
            "/api/v1/challenges/1/exception-days",
            json={"date": "2026-04-20"},
            headers=user_context_headers,
        )
        assert response.status_code == 401


class TestDeleteExceptionDay:
    """DELETE /api/v1/challenges/{id}/exception-days/{date}."""

    def test_delete_success(self, client, mock_repos, auth_and_user_headers):
        mock_repos["challenge_exception_day"].remove.return_value = True

        response = client.delete(
            "/api/v1/challenges/1/exception-days/2026-04-20",
            headers=auth_and_user_headers,
        )

        assert response.status_code == 204

    def test_delete_missing_returns_404(
        self, client, mock_repos, auth_and_user_headers
    ):
        mock_repos["challenge_exception_day"].remove.return_value = False

        response = client.delete(
            "/api/v1/challenges/1/exception-days/2026-04-20",
            headers=auth_and_user_headers,
        )

        assert response.status_code == 404

    def test_delete_invalid_date_returns_422(
        self, client, mock_repos, auth_and_user_headers
    ):
        response = client.delete(
            "/api/v1/challenges/1/exception-days/not-a-date",
            headers=auth_and_user_headers,
        )

        # FastAPI path validation rejects non-ISO dates with 422.
        assert response.status_code == 422

    def test_delete_requires_api_key(self, client):
        response = client.delete("/api/v1/challenges/1/exception-days/2026-04-20")
        assert response.status_code == 401
