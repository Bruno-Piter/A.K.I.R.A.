"""Retrieval router: dispatch chunk | entity | hybrid | multihop via memory ARM."""

from __future__ import annotations

import logging
from typing import Any

from app.arms.routines.emit import emit

logger = logging.getLogger(__name__)

_MODE_TO_MEMORY = {
    "chunk": "chunk",
    "entity": "entity",
    "hybrid": "hybrid",
    "multihop": "multi_hop",
    "multi_hop": "multi_hop",
    "multi-hop": "multi_hop",
}


def retrieval_router(state: dict[str, Any]) -> dict[str, Any]:
    emit({"type": "stage", "node": "retrieval_router", "status": "start"})
    query = str(state.get("query") or "").strip()
    mode = str(state.get("retrieval_mode") or "hybrid").strip().lower()
    memory_mode = _MODE_TO_MEMORY.get(mode, "hybrid")
    document_ids = {str(x) for x in (state.get("document_ids") or []) if x}

    hits: list[dict[str, Any]] = []
    error = None
    try:
        from app.arms.memory.retriever import search

        hits = search(query, mode=memory_mode, top_k=8)  # type: ignore[arg-type]
    except Exception as exc:
        logger.info("memory search failed: %s", exc)
        error = f"memory retrieval failed: {exc}"
        hits = []

    if document_ids:
        filtered = [
            h
            for h in hits
            if not h.get("document_id") or str(h.get("document_id")) in document_ids
        ]
        if filtered:
            hits = filtered

    graph_context: dict[str, Any] = {"nodes": [], "links": []}
    seed = _seed_id(hits)
    if seed:
        try:
            from app.arms.memory import neighborhood

            graph_context = neighborhood(seed, hops=2)
        except Exception as exc:
            logger.info("neighborhood after retrieval failed: %s", exc)

    emit(
        {
            "type": "stage",
            "node": "retrieval_router",
            "status": "end",
            "mode": memory_mode,
            "hit_count": len(hits),
        }
    )
    out: dict[str, Any] = {
        "retrieved": hits,
        "hits": hits,
        "retrieval_mode": "multihop" if memory_mode == "multi_hop" else mode,
        "graph_context": graph_context,
        "graph_payload": graph_context,
        "error": error,
    }
    return out


def route_after_retrieval(state: dict[str, Any]) -> str:
    """Hybrid continues to the MCP ReAct subgraph; memory-only goes to quality."""
    if int(state.get("backtrack_count") or 0) > 0:
        return "quality_gate"
    if str(state.get("intent") or "") == "hybrid":
        return "react_tools"
    return "quality_gate"


def _seed_id(hits: list[dict[str, Any]]) -> str | None:
    for key in ("entity_id", "document_id", "chunk_id"):
        for hit in hits:
            value = hit.get(key)
            if value:
                return str(value)
    return None