"""API security module for authentication.

Provides shared authentication dependencies for API endpoints.
Uses API key authentication via the Authorization header.
"""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from app.config import settings

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

