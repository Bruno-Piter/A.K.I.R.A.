"""Branching query StateGraph (planner -> intent router -> memory/skill/hybrid)."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.arms.routines.nodes.generate import generate
from app.arms.routines.nodes.intent_router import intent_router, route_after_intent
from app.arms.routines.nodes.planner import planner
from app.arms.routines.nodes.quality_gate import quality_gate, route_after_quality
from app.arms.routines.nodes.react_tools import react_tools
from app.arms.routines.nodes.retrieval_router import retrieval_router, route_after_retrieval
from app.arms.routines.state import QueryState

logger = logging.getLogger(__name__)

_compiled: Any = None


def build_query_graph() -> StateGraph:
    graph = StateGraph(QueryState)
    graph.add_node("planner", planner)
    graph.add_node("intent_router", intent_router)
    graph.add_node("retrieval_router", retrieval_router)
    graph.add_node("react_tools", react_tools)
    graph.add_node("quality_gate", quality_gate)
    graph.add_node("generate", generate)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "intent_router")
    graph.add_conditional_edges(
        "intent_router",
        route_after_intent,
        {
            "retrieval_router": "retrieval_router",
            "react_tools": "react_tools",
        },
    )
    graph.add_conditional_edges(
        "retrieval_router",
        route_after_retrieval,
        {
            "react_tools": "react_tools",
            "quality_gate": "quality_gate",
        },
    )
    graph.add_edge("react_tools", "quality_gate")
    graph.add_conditional_edges(
        "quality_gate",
        route_after_quality,
        {
            "retrieval_router": "retrieval_router",
            "react_tools": "react_tools",
            "generate": "generate",
        },
    )
    graph.add_edge("generate", END)
    return graph


def compile_query_graph(*, checkpointer: Any | None = None) -> Any:
    builder = build_query_graph()
    saver = checkpointer
    if saver is None:
        try:
            from app.arms.routines.checkpoint import get_checkpointer

            saver = get_checkpointer()
        except Exception as exc:
            logger.warning("query_graph compiling without sqlite checkpointer: %s", exc)
            saver = None
    return builder.compile(checkpointer=saver, name="query_graph")


def get_query_graph() -> Any:
    """Lazily compile (and cache) the query graph with the sqlite checkpointer."""
    global _compiled
    if _compiled is None:
        _compiled = compile_query_graph()
    return _compiled


def reset_query_graph() -> None:
    global _compiled
    _compiled = None