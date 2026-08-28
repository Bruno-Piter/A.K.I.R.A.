"""Planner node: interpret the user question and produce a route-ready plan."""

from __future__ import annotations

import logging
from typing import Any

from app.arms.routines.emit import emit
from app.arms.routines.history import load_history
from app.arms.routines.llm import LLMConfigError, complete_json

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are the A.K.I.R.A. query planner. Return STRICT JSON only. "
    "No markdown, no commentary. Keys: plan, intent, retrieval_mode, rationale. "
    "intent: memory | skill | hybrid. "
    "retrieval_mode: chunk | entity | hybrid | multihop."
)

_PROMPT = (
    "Given the user question, produce a plan for the orchestrator.\n"
    "intent=memory: answer from the knowledge graph / ingested documents\n"
    "intent=skill: needs external MCP tools (web search, filesystem, ingest)\n"
    "intent=hybrid: retrieval AND tools\n"
    "Question:\n{query}\n"
)


def planner(state: dict[str, Any]) -> dict[str, Any]:
    emit({"type": "stage", "node": "planner", "status": "start"})
    query = str(state.get("query") or "").strip()
    session_id = str(state.get("session_id") or state.get("thread_id") or "").strip()
    document_ids = list(state.get("document_ids") or [])

    history = list(state.get("messages") or [])
    if session_id and not history:
        history = load_history(session_id)

    planned = heuristic_plan(query)
    try:
        parsed = complete_json(_PROMPT.format(query=query), system=_SYSTEM)
        planned = _merge_llm_plan(planned, parsed)
    except (LLMConfigError, Exception) as exc:
        logger.info("planner LLM unavailable, using heuristic: %s", empty_exc(exc))

    emit({"type": "stage", "node": "planner", "status": "end", "intent": planned["intent"]})
    return {
        "query": query,
        "session_id": session_id,
        "thread_id": session_id,
        "document_ids": document_ids,
        "messages": history,
        "plan": planned["plan"],
        "intent": planned["intent"],
        "retrieval_mode": planned["retrieval_mode"],
        "retrieved": [],
        "hits": [],
        "tool_results": [],
        "graph_context": {"nodes": [], "links": []},
        "graph_payload": None,
        "quality_ok": True,
        "quality_reason": "",
        "backtrack_count": 0,
        "backtrack_target": "",
        "answer": "",
        "error": None,
    }


def heuristic_plan(query: str) -> dict[str, str]:
    q = (query or "").lower()
    skill_kw = (
        "search the web",
        "web search",
        "search online",
        "google",
        "browse",
        "list files",
        "list directory",
        "read file",
        "open file",
        "download",
        "tavily",
        "http://",
        "https://",
        "look up online",
        "current news",
        "latest news",
        "weather",
    )
    relation_kw = (
        "related to",
        "connection between",
        "connected to",
        "how are",
        "how is",
        "multi hop",
        "multi-hop",
        "multihop",
        "path from",
        "path between",
        "linked to",
        "relationship",
    )
    entity_kw = ("who is", "who was", "what is", "what are", "where is", "entity", "person named")
    memory_kw = ("document", "knowledge", "according to", "in the graph", "our notes", "chunk")

    wants_skill = any(k in q for k in skill_kw)
    if wants_skill and any(k in q for k in memory_kw + relation_kw + entity_kw):
        intent = "hybrid"
    elif wants_skill:
        intent = "skill"
    else:
        intent = "memory"

    if any(k in q for k in relation_kw):
        mode = "multihop"
    elif any(k in q for k in entity_kw):
        mode = "entity"
    elif "quote" in q or "passage" in q or "chunk" in q:
        mode = "chunk"
    else:
        mode = "hybrid"

    plan = (
        f"1. Classify intent as {intent}. "
        f"2. If memory is needed, retrieve with mode={mode}. "
        "3. If tools are needed, run the MCP ReAct subgraph. "
        "4. Quality-gate results (one backtrack max). "
        "5. Generate the answer."
    )
    return {"plan": plan, "intent": intent, "retrieval_mode": mode}


def _merge_llm_plan(base: dict[str, str], parsed: dict[str, Any]) -> dict[str, str]:
    intent = str(parsed.get("intent") or base["intent"]).strip().lower()
    if intent not in {"memory", "skill", "hybrid"}:
        intent = base["intent"]
    mode = str(parsed.get("retrieval_mode") or base["retrieval_mode"]).strip().lower()
    mode = {"multi_hop": "multihop", "multi-hop": "multihop"}.get(mode, mode)
    if mode not in {"chunk", "entity", "hybrid", "multihop"}:
        mode = base["retrieval_mode"]
    plan = str(parsed.get("plan") or base["plan"]).strip() or base["plan"]
    return {"plan": plan, "intent": intent, "retrieval_mode": mode}


def empty_exc(exc: Exception) -> str:
    return str(exc)