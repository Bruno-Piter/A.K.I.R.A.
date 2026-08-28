"""Frozen HTTP contracts for A.K.I.R.A. Routers must not invent fields or routes."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"
    version: str
    llm_provider: str
    embeddings_provider: str
    neo4j_uri: str


class SseEventType(str, Enum):
    stage = "stage"
    token = "token"
    sources = "sources"
    graph_context = "graph_context"
    done = "done"


class ChatStreamRequest(BaseModel):
    message: str
    thread_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)


class ChatSource(BaseModel):
    chunk_id: str
    document_id: str
    title: str = ""
    excerpt: str = ""
    score: float | None = None


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    val: float = 1.0
    color: str | None = None


class GraphLink(BaseModel):
    source: str
    target: str
    type: str = "RELATED_TO"
    strength: float = 1.0


class GraphPayload(BaseModel):
    """Payload for react-force-graph-2d (`nodes` + `links`)."""

    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphLink] = Field(default_factory=list)


class SseEvent(BaseModel):
    type: SseEventType
    content: Any = None


class DocumentSummary(BaseModel):
    id: str
    filename: str
    status: str
    created_at: str | None = None
    hashtags: list[str] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary] = Field(default_factory=list)


class DocumentUploadResponse(BaseModel):
    job_id: str
    document_id: str
    filename: str
    status: str = "queued"


class GraphNeighborhoodQuery(BaseModel):
    id: str
    hops: int = Field(default=2, ge=1, le=6)


class GraphOverviewResponse(GraphPayload):
    document_count: int = 0
    entity_count: int = 0
    chunk_count: int = 0
