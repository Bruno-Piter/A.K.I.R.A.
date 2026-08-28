"""ConversationSession / Message persistence via the memory ARM (Neo4j)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def load_history(session_id: str) -> list[dict[str, str]]:
    """Best-effort history from the memory neighborhood around a session node."""
    sid = (session_id or "").strip()
    if not sid:
        return []
    try:
        from app.arms.memory import neighborhood

        payload = neighborhood(sid, hops=1)
    except Exception as exc:
        logger.info("neighborhood history load failed: %s", exc)
        return []
    messages: list[dict[str, str]] = []
    for node in payload.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        if str(node.get("type") or "") != "Message":
            continue
        content = str(node.get("label") or "").strip()
        if content:
            messages.append({"role": "assistant", "content": content})
    return messages


def persist_turn(
    thread_id: str,
    user_content: str,
    assistant_content: str,
    *,
    index: int = 0,
    title: str | None = None,
    session_id: str | None = None,
) -> None:
    """MERGE ConversationSession + user/assistant Message nodes via memory ARM."""
    sid = (session_id or thread_id or "").strip()
    if not sid:
        return
    try:
        from app.arms.memory.graph_db import merge_conversation_session, merge_message
    except Exception as exc:
        logger.info("memory ARM unavailable for history save: %s", exc)
        return
    try:
        heading = title if title is not None else ((user_content or "").strip().replace("\n", " ")[:80] or None)
        merge_conversation_session(sid, title=heading)
        merge_message(
            f"{sid}:user:{index}",
            session_id=sid,
            role="user",
            content=user_content or "",
            index=index * 2,
        )
        merge_message(
            f"{sid}:assistant:{index}",
            session_id=sid,
            role="assistant",
            content=assistant_content or "",
            index=index * 2 + 1,
        )
    except Exception as exc:
        logger.info("persist_turn failed (neo4j down?): %s", exc)