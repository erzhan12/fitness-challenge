import json
import logging
from typing import List, Dict, Any
from openai import OpenAI
from app.config import settings
from app.models import ParseResult, ExerciseType
from app.services.deterministic_parser import (
    try_deterministic_parse_workout_message,
)

logger = logging.getLogger(__name__)

# OpenRouter requires HTTP-Referer header (optional but recommended)
# Also add X-Title for better tracking
default_headers = {}
if "openrouter.ai" in settings.LLM_BASE_URL.lower():
    default_headers = {
        "HTTP-Referer": "https://github.com/yourusername/fitness-challenge",  # Optional: your app URL
        "X-Title": "Fitness Challenge Bot",  # Optional: your app name
    }
    logger.info("Detected OpenRouter, adding required headers")

client = OpenAI(
    base_url=settings.LLM_BASE_URL,
    api_key=settings.LLM_API_KEY,
    default_headers=default_headers if default_headers else None,
)

logger.info(
    f"Initialized OpenAI client with base_url: {settings.LLM_BASE_URL}, model: {settings.LLM_MODEL}"
)


def parse_workout_message(text: str, exercise_types: List[ExerciseType], default_exercise_name: str = "pushups") -> ParseResult:
    """
    Uses OpenAI to parse the user's message into structured exercise data.

    Args:
        text: The user's workout message
        exercise_types: List of valid exercise types
        default_exercise_name: Exercise to default to when user only provides a number (default: "pushups")
    """

    # Try deterministic parsing first (uses existing aliases or simple singular/plural)
    logger.info(f"🔍 Attempting deterministic parse for: '{text}'")
    deterministic = try_deterministic_parse_workout_message(text, exercise_types)
    if deterministic is not None:
        logger.info(f"✅ Deterministic parse SUCCESS - parsed without LLM: {[e.exercise_type_name for e in deterministic.entries]}")
        return deterministic

    logger.info("⚠️  Deterministic parse failed - falling back to LLM")

    # Prepare list of valid exercises for the prompt
    exercises_info = [
        f"{et.name} (aliases: {', '.join(et.aliases or [])}, unit: {et.unit})"
        for et in exercise_types
    ]

    system_prompt = f"""
    You are a fitness log parser. Extract exercise data from natural language text.

    Constraint: You ONLY accept these exercise types:
    {json.dumps(exercises_info, indent=2)}

    Rules:
    1. If the user provides a number without an exercise name, default to '{default_exercise_name}'.
    2. For time-based exercises (like plank), 'count' should be the display value (e.g. minutes), and 'duration_seconds' must be the total seconds.
       - If user says "2 min plank", count=2, duration_seconds=120.
       - If user says "90 sec plank", count=1 (rounded min is okay for display) or 1.5, duration_seconds=90.
    3. For rep-based exercises, 'count' is the number of reps, 'duration_seconds' is null.
    4. Handle multiple exercises in one message (e.g., "20 pushups and 30 squats").
    5. VALIDATION: The 'count' field MUST be a positive integer greater than 0. If the user provides 0, 0.0, 0.1, or any value <= 0, set is_valid to false and return error_reason: "Count must be greater than 0 and should be an integer."
    6. Return strict JSON.

    Schema:
    {{
      "entries": [
        {{
          "exercise_type_name": "string (must match one of the 'name' fields provided)",
          "count": "integer (reps or minutes, MUST be > 0)",
          "duration_seconds": "integer (or null)",
          "notes": "string (optional context)",
          "confidence": "float (0.0 to 1.0)"
        }}
      ],
      "is_valid": boolean,
      "error_reason": "string (friendly reply if no exercises found or validation fails, else null)"
    }}
    """

    try:
        logger.info(f"🤖 Calling LLM API (model: {settings.LLM_MODEL})")
        logger.debug(f"User input: {text[:100]}...")  # Log first 100 chars

        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )

        content = response.choices[0].message.content
        logger.info("✅ LLM parse SUCCESS")
        logger.debug(f"LLM response: {content[:200]}...")  # Log first 200 chars
        data = json.loads(content)

        # Post-processing validation: check all counts are > 0
        if data.get("is_valid") and data.get("entries"):
            for entry in data["entries"]:
                if entry.get("count", 0) <= 0:
                    logger.warning(f"LLM returned invalid count: {entry.get('count')}")
                    return ParseResult(
                        entries=[],
                        is_valid=False,
                        error_reason="Count must be greater than 0 and should be an integer."
                    )

        return ParseResult(**data)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"LLM API error: {type(e).__name__}: {error_msg}", exc_info=True)

        # Provide more helpful error messages
        if "404" in error_msg or "No endpoints found" in error_msg:
            logger.error(
                f"Model '{settings.LLM_MODEL}' not found. Check your LLM_MODEL setting."
            )
            logger.error(f"Current model: {settings.LLM_MODEL}")
            logger.error(f"Current base_url: {settings.LLM_BASE_URL}")
            user_friendly_msg = f"AI service unavailable. Please check model configuration (model: {settings.LLM_MODEL})."
        else:
            user_friendly_msg = "AI parsing failed. Please try again later."

        # Fallback for API errors
        return ParseResult(entries=[], is_valid=False, error_reason=user_friendly_msg)


def generate_motivational_response(exercise_name: str, stats: Dict[str, Any]) -> str:
    """
    Generates a short, witty, exercise-aware comment.
    stats includes: today_total, target_total, day_number, status ('ahead', 'behind', 'on_track'), streak
    """

    system_prompt = """
    You are a sarcastic but kind fitness coach bot.
    Generate a VERY SHORT (1-2 sentences max) witty comment based on the user's progress.
    Tone: Playful, slightly judging but encouraging.
    """

    user_content = f"""
    Exercise: {exercise_name}
    Status: {stats.get("status")}
    Today's Count: {stats.get("today_total")}
    Challenge Day: {stats.get("day_number")}
    Streak: {stats.get("streak")}
    
    Write a one-liner.
    """

    try:
        logger.debug(f"Generating motivational response for {exercise_name}")
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.7,
            max_tokens=60,
        )
        result = response.choices[0].message.content.strip()
        logger.debug(f"Generated response: {result}")
        return result
    except Exception as e:
        logger.error(
            f"Error generating motivational response: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return "Keep crushing it! 💪"
