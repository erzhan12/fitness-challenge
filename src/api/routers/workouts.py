"""REST API endpoints for workout parsing."""

from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends

from app.config import settings
from app.models import ExerciseType, ParseResult, ExerciseEntry
from app.services.openai_service import parse_workout_message
from app.services.deterministic_parser import get_numbers_from_message
from app.services.workout_service import determine_default_exercise
from src.api.models import (
    ParseWorkoutRequest,
    ParseWorkoutResponse,
    ParseWorkoutEntry,
)
from src.api.services import (
    list_current_active_challenges,
    get_ordered_challenges,
)
from src.api.security import verify_api_key, get_current_user
from src.api.constants import NO_ACTIVE_CHALLENGES_MSG
from src.core.models import AppUser
from src.core.repositories import exercise_type_repo

router = APIRouter(prefix="/workouts", tags=["Workouts"])
TZ = ZoneInfo(settings.TZ)


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
    current_user: AppUser = Depends(get_current_user),
) -> ParseWorkoutResponse:
    """Parse a workout message into structured entries.

    This endpoint calls the AI-powered parser to extract exercise entries
    from natural language text. It does not create any logs - use POST /logs
    to actually record workouts.
    """
    today_local = datetime.now(TZ).date()
    challenges_data = await list_current_active_challenges(
        user_id=current_user.id,
        target_date=today_local,
    )

    if not challenges_data:
        return ParseWorkoutResponse(
            entries=[],
            is_valid=False,
            error_reason=NO_ACTIVE_CHALLENGES_MSG,
        )

    challenge_type_ids = list({c["exercise_type_id"] for c in challenges_data})
    types_models = await exercise_type_repo.get_by_ids(
        challenge_type_ids,
        user_id=current_user.id,
    )
    types_models = [t for t in types_models if t.is_active]
    types_models.sort(key=lambda x: x.id)

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
        for et in types_models
    ]

    # Compute default exercise name (consistent with Telegram flow)
    default_exercise_name = determine_default_exercise(challenges_data, exercise_types)

    # Try fast path (numbers-only mapping to challenges)
    result = None
    counts, parse_error = get_numbers_from_message(data.text)

    if parse_error:
        result = ParseResult(entries=[], is_valid=False, error_reason=parse_error)
    elif counts is not None:
        # Valid multi-number input. challenges_data is guaranteed non-empty here
        # (the endpoint returns early above when there are no in-window challenges).
        ordered = get_ordered_challenges(challenges_data)
        entries = []
        for i, count in enumerate(counts):
            if i >= len(ordered):
                break

            challenge = ordered[i]
            # Find exercise type matching challenge
            etype = next((et for et in exercise_types if et.id == challenge["exercise_type_id"]), None)

            if etype:
                duration_seconds = count * 60 if etype.unit.lower() in {"minute", "minutes"} else None
                entries.append(ExerciseEntry(
                    exercise_type_name=etype.name,
                    count=count,
                    duration_seconds=duration_seconds,
                    notes=None,
                    confidence=1.0
                ))

        if not entries:
            result = ParseResult(
                entries=[],
                is_valid=False,
                error_reason="Could not map numbers to active exercises."
            )
        else:
            result = ParseResult(entries=entries, is_valid=True)

    # Parse the message (Fallback)
    if not result:
        result = parse_workout_message(data.text, exercise_types, default_exercise_name)

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
