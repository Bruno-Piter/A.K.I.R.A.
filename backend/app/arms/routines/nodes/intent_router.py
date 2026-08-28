"""Intent router: normalize intent and branch memory | skill | hybrid."""

from __future__ import annotations

from typing import Any

from app.arms.routines.emit import emit

_INTENTS = {"memory", "skill", "hybrid"}


def intent_router(state: dict[str, Any]) -> dict[str, Any]:
    emit({"type": "stage", "node": "intent_router", "status": "start"})
    intent = str(state.get("intent") or "memory").strip().lower()
    if intent not in _INTENTS:
        intent = "memory"
    mode = str(state.get("retrieval_mode") or "hybrid").strip().lower()
    if mode in {"multi_hop", "multi-hop", "multihop"}:
        mode = "multihop"
    if mode not in {"chunk", "entity", "hybrid", "multihop"}:
        mode = "hybrid"
    emit(
        {
            "type": "stage",
            "node": "intent_router",
            "status": "end",
            "intent": intent,
            "retrieval_mode": mode,
        }
    )
    return {"intent": intent, "retrieval_mode": mode}


def route_after_intent(state: dict[str, Any]) -> str:
    """Conditional edge from intent_router."""
    intent = str(state.get("intent") or "memory").strip().lower()
    if intent == "skill":
        return "react_tools"
    return "retrieval_router"


route_intent = route_after_intent