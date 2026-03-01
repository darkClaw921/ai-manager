"""Sentence-transformers model loader and embedding manager."""

import asyncio
import structlog
from typing import ClassVar

logger = structlog.get_logger(__name__)

# Default multilingual model — 384-dimensional vectors
DEFAULT_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_DIMENSION = 384


class EmbeddingsManager:
    """Manages sentence-transformer model loading and text embedding.

    Uses lazy loading (model loaded on first call) and singleton caching.
    CPU-bound encode operations run in a thread pool to avoid blocking the event loop.
    """

    _instances: ClassVar[dict[str, "EmbeddingsManager"]] = {}

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self._model_name = model_name
        self._model = None

    @classmethod
    def get_instance(cls, model_name: str = DEFAULT_MODEL_NAME) -> "EmbeddingsManager":
        """Return a cached singleton instance for the given model name."""
        if model_name not in cls._instances:
            cls._instances[model_name] = cls(model_name)
        return cls._instances[model_name]

    def _load_model(self):
        """Load the sentence-transformers model (lazy, first call only)."""
        if self._model is None:
            logger.info("Loading sentence-transformers model: %s", self._model_name)
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
            logger.info(
                "Model loaded: %s (dimension=%d)",
                self._model_name,
                self._model.get_sentence_embedding_dimension(),
            )
        return self._model

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous encode — runs in the calling thread."""
        model = self._load_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string, returning a vector of floats.

        Runs the CPU-bound encoding in a thread pool.
        """
        results = await asyncio.to_thread(self._encode_sync, [text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings, returning a list of vectors.

        Runs the CPU-bound encoding in a thread pool.
        """
        if not texts:
            return []
        return await asyncio.to_thread(self._encode_sync, texts)

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        return VECTOR_DIMENSION

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model_name
