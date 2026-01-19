"""REST API endpoints for user management."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.models import (
    UserOut,
    UserCreate,
    UserUpdate,
    UserSettingsOut,
    UserSettingsUpdate,
    UserWithSettingsOut,
    ErrorResponse,
)
from src.api.security import verify_api_key, get_current_user
from src.core.models import AppUser
from src.core.repositories import app_user_repo, user_settings_repo

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register a new user with Telegram user ID. "
    "New users start with 'pending' status and must be approved by an admin.",
    responses={
        201: {"description": "User registered successfully (pending approval)"},
        400: {"model": ErrorResponse, "description": "User already exists"},
    },
)
async def register_user(data: UserCreate) -> UserOut:
    """Register a new user.

    Creates a new user with 'pending' status.
    The user must be approved by an admin before they can use the API.
    """
    # Check if user already exists
    existing_user = await app_user_repo.get_by_telegram_user_id(data.telegram_user_id)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with telegram_user_id {data.telegram_user_id} already exists",
        )

    # Create the user
    user = await app_user_repo.create({
        "telegram_user_id": data.telegram_user_id,
        "username": data.username,
        "first_name": data.first_name,
        "timezone": data.timezone,
        "status": AppUser.Status.PENDING,
    })

    # Create default user settings
    await user_settings_repo.get_or_create(user.id)

    return UserOut.model_validate(user)


@router.get(
    "/me",
    response_model=UserWithSettingsOut,
    summary="Get current user profile",
    description="Get the profile and settings of the currently authenticated user. "
    "Requires X-Telegram-User-Id header.",
    responses={
        200: {"description": "User profile and settings"},
        401: {"model": ErrorResponse, "description": "Missing X-Telegram-User-Id header"},
        403: {"model": ErrorResponse, "description": "User not found or not approved"},
    },
)
async def get_current_user_profile(
    current_user: AppUser = Depends(get_current_user),
) -> UserWithSettingsOut:
    """Get the current user's profile and settings."""
    user_settings = await user_settings_repo.get_by_user_id(current_user.id)

    return UserWithSettingsOut(
        user=UserOut.model_validate(current_user),
        settings=UserSettingsOut.model_validate(user_settings) if user_settings else None,
    )


@router.patch(
    "/me",
    response_model=UserOut,
    summary="Update current user profile",
    description="Update the profile of the currently authenticated user. "
    "Requires X-Telegram-User-Id header.",
    responses={
        200: {"description": "User profile updated"},
        401: {"model": ErrorResponse, "description": "Missing X-Telegram-User-Id header"},
        403: {"model": ErrorResponse, "description": "User not found or not approved"},
    },
)
async def update_current_user_profile(
    data: UserUpdate,
    current_user: AppUser = Depends(get_current_user),
) -> UserOut:
    """Update the current user's profile."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        # No fields to update, return current user
        return UserOut.model_validate(current_user)

    updated_user = await app_user_repo.update(current_user.id, update_data)
    return UserOut.model_validate(updated_user)


@router.get(
    "/me/settings",
    response_model=UserSettingsOut,
    summary="Get current user settings",
    description="Get the settings of the currently authenticated user. "
    "Requires X-Telegram-User-Id header.",
    responses={
        200: {"description": "User settings"},
        401: {"model": ErrorResponse, "description": "Missing X-Telegram-User-Id header"},
        403: {"model": ErrorResponse, "description": "User not found or not approved"},
    },
)
async def get_current_user_settings(
    current_user: AppUser = Depends(get_current_user),
) -> UserSettingsOut:
    """Get the current user's settings."""
    user_settings = await user_settings_repo.get_or_create(current_user.id)
    return UserSettingsOut.model_validate(user_settings)


@router.patch(
    "/me/settings",
    response_model=UserSettingsOut,
    summary="Update current user settings",
    description="Update the settings of the currently authenticated user. "
    "Requires X-Telegram-User-Id header.",
    responses={
        200: {"description": "User settings updated"},
        401: {"model": ErrorResponse, "description": "Missing X-Telegram-User-Id header"},
        403: {"model": ErrorResponse, "description": "User not found or not approved"},
    },
)
async def update_current_user_settings(
    data: UserSettingsUpdate,
    current_user: AppUser = Depends(get_current_user),
) -> UserSettingsOut:
    """Update the current user's settings."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        # No fields to update, return current settings
        user_settings = await user_settings_repo.get_or_create(current_user.id)
        return UserSettingsOut.model_validate(user_settings)

    # Ensure settings exist
    await user_settings_repo.get_or_create(current_user.id)

    updated_settings = await user_settings_repo.update(current_user.id, update_data)
    return UserSettingsOut.model_validate(updated_settings)


# =============================================================================
# Admin Endpoints (require API key)
# =============================================================================


@router.post(
    "/{user_id}/approve",
    response_model=UserOut,
    summary="Approve a user (Admin)",
    description="Approve a pending user. Requires API key authentication.",
    responses={
        200: {"description": "User approved"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
)
async def approve_user(
    user_id: int,
    _: str = Depends(verify_api_key),
) -> UserOut:
    """Approve a user (admin only)."""
    user = await app_user_repo.approve(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )
    return UserOut.model_validate(user)


@router.post(
    "/{user_id}/reject",
    response_model=UserOut,
    summary="Reject a user (Admin)",
    description="Reject a pending user. Requires API key authentication.",
    responses={
        200: {"description": "User rejected"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
)
async def reject_user(
    user_id: int,
    _: str = Depends(verify_api_key),
) -> UserOut:
    """Reject a user (admin only)."""
    user = await app_user_repo.reject(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )
    return UserOut.model_validate(user)


@router.get(
    "",
    response_model=list[UserOut],
    summary="List all users (Admin)",
    description="List all users. Requires API key authentication.",
    responses={
        200: {"description": "List of users"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
    },
)
async def list_users(
    status_filter: str | None = None,
    _: str = Depends(verify_api_key),
) -> list[UserOut]:
    """List all users (admin only)."""
    users = await app_user_repo.get_all(status=status_filter)
    return [UserOut.model_validate(user) for user in users]


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Get user by ID (Admin)",
    description="Get a user by their ID. Requires API key authentication.",
    responses={
        200: {"description": "User details"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
)
async def get_user(
    user_id: int,
    _: str = Depends(verify_api_key),
) -> UserOut:
    """Get a user by ID (admin only)."""
    user = await app_user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )
    return UserOut.model_validate(user)
