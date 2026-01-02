import pytest
from app.models import ExerciseType
from app.services.workout_service import determine_default_exercise

@pytest.fixture
def exercise_types():
    return [
        ExerciseType(
            id=1,
            name="pushups",
            display_name="Push-ups",
            emoji="💪",
            unit="reps",
            aliases=["pushup"]
        ),
        ExerciseType(
            id=2,
            name="squats",
            display_name="Squats",
            emoji="🏋️",
            unit="reps",
            aliases=["squat"]
        ),
        ExerciseType(
            id=3,
            name="plank",
            display_name="Plank",
            emoji="⏱️",
            unit="min",
            aliases=[]
        )
    ]

def test_single_challenge(exercise_types):
    """Scenario: 1 active challenge (squats)"""
    challenges = [
        {"id": 10, "exercise_type_id": 2, "is_default": False}
    ]
    result = determine_default_exercise(challenges, exercise_types)
    assert result == "squats"

def test_single_challenge_default_true(exercise_types):
    """Scenario: 1 active challenge (squats), marked default (doesn't matter but good to check)"""
    challenges = [
        {"id": 10, "exercise_type_id": 2, "is_default": True}
    ]
    result = determine_default_exercise(challenges, exercise_types)
    assert result == "squats"

def test_multiple_challenges_no_default(exercise_types):
    """Scenario: 2 active challenges, none default -> fallback to pushups"""
    challenges = [
        {"id": 10, "exercise_type_id": 2, "is_default": False}, # squats
        {"id": 11, "exercise_type_id": 3, "is_default": False}, # plank
    ]
    result = determine_default_exercise(challenges, exercise_types)
    assert result == "pushups"

def test_multiple_challenges_one_default(exercise_types):
    """Scenario: 2 active challenges, one default -> use default"""
    challenges = [
        {"id": 10, "exercise_type_id": 2, "is_default": False}, # squats
        {"id": 11, "exercise_type_id": 3, "is_default": True},  # plank
    ]
    result = determine_default_exercise(challenges, exercise_types)
    assert result == "plank"

def test_multiple_challenges_multiple_defaults(exercise_types):
    """Scenario: 2 active challenges, both default -> use lowest ID"""
    challenges = [
        {"id": 20, "exercise_type_id": 3, "is_default": True},  # plank (id 20)
        {"id": 15, "exercise_type_id": 2, "is_default": True},  # squats (id 15)
    ]
    result = determine_default_exercise(challenges, exercise_types)
    # Should pick ID 15 -> squats
    assert result == "squats"

def test_no_challenges(exercise_types):
    """Scenario: No active challenges -> fallback to pushups"""
    challenges = []
    result = determine_default_exercise(challenges, exercise_types)
    assert result == "pushups"

def test_default_challenge_exercise_not_found(exercise_types):
    """Scenario: Default challenge points to unknown exercise type (should fallback)"""
    challenges = [
        {"id": 10, "exercise_type_id": 999, "is_default": True}
    ]
    # Should fallback to pushups because 999 is not in exercise_types
    result = determine_default_exercise(challenges, exercise_types)
    assert result == "pushups"

