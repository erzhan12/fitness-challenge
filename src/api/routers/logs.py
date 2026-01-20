"""REST API endpoints for exercise logs."""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.models import (
    ExerciseLogOut,
    ExerciseLogCreate,
    ExerciseLogCreateResponse,
    PaginatedLogsResponse,
    ErrorResponse,
)
from src.api.services import (
    list_logs,
    get_log,
    create_log,
    delete_log,
    get_exercise_type,
)
from src.api.security import verify_api_key, get_current_user
from src.core.models import AppUser

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get(
    "",
    response_model=PaginatedLogsResponse,
    summary="List exercise logs",
    description="Returns paginated log entries with optional filtering by exercise type, "
    "challenge, and date range.",
    responses={
        200: {
            "description": "Paginated list of logs",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": 1,
                                "exercise_type_id": 1,
                                "challenge_id": 1,
                                "date": "2024-01-15",
                                "timestamp": "2024-01-15T10:30:00+05:00",
                                "count": 25,
                                "cumulative_total": 250,
                                "day_number": 15,
                                "status": "on_track",
                                "raw_message": "25 pushups",
                            }
                        ],
                        "pagination": {
                            "total": 100,
                            "limit": 50,
                            "offset": 0,
                            "has_more": True,
                        },
                    }
                }
            },
        }
    },
)
async def list_all_logs(
    exercise_type_id: Optional[int] = Query(
        None, description="Filter by exercise type ID"
    ),
    challenge_id: Optional[int] = Query(None, description="Filter by challenge ID"),
    date_from: Optional[date] = Query(
        None, description="Filter logs from this date (inclusive)"
    ),
    date_to: Optional[date] = Query(
        None, description="Filter logs to this date (inclusive)"
    ),
    limit: int = Query(50, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: AppUser = Depends(get_current_user),
) -> PaginatedLogsResponse:
    """List exercise logs with pagination and filters."""
    return await list_logs(
        user_id=current_user.id,
        exercise_type_id=exercise_type_id,
        challenge_id=challenge_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{log_id}",
    response_model=ExerciseLogOut,
    summary="Get log entry by ID",
    responses={
        200: {"description": "Log entry details"},
        404: {"model": ErrorResponse, "description": "Log entry not found"},
    },
)
async def get_single_log(
    log_id: int,
    current_user: AppUser = Depends(get_current_user),
) -> ExerciseLogOut:
    """Get a single log entry by its ID."""
    result = await get_log(log_id, user_id=current_user.id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log entry {log_id} not found",
        )
    return result


@router.post(
    "",
    response_model=ExerciseLogCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create log entry",
    description="Create a new exercise log entry. Automatically associates with the "
    "active challenge for the exercise type and updates user stats. "
    "Returns both the created log and updated stats. Requires API key authentication.",
    responses={
        201: {
            "description": "Log created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "log": {
                            "id": 123,
                            "exercise_type_id": 1,
                            "challenge_id": 1,
                            "date": "2024-01-15",
                            "timestamp": "2024-01-15T10:30:00+05:00",
                            "count": 25,
                            "cumulative_total": 275,
                            "day_number": 15,
                            "status": "on_track",
                        },
                        "stats": {
                            "exercise_type_id": 1,
                            "exercise_type_name": "Push-ups",
                            "exercise_type_emoji": "💪",
                            "challenge_id": 1,
                            "day_number": 15,
                            "total_days": 31,
                            "target_total": 1000,
                            "daily_target": 33,
                            "today_total": 50,
                            "cumulative_total": 275,
                            "progress_percent": 27.5,
                            "status": "on_track",
                            "catch_up_reps": 0,
                        },
                    }
                }
            },
        },
        400: {"model": ErrorResponse, "description": "Invalid request data"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Exercise type not found"},
    },
)
async def create_new_log(
    data: ExerciseLogCreate,
    current_user: AppUser = Depends(get_current_user),
    _: str = Depends(verify_api_key),
) -> ExerciseLogCreateResponse:
    """Create a new log entry."""
    # Validate exercise type exists
    etype = await get_exercise_type(data.exercise_type_id, user_id=current_user.id)
    if not etype:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exercise type {data.exercise_type_id} not found",
        )

    try:
        log, stats = await create_log(data, user_id=current_user.id)
        return ExerciseLogCreateResponse(log=log, stats=stats)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        # Log the full error for debugging
        import traceback
        error_details = traceback.format_exc()
        print(f"Error creating log: {error_details}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create log: {str(e)}",
        )


@router.delete(
    "/{log_id}",
    response_model=ExerciseLogCreateResponse,
    summary="Delete log entry",
    description="Delete a log entry and update user stats. "
    "Returns the deleted log metadata and updated stats. Requires API key authentication.",
    responses={
        200: {"description": "Log deleted successfully"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Log entry not found"},
    },
)
async def delete_single_log(
    log_id: int,
    current_user: AppUser = Depends(get_current_user),
    _: str = Depends(verify_api_key),
) -> ExerciseLogCreateResponse:
    """Delete a log entry."""
    log, stats = await delete_log(log_id, user_id=current_user.id)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log entry {log_id} not found",
        )
    return ExerciseLogCreateResponse(log=log, stats=stats)
