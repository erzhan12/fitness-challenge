"""REST API endpoints for statistics."""

from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Query

from src.api.models import (
    ExerciseStatsOut,
    StatsSummaryOut,
)
from src.api.services import (
    compute_exercise_stats,
    get_all_exercise_stats,
    get_stats_summary,
)

router = APIRouter(prefix="/stats", tags=["Stats"])


@router.get(
    "/exercises",
    response_model=List[ExerciseStatsOut],
    summary="Get stats for all exercises",
    description="Returns current stats for all active exercises within their "
    "challenge contexts. Includes progress, status, and catch-up information.",
    responses={
        200: {
            "description": "Stats for all exercises",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "exercise_type_id": 1,
                            "exercise_type_name": "Push-ups",
                            "exercise_type_emoji": "💪",
                            "challenge_id": 1,
                            "challenge_name": "January Push-up Challenge",
                            "day_number": 15,
                            "total_days": 31,
                            "target_total": 1000,
                            "daily_target": 33,
                            "today_total": 50,
                            "cumulative_total": 495,
                            "progress_percent": 49.5,
                            "status": "on_track",
                            "catch_up_reps": 0,
                        }
                    ]
                }
            },
        }
    },
)
async def get_exercises_stats(
    target_date: Optional[date] = Query(
        None, description="Date context for stats calculation (defaults to today)"
    ),
    challenge_only: bool = Query(
        True, description="Only include exercises with active challenges"
    ),
) -> List[ExerciseStatsOut]:
    """Get stats for all exercises."""
    return await get_all_exercise_stats(target_date=target_date, challenge_only=challenge_only)


@router.get(
    "/exercises/{exercise_type_id}",
    response_model=ExerciseStatsOut,
    summary="Get stats for a single exercise",
    description="Returns detailed stats for a specific exercise type within "
    "its active challenge context.",
    responses={
        200: {"description": "Exercise stats"},
        404: {"description": "Exercise type not found"},
    },
)
async def get_single_exercise_stats(
    exercise_type_id: int,
    target_date: Optional[date] = Query(
        None, description="Date context for stats calculation (defaults to today)"
    ),
) -> ExerciseStatsOut:
    """Get stats for a specific exercise type."""
    return await compute_exercise_stats(exercise_type_id, target_date=target_date)


@router.get(
    "/summary",
    response_model=StatsSummaryOut,
    summary="Get overall stats summary",
    description="Returns aggregated stats across all exercise types including "
    "total reps, active days, and per-exercise breakdowns.",
    responses={
        200: {
            "description": "Overall stats summary",
            "content": {
                "application/json": {
                    "example": {
                        "total_reps_all_time": 5000,
                        "total_active_days": 45,
                        "exercise_stats": [
                            {
                                "exercise_type_id": 1,
                                "all_time_total": 3000,
                                "best_daily_count": 100,
                                "current_streak": 7,
                                "longest_streak": 14,
                                "last_logged_date": "2024-01-15",
                            }
                        ],
                    }
                }
            },
        }
    },
)
async def get_summary_stats() -> StatsSummaryOut:
    """Get overall stats summary."""
    return await get_stats_summary()

