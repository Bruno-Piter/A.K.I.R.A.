"""Generate node: produce the final answer from LLM + gathered context."""

from __future__ import annotations

import logging
from typing import Any

from app.arms.routines.emit import emit
from app.arms.routines.history import persist_turn
from app.arms.routines.llm import LLMConfigError, stream_tokens

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are A.K.I.R.A., an agentic knowledge assistant. "
    "Answer using the retrieved memory and tool observations when present. "
    "Cite chunk or entity ids when you use them. "
    "If evidence is missing, say what you could not find. Be concise."
)


def generate(state: dict[str, Any]) -> dict[str, Any]:
    emit({"type": "stage", "node": "generate", "status": "start"})
    query = str(state.get("query") or "").strip()
    plan = str(state.get("plan") or "")
    retrieved = list(state.get("retrieved") or state.get("hits") or [])
    tools = list(state.get("tool_results") or [])
    history = list(state.get("messages") or [])
    quality_reason = str(state.get("quality_reason") or "")
    existing_error = state.get("error")
    error = str(existing_error) if existing_error else ""

    prompt = _build_prompt(query, plan, retrieved, tools, history, quality_reason)
    answer = _fallback_answer(query, retrieved, tools, error)
    try:
        chunks: list[str] = []
        for token in stream_tokens(prompt, system=_SYSTEM):
            if token:
                chunks.append(token)
                emit({"type": "token", "content": token})
        if "".join(chunks).strip():
            answer = "".join(chunks).strip()
    except LLMConfigError:
        pass
    except Exception as exc:
        logger.info("generate LLM failed: %s", exc)
        error = (error + "; " if error else "") + f"llm failed: {exc}"

    session_id = str(state.get("session_id") or state.get("thread_id") or "")
    if session_id:
        index = max(len(history) // 2, 0)
        persist_turn(session_id, query, answer, index=index, title=query[:80] or None)

    sources = _hit_sources(retrieved, [str(x) for x in (state.get("document_ids") or []) if x])
    new_messages = history + [
        {"role": "user", "content": query},
        {"role": "assistant", "content": answer},
    ]
    emit({"type": "stage", "node": "generate", "status": "end"})
    out: dict[str, Any] = {
        "answer": answer,
        "messages": new_messages,
        "sources": sources,
        "hits": retrieved,
        "retrieved": retrieved,
        "error": error or None,
    }
    return out


def _hit_sources(hits: list[dict[str, Any]], document_ids: list[str]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for hit in hits:
        chunk_id = str(hit.get("chunk_id") or hit.get("entity_id") or "")
        document_id = str(hit.get("document_id") or "")
        if document_ids and document_id and document_id not in document_ids:
            continue
        if not chunk_id and not document_id:
            continue
        sources.append(
            {
                "chunk_id": chunk_id or document_id,
                "document_id": document_id,
                "title": str(hit.get("title") or ""),
                "excerpt": str(hit.get("excerpt") or ""),
                "score": hit.get("score"),
            }
        )
    return sources


def _build_prompt(
    query: str,
    plan: str,
    retrieved: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    history: list[dict[str, str]],
    quality_reason: str,
) -> str:
    parts = [f"Question: {query}"]
    if plan:
        parts.append(f"Plan: {plan}")
    if quality_reason:
        parts.append(f"Quality gate: {quality_reason}")
    if history:
        tail = history[-6:]
        rendered = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in tail
        )
        parts.append(f"Conversation so far:\n{rendered}")
    if retrieved:
        lines = []
        for hit in retrieved[:8]:
            cid = hit.get("chunk_id") or hit.get("entity_id") or ""
            title = hit.get("title") or ""
            excerpt = hit.get("excerpt") or ""
            score = hit.get("score")
            lines.append(f"- [{cid}] {title} (score={score}): {excerpt}")
        parts.append("Retrieved memory:\n" + "\n".join(lines))
    else:
        parts.append("Retrieved memory: (none)")
    if tools:
        lines = []
        for item in tools[:8]:
            name = item.get("name") or item.get("type") or "tool"
            content = item.get("content") or item.get("output") or ""
            lines.append(f"- {name}: {content}")
        parts.append("Tool observations:\n" + "\n".join(lines))
    parts.append("Write the final answer for the user.")
    return "\n\n".join(parts)


def _fallback_answer(
    query: str,
    retrieved: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    error: str,
) -> str:
    excerpts = [
        str(h.get("excerpt") or h.get("title") or "").strip()
        for h in retrieved
        if str(h.get("excerpt") or h.get("title") or "").strip()
    ]
    tool_bits = [
        str(t.get("content") or t.get("output") or "").strip()
        for t in tools
        if str(t.get("content") or t.get("output") or "").strip()
    ]
    if excerpts:
        body = " ".join(excerpts[:3])
        return f"Based on memory: {body}"
    if tool_bits:
        return f"Tool result: {tool_bits[0][:800]}"
    if error:
        return (
            f"I could not complete a full answer for {query!r}. "
            f"Degraded mode: {error}"
        )
    return f"I do not have enough retrieved context yet to answer {query!r}."