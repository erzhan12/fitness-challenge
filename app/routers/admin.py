from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader

from app.config import settings
from app.services.workout_service import check_daily_reminders

router = APIRouter(prefix="/jobs", tags=["Jobs"])

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


async def verify_admin_key(key: str = Security(api_key_header)):
    if not key:
        raise HTTPException(status_code=403, detail="Missing API Key")
    # Allow "Bearer <key>" or just "<key>"
    token = key.replace("Bearer ", "")
    if token != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return token


@router.post("/daily-reminder")
async def trigger_daily_reminders(
    hour: Optional[int] = Query(
        None,
        ge=21,
        le=23,
        description="Evening reminder hour (21, 22, or 23). If omitted, uses legacy simple reminders.",
    ),
    token: str = Depends(verify_admin_key),
):
    """
    Triggers reminders.

    - **hour=None** (default): Legacy behavior - sends per-challenge "missing you" messages
    - **hour=21/22/23**: Evening reminder flow - sends one combined message for all incomplete challenges

    Intended to be called by cron/n8n or for manual testing.
    """
    await check_daily_reminders(hour=hour)
    return {
        "status": "triggered",
        "mode": "evening" if hour else "legacy",
        "hour": hour,
    }
