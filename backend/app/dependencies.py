"""FastAPI dependencies: database session, JWT authentication, owner scoping."""

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.user import AdminUser, UserRole
from app.services.auth_service import decode_token, get_user_by_id

security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency that provides an async database session."""
    session = async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUser:
    """Extract and validate JWT token, return the authenticated user."""
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
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

    return user


async def require_admin(
    current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> AdminUser:
    """Require the current user to have admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


async def get_effective_owner_id(
    current_user: Annotated[AdminUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_impersonate_manager_id: str | None = Header(None),
) -> uuid.UUID | None:
    """Determine the effective owner_id for data scoping.

    - Manager users always get their own UUID (see only their data).
    - Admin users without X-Impersonate-Manager-Id header get None (see all data).
    - Admin users with the header get the target manager UUID after validation.

    Raises:
        HTTPException 404: If the impersonation target is not found or not a manager.
    """
    # Managers always scoped to their own data
    if current_user.role != UserRole.ADMIN:
        return current_user.id

    # Admin without impersonation — sees everything
    if x_impersonate_manager_id is None:
        return None

    # Admin with impersonation — validate target user
    try:
        target_id = uuid.UUID(x_impersonate_manager_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manager not found",
        )

    target_user = await get_user_by_id(db, target_id)
    if target_user is None or target_user.role != UserRole.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manager not found",
        )

    return target_id


# Annotated type alias for convenience in endpoint signatures
EffectiveOwnerId = Annotated[uuid.UUID | None, Depends(get_effective_owner_id)]
