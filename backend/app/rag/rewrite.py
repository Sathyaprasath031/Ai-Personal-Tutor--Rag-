"""Conversational query rewriter for multi-turn tutoring.

Resolves pronouns and context references into a standalone search query.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)

REWRITE_SYSTEM = (
    "You are an expert query reformulation assistant. "
    "Rewrite the student's latest message as a single, clear, standalone search query "
    "suitable for retrieving information from lecture notes or textbooks. "
    "Resolve all pronouns, conversational references, and ellipses using the prior dialogue. "
    "Output ONLY the standalone search query. Do NOT add preamble, quotes, or explanations."
)


def rewrite_query(question: str, history: list[dict[str, Any]] | None = None) -> str:
    """Rewrite a follow-up question using chat history into a standalone search query."""
    if not history:
        return question.strip()

    # Fast-path: If the question is already detailed and contains no ambiguous pronouns, skip heavy LLM rewrite!
    import re
    pronouns = {"it", "its", "they", "them", "their", "this", "that", "these", "those", "he", "him", "his", "she", "her"}
    words = set(re.findall(r"[a-zA-Z]+", question.lower()))
    if not (words & pronouns) and len(words) >= 5:
        return question.strip()

    # Priority 1: OpenAI
    if settings.openai_api_key and not settings.openai_api_key.startswith("sk-REPLACE") and "your-openai" not in settings.openai_api_key:
        try:
            import openai
            client = openai.OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url or None)
            recent_turns = history[-6:]
            transcript = "\n".join(f"{turn['role'].capitalize()}: {turn['content'][:400]}" for turn in recent_turns)
            prompt = f"Prior Conversation:\n{transcript}\n\nLatest Student Message: {question}"
            res = client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "system", "content": REWRITE_SYSTEM}, {"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.0,
            )
            rewritten = (res.choices[0].message.content or "").strip()
            if rewritten:
                logger.info("OpenAI rewrote '%s' -> '%s'", question, rewritten)
                return rewritten
        except Exception as exc:
            logger.warning("OpenAI query rewriting failed: %s. Using original query.", exc)

    # Priority 2: Groq (Free Tier)
    elif settings.groq_api_key and not settings.groq_api_key.startswith("gsk-REPLACE") and "your-groq" not in settings.groq_api_key:
        try:
            import openai
            client = openai.OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")
            recent_turns = history[-6:]
            transcript = "\n".join(f"{turn['role'].capitalize()}: {turn['content'][:400]}" for turn in recent_turns)
            prompt = f"Prior Conversation:\n{transcript}\n\nLatest Student Message: {question}"
            res = client.chat.completions.create(
                model=settings.groq_model,
                messages=[{"role": "system", "content": REWRITE_SYSTEM}, {"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.0,
            )
            rewritten = (res.choices[0].message.content or "").strip()
            if rewritten:
                logger.info("Groq rewrote '%s' -> '%s'", question, rewritten)
                return rewritten
        except Exception as exc:
            logger.warning("Groq query rewriting failed: %s. Using original query.", exc)

    # Priority 3: Google Gemini API
    elif settings.gemini_api_key and not settings.gemini_api_key.startswith("AIzaSy-REPLACE") and "your-gemini" not in settings.gemini_api_key:
        try:
            import openai
            client = openai.OpenAI(api_key=settings.gemini_api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
            recent_turns = history[-6:]
            transcript = "\n".join(f"{turn['role'].capitalize()}: {turn['content'][:400]}" for turn in recent_turns)
            prompt = f"Prior Conversation:\n{transcript}\n\nLatest Student Message: {question}"
            res = client.chat.completions.create(
                model=settings.gemini_model,
                messages=[{"role": "system", "content": REWRITE_SYSTEM}, {"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.0,
            )
            rewritten = (res.choices[0].message.content or "").strip()
            if rewritten:
                logger.info("Gemini rewrote '%s' -> '%s'", question, rewritten)
                return rewritten
        except Exception as exc:
            logger.warning("Gemini query rewriting failed: %s. Using original query.", exc)

    # Priority 3: Anthropic
    elif settings.anthropic_api_key and not settings.anthropic_api_key.startswith("sk-ant-REPLACE") and "your-anthropic" not in settings.anthropic_api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            recent_turns = history[-6:]
            transcript = "\n".join(f"{turn['role'].capitalize()}: {turn['content'][:400]}" for turn in recent_turns)
            prompt = f"Prior Conversation:\n{transcript}\n\nLatest Student Message: {question}"
            response = client.messages.create(
                model=settings.rewrite_model,
                max_tokens=100,
                system=REWRITE_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            rewritten = response.content[0].text.strip()
            if rewritten:
                logger.info("Anthropic rewrote '%s' -> '%s'", question, rewritten)
                return rewritten
        except Exception as exc:
            logger.warning("Anthropic query rewriting failed: %s. Using original query.", exc)

    return question.strip()
