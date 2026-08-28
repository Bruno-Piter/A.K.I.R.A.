"""Smoke tests: app import, routes, compiled graphs. No live Neo4j required."""

from __future__ import annotations

from pathlib import Path


def test_routes_exist() -> None:
    from app.main import app

    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/health" in paths
    assert "/api/chat/stream" in paths
    assert "/api/documents" in paths
    assert "/api/graph/neighborhood" in paths


def test_compile_graphs() -> None:
    from app.arms.routines.ingest_graph import compile_ingest_graph
    from app.arms.routines.query_graph import compile_query_graph

    query = compile_query_graph()
    ingest = compile_ingest_graph()
    assert query is not None
    assert ingest is not None


def test_hooks_graph_runtime_free() -> None:
    text = Path(__file__).resolve().parents[2] / "app" / "arms" / "routines" / "hooks.py"
    source = text.read_text(encoding="utf-8")
    assert "langgraph" not in source.lower()
    from app.arms.routines.hooks import enqueue_ingest

    assert callable(enqueue_ingest)
