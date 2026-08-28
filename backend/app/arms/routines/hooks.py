"""Ingest hook used by MCP ingest_server and HTTP documents."""

from __future__ import annotations

from pathlib import Path

from app.arms.routines.pipeline import run_ingest


def enqueue_ingest(
    path: str,
    document_id: str | None = None,
    filename: str | None = None,
) -> dict:
    """Run ingest via the plain pipeline (no graph runtime)."""
    try:
        result = run_ingest(path, document_id=document_id, filename=filename)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    if not result.get("ok"):
        return {"ok": False, "error": result.get("error") or "ingest failed"}

    name = result.get("filename") or filename or Path(path).name
    return {
        "ok": True,
        "document_id": result.get("document_id"),
        "filename": name,
        "status": result.get("status") or "ingested",
        "chunk_count": int(result.get("chunk_count") or 0),
        "entity_count": int(result.get("entity_count") or 0),
    }
