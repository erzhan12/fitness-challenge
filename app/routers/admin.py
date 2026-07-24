from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader

from app.config import settings
from app.services.workout_service import check_daily_reminders
from src.core.repositories import app_settings_repo

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
        ge=0,
        le=23,
        description=(
            "Reminder hour (0–23). Default reminder hours are [13, 21, 22], "
            "but any hour in range is accepted for manual dispatch."
        ),
        examples=[13, 21, 22, 23, 8],
    ),
    token: str = Depends(verify_admin_key),
):
    """
    Triggers reminders.

    - **hour=None** (default): Legacy behavior - sends per-user "missing you" messages
    - **hour=0–23**: Hour-specific reminder flow for users with that hour in `reminder_hours`

    Intended to be called by cron/n8n or for manual testing.
    """
    await check_daily_reminders(hour=hour)
    return {
        "status": "triggered",
        "mode": "evening" if hour else "legacy",
        "hour": hour,
    }


@router.get("/registration")
async def get_registration_status(
    token: str = Depends(verify_admin_key),
):
    """Get the current registration gate status."""
    app_settings = await app_settings_repo.get_singleton()
    return {"is_registration_open": app_settings.is_registration_open}


@router.post("/registration")
async def set_registration_status(
    is_open: bool = Query(..., description="Set registration open/closed"),
    token: str = Depends(verify_admin_key),
):
    """Enable or disable new user registrations."""
    app_settings = await app_settings_repo.update({"is_registration_open": is_open})
    return {"is_registration_open": app_settings.is_registration_open}
