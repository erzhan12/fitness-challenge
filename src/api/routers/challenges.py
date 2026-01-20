"""REST API endpoints for challenges."""

from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.models import (
    ExerciseChallengeOut,
    ExerciseChallengeCreate,
    ExerciseChallengeUpdate,
    ErrorResponse,
)
from src.api.services import (
    list_challenges,
    get_challenge,
    get_exercise_type,
    create_challenge,
    update_challenge,
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
                            "target_total": 1000,
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
