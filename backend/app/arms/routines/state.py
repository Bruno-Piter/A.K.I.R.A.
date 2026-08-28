"""TypedDict state for query and ingest graphs."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

Intent = Literal["memory", "skill", "hybrid"]
RetrievalMode = Literal["chunk", "entity", "hybrid", "multihop", "multi_hop"]


class QueryState(TypedDict, total=False):
    query: str
    session_id: str
    thread_id: str
    document_ids: list[str]
    messages: list[dict[str, str]]
    plan: str
    intent: Intent
    retrieval_mode: RetrievalMode
    retrieved: list[dict[str, Any]]
    hits: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    graph_context: dict[str, Any]
    graph_payload: dict[str, Any] | None
    sources: list[dict[str, Any]]
    quality_ok: bool
    quality_reason: str
    backtrack_count: int
    backtrack_target: str
    answer: str
    error: str | None
    events: list[dict[str, Any]]


class IngestState(TypedDict, total=False):
    filename: str
    content_type: str
    file_bytes: bytes
    path: str
    text: str
    document_id: str
    extracted_text_path: str | None
    chunks: list[str]
    embeddings: list[Any]
    entities: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    chunk_count: int
    entity_count: int
    status: str
    error: str | None
    job_id: str
    ok: bool