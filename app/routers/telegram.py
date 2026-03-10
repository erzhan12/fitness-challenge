from fastapi import APIRouter, Header, BackgroundTasks, HTTPException
from app.config import settings
from app.models import TelegramUpdate
from app.services.workout_service import process_incoming_message, process_callback_query
from collections import OrderedDict
from threading import Lock
import logging
import time

router = APIRouter(prefix="/telegram", tags=["Telegram"])
logger = logging.getLogger(__name__)
_replay_cache_lock = Lock()
_replay_cache: OrderedDict[int, float] = OrderedDict()


def _is_replay(update_id: int, now: float) -> bool:
    ttl_seconds = settings.TELEGRAM_WEBHOOK_REPLAY_TTL_SECONDS
    max_entries = settings.TELEGRAM_WEBHOOK_REPLAY_CACHE_SIZE
    if ttl_seconds <= 0 or max_entries <= 0:
        return False

    cutoff = now - ttl_seconds
    with _replay_cache_lock:
        while _replay_cache:
            _, timestamp = next(iter(_replay_cache.items()))
            if timestamp >= cutoff:
                break
            _replay_cache.popitem(last=False)

        if update_id in _replay_cache:
            return True

        _replay_cache[update_id] = now
        if len(_replay_cache) > max_entries:
            _replay_cache.popitem(last=False)

    return False


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

    now = time.time()
    if _is_replay(update.update_id, now):
        logger.warning("Duplicate webhook update ignored: update_id=%s", update.update_id)
        return {"status": "ignored", "reason": "duplicate update"}

    max_age_seconds = settings.TELEGRAM_WEBHOOK_MAX_AGE_SECONDS
    if update.message and max_age_seconds > 0:
        age_seconds = now - update.message.date
        if age_seconds > max_age_seconds:
            logger.warning(
                "Stale webhook update ignored: update_id=%s age_seconds=%s",
                update.update_id,
                int(age_seconds),
            )
            return {"status": "ignored", "reason": "stale update"}

    # Handle callback queries (inline button presses)
    if update.callback_query:
        cb = update.callback_query
        if not cb.data or len(cb.data) > 100:
            return {"status": "ignored", "reason": "invalid callback data"}
        if cb.from_ and cb.message and cb.message.chat and cb.data:
            background_tasks.add_task(
                process_callback_query,
                cb.id,
                cb.data,
                cb.from_.id,
                cb.message.chat.id,
            )
            return {"status": "ok"}
        return {"status": "ignored", "reason": "incomplete callback query"}

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
