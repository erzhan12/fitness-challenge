"""Habit Reward API client for sending daily completion notifications."""

import httpx
import logging
from datetime import date
from typing import Optional

from app.config import settings
from src.core import setup_django

setup_django()

from src.core.repositories import user_settings_repo

logger = logging.getLogger(__name__)


async def send_habit_completion(
    user_id: int, completion_date: Optional[date] = None
) -> bool:
    """Send daily habit completion to Habit Reward API.

    Reads per-user API key and habit ID from UserSettings DB record.

    Args:
        user_id: The AppUser ID (used to fetch per-user habit reward settings)
        completion_date: Date of completion (optional, for potential backdating)

    Returns:
        True if successful (200 response), False otherwise
    """
    user_settings = await user_settings_repo.get_by_user_id(user_id)
    if not user_settings:
        logger.debug("No user settings found, skipping habit reward")
        return False

    api_key = user_settings.habit_reward_api_key
    habit_id = user_settings.habit_reward_habit_id
    if not api_key or not habit_id:
        logger.debug("Habit Reward not configured for user, skipping")
        return False

    base_url = settings.HABIT_REWARD_BASE_URL

    url = f"{base_url}/v1/habits/{habit_id}/complete"

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }

    payload = {}
    if completion_date:
        payload["target_date"] = completion_date.isoformat()

    logger.info(f"Sending habit completion (user_id: {user_id}, habit_id: {habit_id})")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json=payload if payload else None,
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            logger.info(f"Habit completion sent successfully (status: {response.status_code})")
            return True
        except httpx.HTTPStatusError as e:
            # Don't log response body - may contain sensitive data
            logger.error(
                f"Habit Reward API error (user_id: {user_id}, status: {e.response.status_code})"
            )
            return False
        except httpx.RequestError as e:
            # Log error type only, not full details which may include URL/headers
            logger.error(
                f"Habit Reward request failed (user_id: {user_id}, error: {type(e).__name__})"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error in habit completion (user_id: {user_id}, error: {type(e).__name__})"
            )
            return False
