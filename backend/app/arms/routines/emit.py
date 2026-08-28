"""Best-effort custom stream events for SSE (ignored if no stream writer)."""

from __future__ import annotations

from typing import Any


def emit(payload: dict[str, Any]) -> None:
    try:
        from langgraph.config import get_stream_writer

        writer = get_stream_writer()
        writer(payload)
    except Exception:
        return