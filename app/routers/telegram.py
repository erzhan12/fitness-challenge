from fastapi import APIRouter, Header, BackgroundTasks, HTTPException
from app.config import settings
from app.models import TelegramUpdate
from app.services.workout_service import process_incoming_message
from src.core.repositories import app_settings_repo
from src.core.validators import validate_telegram_chat_id
import logging

router = APIRouter(prefix="/telegram", tags=["Telegram"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def telegram_webhook(
    update: TelegramUpdate,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str = Header(None),
):
    """
    Receives webhook updates from Telegram.
    """
    # Verify Secret Token
    if x_telegram_bot_api_secret_token != settings.TELEGRAM_SECRET_TOKEN:
        logger.warning("Unauthorized webhook attempt")
        raise HTTPException(status_code=403, detail="Unauthorized")

    if not update.message or not update.message.text:
        return {"status": "ignored", "reason": "no text message"}

    # Auto-capture telegram_chat_id for reminders
    chat_id = update.message.chat.id
    
    # Validate chat_id range before storing
    # This prevents malicious values from being stored
    try:
        validate_telegram_chat_id(chat_id)
        background_tasks.add_task(app_settings_repo.update_chat_id, chat_id)
    except ValueError:
        logger.warning(f"Invalid chat_id received from webhook: {chat_id}")
        # Don't raise - just log and skip storing invalid chat_id
        # This prevents malicious values from being stored while allowing
        # the message processing to continue

    # Process in background to reply fast to Telegram
    background_tasks.add_task(
        process_incoming_message, update.message.text, chat_id
    )

    return {"status": "ok"}
