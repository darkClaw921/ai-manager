"""Authentication endpoints: login, refresh token, register."""

import uuid
from typing import Annotated

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import BaseRepository
from app.dependencies import get_db
from app.models.booking import BookingSettings
from app.models.settings import SystemSettings
from app.models.user import AdminUser, UserRole
from app.rate_limit import limiter
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, RegisterResponse, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_id,
)

router = APIRouter()


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Authenticate user and return JWT tokens."""
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Refresh access token using refresh token."""
    payload = decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    access_token = create_access_token(str(user.id), user.role.value)
    new_refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


# Default settings that are copied for each new manager
_DEFAULT_MANAGER_SETTINGS = [
    {
        "key": "llm_provider",
        "value": "anthropic",
        "description": "LLM provider: anthropic, openai, openrouter",
    },
    {
        "key": "ai_model",
        "value": "claude-sonnet-4-5",
        "description": "AI model used for conversations",
    },
    {
        "key": "max_conversation_messages",
        "value": 50,
        "description": "Maximum number of messages loaded as context for AI",
    },
    {
        "key": "qualification_timeout_hours",
        "value": 24,
        "description": "Hours before a qualifying lead is marked as lost",
    },
    {
        "key": "default_greeting",
        "value": "Здравствуйте! Я виртуальный ассистент. Чем могу помочь?",
        "description": "Default greeting message for new conversations",
    },
    {
        "key": "booking_mode",
        "value": "internal",
        "description": "Booking mode: internal, external_link, handoff",
    },
    {
        "key": "anthropic_api_key",
        "value": "",
        "description": "Anthropic API key (used when llm_provider=anthropic)",
    },
    {
        "key": "openai_api_key",
        "value": "",
        "description": "OpenAI API key (used when llm_provider=openai)",
    },
    {
        "key": "openrouter_api_key",
        "value": "",
        "description": "OpenRouter API key (used when llm_provider=openrouter)",
    },
]


async def _create_default_settings_for_manager(
    db: AsyncSession, owner_id: uuid.UUID
) -> None:
    """Create default SystemSettings entries for a new manager.

    Copies the global defaults so each manager starts with their own
    independent set of settings.
    """
    for item in _DEFAULT_MANAGER_SETTINGS:
        setting = SystemSettings(
            key=item["key"],
            value=item["value"],
            description=item["description"],
            owner_id=owner_id,
        )
        db.add(setting)
    await db.flush()


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RegisterResponse:
    """Register a new manager account (public endpoint, rate limited).

    Creates an AdminUser with role=manager, auto-creates BookingSettings
    and default SystemSettings for the new manager.
    """
    # Check email uniqueness
    repo = BaseRepository(AdminUser, db)
    existing = await repo.get_multi(filters=[AdminUser.email == body.email], limit=1)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create the manager user
    user = await repo.create(
        email=body.email,
        password_hash=_hash_password(body.password),
        full_name=body.full_name,
        role=UserRole.MANAGER,
        is_active=True,
    )

    # Auto-create BookingSettings
    repo_bs = BaseRepository(BookingSettings, db)
    await repo_bs.create(manager_id=user.id)

    # Auto-create default SystemSettings for the manager
    await _create_default_settings_for_manager(db, user.id)

    # Generate JWT tokens
    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = create_refresh_token(str(user.id))

    return RegisterResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )
