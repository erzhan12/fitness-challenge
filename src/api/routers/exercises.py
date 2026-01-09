"""REST API endpoints for exercise types."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.models import (
    ExerciseTypeOut,
    ExerciseTypeCreate,
    ExerciseTypeUpdate,
    ErrorResponse,
)
from src.api.services import (
    list_exercise_types,
    get_exercise_type,
    create_exercise_type,
    update_exercise_type,
)
from src.api.security import verify_api_key

router = APIRouter(prefix="/exercises", tags=["Exercises"])


@router.get(
    "",
    response_model=List[ExerciseTypeOut],
    summary="List exercise types",
    description="Returns all exercise types, with optional filtering by active status "
    "or whether they have active challenges.",
    responses={
        200: {
            "description": "List of exercise types",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 1,
                            "name": "pushups",
                            "display_name": "Push-ups",
                            "emoji": "💪",
                            "unit": "reps",
                            "aliases": ["push-up", "push up"],
                            "is_active": True,
                        }
                    ]
                }
            },
        }
    },
)
async def list_exercises(
    is_active: Optional[bool] = Query(
        True,
        description="Filter by active status. Use null/None to get all.",
    ),
    challenge_only: bool = Query(
        False,
        description="Only return exercise types with at least one active challenge",
    ),
) -> List[ExerciseTypeOut]:
    """List all exercise types with optional filters."""
    return await list_exercise_types(is_active=is_active, challenge_only=challenge_only)


@router.get(
    "/{exercise_type_id}",
    response_model=ExerciseTypeOut,
    summary="Get exercise type by ID",
    responses={
        200: {"description": "Exercise type details"},
        404: {"model": ErrorResponse, "description": "Exercise type not found"},
    },
)
async def get_exercise(exercise_type_id: int) -> ExerciseTypeOut:
    """Get a single exercise type by its ID."""
    result = await get_exercise_type(exercise_type_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exercise type {exercise_type_id} not found",
        )
    return result


@router.post(
    "",
    response_model=ExerciseTypeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create exercise type",
    description="Create a new exercise type. Requires API key authentication.",
    responses={
        201: {"description": "Exercise type created successfully"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
    },
)
async def create_exercise(
    data: ExerciseTypeCreate,
    _: str = Depends(verify_api_key),
) -> ExerciseTypeOut:
    """Create a new exercise type."""
    return await create_exercise_type(data)


@router.patch(
    "/{exercise_type_id}",
    response_model=ExerciseTypeOut,
    summary="Update exercise type",
    description="Update an exercise type. Only provided fields will be updated. "
    "Requires API key authentication.",
    responses={
        200: {"description": "Exercise type updated successfully"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Exercise type not found"},
    },
)
async def update_exercise(
    exercise_type_id: int,
    data: ExerciseTypeUpdate,
    _: str = Depends(verify_api_key),
) -> ExerciseTypeOut:
    """Update an exercise type (partial update)."""
    result = await update_exercise_type(exercise_type_id, data)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exercise type {exercise_type_id} not found",
        )
    return result

