"""Unit tests for parse_challenge_prompt() in app/services/openai_service.py."""

import json
from datetime import date
from unittest.mock import Mock, patch

from app.models import ExerciseType
from app.services.openai_service import parse_challenge_prompt


def _make_exercise(name="pushups", display="Push-ups", aliases=None):
    return ExerciseType(
        id=1,
        name=name,
        display_name=display,
        emoji="💪",
        unit="reps",
        aliases=aliases or [],
    )


def _mock_llm_response(payload: dict) -> Mock:
    response = Mock()
    response.choices = [Mock(message=Mock(content=json.dumps(payload)))]
    return response


TODAY = date(2026, 3, 4)


class TestParseChallengePrompt:
    """Tests for parse_challenge_prompt()."""

    def test_parse_target_total_only(self):
        """LLM returns target_total only; daily_target is null."""
        llm_payload = {
            "exercise_type_name": "pushups",
            "start_date": "2026-03-05",
            "duration_days": 30,
            "target_total": 2000,
            "daily_target": None,
            "challenge_name": "30-Day Push-ups Challenge",
            "is_valid": True,
            "error_reason": None,
        }
        exercise = _make_exercise()

        with patch("app.services.openai_service.client.chat.completions.create") as mock_create:
            mock_create.return_value = _mock_llm_response(llm_payload)
            result = parse_challenge_prompt(
                "pushups challenge for 30 days starting tomorrow 2000 reps total",
                [exercise],
                today=TODAY,
            )

        assert result["is_valid"] is True
        assert result["exercise_type_name"] == "pushups"
        assert result["start_date"] == "2026-03-05"
        assert result["duration_days"] == 30
        assert result["target_total"] == 2000
        assert result["daily_target"] is None
        assert result["challenge_name"] == "30-Day Push-ups Challenge"
        mock_create.assert_called_once()

    def test_parse_daily_target_only(self):
        """LLM returns daily_target only; target_total is null."""
        llm_payload = {
            "exercise_type_name": "pushups",
            "start_date": "2026-03-04",
            "duration_days": 30,
            "target_total": None,
            "daily_target": 50,
            "challenge_name": "Daily 50 Push-ups",
            "is_valid": True,
            "error_reason": None,
        }
        exercise = _make_exercise()

        with patch("app.services.openai_service.client.chat.completions.create") as mock_create:
            mock_create.return_value = _mock_llm_response(llm_payload)
            result = parse_challenge_prompt("50 pushups daily for 30 days", [exercise], today=TODAY)

        assert result["is_valid"] is True
        assert result["daily_target"] == 50
        assert result["target_total"] is None

    def test_parse_both_targets_provided(self):
        """LLM returns both target_total and daily_target."""
        llm_payload = {
            "exercise_type_name": "pushups",
            "start_date": "2026-03-04",
            "duration_days": 30,
            "target_total": 1500,
            "daily_target": 50,
            "challenge_name": "Push-ups Challenge",
            "is_valid": True,
            "error_reason": None,
        }
        exercise = _make_exercise()

        with patch("app.services.openai_service.client.chat.completions.create") as mock_create:
            mock_create.return_value = _mock_llm_response(llm_payload)
            result = parse_challenge_prompt(
                "pushups for 30 days, 1500 total and 50 daily",
                [exercise],
                today=TODAY,
            )

        assert result["is_valid"] is True
        assert result["target_total"] == 1500
        assert result["daily_target"] == 50

    def test_parse_invalid_exercise_type(self):
        """LLM returns is_valid=False when exercise type not recognized."""
        llm_payload = {
            "exercise_type_name": None,
            "start_date": None,
            "duration_days": None,
            "target_total": None,
            "daily_target": None,
            "challenge_name": None,
            "is_valid": False,
            "error_reason": "Could not match exercise type 'swimming' to any available types.",
        }
        exercise = _make_exercise()

        with patch("app.services.openai_service.client.chat.completions.create") as mock_create:
            mock_create.return_value = _mock_llm_response(llm_payload)
            result = parse_challenge_prompt("swimming challenge for 30 days", [exercise], today=TODAY)

        assert result["is_valid"] is False
        assert result["error_reason"] is not None

    def test_parse_relative_date_tomorrow(self):
        """LLM resolves 'tomorrow' relative to today."""
        llm_payload = {
            "exercise_type_name": "pushups",
            "start_date": "2026-03-05",  # tomorrow relative to TODAY=2026-03-04
            "duration_days": 30,
            "target_total": 1000,
            "daily_target": None,
            "challenge_name": "Push-ups Challenge",
            "is_valid": True,
            "error_reason": None,
        }
        exercise = _make_exercise()

        with patch("app.services.openai_service.client.chat.completions.create") as mock_create:
            mock_create.return_value = _mock_llm_response(llm_payload)
            result = parse_challenge_prompt(
                "1000 pushups starting tomorrow for 30 days", [exercise], today=TODAY
            )

        assert result["start_date"] == "2026-03-05"

    def test_llm_api_failure_raises_llm_unavailable(self):
        """LLM API exception raises LLMUnavailableError."""
        import pytest
        from app.services.openai_service import LLMUnavailableError

        exercise = _make_exercise()

        with patch("app.services.openai_service.client.chat.completions.create") as mock_create:
            mock_create.side_effect = Exception("Connection error")
            with pytest.raises(LLMUnavailableError, match="Connection error"):
                parse_challenge_prompt("some challenge", [exercise], today=TODAY)

    def test_today_passed_in_system_prompt(self):
        """Today's date is included in the LLM system prompt."""
        llm_payload = {
            "exercise_type_name": "pushups",
            "start_date": "2026-03-04",
            "duration_days": 30,
            "target_total": 900,
            "daily_target": None,
            "challenge_name": "Push-ups Challenge",
            "is_valid": True,
            "error_reason": None,
        }
        exercise = _make_exercise()

        with patch("app.services.openai_service.client.chat.completions.create") as mock_create:
            mock_create.return_value = _mock_llm_response(llm_payload)
            parse_challenge_prompt("pushups for 30 days 900 total", [exercise], today=TODAY)

        call_args = mock_create.call_args
        system_msg = call_args[1]["messages"][0]["content"]
        assert "2026-03-04" in system_msg

    def test_exercise_types_included_in_prompt(self):
        """Available exercise types are included in the LLM system prompt."""
        llm_payload = {
            "exercise_type_name": "squats",
            "start_date": "2026-03-04",
            "duration_days": 30,
            "target_total": 600,
            "daily_target": None,
            "challenge_name": "Squats Challenge",
            "is_valid": True,
            "error_reason": None,
        }
        exercises = [
            _make_exercise("pushups", "Push-ups"),
            ExerciseType(id=2, name="squats", display_name="Squats", emoji="🏋️", unit="reps", aliases=["squat"]),
        ]

        with patch("app.services.openai_service.client.chat.completions.create") as mock_create:
            mock_create.return_value = _mock_llm_response(llm_payload)
            parse_challenge_prompt("squats challenge 600 total 30 days", exercises, today=TODAY)

        call_args = mock_create.call_args
        system_msg = call_args[1]["messages"][0]["content"]
        assert "squats" in system_msg
        assert "pushups" in system_msg
