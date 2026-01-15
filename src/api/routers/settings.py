"""Settings API router."""

from fastapi import APIRouter, Depends

from src.api import services
from src.api.models import SettingsOut, SettingsUpdate
from src.api.security import verify_api_key

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get(
    "",
    response_model=SettingsOut,
    summary="Get application settings",
    description="Retrieve current application settings including reminder preferences.",
)
async def get_settings():
    """
    Get application settings.

    Returns the current configuration including:
    - **is_reminder_active**: Whether evening reminders are enabled
    - **telegram_chat_id**: Telegram chat ID where reminders are sent (if configured)

    No authentication required for reading settings.
    """
    return await services.get_settings()


@router.patch(
    "",
    response_model=SettingsOut,
    summary="Update application settings",
    description="Update application settings (requires API key authentication).",
    responses={
        200: {"description": "Settings updated successfully"},
        401: {"description": "Missing or invalid API key"},
    },
)
async def update_settings(
    update: SettingsUpdate,
    api_key: str = Depends(verify_api_key)
):
    """
    Update application settings.

    Currently supports updating:
    - **is_reminder_active**: Enable or disable evening reminders

    Requires API key authentication via Authorization header.

    Returns the updated settings.
    """
    return await services.update_settings(update)
