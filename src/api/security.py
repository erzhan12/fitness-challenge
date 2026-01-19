"""API security module for authentication.

Provides shared authentication dependencies for API endpoints.
Uses API key authentication via the Authorization header.
Supports user context via X-Telegram-User-Id header for multi-user operations.
"""

from typing import Optional
from fastapi import HTTPException, Security, Header, status
from fastapi.security import APIKeyHeader
from app.config import settings
from src.core.models import AppUser
from src.core.repositories import app_user_repo

# API key header configuration
api_key_header = APIKeyHeader(
    name="Authorization",
    auto_error=False,
    description="API key for authentication. Use 'Bearer <key>' or just '<key>'",
)


async def verify_api_key(key: str = Security(api_key_header)) -> str:
    """Verify the API key from the Authorization header.

    Accepts both 'Bearer <key>' and raw '<key>' formats.

    Raises:
        HTTPException: 401 if key is missing, 403 if key is invalid

    Returns:
        The validated API key
    """
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Allow "Bearer <key>" or just "<key>"
    token = key.replace("Bearer ", "").strip()

    if token != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return token


async def verify_api_key_optional(
    key: str = Security(api_key_header),
) -> str | None:
    """Optionally verify the API key.

    Returns None if no key provided (for public read endpoints).

    Returns:
        The validated API key or None
    """
    if not key:
        return None

    token = key.replace("Bearer ", "").strip()

    if token != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return token


# =============================================================================
# User Context Dependencies
# =============================================================================


async def get_current_user(
    x_telegram_user_id: Optional[str] = Header(None, alias="X-Telegram-User-Id"),
) -> AppUser:
    """Get the current user from X-Telegram-User-Id header.

    This dependency is used for user-scoped endpoints that require authentication.
    The user must exist and be approved.

    Args:
        x_telegram_user_id: Telegram user ID from header

    Raises:
        HTTPException: 401 if header is missing
        HTTPException: 403 if user not found or not approved

    Returns:
        The authenticated AppUser instance
    """
    if not x_telegram_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Telegram-User-Id header",
        )

    try:
        telegram_user_id = int(x_telegram_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-Telegram-User-Id header: must be an integer",
        )

    user = await app_user_repo.get_by_telegram_user_id(telegram_user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found. Please register first.",
        )

    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User not approved. Current status: {user.status}",
        )

    return user


async def get_current_user_optional(
    x_telegram_user_id: Optional[str] = Header(None, alias="X-Telegram-User-Id"),
) -> Optional[AppUser]:
    """Optionally get the current user from X-Telegram-User-Id header.

    This dependency is used for public endpoints that can optionally use user context.
    Returns None if no header provided.

    Args:
        x_telegram_user_id: Telegram user ID from header (optional)

    Returns:
        The AppUser instance if found and approved, None otherwise
    """
    if not x_telegram_user_id:
        return None

    try:
        telegram_user_id = int(x_telegram_user_id)
    except ValueError:
        return None

    user = await app_user_repo.get_by_telegram_user_id(telegram_user_id)

    if not user or not user.is_approved:
        return None

    return user

