"""Admin users API: CRUD, admin-only access."""

import uuid
from typing import Annotated

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import BaseRepository
from app.dependencies import get_db, require_admin
from app.models.booking import BookingSettings
from app.models.user import AdminUser, UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[AdminUser, Depends(require_admin)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[UserResponse]:
    """List all admin users (admin only)."""
    repo = BaseRepository(AdminUser, db)
    total = await repo.count()
    offset = (page - 1) * page_size
    items = await repo.get_multi(offset=offset, limit=page_size, order_by=AdminUser.created_at.desc())
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=[UserResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        pages=pages,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[AdminUser, Depends(require_admin)],
) -> UserResponse:
    """Create a new admin user (admin only)."""
    repo = BaseRepository(AdminUser, db)

    # Check if email already exists
    existing = await repo.get_multi(filters=[AdminUser.email == body.email], limit=1)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    user = await repo.create(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        is_active=body.is_active,
    )

    # Auto-create BookingSettings for managers
    if body.role == UserRole.MANAGER:
        repo_bs = BaseRepository(BookingSettings, db)
        await repo_bs.create(manager_id=user.id)

    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[AdminUser, Depends(require_admin)],
) -> UserResponse:
    """Get user details (admin only)."""
    repo = BaseRepository(AdminUser, db)
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[AdminUser, Depends(require_admin)],
) -> UserResponse:
    """Update a user (admin only)."""
    repo = BaseRepository(AdminUser, db)
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = body.model_dump(exclude_unset=True)

    # Hash password if provided
    if "password" in update_data:
        update_data["password_hash"] = hash_password(update_data.pop("password"))

    # Track role change before update
    old_role = user.role
    new_role = update_data.get("role")

    user = await repo.update(user, **update_data)

    # Handle BookingSettings on role change
    if new_role is not None and old_role != new_role:
        repo_bs = BaseRepository(BookingSettings, db)
        if new_role == UserRole.MANAGER:
            # Create BookingSettings if doesn't exist
            existing = await repo_bs.get_multi(filters=[BookingSettings.manager_id == user.id], limit=1)
            if not existing:
                await repo_bs.create(manager_id=user.id)
        elif old_role == UserRole.MANAGER:
            # Remove BookingSettings when leaving manager role
            existing = await repo_bs.get_multi(filters=[BookingSettings.manager_id == user.id], limit=1)
            if existing:
                await repo_bs.delete(existing[0])

    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AdminUser, Depends(require_admin)],
) -> None:
    """Delete a user (admin only). Cannot delete yourself."""
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")

    repo = BaseRepository(AdminUser, db)
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Delete BookingSettings before deleting user (no CASCADE)
    repo_bs = BaseRepository(BookingSettings, db)
    existing_bs = await repo_bs.get_multi(filters=[BookingSettings.manager_id == user_id], limit=1)
    if existing_bs:
        await repo_bs.delete(existing_bs[0])

    await repo.delete(user)
