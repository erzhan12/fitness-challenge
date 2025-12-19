import json
from unittest.mock import Mock, patch

from app.models import ExerciseType
from app.services.openai_service import parse_workout_message


def _mock_llm_response(payload: dict) -> Mock:
    response = Mock()
    response.choices = [Mock(message=Mock(content=json.dumps(payload)))]
    return response


def test_deterministic_number_only_single_active_type_skips_llm():
    etype = ExerciseType(
        id=1,
        name="pushups",
        display_name="Push-ups",
        emoji="💪",
        unit="reps",
        aliases=[],
    )

    with patch("app.services.openai_service.client.chat.completions.create") as create:
        result = parse_workout_message("25", [etype])

    assert create.call_count == 0
    assert result.is_valid is True
    assert [(e.exercise_type_name, e.count) for e in result.entries] == [("pushups", 25)]


def test_deterministic_number_word_pair_matches_alias_punctuation_skips_llm():
    etype = ExerciseType(
        id=1,
        name="pushups",
        display_name="Push-ups",
        emoji="💪",
        unit="reps",
        aliases=[],
    )
    other = ExerciseType(
        id=2,
        name="squats",
        display_name="Squats",
        emoji="🏋️",
        unit="reps",
        aliases=["squat"],
    )

    with patch("app.services.openai_service.client.chat.completions.create") as create:
        result = parse_workout_message("25 push-up", [etype, other])

    assert create.call_count == 0
    assert result.is_valid is True
    assert [(e.exercise_type_name, e.count) for e in result.entries] == [("pushups", 25)]


def test_deterministic_multiple_pairs_parses_all_skips_llm():
    pushups = ExerciseType(
        id=1,
        name="pushups",
        display_name="Push-ups",
        emoji="💪",
        unit="reps",
        aliases=["push-up", "push up"],
    )
    squats = ExerciseType(
        id=2,
        name="squats",
        display_name="Squats",
        emoji="🏋️",
        unit="reps",
        aliases=["squat"],
    )

    with patch("app.services.openai_service.client.chat.completions.create") as create:
        result = parse_workout_message("20 pushups and 30 squats", [pushups, squats])

    assert create.call_count == 0
    assert result.is_valid is True
    assert [(e.exercise_type_name, e.count) for e in result.entries] == [
        ("pushups", 20),
        ("squats", 30),
    ]


def test_ambiguous_deterministic_parse_falls_back_to_llm():
    pushups = ExerciseType(
        id=1,
        name="pushups",
        display_name="Push-ups",
        emoji="💪",
        unit="reps",
        aliases=["press"],
    )
    bench = ExerciseType(
        id=2,
        name="benchpress",
        display_name="Bench press",
        emoji="🏋️",
        unit="reps",
        aliases=["press"],
    )

    llm_payload = {
        "entries": [
            {
                "exercise_type_name": "pushups",
                "count": 10,
                "duration_seconds": None,
                "notes": None,
                "confidence": 0.9,
            }
        ],
        "is_valid": True,
        "error_reason": None,
    }

    with patch(
        "app.services.openai_service.client.chat.completions.create",
        return_value=_mock_llm_response(llm_payload),
    ) as create:
        result = parse_workout_message("10 press", [pushups, bench])

    assert create.call_count == 1
    assert result.is_valid is True
    assert [(e.exercise_type_name, e.count) for e in result.entries] == [("pushups", 10)]


def test_unmatched_deterministic_parse_falls_back_to_llm():
    pushups = ExerciseType(
        id=1,
        name="pushups",
        display_name="Push-ups",
        emoji="💪",
        unit="reps",
        aliases=[],
    )

    llm_payload = {
        "entries": [],
        "is_valid": False,
        "error_reason": "Could not understand",
    }

    with patch(
        "app.services.openai_service.client.chat.completions.create",
        return_value=_mock_llm_response(llm_payload),
    ) as create:
        result = parse_workout_message("10 flarb", [pushups])

    assert create.call_count == 1
    assert result.is_valid is False
    assert result.entries == []

