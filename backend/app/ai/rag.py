"""RAG pipeline: embed query, search Qdrant, format results.

Provides FAQ and objection retrieval for contextual AI responses.
Supports per-owner filtering via owner_id and per-script filtering via
script_id in Qdrant payloads.
"""

import uuid
from dataclasses import dataclass, field

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import ScoredPoint

from app.ai.embeddings import EmbeddingsManager

logger = structlog.get_logger(__name__)

# Score threshold for relevance filtering
DEFAULT_SCORE_THRESHOLD = 0.7

# Default number of results to return
DEFAULT_LIMIT = 3

# Qdrant collection names
FAQ_COLLECTION = "faq_knowledge"
OBJECTIONS_COLLECTION = "objections_knowledge"


@dataclass
class FAQResult:
    """A single FAQ search result."""

    question: str
    answer: str
    score: float


@dataclass
class ObjectionResult:
    """A single objection search result."""

    pattern: str
    response: str
    score: float


@dataclass
class RAGContext:
    """Combined RAG context with FAQ and objection results."""

    faq_items: list[FAQResult] = field(default_factory=list)
    objections: list[ObjectionResult] = field(default_factory=list)

    @property
    def has_context(self) -> bool:
        """Check if any relevant context was found."""
        return bool(self.faq_items or self.objections)


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline using Qdrant vector search.

    Embeds the user query, searches Qdrant for similar FAQ/objection entries,
    and returns formatted results above a score threshold.

    Supports per-owner filtering: when owner_id is provided, only results
    belonging to that owner are returned.
    """

    def __init__(
        self,
        qdrant_client: AsyncQdrantClient,
        embeddings_manager: EmbeddingsManager,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    ) -> None:
        self._qdrant = qdrant_client
        self._embeddings = embeddings_manager
        self._score_threshold = score_threshold

    @staticmethod
    def _build_search_filter(
        owner_id: uuid.UUID | None,
        script_id: uuid.UUID | None = None,
    ) -> "dict | None":
        """Build a Qdrant filter for owner_id and script_id.

        Combines:
        - must: [owner_id == str(owner_id)] when owner_id is provided
        - should: [script_id == str(script_id), script_id == ''] when script_id
          is provided (returns entries bound to the script OR global entries)

        Returns None when no filtering is needed (both are None).
        """
        if owner_id is None and script_id is None:
            return None

        from qdrant_client import models as qmodels

        must = []
        should = []

        if owner_id is not None:
            must.append(
                qmodels.FieldCondition(
                    key="owner_id",
                    match=qmodels.MatchValue(value=str(owner_id)),
                )
            )

        if script_id is not None:
            should.append(
                qmodels.FieldCondition(
                    key="script_id",
                    match=qmodels.MatchValue(value=str(script_id)),
                )
            )
            should.append(
                qmodels.FieldCondition(
                    key="script_id",
                    match=qmodels.MatchValue(value=""),
                )
            )

        return qmodels.Filter(
            must=must or None,
            should=should or None,
        )

    async def search_faq(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        owner_id: uuid.UUID | None = None,
        script_id: uuid.UUID | None = None,
    ) -> list[FAQResult]:
        """Search FAQ knowledge base for relevant entries.

        Args:
            query: User's message text.
            limit: Maximum number of results.
            owner_id: Optional owner UUID to filter results by manager.
            script_id: Optional script UUID to filter by qualification script.

        Returns:
            List of FAQResult sorted by score descending.
        """
        query_vector = await self._embeddings.embed_text(query)
        query_filter = self._build_search_filter(owner_id, script_id=script_id)

        try:
            results: list[ScoredPoint] = await self._qdrant.search(
                collection_name=FAQ_COLLECTION,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                score_threshold=self._score_threshold,
            )
        except Exception as e:
            logger.warning("faq_search_failed", error=str(e))
            return []

        logger.debug(
            "faq_search_completed",
            query=query[:100],
            results_count=len(results),
            top_score=results[0].score if results else None,
            owner_id=str(owner_id),
        )

        return [
            FAQResult(
                question=point.payload.get("question", ""),
                answer=point.payload.get("answer", ""),
                score=point.score,
            )
            for point in results
            if point.payload
        ]

    async def search_objections(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        owner_id: uuid.UUID | None = None,
        script_id: uuid.UUID | None = None,
    ) -> list[ObjectionResult]:
        """Search objections knowledge base for relevant entries.

        Args:
            query: User's message text.
            limit: Maximum number of results.
            owner_id: Optional owner UUID to filter results by manager.
            script_id: Optional script UUID to filter by qualification script.

        Returns:
            List of ObjectionResult sorted by score descending.
        """
        query_vector = await self._embeddings.embed_text(query)
        query_filter = self._build_search_filter(owner_id, script_id=script_id)

        try:
            results: list[ScoredPoint] = await self._qdrant.search(
                collection_name=OBJECTIONS_COLLECTION,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                score_threshold=self._score_threshold,
            )
        except Exception as e:
            logger.warning("objections_search_failed", error=str(e))
            return []

        logger.debug(
            "objections_search_completed",
            query=query[:100],
            results_count=len(results),
            top_score=results[0].score if results else None,
            owner_id=str(owner_id),
        )

        return [
            ObjectionResult(
                pattern=point.payload.get("pattern", ""),
                response=point.payload.get("response", ""),
                score=point.score,
            )
            for point in results
            if point.payload
        ]

    async def get_relevant_context(
        self,
        query: str,
        faq_limit: int = DEFAULT_LIMIT,
        objections_limit: int = DEFAULT_LIMIT,
        owner_id: uuid.UUID | None = None,
        script_id: uuid.UUID | None = None,
    ) -> RAGContext:
        """Get combined FAQ + objection context for a user message.

        Args:
            query: User's message text.
            faq_limit: Max FAQ results.
            objections_limit: Max objection results.
            owner_id: Optional owner UUID to filter results by manager.
            script_id: Optional script UUID to filter by qualification script.

        Returns:
            RAGContext with filtered and combined results.
        """
        faq_items = await self.search_faq(
            query, limit=faq_limit, owner_id=owner_id, script_id=script_id,
        )
        objections = await self.search_objections(
            query, limit=objections_limit, owner_id=owner_id, script_id=script_id,
        )

        logger.debug(
            "rag_context_assembled",
            faq_count=len(faq_items),
            objections_count=len(objections),
            query=query[:100],
            owner_id=str(owner_id),
        )

        return RAGContext(faq_items=faq_items, objections=objections)
