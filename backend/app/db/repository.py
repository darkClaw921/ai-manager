"""Generic base CRUD repository for SQLAlchemy async models."""

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic async CRUD repository.

    Provides get, get_multi, create, update, delete operations
    for any SQLAlchemy model inheriting from Base.
    """

    def __init__(self, model: type[ModelT], db_session: AsyncSession) -> None:
        self._model = model
        self._db = db_session

    async def get(self, entity_id: uuid.UUID) -> ModelT | None:
        """Get a single entity by its UUID primary key."""
        result = await self._db.execute(
            select(self._model).where(self._model.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        offset: int = 0,
        limit: int = 50,
        filters: list | None = None,
        order_by: Any | None = None,
    ) -> list[ModelT]:
        """Get multiple entities with optional filtering, ordering, and pagination.

        Args:
            offset: Number of rows to skip.
            limit: Maximum number of rows to return.
            filters: List of SQLAlchemy filter expressions.
            order_by: Column or expression to order by.

        Returns:
            List of model instances.
        """
        stmt = select(self._model)

        if filters:
            for f in filters:
                stmt = stmt.where(f)

        if order_by is not None:
            stmt = stmt.order_by(order_by)

        stmt = stmt.offset(offset).limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def count(self, filters: list | None = None) -> int:
        """Count entities matching the given filters."""
        stmt = select(func.count()).select_from(self._model)
        if filters:
            for f in filters:
                stmt = stmt.where(f)
        result = await self._db.execute(stmt)
        return result.scalar_one()

    async def create(self, **kwargs: Any) -> ModelT:
        """Create a new entity and flush to get the ID."""
        entity = self._model(**kwargs)
        self._db.add(entity)
        await self._db.flush()
        await self._db.refresh(entity)
        return entity

    async def update(self, entity: ModelT, **kwargs: Any) -> ModelT:
        """Update an existing entity's attributes and flush."""
        for key, value in kwargs.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        await self._db.flush()
        await self._db.refresh(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Delete an entity."""
        await self._db.delete(entity)
        await self._db.flush()
