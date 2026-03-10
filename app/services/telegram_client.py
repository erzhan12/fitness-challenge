import httpx
from app.config import settings
import logging

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

_http_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient()
    return _http_client


async def send_chat_action(chat_id: int, action: str = "typing"):
    """
    Sends a chat action (e.g., 'typing', 'upload_photo') to a Telegram chat.
    The action will be displayed for 5 seconds or until a message is sent.
    """
    url = f"{TELEGRAM_API_BASE}/sendChatAction"
    payload = {"chat_id": chat_id, "action": action}

    logger.debug(f"Sending chat action '{action}' to chat_id {chat_id}")

    client = await _get_client()
    try:
        response = await client.post(url, json=payload, timeout=5.0)
        response.raise_for_status()
        logger.debug(f"Chat action sent successfully: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Failed to send chat action: {e}")
        return None


async def send_telegram_message(chat_id: int, text: str, parse_mode: str = "HTML"):
    """
    Sends a message to a Telegram chat.
    """
    url = f"{TELEGRAM_API_BASE}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}

    client = await _get_client()
    try:
        response = await client.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        # We don't raise here to avoid crashing the processing flow after DB writes
        return None


async def send_telegram_message_with_keyboard(
    chat_id: int,
    text: str,
    reply_markup: dict,
    parse_mode: str = "HTML",
):
    """Sends a message with an inline keyboard to a Telegram chat."""
    url = f"{TELEGRAM_API_BASE}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "reply_markup": reply_markup,
    }

    client = await _get_client()
    try:
        response = await client.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to send Telegram message with keyboard: {e}")
        return None


async def answer_callback_query(callback_query_id: str, text: str = None):
    """Answers a callback query to dismiss the loading spinner on inline buttons."""
    url = f"{TELEGRAM_API_BASE}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text

    client = await _get_client()
    try:
        response = await client.post(url, json=payload, timeout=5.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to answer callback query: {e}")
        return None
