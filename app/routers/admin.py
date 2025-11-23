from fastapi import APIRouter, Depends, HTTPException, Security
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
async def trigger_daily_reminders(token: str = Depends(verify_admin_key)):
    """
    Triggers the daily reminder check. 
    Intended to be called by cron/n8n.
    """
    await check_daily_reminders()
    return {"status": "triggered"}

