"""POST /api/documents -- multipart ingest through the ingest StateGraph."""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.schemas import DocumentListResponse, DocumentSummary, DocumentUploadResponse
from app.arms.routines.extract_text import allowed_content_type, allowed_filename

logger = logging.getLogger(__name__)

router = APIRouter()

_ACCEPTED_TYPES = "pdf, txt, md, docx"


@router.get("/documents", response_model=DocumentListResponse)
async def list_uploaded_documents() -> DocumentListResponse:
    try:
        from app.arms.memory import list_documents

        rows = list_documents()
    except Exception:
        logger.exception("list_documents unavailable")
        return DocumentListResponse(documents=[])
    documents = []
    for row in rows:
        try:
            documents.append(DocumentSummary.model_validate(row))
        except Exception:
            continue
    return DocumentListResponse(documents=documents)


@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    filename = file.filename or "upload.txt"
    content_type = file.content_type or ""
    if not allowed_filename(filename) and not allowed_content_type(content_type):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type. Accepted: {_ACCEPTED_TYPES}",
        )
    data = await file.read()
    job_id = uuid.uuid4().hex

    try:
        from app.arms.routines.ingest_graph import get_ingest_graph

        graph = get_ingest_graph()
        thread_id = f"ingest-{job_id}"
        result = await asyncio.to_thread(
            graph.invoke,
            {
                "filename": filename,
                "content_type": content_type,
                "file_bytes": data,
                "job_id": job_id,
            },
            {"configurable": {"thread_id": thread_id}, "recursion_limit": 16},
        )
    except Exception as exc:
        logger.exception("ingest_graph failed, falling back to enqueue_ingest")
        try:
            result = _fallback_enqueue(filename, data, job_id)
        except Exception as inner:
            raise HTTPException(
                status_code=503,
                detail=f"document ingest unavailable: {exc}; fallback: {inner}",
            ) from inner

    result = result or {}
    document_id = str(result.get("document_id") or job_id)
    status = str(result.get("status") or "queued")
    return DocumentUploadResponse(
        job_id=job_id,
        document_id=document_id,
        filename=filename,
        status=status,
    )


def _fallback_enqueue(filename: str, data: bytes, job_id: str) -> dict:
    from pathlib import Path

    from app.arms.routines.hooks import enqueue_ingest

    upload_dir = Path(__file__).resolve().parents[3] / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix or ".md"
    dest = upload_dir / f"{job_id}{suffix}"
    dest.write_bytes(data)
    result = enqueue_ingest(str(dest), document_id=job_id, filename=filename)
    status = "ready" if result.get("ok") else "error"
    return {
        "document_id": result.get("document_id") or job_id,
        "status": status,
        "error": result.get("error"),
    }