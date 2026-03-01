"""System settings API: get all, bulk update, secret masking, per-manager fallback."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import EffectiveOwnerId, get_current_user, get_db
from app.models.settings import SystemSettings
from app.models.user import AdminUser, UserRole
from app.schemas.settings import SystemSettingsResponse, SystemSettingsUpdate

router = APIRouter()

# Keys that contain sensitive values and must be masked in GET responses
SECRET_SETTING_KEYS = {"anthropic_api_key", "openai_api_key", "openrouter_api_key"}

MASK_PREFIX = "\u2022" * 8  # "••••••••"


def mask_secret_value(value: object) -> str:
    """Mask a secret value, showing only the last 4 characters."""
    if not value or not isinstance(value, str) or len(value) <= 4:
        return MASK_PREFIX
    return MASK_PREFIX + value[-4:]


def is_masked_value(value: object) -> bool:
    """Check if a value is still masked (unchanged by the user)."""
    return isinstance(value, str) and value.startswith(MASK_PREFIX)


def _build_masked_response(
    items: list[SystemSettings],
) -> list[SystemSettingsResponse]:
    """Build response list with secrets masked."""
    response = []
    for item in items:
        resp = SystemSettingsResponse.model_validate(item)
        if resp.key in SECRET_SETTING_KEYS:
            resp.value = mask_secret_value(resp.value)
        response.append(resp)
    return response


async def get_settings_for_owner(
    db: AsyncSession, owner_id: uuid.UUID | None
) -> dict[str, SystemSettings]:
    """Load merged settings for a given owner_id.

    Loads global settings (owner_id IS NULL) and per-manager settings (owner_id = value),
    then merges them with per-manager settings taking priority over globals.

    Args:
        db: Async SQLAlchemy session.
        owner_id: Manager UUID or None (admin / global scope).

    Returns:
        Dict mapping setting key to SystemSettings instance.
    """
    if owner_id is None:
        # Admin / global scope — just load global settings
        result = await db.execute(
            select(SystemSettings).where(SystemSettings.owner_id.is_(None))
        )
        return {s.key: s for s in result.scalars().all()}

    # Load both global and per-manager settings in one query
    result = await db.execute(
        select(SystemSettings).where(
            or_(
                SystemSettings.owner_id.is_(None),
                SystemSettings.owner_id == owner_id,
            )
        )
    )
    all_settings = result.scalars().all()

    # Merge: global first, then per-manager overrides
    merged: dict[str, SystemSettings] = {}
    for s in all_settings:
        if s.owner_id is None:
            # Global — only set if not already overridden by per-manager
            if s.key not in merged:
                merged[s.key] = s
        else:
            # Per-manager — always overrides
            merged[s.key] = s
    return merged


async def _get_merged_settings(
    db: AsyncSession, owner_id: uuid.UUID | None
) -> list[SystemSettings]:
    """Get merged settings list for response building."""
    merged = await get_settings_for_owner(db, owner_id)
    return list(merged.values())


@router.get("", response_model=list[SystemSettingsResponse])
async def get_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> list[SystemSettingsResponse]:
    """Get all system settings (merged: per-manager over global)."""
    items = await _get_merged_settings(db, owner_id)
    return _build_masked_response(items)


@router.put("", response_model=list[SystemSettingsResponse])
async def update_settings(
    body: SystemSettingsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> list[SystemSettingsResponse]:
    """Bulk update system settings.

    - Manager: creates/updates per-manager settings (owner_id = current_user.id).
    - Admin without impersonation: creates/updates global settings (owner_id IS NULL).
    - Admin with impersonation: creates/updates per-manager settings for target.
    """
    # Determine the target owner_id for writes
    target_owner_id = owner_id  # None for admin global, UUID for manager/impersonation

    for key, value in body.settings.items():
        # Skip secret fields that were not changed (still masked)
        if key in SECRET_SETTING_KEYS and is_masked_value(value):
            continue

        # Find existing setting for this key+owner_id combination
        if target_owner_id is None:
            result = await db.execute(
                select(SystemSettings).where(
                    SystemSettings.key == key,
                    SystemSettings.owner_id.is_(None),
                )
            )
        else:
            result = await db.execute(
                select(SystemSettings).where(
                    SystemSettings.key == key,
                    SystemSettings.owner_id == target_owner_id,
                )
            )
        setting = result.scalar_one_or_none()

        if setting is not None:
            setting.value = value
        else:
            new_setting = SystemSettings(key=key, value=value, owner_id=target_owner_id)
            db.add(new_setting)

    await db.flush()

    # Return merged settings after update (with masking)
    items = await _get_merged_settings(db, owner_id)
    return _build_masked_response(items)
