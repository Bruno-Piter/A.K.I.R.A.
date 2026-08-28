"""Ingest MCP server. Dispatches document ingest; never imports LangGraph."""

from __future__ import annotations

import _bootstrap  # noqa: F401

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ingest", log_level="ERROR")

_TODO = (
    "Wire ingest_graph when Agent 4 publishes a LangGraph-free enqueue hook. "
    "Skills must not import LangGraph."
)


@mcp.tool()
def ingest_document(
    path: str,
    document_id: str | None = None,
    filename: str | None = None,
) -> dict:
    """Dispatch an ingest routine for a document path. Does not import LangGraph."""
    try:
        from app.arms.routines.hooks import enqueue_ingest
    except ImportError:
        enqueue_ingest = None

    if not callable(enqueue_ingest):
        return {
            "ok": True,
            "status": "hook_pending",
            "todo": _TODO,
            "path": path,
            "document_id": document_id,
            "filename": filename,
        }
    return enqueue_ingest(path=path, document_id=document_id, filename=filename)


if __name__ == "__main__":
    mcp.run(transport="stdio")
