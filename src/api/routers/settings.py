"""Settings API router."""

from fastapi import APIRouter, Depends

from src.api import services
from src.api.models import SettingsOut, SettingsUpdate
from src.api.security import verify_api_key, get_current_user
from src.core.models import AppUser

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get(
    "",
    response_model=SettingsOut,
    summary="Get current user settings",
    description="Retrieve current user settings including reminder preferences.",
)
async def get_settings(
    current_user: AppUser = Depends(get_current_user),
):
    """
    Get current user settings.

    Returns the current configuration including:
    - **is_reminder_active**: Whether evening reminders are enabled
    - **is_workout_motivation_active**: Whether the LLM motivational line is
      appended to workout-log replies (does not affect evening reminders)
    - **telegram_chat_id**: Telegram chat ID where reminders are sent (if configured)

    Requires X-Telegram-User-Id header.
    """
    return await services.get_settings(user_id=current_user.id)


@router.patch(
    "",
    response_model=SettingsOut,
    summary="Update current user settings",
    description="Update current user settings (requires API key authentication).",
    responses={
        200: {"description": "Settings updated successfully"},
        401: {"description": "Missing or invalid API key"},
    },
)
async def update_settings(
    update: SettingsUpdate,
    api_key: str = Depends(verify_api_key),
    current_user: AppUser = Depends(get_current_user),
):
    """
    Update current user settings.

    Currently supports updating:
    - **is_reminder_active**: Enable or disable evening reminders
    - **is_workout_motivation_active**: Enable or disable the workout-log reply
      motivational line (does not affect evening reminders)

    Requires API key authentication via Authorization header.

    Returns the updated settings.
    """
    return await services.update_settings(update, user_id=current_user.id)
