"""REST API endpoints for one-off challenge exception (rest) days."""

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.models import (
    ChallengeExceptionDayOut,
    ChallengeExceptionDayCreate,
    ErrorResponse,
)
from src.api.services import (
    list_exception_days,
    add_exception_day,
    remove_exception_day,
)
from src.api.security import verify_api_key, get_current_user
from src.core.models import AppUser, ExerciseChallenge

router = APIRouter(
    prefix="/challenges/{challenge_id}/exception-days",
    tags=["Challenge Exception Days"],
)


@router.get(
    "",
    response_model=List[ChallengeExceptionDayOut],
    summary="List exception days for a challenge",
    description=(
        "Returns the one-off exception (rest) days attached to a challenge, "
        "ordered by date. Recurring weekday exceptions live on the parent "
        "challenge as ``exception_weekdays`` and are **not** returned here.\n\n"
        "To get the full rest-day picture for a challenge (recurring **and** "
        "one-off), combine this endpoint with ``GET /api/v1/challenges/{id}``:\n\n"
        "```\n"
        "# 1. One-off exception dates (this endpoint)\n"
        "GET /api/v1/challenges/1/exception-days\n"
        '→ [{"id": 7, "date": "2026-04-20", "reason": "Easter Monday", ...}]\n'
        "\n"
        "# 2. Recurring weekdays (from the parent challenge)\n"
        "GET /api/v1/challenges/1\n"
        '→ {"id": 1, ..., "exception_weekdays": "6,7"}\n'
        "# ISO weekday ints, 1=Mon..7=Sun → here Sat+Sun are recurring rest days.\n"
        "```\n\n"
        "A date is a rest day iff it appears in either list. If you only "
        "need an aggregate count, "
        "``GET /api/v1/stats/exercises/{exercise_type_id}`` already merges "
        "both sources and reports ``total_days`` as the *effective* "
        "(non-rest) day count — prefer that over computing the union "
        "client-side."
    ),
    responses={
        200: {"description": "List of exception days"},
        404: {"model": ErrorResponse, "description": "Challenge not found"},
    },
)
async def list_challenge_exception_days(
    challenge_id: int,
    current_user: AppUser = Depends(get_current_user),
) -> List[ChallengeExceptionDayOut]:
    """List exception days for a challenge owned by the current user."""
    return await list_exception_days(challenge_id, user_id=current_user.id)


@router.post(
    "",
    response_model=ChallengeExceptionDayOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add an exception day to a challenge",
    description=(
        "Idempotently add a one-off exception (rest) day to a challenge. "
        "The date must fall within the challenge window. Re-posting an "
        "existing date is a no-op and returns the same row."
    ),
    responses={
        201: {"description": "Exception day created (or already existed)"},
        400: {"model": ErrorResponse, "description": "Date outside challenge window"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Challenge not found"},
    },
)
async def create_challenge_exception_day(
    challenge_id: int,
    data: ChallengeExceptionDayCreate,
    _: str = Depends(verify_api_key),
    current_user: AppUser = Depends(get_current_user),
) -> ChallengeExceptionDayOut:
    """Add a one-off exception day to a challenge."""
    try:
        return await add_exception_day(
            challenge_id,
            data.date,
            data.reason or "",
            user_id=current_user.id,
        )
    except ExerciseChallenge.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Challenge {challenge_id} not found",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.delete(
    "/{exception_date}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an exception day",
    description="Delete a one-off exception day from a challenge by its date.",
    responses={
        204: {"description": "Exception day removed"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Exception day not found"},
    },
)
async def delete_challenge_exception_day(
    challenge_id: int,
    exception_date: date,
    _: str = Depends(verify_api_key),
    current_user: AppUser = Depends(get_current_user),
) -> None:
    """Delete a one-off exception day by date."""
    deleted = await remove_exception_day(
        challenge_id,
        exception_date,
        user_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Exception day {exception_date.isoformat()} not found "
                f"for challenge {challenge_id}"
            ),
        )
