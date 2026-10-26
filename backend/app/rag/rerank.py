"""Cross-encoder reranker using BAAI/bge-reranker-base.

Scores (query, passage) pairs and maps logits to [0, 1] via sigmoid.
"""

from __future__ import annotations

import logging
import math
from functools import lru_cache

from sentence_transformers import CrossEncoder

from ..config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_reranker() -> CrossEncoder:
    """Load and cache the cross-encoder model."""
    logger.info("Loading reranker model: %s", settings.rerank_model)
    model = CrossEncoder(settings.rerank_model)
    logger.info("Reranker model loaded successfully")
    return model


def rerank(query: str, candidates: list[dict], top_n: int = 6) -> list[dict]:
    """Score candidates using the cross-encoder reranker and return the top_n."""
    if not candidates:
        return []

    # Construct input pairs: (query, section + content)
    pairs = [
        (query, f"{c.get('section', '')}\n{c['content']}")
        for c in candidates
    ]

    try:
        model = _load_reranker()
        raw_scores = model.predict(pairs, show_progress_bar=False)

        for candidate, raw_score in zip(candidates, raw_scores):
            # Sigmoid activation to normalize logits into [0, 1]
            candidate["score"] = 1.0 / (1.0 + math.exp(-float(raw_score)))

        sorted_candidates = sorted(candidates, key=lambda c: c["score"], reverse=True)
        return sorted_candidates[:top_n]
    except Exception as exc:
        logger.error("Reranking failed: %s. Falling back to initial rankings.", exc)
        for c in candidates:
            c.setdefault("score", c.get("rrf_score", 0.5))
        return candidates[:top_n]
