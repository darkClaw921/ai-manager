"""Qdrant collection initialization and data synchronization.

Creates faq_knowledge and objections_knowledge collections on startup.
Provides sync functions to populate Qdrant from PostgreSQL data.
"""

import structlog
import uuid

from qdrant_client import AsyncQdrantClient, models
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import VECTOR_DIMENSION, EmbeddingsManager
from app.ai.rag import FAQ_COLLECTION, OBJECTIONS_COLLECTION
from app.models.script import FAQItem, ObjectionScript

logger = structlog.get_logger(__name__)


async def ensure_collections(client: AsyncQdrantClient) -> None:
    """Create Qdrant collections if they do not already exist.

    Idempotent: checks for existence before creating.

    Collections:
        - faq_knowledge: 384-dim cosine vectors with FAQ payload
        - objections_knowledge: 384-dim cosine vectors with objection payload
    """
    # FAQ collection
    if not await client.collection_exists(FAQ_COLLECTION):
        await client.create_collection(
            collection_name=FAQ_COLLECTION,
            vectors_config=models.VectorParams(
                size=VECTOR_DIMENSION,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info("Created Qdrant collection: %s", FAQ_COLLECTION)
    else:
        logger.debug("Qdrant collection already exists: %s", FAQ_COLLECTION)

    # Objections collection
    if not await client.collection_exists(OBJECTIONS_COLLECTION):
        await client.create_collection(
            collection_name=OBJECTIONS_COLLECTION,
            vectors_config=models.VectorParams(
                size=VECTOR_DIMENSION,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info("Created Qdrant collection: %s", OBJECTIONS_COLLECTION)
    else:
        logger.debug("Qdrant collection already exists: %s", OBJECTIONS_COLLECTION)


async def sync_faq_to_qdrant(
    db_session: AsyncSession,
    qdrant_client: AsyncQdrantClient,
    embeddings_manager: EmbeddingsManager,
) -> int:
    """Synchronize active FAQ items from PostgreSQL to Qdrant.

    Loads all active FAQItem records, generates embeddings for their questions,
    and upserts them into the faq_knowledge collection.

    Args:
        db_session: Async SQLAlchemy session.
        qdrant_client: Async Qdrant client.
        embeddings_manager: Embeddings manager for vectorization.

    Returns:
        Number of FAQ items synced.
    """
    result = await db_session.execute(
        select(FAQItem).where(FAQItem.is_active.is_(True))
    )
    faq_items = list(result.scalars().all())

    if not faq_items:
        logger.info("No active FAQ items to sync")
        return 0

    # Build texts for embedding: question + answer for better retrieval
    texts = [f"{item.question} {item.answer}" for item in faq_items]
    embeddings = await embeddings_manager.embed_batch(texts)

    points = [
        models.PointStruct(
            id=str(item.id),
            vector=embedding,
            payload={
                "faq_id": str(item.id),
                "question": item.question,
                "answer": item.answer,
                "category": item.category or "",
                "owner_id": str(item.owner_id) if item.owner_id else "",
                "script_id": str(item.qualification_script_id) if item.qualification_script_id else "",
            },
        )
        for item, embedding in zip(faq_items, embeddings, strict=True)
    ]

    await qdrant_client.upsert(
        collection_name=FAQ_COLLECTION,
        points=points,
    )

    logger.info("Synced %d FAQ items to Qdrant", len(points))
    return len(points)


async def sync_objections_to_qdrant(
    db_session: AsyncSession,
    qdrant_client: AsyncQdrantClient,
    embeddings_manager: EmbeddingsManager,
) -> int:
    """Synchronize active objection scripts from PostgreSQL to Qdrant.

    Loads all active ObjectionScript records, generates embeddings for their patterns,
    and upserts them into the objections_knowledge collection.

    Args:
        db_session: Async SQLAlchemy session.
        qdrant_client: Async Qdrant client.
        embeddings_manager: Embeddings manager for vectorization.

    Returns:
        Number of objection scripts synced.
    """
    result = await db_session.execute(
        select(ObjectionScript).where(ObjectionScript.is_active.is_(True))
    )
    objections = list(result.scalars().all())

    if not objections:
        logger.info("No active objection scripts to sync")
        return 0

    # Embed the objection pattern for similarity matching
    texts = [item.objection_pattern for item in objections]
    embeddings = await embeddings_manager.embed_batch(texts)

    points = [
        models.PointStruct(
            id=str(item.id),
            vector=embedding,
            payload={
                "objection_id": str(item.id),
                "pattern": item.objection_pattern,
                "response": item.response_template,
                "category": item.category or "",
                "owner_id": str(item.owner_id) if item.owner_id else "",
                "script_id": str(item.qualification_script_id) if item.qualification_script_id else "",
            },
        )
        for item, embedding in zip(objections, embeddings, strict=True)
    ]

    await qdrant_client.upsert(
        collection_name=OBJECTIONS_COLLECTION,
        points=points,
    )

    logger.info("Synced %d objection scripts to Qdrant", len(points))
    return len(points)


async def sync_all(
    db_session: AsyncSession,
    qdrant_client: AsyncQdrantClient,
    embeddings_manager: EmbeddingsManager,
) -> dict[str, int]:
    """Synchronize all knowledge bases from PostgreSQL to Qdrant.

    Returns:
        Dict with counts: {"faq": N, "objections": M}
    """
    await ensure_collections(qdrant_client)

    faq_count = await sync_faq_to_qdrant(db_session, qdrant_client, embeddings_manager)
    obj_count = await sync_objections_to_qdrant(db_session, qdrant_client, embeddings_manager)

    return {"faq": faq_count, "objections": obj_count}
