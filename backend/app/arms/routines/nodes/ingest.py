"""Thin ingest graph node wrappers around the LangGraph-free pipeline."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from app.arms.routines import pipeline

_UPLOAD_DIR = Path(__file__).resolve().parents[4] / "data" / "uploads"


def _ensure_path(state: dict[str, Any]) -> dict[str, Any]:
    path = state.get("path")
    if path:
        return dict(state)
    raw = state.get("file_bytes") or b""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    filename = str(state.get("filename") or "upload.md")
    document_id = str(state.get("document_id") or uuid.uuid4())
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix or ".md"
    dest = _UPLOAD_DIR / f"{document_id}{suffix}"
    dest.write_bytes(bytes(raw))
    out = dict(state)
    out["path"] = str(dest)
    out["document_id"] = document_id
    out["filename"] = filename
    return out


def prepare(state: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if isinstance(state, dict):
        merged.update(state)
    merged.update(kwargs)
    content_type = merged.get("content_type")
    if merged.get("path") and not merged.get("file_bytes"):
        return pipeline.prepare(
            merged.get("path") or "",
            document_id=merged.get("document_id"),
            filename=merged.get("filename"),
            content_type=content_type,
        )
    ready = _ensure_path(merged)
    return pipeline.prepare(
        ready.get("path") or "",
        document_id=ready.get("document_id"),
        filename=ready.get("filename"),
        content_type=ready.get("content_type") or content_type,
    )


def chunk(state: dict[str, Any]) -> dict[str, Any]:
    return pipeline.chunk(state)


def embed(state: dict[str, Any]) -> dict[str, Any]:
    return pipeline.embed(state)


def extract(state: dict[str, Any]) -> dict[str, Any]:
    return pipeline.extract(state)


def write_graph(state: dict[str, Any]) -> dict[str, Any]:
    try:
        return pipeline.write_graph(state)
    except Exception as exc:
        return {
            "ok": False,
            "status": "error",
            "error": str(exc),
            "chunk_count": int(state.get("chunk_count") or 0),
            "entity_count": int(state.get("entity_count") or 0),
        }


prepare_node = prepare
chunk_node = chunk
embed_node = embed
extract_node = extract
write_graph_node = write_graph