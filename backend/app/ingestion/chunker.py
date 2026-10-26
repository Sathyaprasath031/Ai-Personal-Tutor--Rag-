"""Structure-aware document chunker.

Groups consecutive body blocks under the current heading, then splits
into ~CHUNK_WORDS-word chunks with CHUNK_OVERLAP_WORDS overlap.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .parser import ParsedDoc
from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A single chunk ready for embedding and storage."""
    index: int
    page_start: int
    page_end: int
    section_path: str
    content: str


def _word_count(text: str) -> int:
    return len(text.split())


def chunk_document(parsed: ParsedDoc) -> list[Chunk]:
    """Split a ParsedDoc into sized chunks, respecting heading boundaries.

    Strategy:
    - Track the current section heading.
    - Accumulate body blocks in a buffer.
    - When the buffer hits CHUNK_WORDS, flush it as a chunk.
    - Keep an overlap tail from the end of the flushed buffer.
    - A new heading always forces a flush (don't mix sections).
    """
    max_words = settings.chunk_words
    overlap_words = settings.chunk_overlap_words

    chunks: list[Chunk] = []
    section = "Introduction"
    # buffer entries: (page_number, paragraph_text)
    buf: list[tuple[int, str]] = []

    def _flush():
        """Create a Chunk from the current buffer."""
        if not buf:
            return
        combined = " ".join(text for _, text in buf)
        chunks.append(Chunk(
            index=len(chunks),
            page_start=buf[0][0],
            page_end=buf[-1][0],
            section_path=section,
            content=combined,
        ))

    def _overlap_tail() -> list[tuple[int, str]]:
        """Return the tail of the buffer that provides overlap for the next chunk."""
        if not buf:
            return []
        tail: list[tuple[int, str]] = []
        word_budget = overlap_words
        for page, text in reversed(buf):
            wc = _word_count(text)
            tail.insert(0, (page, text))
            word_budget -= wc
            if word_budget <= 0:
                break
        # Don't return the full buffer as tail (that would be no progress)
        if len(tail) >= len(buf):
            return []
        return tail

    for block in parsed.blocks:
        if block.is_heading:
            # Flush the previous section's buffer
            _flush()
            buf.clear()
            section = block.text
            continue

        buf.append((block.page, block.text))

        # Check if buffer exceeds the word limit
        total_words = sum(_word_count(text) for _, text in buf)
        if total_words >= max_words:
            _flush()
            tail = _overlap_tail()
            buf.clear()
            buf.extend(tail)

    # Flush remaining content
    _flush()

    # Drop tiny fragments (< 15 words) that won't contribute meaningful retrieval
    result = [c for c in chunks if _word_count(c.content) >= 15]

    # Re-index after filtering
    for i, chunk in enumerate(result):
        chunk.index = i

    logger.info("Chunked document into %d chunks (dropped %d tiny fragments)",
                len(result), len(chunks) - len(result))
    return result
