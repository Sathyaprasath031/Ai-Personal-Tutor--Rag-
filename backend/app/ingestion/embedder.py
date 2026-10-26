"""Embedding model wrapper using sentence-transformers.

Uses BAAI/bge-small-en-v1.5 (384 dimensions) by default.
Model is loaded once and cached in memory.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from ..config import settings

logger = logging.getLogger(__name__)

# BGE models recommend this prefix for retrieval *queries* (not passages).
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    """Load and cache the embedding model."""
    logger.info("Loading embedding model: %s", settings.embed_model)
    model = SentenceTransformer(settings.embed_model)
    logger.info("Embedding model loaded (dim=%d)", model.get_sentence_embedding_dimension())
    return model


def embed_passages(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Embed document passages (no query prefix).

    Returns a list of float vectors, one per input text.
    """
    if not texts:
        return []
    model = _load_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """Embed a search query (with BGE query prefix).

    Returns a single float vector.
    """
    model = _load_model()
    embedding = model.encode(
        QUERY_PREFIX + text,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embedding.tolist()
