"""LangGraph-free ingest pipeline. MCP/hooks import this module only."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from app.arms.routines.extract_text import extract_text

_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "data" / "uploads"
_TEXT_SIDECARS = {".md", ".txt", ".markdown"}


def prepare(
    path: str | Path,
    document_id: str | None = None,
    filename: str | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    md_path = Path(path)
    if not md_path.is_file():
        raise FileNotFoundError(f"ingest path not found: {md_path}")
    name = filename or md_path.name
    doc_id = document_id or str(uuid.uuid4())
    text = extract_text(path=md_path, filename=name, content_type=content_type)
    if not str(text).strip():
        raise ValueError(f"no extractable text in {name} (scanned PDF needs OCR, which is not supported)")
    return {
        "path": str(md_path.resolve()),
        "document_id": doc_id,
        "filename": name,
        "text": text,
        "status": "prepared",
        "ok": True,
        "extracted_text_path": None,
    }


def chunk(state: dict[str, Any]) -> dict[str, Any]:
    from app.arms.memory.chunking import split_text

    text = state.get("text") or ""
    chunks = split_text(text) if text else []
    return {"chunks": chunks, "chunk_count": len(chunks)}


def embed(state: dict[str, Any]) -> dict[str, Any]:
    from app.arms.memory.embeddings import embed_texts

    chunks = list(state.get("chunks") or [])
    if not chunks:
        return {"embeddings": []}
    try:
        vectors = embed_texts(chunks)
    except Exception:
        vectors = [None] * len(chunks)
    return {"embeddings": vectors}


def extract(state: dict[str, Any]) -> dict[str, Any]:
    text = state.get("text") or ""
    try:
        from app.arms.memory.extract import extract_graph

        graph = extract_graph(text) if text else {"entities": [], "relations": []}
    except Exception:
        graph = {"entities": [], "relations": []}
    entities = list(graph.get("entities") or [])
    relations = list(graph.get("relations") or [])
    return {
        "entities": entities,
        "relations": relations,
        "entity_count": len(entities),
    }


def _text_sidecar_path(document_id: str) -> Path:
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return _UPLOAD_DIR / f"{document_id}.md"


def _is_text_sidecar(path: str | Path | None) -> bool:
    if not path:
        return False
    p = Path(path)
    return p.is_file() and p.suffix.lower() in _TEXT_SIDECARS


def write_graph(state: dict[str, Any]) -> dict[str, Any]:
    """Persist the document. Memory ingest_markdown receives a UTF-8 text sidecar only."""
    from app.arms.memory.ingest import ingest_markdown

    document_id = str(state.get("document_id") or uuid.uuid4())
    original_filename = state.get("filename")
    original_path = state.get("path")
    text = state.get("text") or ""

    sidecar = state.get("extracted_text_path")
    if _is_text_sidecar(sidecar):
        text_md_path = Path(str(sidecar))
    else:
        text_md_path = _text_sidecar_path(document_id)
        text_md_path.write_text(text, encoding="utf-8")

    result = ingest_markdown(
        text_md_path,
        document_id=document_id,
        filename=original_filename or Path(str(original_path or text_md_path)).name,
    )
    return {
        "ok": True,
        "document_id": result.get("document_id") or document_id,
        "filename": original_filename or Path(str(original_path or text_md_path)).name,
        "status": "ready",
        "chunk_count": int(result.get("chunk_count") or 0),
        "entity_count": int(result.get("entity_count") or 0),
        "error": None,
        "extracted_text_path": str(text_md_path),
    }


def run_ingest(
    path: str | Path,
    document_id: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Full ingest used by enqueue_ingest. Calls ingest_markdown on extracted text."""
    prepared = prepare(path, document_id=document_id, filename=filename)
    try:
        written = write_graph(prepared)
        written.setdefault("filename", prepared.get("filename"))
        written.setdefault("document_id", prepared.get("document_id"))
        return written
    except Exception as exc:
        return {
            "ok": False,
            "document_id": prepared.get("document_id"),
            "filename": prepared.get("filename"),
            "status": "error",
            "chunk_count": 0,
            "entity_count": 0,
            "error": str(exc),
        }