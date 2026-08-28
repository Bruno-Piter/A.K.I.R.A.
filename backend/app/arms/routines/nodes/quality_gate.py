"""Quality gate: validate retrieval/tool results. Exactly one backtrack allowed."""

from __future__ import annotations

from typing import Any

from app.arms.routines.emit import emit

_NEXT_MODE = {
    "chunk": "hybrid",
    "entity": "hybrid",
    "hybrid": "multihop",
    "multihop": "hybrid",
    "multi_hop": "hybrid",
}


def quality_gate(state: dict[str, Any]) -> dict[str, Any]:
    emit({"type": "stage", "node": "quality_gate", "status": "start"})
    intent = str(state.get("intent") or "memory")
    retrieved = list(state.get("retrieved") or state.get("hits") or [])
    tools = list(state.get("tool_results") or [])
    count = int(state.get("backtrack_count") or 0)
    mode = str(state.get("retrieval_mode") or "hybrid")

    retrieval_ok = _retrieval_ok(retrieved)
    tools_ok = _tools_ok(tools)

    if intent == "memory":
        ok = retrieval_ok
        reason = "retrieval has usable hits" if ok else "retrieval empty or low quality"
        retry_target = "retrieval"
    elif intent == "skill":
        ok = tools_ok
        reason = "tools returned observations" if ok else "tools returned nothing useful"
        retry_target = "tools"
    else:
        ok = retrieval_ok or tools_ok
        reason = (
            "hybrid has retrieval or tool evidence"
            if ok
            else "hybrid: both retrieval and tools were weak"
        )
        retry_target = "retrieval" if not retrieval_ok else "tools"

    backtrack_target = ""
    new_mode = mode
    new_count = count
    if not ok and count < 1:
        backtrack_target = retry_target
        new_count = count + 1
        if retry_target == "retrieval":
            new_mode = _NEXT_MODE.get(mode, "hybrid")
        reason = f"{reason}; backtrack #{new_count} -> {backtrack_target}"
    elif not ok:
        reason = f"{reason}; backtrack budget exhausted, continuing to generate"

    emit(
        {
            "type": "stage",
            "node": "quality_gate",
            "status": "end",
            "quality_ok": ok,
            "backtrack_target": backtrack_target,
            "backtrack_count": new_count,
        }
    )
    return {
        "quality_ok": ok,
        "quality_reason": reason,
        "backtrack_count": new_count,
        "backtrack_target": backtrack_target,
        "retrieval_mode": new_mode,
        "hits": retrieved,
        "retrieved": retrieved,
    }


def route_after_quality(state: dict[str, Any]) -> str:
    """Backtrack only when this node just requested it (backtrack_target set)."""
    target = str(state.get("backtrack_target") or "").strip().lower()
    if target in {"retrieval", "retrieval_router"}:
        return "retrieval_router"
    if target in {"tools", "react_tools", "skill"}:
        return "react_tools"
    return "generate"


def _retrieval_ok(hits: list[dict[str, Any]]) -> bool:
    if not hits:
        return False
    for hit in hits:
        excerpt = str(hit.get("excerpt") or hit.get("title") or "").strip()
        if excerpt:
            return True
    return False


def _tools_ok(results: list[dict[str, Any]]) -> bool:
    if not results:
        return False
    for item in results:
        name = str(item.get("name") or "").lower()
        content = str(item.get("content") or item.get("output") or "").strip()
        if name in {"error", "none"}:
            continue
        if str(item.get("type") or "") == "error":
            continue
        if content.lower().startswith("skill tools failed"):
            continue
        if content:
            return True
    return False