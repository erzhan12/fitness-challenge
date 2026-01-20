from fastapi import APIRouter, Header, BackgroundTasks, HTTPException
from app.config import settings
from app.models import TelegramUpdate
from app.services.workout_service import process_incoming_message
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

    # Extract user info
    chat_id = update.message.chat.id
    telegram_user = update.message.from_

    if not telegram_user:
        logger.warning("No user info in webhook message")
        return {"status": "ignored", "reason": "no user info"}

    telegram_user_id = telegram_user.id
    first_name = telegram_user.first_name
    username = telegram_user.username

    # Process in background to reply fast to Telegram
    background_tasks.add_task(
        process_incoming_message,
        update.message.text,
        chat_id,
        telegram_user_id,
        first_name,
        username
    )

    return {"status": "ok"}
