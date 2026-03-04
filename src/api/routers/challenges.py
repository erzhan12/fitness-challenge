"""REST API endpoints for challenges."""

from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.models import (
    ExerciseChallengeOut,
    ExerciseChallengeCreate,
    ExerciseChallengeUpdate,
    ChallengePromptRequest,
    ErrorResponse,
)
from src.api.services import (
    list_challenges,
    get_challenge,
    get_exercise_type,
    create_challenge,
    update_challenge,
    create_challenge_from_prompt,
    ExerciseTypeNotFoundError,
)
from src.api.security import verify_api_key, get_current_user
from src.core.models import AppUser

router = APIRouter(prefix="/challenges", tags=["Challenges"])


@router.get(
    "",
    response_model=List[ExerciseChallengeOut],
    summary="List challenges",
    description="Returns challenges with optional filtering by exercise type, "
    "active status, and date range.",
    responses={
        200: {
            "description": "List of challenges",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 1,
                            "exercise_type_id": 1,
                            "start_date": "2024-01-01",
                            "end_date": "2024-01-31",
                            "target_total": 1023,
                            "daily_target": 33,
                            "challenge_name": "January Push-up Challenge",
                            "is_active": True,
                            "total_days": 31,
                            "is_current": True,
                        }
                    ]
                }
            },
        }
    },
)
async def list_all_challenges(
    exercise_type_id: Optional[int] = Query(
        None, description="Filter by exercise type ID"
    ),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    starts_before: Optional[date] = Query(
        None, description="Filter challenges starting before this date"
    ),
    ends_after: Optional[date] = Query(
        None, description="Filter challenges ending after this date"
    ),
    current_user: AppUser = Depends(get_current_user),
) -> List[ExerciseChallengeOut]:
    """List all challenges with optional filters."""
    return await list_challenges(
        user_id=current_user.id,
        exercise_type_id=exercise_type_id,
        is_active=is_active,
        starts_before=starts_before,
        ends_after=ends_after,
    )


@router.get(
    "/{challenge_id}",
    response_model=ExerciseChallengeOut,
    summary="Get challenge by ID",
    description="Returns details of a specific challenge including computed fields "
    "like total_days and whether it is currently active.",
    responses={
        200: {"description": "Challenge details"},
        404: {"model": ErrorResponse, "description": "Challenge not found"},
    },
)
async def get_single_challenge(
    challenge_id: int,
    current_user: AppUser = Depends(get_current_user),
) -> ExerciseChallengeOut:
    """Get a single challenge by its ID."""
    result = await get_challenge(challenge_id, user_id=current_user.id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Challenge {challenge_id} not found",
        )
    return result


@router.post(
    "",
    response_model=ExerciseChallengeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create challenge",
    description="Create a new challenge for an exercise type. "
    "Requires API key authentication.",
    responses={
        201: {"description": "Challenge created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request data"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
    },
)
async def create_new_challenge(
    data: ExerciseChallengeCreate,
    _: str = Depends(verify_api_key),
    current_user: AppUser = Depends(get_current_user),
) -> ExerciseChallengeOut:
    """Create a new challenge."""
    etype = await get_exercise_type(data.exercise_type_id, user_id=current_user.id)
    if not etype:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exercise type {data.exercise_type_id} not found",
        )

    # Validate date range
    if data.end_date < data.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after or equal to start_date",
        )
    return await create_challenge(data, user_id=current_user.id)


@router.post(
    "/create-from-prompt",
    response_model=ExerciseChallengeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create challenge from natural language prompt",
    description=(
        "Accepts a natural language description and uses an LLM to parse it into "
        "a structured challenge, then saves it. "
        "Example input: 'pushups challenge for 30 days starting tomorrow, 2000 reps total'. "
        "Requires API key authentication."
    ),
    tags=["Challenges"],
    responses={
        201: {"description": "Challenge created successfully"},
        400: {"model": ErrorResponse, "description": "Could not parse prompt or invalid data"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Exercise type not found"},
        503: {"model": ErrorResponse, "description": "LLM service unavailable"},
    },
)
async def create_challenge_from_natural_language(
    data: ChallengePromptRequest,
    _: str = Depends(verify_api_key),
    current_user: AppUser = Depends(get_current_user),
) -> ExerciseChallengeOut:
    """
    Create a challenge from a natural language description.

    - **text**: Free-form text describing the challenge
      (e.g. "pushups challenge for 30 days starting tomorrow, 2000 reps total"
      or "daily 50 squats for a month starting Jan 1")

    The LLM extracts: exercise type, start date, duration, and target (total or daily).
    If the exercise type is not found in the user's exercise types, a 404 is returned
    with a list of available types.
    """
    try:
        return await create_challenge_from_prompt(data.text, user_id=current_user.id)
    except ExerciseTypeNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Exercise type '{e.exercise_type_name}' not found. "
                f"Available types: {', '.join(e.available_names)}. "
                "Create a new exercise type first using /api/v1/exercises."
            ),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        if "unavailable" in str(e).lower() or "failed" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM service is currently unavailable. Please try again later.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/{challenge_id}",
    response_model=ExerciseChallengeOut,
    summary="Update challenge",
    description="Update a challenge. Only provided fields will be updated. "
    "Requires API key authentication.",
    responses={
        200: {"description": "Challenge updated successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request data"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Challenge not found"},
    },
)
async def update_existing_challenge(
    challenge_id: int,
    data: ExerciseChallengeUpdate,
    _: str = Depends(verify_api_key),
    current_user: AppUser = Depends(get_current_user),
) -> ExerciseChallengeOut:
    """Update a challenge (partial update)."""
    # Get existing to validate date changes
    existing = await get_challenge(challenge_id, user_id=current_user.id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Challenge {challenge_id} not found",
        )

    # Validate date range if dates are being updated
    new_start = data.start_date or existing.start_date
    new_end = data.end_date or existing.end_date
    if new_end < new_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after or equal to start_date",
        )

    result = await update_challenge(
        challenge_id,
        data,
        user_id=current_user.id,
    )
    return result
