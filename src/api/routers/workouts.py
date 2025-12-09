"""REST API endpoints for workout parsing."""

from fastapi import APIRouter, Depends

from src.api.models import (
    ParseWorkoutRequest,
    ParseWorkoutResponse,
    ParseWorkoutEntry,
)
from src.api.services import list_exercise_types
from src.api.security import verify_api_key
from app.services.openai_service import parse_workout_message
from app.models import ExerciseType

router = APIRouter(prefix="/workouts", tags=["Workouts"])


@router.post(
    "/parse",
    response_model=ParseWorkoutResponse,
    summary="Parse workout message",
    description="Parse a free-form workout message into structured exercise entries. "
    "Uses AI to extract exercise types and counts from natural language. "
    "Does not persist anything to the database. Requires API key authentication.",
    responses={
        200: {
            "description": "Parsed workout entries",
            "content": {
                "application/json": {
                    "example": {
                        "entries": [
                            {
                                "exercise_type_name": "pushups",
                                "count": 20,
                                "duration_seconds": None,
                                "notes": None,
                                "confidence": 0.95,
                            },
                            {
                                "exercise_type_name": "squats",
                                "count": 30,
                                "duration_seconds": None,
                                "notes": None,
                                "confidence": 0.92,
                            },
                        ],
                        "is_valid": True,
                        "error_reason": None,
                    }
                }
            },
        },
        401: {"description": "Missing API key"},
        403: {"description": "Invalid API key"},
    },
)
async def parse_workout(
    data: ParseWorkoutRequest,
    _: str = Depends(verify_api_key),
) -> ParseWorkoutResponse:
    """Parse a workout message into structured entries.

    This endpoint calls the AI-powered parser to extract exercise entries
    from natural language text. It does not create any logs - use POST /logs
    to actually record workouts.
    """
    # Get active exercise types for the parser
    # Try challenge-only first, but fallback to all active if no challenges exist
    api_exercise_types = list_exercise_types(is_active=True, challenge_only=True)
    
    # Fallback: if no challenges exist, use all active exercise types
    if not api_exercise_types:
        api_exercise_types = list_exercise_types(is_active=True, challenge_only=False)

    # Convert to app models for the parser
    exercise_types = [
        ExerciseType(
            id=et.id,
            name=et.name,
            display_name=et.display_name,
            emoji=et.emoji,
            unit=et.unit,
            aliases=et.aliases,
        )
        for et in api_exercise_types
    ]

    # Parse the message
    result = parse_workout_message(data.text, exercise_types)

    # Convert to API response model
    entries = [
        ParseWorkoutEntry(
            exercise_type_name=entry.exercise_type_name,
            count=entry.count,
            duration_seconds=entry.duration_seconds,
            notes=entry.notes,
            confidence=entry.confidence,
        )
        for entry in result.entries
    ]

    return ParseWorkoutResponse(
        entries=entries,
        is_valid=result.is_valid,
        error_reason=result.error_reason,
    )

