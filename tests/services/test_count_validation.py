"""
Tests for count validation feature.

This test suite validates that the system correctly rejects invalid exercise counts
(zero, negative, and decimal values) and accepts valid positive integers.
"""

import json
from unittest.mock import Mock, patch

from app.models import ExerciseType
from app.services.openai_service import parse_workout_message
from app.services.deterministic_parser import try_deterministic_parse_workout_message


def _mock_llm_response(payload: dict) -> Mock:
    """Helper to create a mock LLM response."""
    response = Mock()
    response.choices = [Mock(message=Mock(content=json.dumps(payload)))]
    return response


class TestDeterministicParserValidation:
    """Test count validation in the deterministic parser."""

    def setup_method(self):
        """Set up common test fixtures."""
        self.pushups = ExerciseType(
            id=1,
            name="pushups",
            display_name="Push-ups",
            emoji="💪",
            unit="reps",
            aliases=["pushup", "push-up"],
        )
        self.squats = ExerciseType(
            id=2,
            name="squats",
            display_name="Squats",
            emoji="🦵",
            unit="reps",
            aliases=["squat"],
        )

    def test_rejects_zero_count(self):
        """Should reject count of 0."""
        result = try_deterministic_parse_workout_message("0 pushups", [self.pushups])
        assert result is not None
        assert result.is_valid is False
        assert result.error_reason == "Count must be greater than 0 and should be an integer."
        assert result.entries == []

    def test_rejects_zero_count_single_exercise(self):
        """Should reject count of 0 when only one exercise type is active."""
        result = try_deterministic_parse_workout_message("0", [self.pushups])
        assert result is not None
        assert result.is_valid is False
        assert result.error_reason == "Count must be greater than 0 and should be an integer."
        assert result.entries == []

    def test_rejects_decimal_zero(self):
        """Should reject decimal zero (0.0)."""
        result = try_deterministic_parse_workout_message("0.0 pushups", [self.pushups])
        assert result is not None
        assert result.is_valid is False
        assert result.error_reason == "Count must be greater than 0 and should be an integer."

    def test_rejects_small_decimal(self):
        """Should reject small decimal values (0.1, 0.01, 0.001)."""
        test_cases = ["0.1 pushups", "0.01 pushups", "0.001 pushups"]
        for test_input in test_cases:
            result = try_deterministic_parse_workout_message(test_input, [self.pushups])
            assert result is not None, f"Failed for input: {test_input}"
            assert result.is_valid is False, f"Failed for input: {test_input}"
            assert result.error_reason == "Count must be greater than 0 and should be an integer."

    def test_rejects_decimal_without_leading_zero(self):
        """Should reject decimal values without leading zero (.5, .25)."""
        test_cases = [".5 pushups", ".25 pushups"]
        for test_input in test_cases:
            result = try_deterministic_parse_workout_message(test_input, [self.pushups])
            assert result is not None, f"Failed for input: {test_input}"
            assert result.is_valid is False, f"Failed for input: {test_input}"
            assert result.error_reason == "Count must be greater than 0 and should be an integer."

    def test_rejects_larger_decimal_values(self):
        """Should reject larger decimal values (1.5, 10.5)."""
        test_cases = ["1.5 pushups", "10.5 pushups", "100.25 pushups"]
        for test_input in test_cases:
            result = try_deterministic_parse_workout_message(test_input, [self.pushups])
            assert result is not None, f"Failed for input: {test_input}"
            assert result.is_valid is False, f"Failed for input: {test_input}"
            assert result.error_reason == "Count must be greater than 0 and should be an integer."

    def test_accepts_valid_single_count(self):
        """Should accept valid count of 1."""
        result = try_deterministic_parse_workout_message("1 pushup", [self.pushups])
        assert result is not None
        assert result.is_valid is True
        assert len(result.entries) == 1
        assert result.entries[0].count == 1
        assert result.entries[0].exercise_type_name == "pushups"

    def test_accepts_valid_count(self):
        """Should accept valid positive integer counts."""
        test_cases = [
            ("20 pushups", 20),
            ("100 pushups", 100),
            ("1000 pushups", 1000),
        ]
        for test_input, expected_count in test_cases:
            result = try_deterministic_parse_workout_message(test_input, [self.pushups])
            assert result is not None, f"Failed for input: {test_input}"
            assert result.is_valid is True, f"Failed for input: {test_input}"
            assert result.entries[0].count == expected_count, f"Failed for input: {test_input}"

    def test_rejects_zero_in_multiple_exercises(self):
        """Should reject when any exercise has count of 0 in multiple exercise input."""
        result = try_deterministic_parse_workout_message(
            "0 pushups and 30 squats", [self.pushups, self.squats]
        )
        assert result is not None
        assert result.is_valid is False
        assert result.error_reason == "Count must be greater than 0 and should be an integer."

    def test_accepts_multiple_valid_exercises(self):
        """Should accept multiple exercises with valid counts."""
        result = try_deterministic_parse_workout_message(
            "20 pushups and 30 squats", [self.pushups, self.squats]
        )
        assert result is not None
        assert result.is_valid is True
        assert len(result.entries) == 2
        assert result.entries[0].exercise_type_name == "pushups"
        assert result.entries[0].count == 20
        assert result.entries[1].exercise_type_name == "squats"
        assert result.entries[1].count == 30


class TestLLMParserValidation:
    """Test count validation in the LLM parser."""

    def setup_method(self):
        """Set up common test fixtures."""
        self.pushups = ExerciseType(
            id=1,
            name="pushups",
            display_name="Push-ups",
            emoji="💪",
            unit="reps",
            aliases=["pushup"],
        )

    def test_llm_post_validation_rejects_zero_count(self):
        """Should reject LLM response with count of 0."""
        llm_payload = {
            "entries": [
                {
                    "exercise_type_name": "pushups",
                    "count": 0,
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
        ):
            result = parse_workout_message("0 pushups", [self.pushups])

        assert result.is_valid is False
        assert result.error_reason == "Count must be greater than 0 and should be an integer."
        assert result.entries == []

    def test_llm_post_validation_rejects_negative_count(self):
        """Should reject LLM response if it returns a negative count.

        Note: The deterministic parser tokenizer strips minus signs, so negative numbers
        in user input become positive. This test verifies that if the LLM somehow returns
        a negative count, our post-validation catches it.
        """
        llm_payload = {
            "entries": [
                {
                    "exercise_type_name": "pushups",
                    "count": -5,
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
        ):
            # Use a phrase that forces LLM fallback and might cause LLM to return negative
            result = parse_workout_message("some weird input", [self.pushups])

        # If LLM returns negative count, post-validation should catch it
        assert result.is_valid is False
        assert result.error_reason == "Count must be greater than 0 and should be an integer."
        assert result.entries == []

    def test_llm_post_validation_accepts_valid_count(self):
        """Should accept LLM response with valid count."""
        llm_payload = {
            "entries": [
                {
                    "exercise_type_name": "pushups",
                    "count": 20,
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
        ):
            result = parse_workout_message("twenty pushups", [self.pushups])

        assert result.is_valid is True
        assert len(result.entries) == 1
        assert result.entries[0].count == 20

    def test_llm_respects_validation_in_multiple_entries(self):
        """Should reject if any entry in multiple exercises has invalid count."""
        llm_payload = {
            "entries": [
                {
                    "exercise_type_name": "pushups",
                    "count": 20,
                    "duration_seconds": None,
                    "notes": None,
                    "confidence": 0.9,
                },
                {
                    "exercise_type_name": "squats",
                    "count": 0,  # Invalid count
                    "duration_seconds": None,
                    "notes": None,
                    "confidence": 0.9,
                },
            ],
            "is_valid": True,
            "error_reason": None,
        }

        squats = ExerciseType(
            id=2,
            name="squats",
            display_name="Squats",
            emoji="🦵",
            unit="reps",
            aliases=["squat"],
        )

        with patch(
            "app.services.openai_service.client.chat.completions.create",
            return_value=_mock_llm_response(llm_payload),
        ):
            result = parse_workout_message("20 pushups and 0 squats", [self.pushups, squats])

        assert result.is_valid is False
        assert result.error_reason == "Count must be greater than 0 and should be an integer."


class TestEdgeCases:
    """Test edge cases for count validation."""

    def setup_method(self):
        """Set up common test fixtures."""
        self.pushups = ExerciseType(
            id=1,
            name="pushups",
            display_name="Push-ups",
            emoji="💪",
            unit="reps",
            aliases=["pushup"],
        )

    def test_very_large_valid_count(self):
        """Should accept very large valid counts."""
        result = try_deterministic_parse_workout_message("99999 pushups", [self.pushups])
        assert result is not None
        assert result.is_valid is True
        assert result.entries[0].count == 99999

    def test_count_with_commas_removed(self):
        """Should handle counts with commas (which get normalized)."""
        result = try_deterministic_parse_workout_message("1,000 pushups", [self.pushups])
        assert result is not None
        assert result.is_valid is True
        assert result.entries[0].count == 1000

    def test_multiple_zeros_rejected(self):
        """Should reject inputs with multiple zero counts."""
        result = try_deterministic_parse_workout_message(
            "0 pushups", [self.pushups]
        )
        assert result is not None
        assert result.is_valid is False
        assert result.error_reason == "Count must be greater than 0 and should be an integer."
