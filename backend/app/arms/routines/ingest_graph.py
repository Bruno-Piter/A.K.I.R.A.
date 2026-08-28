"""Linear ingest StateGraph: prepare -> chunk -> embed -> extract -> write_graph."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.arms.routines.nodes.ingest import chunk, embed, extract, prepare, write_graph
from app.arms.routines.state import IngestState

logger = logging.getLogger(__name__)

_compiled: Any = None


def build_ingest_graph() -> StateGraph:
    graph = StateGraph(IngestState)
    graph.add_node("prepare", prepare)
    graph.add_node("chunk", chunk)
    graph.add_node("embed", embed)
    graph.add_node("extract", extract)
    graph.add_node("write_graph", write_graph)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "chunk")
    graph.add_edge("chunk", "embed")
    graph.add_edge("embed", "extract")
    graph.add_edge("extract", "write_graph")
    graph.add_edge("write_graph", END)
    return graph


def compile_ingest_graph(*, checkpointer: Any | None = None) -> Any:
    builder = build_ingest_graph()
    saver = checkpointer
    if saver is None:
        try:
            from app.arms.routines.checkpoint import get_checkpointer

            saver = get_checkpointer()
        except Exception as exc:
            logger.warning("ingest_graph compiling without sqlite checkpointer: %s", exc)
            saver = None
    return builder.compile(checkpointer=saver, name="ingest_graph")


def get_ingest_graph() -> Any:
    global _compiled
    if _compiled is None:
        _compiled = compile_ingest_graph()
    return _compiled


def reset_ingest_graph() -> None:
    global _compiled
    _compiled = None