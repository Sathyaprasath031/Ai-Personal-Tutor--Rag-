"""Answer generation pipeline with context assembly and SSE streaming.

Emits Server-Sent Events:
- event: token    -> {"data": "..."}
- event: sources  -> [{"id": "S1", "filename": "...", "page_start": 1, ...}]
- event: done     -> {"text": "..."}
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterator

from ..config import settings
from .prompts import NOT_FOUND_HINT, build_system_prompt
from .rerank import rerank
from .retrieve import hybrid_search
from .rewrite import rewrite_query

logger = logging.getLogger(__name__)


def format_sources_xml(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks into clean XML with source IDs."""
    source_elements = []
    for i, c in enumerate(chunks, start=1):
        p_start = c.get("page_start", 1)
        p_end = c.get("page_end", 1)
        pages = f"p.{p_start}" if p_start == p_end else f"pp.{p_start}-{p_end}"
        filename = c.get("filename", "Notes")
        section = c.get("section", "General")
        content = c.get("content", "").strip()

        source_elements.append(
            f'<source id="S{i}" file="{filename}" pages="{pages}" section="{section}">\n'
            f'{content}\n'
            f'</source>'
        )

    return "<sources>\n" + "\n".join(source_elements) + "\n</sources>"


def format_sse(event: str, data: Any) -> str:
    """Format a Server-Sent Event message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _extract_relevant_passages(question: str, chunks: list[dict[str, Any]]) -> list[tuple[float, str, str, str, str]]:
    """Score individual sentences from retrieved chunks against query terms to extract exact matching facts."""
    stop_words = {
        'what', 'is', 'the', 'a', 'an', 'in', 'of', 'and', 'to', 'for', 'by', 'on', 'with',
        'does', 'how', 'can', 'you', 'explain', 'tell', 'me', 'about', 'define', 'describe',
        'why', 'which', 'who', 'where', 'when', 'are', 'was', 'were', 'it', 'its', 'from',
        'that', 'this', 'these', 'those', 'have', 'has', 'had', 'do', 'did', 'be', 'been'
    }
    q_words = [w for w in re.findall(r'[a-zA-Z0-9]+', question.lower()) if w not in stop_words and len(w) > 1]
    q_set = set(q_words)
    q_bigrams = {' '.join(q_words[i:i+2]) for i in range(len(q_words)-1)}

    scored_sentences = []
    seen_texts = set()

    for idx, chunk in enumerate(chunks, start=1):
        content = chunk.get('content', '')
        raw_sents = re.split(r'(?<=[.!?\n])\s+', content)
        for s in raw_sents:
            clean = re.sub(r'\s+', ' ', s.strip().strip('- *•\t'))
            if len(clean) < 20 or clean in seen_texts:
                continue
            seen_texts.add(clean)

            s_lower = clean.lower()
            s_words = set(re.findall(r'[a-zA-Z0-9]+', s_lower))

            word_matches = len(q_set & s_words)
            bigram_matches = sum(1 for bg in q_bigrams if bg in s_lower)

            score = (word_matches * 2.0) + (bigram_matches * 4.0)

            # Bonus for definition or formula indicators
            if any(ind in s_lower for ind in ['defined as', 'states that', 'formula', 'principle', 'core', 'primary', 'key', 'problem', 'purpose', '=']):
                score += 1.0

            if score > 0:
                scored_sentences.append((score, clean, f'[S{idx}]', chunk.get('filename', 'your notes'), chunk.get('section', 'Notes')))

    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    return scored_sentences


def _generate_offline_tutor_response(question: str, mode: str, relevant_chunks: list[dict[str, Any]]) -> str:
    """Generate realistic, pedagogically-tailored tutor responses extracting relevant facts from notes."""
    if not relevant_chunks:
        return (
            "I could not find information about this topic in your uploaded notes. "
            "Please make sure you have uploaded the relevant study materials for this subject."
        )

    q_lower = question.lower().strip()
    top_doc = relevant_chunks[0].get("filename", "your notes")
    top_section = relevant_chunks[0].get("section", "Study Notes")

    # Meta-queries about accessing/reading the uploaded file
    is_meta = any(phrase in q_lower for phrase in ["access", "see my", "read my", "upload", "what is this", "what did i", "can you read", "overview"])

    scored = _extract_relevant_passages(question, relevant_chunks)

    if not scored and not is_meta:
        return (
            f"I searched through your uploaded notes in **`{top_doc}`**, but could not find specific information "
            f"addressing: *\"{question}\"*.\n\n"
            f"Please verify that the relevant document or chapter is uploaded to this subject."
        )

    # Use extracted sentences if available, otherwise fallback to top chunk lines
    if scored:
        points = [f"{item[1]} {item[2]}" for item in scored[:4]]
        primary_answer = f"{scored[0][1]} {scored[0][2]}"
    else:
        content = relevant_chunks[0].get("content", "").strip()
        lines = [line.strip("- *• \t") for line in content.split("\n") if len(line.strip()) > 15]
        points = [f"{ln} [S1]" for ln in lines[:3]] or [f"{content[:120]}... [S1]"]
        primary_answer = points[0]

    bullets = "\n".join(f"- {p}" for p in points)

    if is_meta:
        return (
            f"**Yes! I have full access to your uploaded document (`{top_doc}`).** [S1]\n\n"
            f"Here are the core concepts and points extracted from your material:\n\n"
            f"{bullets}\n\n"
            f"You can ask me to explain any specific concept in detail, quiz you, or solve problems step-by-step!"
        )

    if mode == "eli5":
        return (
            f"### ELI5: Core Concept Explained Simply [S1]\n\n"
            f"Here is the simple breakdown of what your notes in **`{top_doc}`** state:\n\n"
            f"> {primary_answer}\n\n"
            f"**Key Takeaways:**\n"
            f"{bullets}\n\n"
            f"In everyday terms: this principle ensures clear cause-and-effect rules so everything behaves predictably!"
        )
    elif mode == "steps":
        numbered = "\n".join(f"{idx+1}. {pt}" for idx, pt in enumerate(points))
        return (
            f"### Step-by-Step Breakdown (`{top_doc}`)\n\n"
            f"Here is how this concept/procedure unfolds according to your notes:\n\n"
            f"{numbered}\n\n"
            f"Each step follows directly from the principles documented in your study material [S1]."
        )
    elif mode == "quiz":
        fact_preview = points[0].split("[")[0].strip()[:70]
        return (
            f"### 📝 Quick Knowledge Check ({top_doc}) [S1]\n\n"
            f"Based strictly on your uploaded materials, test your understanding:\n\n"
            f"1. According to your notes, what is the significance of: *\"{fact_preview}\"*?\n"
            f"2. Which primary law, rule, or formula governs this behavior?\n"
            f"3. How would you apply this concept to solve a practical problem?\n\n"
            f"*Reply with your answer and I will check it against your study materials!*"
        )
    elif mode == "socratic":
        return (
            f"Let's think through this together [S1].\n\n"
            f"Looking closely at your uploaded notes in **`{top_doc}`**, we find this key statement:\n\n"
            f"> {primary_answer}\n\n"
            f"What do you think is the underlying reason or mechanism that makes this true? "
            f"How does it connect to the other concepts in your notes?"
        )
    else:  # explain
        return (
            f"### {top_section}\n\n"
            f"**Direct Answer:**\n"
            f"{primary_answer}\n\n"
            f"**Key Supporting Details (`{top_doc}`):**\n"
            f"{bullets}\n\n"
            f"Feel free to ask a follow-up question or switch modes (e.g. **Quiz me** or **Step-by-step**) to test your grasp!"
        )


def _check_conversational_greeting(question: str) -> str | None:
    """Check if the user is greeting, thanking, or asking conversational casual questions.
    Returns an immediate warm, helpful reply explaining the tutor's role without heavy RAG search.
    """
    cleaned = re.sub(r"[^\w\s]", "", question.strip().lower())
    tokens = cleaned.split()
    if not tokens:
        return None

    greetings = {
        "hi", "hello", "hey", "hola", "greetings", "good morning", "good afternoon",
        "good evening", "howdy", "sup", "yo", "wassup", "hiya"
    }
    intro_queries = {
        "who are you", "what are you", "what can you do", "what is your job",
        "what is your role", "what is your responsibility", "help", "how do you work"
    }
    gratitude = {
        "thank you", "thanks", "thx", "appreciate it", "great job", "awesome"
    }

    joined = " ".join(tokens)

    # 1. Direct greeting
    if joined in greetings or (len(tokens) <= 3 and any(t in greetings for t in tokens)):
        return (
            "Hello! Welcome to your **AI Personal Tutor**! 👋\n\n"
            "I'm here to help you study and understand your course materials. My job is to explain complex concepts, "
            "walk you through problem-solving step-by-step, generate practice quizzes, and answer questions strictly "
            "grounded in your uploaded lecture notes, PDFs, and slide decks—with verifiable citations.\n\n"
            "Upload your notes or select a subject from the sidebar, and ask me anything you'd like to learn!"
        )

    # 2. Who are you / what is your job
    if any(q in joined for q in intro_queries):
        return (
            "I am your **AI Personal Tutor**! 🎓\n\n"
            "**My work and responsibilities include:**\n"
            "- **Grounded Explanations**: Teaching you concepts directly from your uploaded slides, PDFs, and lecture notes.\n"
            "- **Precise Citations**: Citing exact page and slide numbers so you can verify facts for exams.\n"
            "- **Multiple Learning Modes**: Explaining simply (ELI5), step-by-step derivations, generating practice quizzes, or Socratic guided questions.\n"
            "- **Zero Guesswork**: If something isn't in your materials, I'll clearly let you know.\n\n"
            "Feel free to ask a question from your course notes or upload a new document to get started!"
        )

    # 3. Thank you / gratitude
    if any(g in joined for g in gratitude) and len(tokens) <= 4:
        return (
            "You're very welcome! Glad I could help! 😊\n\n"
            "Let me know if you have any more questions from your notes or need another topic explained."
        )

    return None


def answer_stream(
    user_id: str,
    question: str,
    history: list[dict[str, Any]] | None = None,
    subject_id: str | None = None,
    mode: str = "explain",
) -> Iterator[str]:
    """Retrieve context, build grounded prompt, and stream answer via Anthropic API."""
    history = history or []

    # 0. Instant conversational fast-path (greetings, 'who are you', thanks)
    greeting_reply = _check_conversational_greeting(question)
    if greeting_reply:
        yield format_sse("sources", [])
        words = re.split(r"(\s+)", greeting_reply)
        for w in words:
            if w:
                yield format_sse("token", w)
        yield format_sse("done", {"text": greeting_reply, "sources": []})
        return

    # 1. Query rewrite for conversational follow-ups
    query = rewrite_query(question, history)

    # 2. Hybrid search (dense pgvector + sparse FTS + RRF)
    # Optimized: k_final=3 minimizes cross-encoder pairs to achieve <10-15s response latency
    candidates = hybrid_search(user_id, query, subject_id=subject_id, k_each=6, k_final=3)

    # 3. Cross-encoder rerank (top_n=3 keeps the most accurate notes)
    top_candidates = rerank(query, candidates, top_n=3)

    # 4. Relevance gate: filter out weak chunks below threshold
    relevant_chunks = [
        c for c in top_candidates
        if c.get("score", 0.0) >= settings.relevance_threshold
    ]

    # 5. Build prompt
    if relevant_chunks:
        sources_xml = format_sources_xml(relevant_chunks)
        user_content = f"{sources_xml}\n\nStudent question: {question}"
    else:
        user_content = f"{NOT_FOUND_HINT}\n\nStudent question: {question}"

    # Build conversation messages payload (last 6 turns + current)
    messages: list[dict[str, str]] = []
    for turn in history[-6:]:
        messages.append({
            "role": turn["role"],
            "content": turn["content"],
        })
    messages.append({
        "role": "user",
        "content": user_content,
    })

    system_prompt = build_system_prompt(mode)

    # 6. Stream tokens from LLM (OpenAI, Groq, Anthropic, or offline engine)
    full_response_text = []

    # Priority 1: OpenAI or custom OpenAI-compatible endpoint
    if settings.openai_api_key and not settings.openai_api_key.startswith("sk-REPLACE") and "your-openai" not in settings.openai_api_key:
        import openai
        client = openai.OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
        try:
            oai_messages = [{"role": "system", "content": system_prompt}] + messages
            stream = client.chat.completions.create(
                model=settings.openai_model,
                messages=oai_messages,
                temperature=0.3,
                max_tokens=2048,
                stream=True,
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    full_response_text.append(token)
                    yield format_sse("token", token)
        except Exception as exc:
            logger.error("OpenAI streaming failed: %s", exc)
            err_msg = f"\n\n[Tutor Error: {str(exc)}]"
            full_response_text.append(err_msg)
            yield format_sse("token", err_msg)

    # Priority 2: Groq (Free Tier)
    elif settings.groq_api_key and not settings.groq_api_key.startswith("gsk-REPLACE") and "your-groq" not in settings.groq_api_key:
        import openai
        client = openai.OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        try:
            groq_messages = [{"role": "system", "content": system_prompt}] + messages
            stream = client.chat.completions.create(
                model=settings.groq_model,
                messages=groq_messages,
                temperature=0.3,
                stream=True,
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    full_response_text.append(token)
                    yield format_sse("token", token)
        except Exception as exc:
            logger.error("Groq streaming failed: %s", exc)
            err_msg = f"\n\n[Tutor Error: {str(exc)}]"
            full_response_text.append(err_msg)
            yield format_sse("token", err_msg)

    # Priority 3: Google Gemini API (Free Tier via OpenAI endpoint)
    elif settings.gemini_api_key and not settings.gemini_api_key.startswith("AIzaSy-REPLACE") and "your-gemini" not in settings.gemini_api_key:
        import openai
        client = openai.OpenAI(
            api_key=settings.gemini_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        try:
            gemini_messages = [{"role": "system", "content": system_prompt}] + messages
            stream = client.chat.completions.create(
                model=settings.gemini_model,
                messages=gemini_messages,
                temperature=0.3,
                stream=True,
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    full_response_text.append(token)
                    yield format_sse("token", token)
        except Exception as exc:
            logger.error("Gemini streaming failed: %s", exc)
            err_msg = f"\n\n[Tutor Error: {str(exc)}]"
            full_response_text.append(err_msg)
            yield format_sse("token", err_msg)

    # Priority 3: Anthropic Claude
    elif settings.anthropic_api_key and not settings.anthropic_api_key.startswith("sk-ant-REPLACE") and "your-anthropic" not in settings.anthropic_api_key:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        try:
            with client.messages.stream(
                model=settings.llm_model,
                max_tokens=1500,
                system=system_prompt,
                messages=messages,
            ) as stream:
                for token in stream.text_stream:
                    full_response_text.append(token)
                    yield format_sse("token", token)
        except Exception as exc:
            logger.error("LLM streaming failed: %s", exc)
            err_msg = f"\n\n[Tutor Error: {str(exc)}]"
            full_response_text.append(err_msg)
            yield format_sse("token", err_msg)

    # Priority 4: Realistic Offline Engine
    else:
        simulated = _generate_offline_tutor_response(question, mode, relevant_chunks)
        for token in simulated.split(" "):
            yield format_sse("token", token + " ")
            full_response_text.append(token + " ")

    # 7. Emit sources event for the UI citation drawer
    sources_payload = [
        {
            "id": f"S{i}",
            "filename": c.get("filename", "Notes"),
            "page_start": c.get("page_start", 1),
            "page_end": c.get("page_end", 1),
            "section": c.get("section", "General"),
            "snippet": c.get("content", "")[:300],
            "score": round(c.get("score", 0.0), 3),
        }
        for i, c in enumerate(relevant_chunks, start=1)
    ]
    yield format_sse("sources", sources_payload)

    # 8. Emit done event
    yield format_sse("done", {"text": "".join(full_response_text)})
