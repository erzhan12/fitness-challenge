#!/usr/bin/env python3
"""
Test script to demonstrate deterministic parsing vs LLM fallback logging.
Run with: uv run python test_deterministic_logging.py
"""

import logging
from app.models import ExerciseType
from app.services.openai_service import parse_workout_message

# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s'
)

# Setup test data
exercise_types = [
    ExerciseType(
        id=1,
        name="pushups",
        display_name="Push-ups",
        emoji="💪",
        unit="reps",
        aliases=["push-up", "push up"],
    ),
    ExerciseType(
        id=2,
        name="squats",
        display_name="Squats",
        emoji="🏋️",
        unit="reps",
        aliases=["squat"],
    ),
]

print("\n" + "="*80)
print("TEST 1: Simple number-word pair (should use deterministic parsing)")
print("="*80)
result = parse_workout_message("25 pushups", exercise_types)
print(f"Result: {result.entries[0].exercise_type_name} - {result.entries[0].count}")

print("\n" + "="*80)
print("TEST 2: Multiple pairs (should use deterministic parsing)")
print("="*80)
result = parse_workout_message("20 pushups and 30 squats", exercise_types)
print(f"Result: {[(e.exercise_type_name, e.count) for e in result.entries]}")

print("\n" + "="*80)
print("TEST 3: Number only with single exercise type (should use deterministic parsing)")
print("="*80)
result = parse_workout_message("50", [exercise_types[0]])
print(f"Result: {result.entries[0].exercise_type_name} - {result.entries[0].count}")

print("\n" + "="*80)
print("TEST 4: Ambiguous/complex input (should fall back to LLM)")
print("="*80)
print("NOTE: This will call the actual LLM API if configured")
# Uncomment to test LLM fallback (requires API key):
# result = parse_workout_message("I did some exercises today", exercise_types)
# print(f"Result: {result}")

print("\n" + "="*80)
print("TEST 5: Punctuation variant (should use deterministic parsing)")
print("="*80)
result = parse_workout_message("25 push-ups", exercise_types)
print(f"Result: {result.entries[0].exercise_type_name} - {result.entries[0].count}")

print("\n✅ All tests completed! Check the logs above to see when deterministic vs LLM parsing was used.\n")
