#!/usr/bin/env python3
"""
Test script to demonstrate LLM fallback logging.
This creates ambiguous scenarios where deterministic parsing fails.
Run with: uv run python test_llm_fallback.py
"""

import logging
from unittest.mock import Mock, patch
import json
from app.models import ExerciseType
from app.services.openai_service import parse_workout_message

# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s'
)

# Setup test data with ambiguous aliases
pushups = ExerciseType(
    id=1,
    name="pushups",
    display_name="Push-ups",
    emoji="💪",
    unit="reps",
    aliases=["press"],  # Ambiguous!
)
bench = ExerciseType(
    id=2,
    name="benchpress",
    display_name="Bench press",
    emoji="🏋️",
    unit="reps",
    aliases=["press"],  # Also has "press" - ambiguous!
)

# Mock LLM response
def mock_llm_response(payload):
    response = Mock()
    response.choices = [Mock(message=Mock(content=json.dumps(payload)))]
    return response

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

print("\n" + "="*80)
print("TEST: Ambiguous input '10 press' (should fall back to LLM)")
print("="*80)
print("Both 'pushups' and 'benchpress' have 'press' as an alias")
print("Deterministic parsing will detect ambiguity and fall back to LLM")
print("="*80 + "\n")

with patch(
    "app.services.openai_service.client.chat.completions.create",
    return_value=mock_llm_response(llm_payload),
) as mock_create:
    result = parse_workout_message("10 press", [pushups, bench])

    print(f"\nResult: {result.entries[0].exercise_type_name} - {result.entries[0].count}")
    print(f"LLM was called: {mock_create.call_count} time(s)")

print("\n" + "="*80)
print("TEST: Unknown exercise (should fall back to LLM)")
print("="*80)
print("Input contains exercise name not in the database")
print("="*80 + "\n")

llm_error_payload = {
    "entries": [],
    "is_valid": False,
    "error_reason": "I don't recognize 'flarb' as an exercise type.",
}

with patch(
    "app.services.openai_service.client.chat.completions.create",
    return_value=mock_llm_response(llm_error_payload),
) as mock_create:
    result = parse_workout_message("10 flarb", [pushups])

    print(f"\nResult: is_valid={result.is_valid}, error={result.error_reason}")
    print(f"LLM was called: {mock_create.call_count} time(s)")

print("\n✅ Check the logs above - you should see:")
print("   🔍 Attempting deterministic parse")
print("   ⚠️  Deterministic parse failed - falling back to LLM")
print("   🤖 Calling LLM API")
print("   ✅ LLM parse SUCCESS\n")
