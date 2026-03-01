"""Celery tasks for Qdrant collection synchronization.

Periodically syncs FAQ and objection data from PostgreSQL to Qdrant.
Also supports single-item upsert for real-time updates.
"""

import asyncio
import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _sync_faq_async() -> int:
    """Async implementation of full FAQ collection sync."""
    from qdrant_client import AsyncQdrantClient

    from app.ai.embeddings import EmbeddingsManager
    from app.ai.qdrant_init import sync_faq_to_qdrant
    from app.config import get_settings
    from app.db.session import get_db_session

    settings = get_settings()
    qdrant = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    embeddings = EmbeddingsManager.get_instance()

    try:
        async with get_db_session() as db:
            count = await sync_faq_to_qdrant(db, qdrant, embeddings)
            logger.info("Qdrant FAQ sync completed: %d items", count)
            return count
    finally:
        await qdrant.close()


async def _sync_objections_async() -> int:
    """Async implementation of full objections collection sync."""
    from qdrant_client import AsyncQdrantClient

    from app.ai.embeddings import EmbeddingsManager
    from app.ai.qdrant_init import sync_objections_to_qdrant
    from app.config import get_settings
    from app.db.session import get_db_session

    settings = get_settings()
    qdrant = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    embeddings = EmbeddingsManager.get_instance()

    try:
        async with get_db_session() as db:
            count = await sync_objections_to_qdrant(db, qdrant, embeddings)
            logger.info("Qdrant objections sync completed: %d items", count)
            return count
    finally:
        await qdrant.close()


async def _sync_single_faq_async(faq_id: str) -> bool:
    """Async implementation of single FAQ item upsert to Qdrant."""
    from qdrant_client import AsyncQdrantClient, models
    from sqlalchemy import select

    from app.ai.embeddings import EmbeddingsManager
    from app.ai.rag import FAQ_COLLECTION
    from app.config import get_settings
    from app.db.session import get_db_session
    from app.models.script import FAQItem

    settings = get_settings()
    qdrant = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    embeddings = EmbeddingsManager.get_instance()

    try:
        async with get_db_session() as db:
            result = await db.execute(select(FAQItem).where(FAQItem.id == faq_id))
            faq_item = result.scalar_one_or_none()

            if faq_item is None or not faq_item.is_active:
                # If item deleted or inactive, remove from Qdrant
                try:
                    await qdrant.delete(
                        collection_name=FAQ_COLLECTION,
                        points_selector=models.PointIdsList(points=[faq_id]),
                    )
                    logger.info("Removed FAQ %s from Qdrant (inactive/deleted)", faq_id)
                except Exception:
                    logger.debug("FAQ %s not found in Qdrant, skipping removal", faq_id)
                return True

            text = f"{faq_item.question} {faq_item.answer}"
            embedding = await embeddings.embed_text(text)

            point = models.PointStruct(
                id=str(faq_item.id),
                vector=embedding,
                payload={
                    "faq_id": str(faq_item.id),
                    "question": faq_item.question,
                    "answer": faq_item.answer,
                    "category": faq_item.category or "",
                },
            )

            await qdrant.upsert(collection_name=FAQ_COLLECTION, points=[point])
            logger.info("Upserted single FAQ %s to Qdrant", faq_id)
            return True
    finally:
        await qdrant.close()


@celery_app.task(
    name="app.tasks.qdrant_sync.sync_faq_collection",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def sync_faq_collection(self) -> int:
    """Full resync of FAQ items from PostgreSQL to Qdrant.

    Periodic task: runs every 5 minutes via Beat schedule.

    Returns:
        Number of items synced.
    """
    try:
        return asyncio.run(_sync_faq_async())
    except Exception as exc:
        logger.exception("Qdrant FAQ sync failed")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.qdrant_sync.sync_objections_collection",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def sync_objections_collection(self) -> int:
    """Full resync of objection scripts from PostgreSQL to Qdrant.

    Periodic task: runs every 5 minutes via Beat schedule.

    Returns:
        Number of items synced.
    """
    try:
        return asyncio.run(_sync_objections_async())
    except Exception as exc:
        logger.exception("Qdrant objections sync failed")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.qdrant_sync.sync_single_faq",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def sync_single_faq(self, faq_id: str) -> bool:
    """Upsert a single FAQ item to Qdrant (real-time update).

    Called when a FAQ item is created or updated via the admin API.

    Args:
        faq_id: UUID string of the FAQ item.

    Returns:
        True on success.
    """
    try:
        return asyncio.run(_sync_single_faq_async(faq_id))
    except Exception as exc:
        logger.exception("Single FAQ sync failed: %s", faq_id)
        raise self.retry(exc=exc)
