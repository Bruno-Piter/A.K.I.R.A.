"""Ingest fixture markdown, hybrid-search it, then expand a neighborhood."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from app.arms.memory.graph_db import delete_document_cascade

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "akira_overview.md"

VOCAB = [
    "akira",
    "neo4j",
    "memory",
    "kernel",
    "chunk",
    "entity",
    "related",
    "hybrid",
    "search",
    "neighborhood",
    "fastapi",
    "langgraph",
    "vector",
    "index",
    "document",
    "embedding",
    "graph",
    "cosine",
    "session",
    "message",
    "retriev",
    "markdown",
]
DIM = 1536

JUNK_LABELS = {
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "for",
    "and",
    "or",
    "o",
    "os",
    "as",
    "de",
    "da",
    "do",
}

CANONICAL_ENTITIES = [
    {
        "name": "A.K.I.R.A.",
        "type": "Technology",
        "description": "Agentic Knowledge Integration and Retrieval Architecture",
    },
    {
        "name": "Neo4j",
        "type": "Technology",
        "description": "Graph database with native vector indexes",
    },
    {
        "name": "FastAPI",
        "type": "Technology",
        "description": "Python web framework serving A.K.I.R.A. HTTP contracts",
    },
    {
        "name": "LangGraph",
        "type": "Technology",
        "description": "Agent orchestration framework used by A.K.I.R.A.",
    },
    {
        "name": "Memory Kernel",
        "type": "Concept",
        "description": "Graph-based memory subsystem over Chunk and Entity nodes",
    },
]

NOISE_ENTITIES = [
    {"name": "the", "type": "Concept", "description": "english article"},
    {"name": "a", "type": "Concept", "description": "english article"},
    {"name": "of", "type": "Concept", "description": "preposition"},
    {"name": "to", "type": "Concept", "description": "preposition"},
    {"name": "x", "type": "Concept", "description": "tiny"},
    {"name": "  ", "type": "Concept", "description": "empty"},
    {"name": '"the"', "type": "Concept", "description": "quoted article"},
]

CANONICAL_RELATIONS = [
    {
        "source": "A.K.I.R.A.",
        "target": "Memory Kernel",
        "type": "HAS_COMPONENT",
        "strength": 1.0,
    },
    {
        "source": "Memory Kernel",
        "target": "Neo4j",
        "type": "USES",
        "strength": 0.95,
    },
    {
        "source": "A.K.I.R.A.",
        "target": "FastAPI",
        "type": "USES",
        "strength": 0.85,
    },
    {
        "source": "A.K.I.R.A.",
        "target": "LangGraph",
        "type": "USES",
        "strength": 0.85,
    },
    {
        "source": "the",
        "target": "Neo4j",
        "type": "MENTIONS",
        "strength": 1.0,
    },
]


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def fake_embed_texts(texts: list[str]) -> list[list[float]]:
    """Deterministic bag-of-words embedder in the first N dims of a 1536-vector."""
    out: list[list[float]] = []
    for text in texts:
        vec = [0.0] * DIM
        compact = (text or "").lower().replace(".", "")
        tokens = _normalize(text).split()
        for i, word in enumerate(VOCAB):
            count = compact.count(word)
            count += sum(1 for tok in tokens if word in tok or tok in word)
            vec[i] = float(count)
        norm = math.sqrt(sum(x * x for x in vec))
        if norm <= 0.0:
            vec[0] = 1.0
            norm = 1.0
        out.append([x / norm for x in vec])
    return out


def fake_embed_query(text: str) -> list[float]:
    return fake_embed_texts([text])[0]


def _noisy_llm_json(_prompt: str, _settings: object) -> str:
    """Simulates a small local LLM that also emits stopword entities."""
    return json.dumps(
        {
            "entities": CANONICAL_ENTITIES + NOISE_ENTITIES,
            "relations": CANONICAL_RELATIONS,
        }
    )


def _entity_label_is_junk(label: str) -> bool:
    compact = re.sub(r"[^a-z0-9]+", "", (label or "").lower())
    if not compact or len(compact) <= 2:
        return True
    return (label or "").strip().lower() in JUNK_LABELS


@pytest.fixture
def patched_llm(monkeypatch):
    monkeypatch.setattr("app.arms.memory.embeddings.embed_texts", fake_embed_texts)
    monkeypatch.setattr("app.arms.memory.embeddings.embed_query", fake_embed_query)
    # Hit the real extract_graph + post-LLM filter with noisy JSON.
    monkeypatch.setattr("app.arms.memory.extract._call_openai", _noisy_llm_json)
    monkeypatch.setattr("app.arms.memory.extract._call_ollama", _noisy_llm_json)


def test_ingest_hybrid_neighborhood(
    neo4j_driver,
    cleanup_fixture_document,
    patched_llm,
):
    from app.arms.memory import hybrid_search, ingest_markdown, neighborhood

    document_id = cleanup_fixture_document
    delete_document_cascade(document_id)

    result = ingest_markdown(FIXTURE_PATH, document_id=document_id)
    assert result["document_id"] == document_id
    assert result["chunk_count"] >= 1
    assert result["entity_count"] >= 1
    # Noise tokens must not survive the post-LLM filter.
    assert result["entity_count"] <= len(CANONICAL_ENTITIES)

    hits = hybrid_search("Neo4j vector index hybrid search", top_k=8)
    assert hits, "hybrid_search must return at least one hit"
    hit = hits[0]
    assert "score" in hit and hit["score"] is not None
    blob = " ".join(
        str(hit.get(key) or "")
        for key in ("title", "excerpt", "chunk_id", "document_id", "entity_id")
    ).lower()
    fixture_markers = (
        "neo4j",
        "akira",
        "hybrid",
        "vector",
        "memory",
        "chunk",
        "entity",
        "overview",
        document_id.lower(),
    )
    assert any(marker in blob for marker in fixture_markers), (
        "hit title/excerpt should relate to the fixture, got: "
        f"title={hit.get('title')!r} excerpt={hit.get('excerpt')!r}"
    )
    for hit_row in hits:
        for key in ("title", "excerpt"):
            value = str(hit_row.get(key) or "").strip().lower()
            assert value not in JUNK_LABELS, f"hybrid hit {key} is junk: {value!r}"

    origin = document_id
    for candidate in (hit.get("document_id"), hit.get("chunk_id"), hit.get("entity_id")):
        if candidate:
            origin = candidate
            break
    payload = neighborhood(origin, hops=2)
    assert isinstance(payload, dict)
    assert "nodes" in payload and "links" in payload
    nodes = payload["nodes"]
    links = payload["links"]
    assert isinstance(nodes, list) and len(nodes) >= 1
    assert isinstance(links, list)

    for node in nodes:
        assert "id" in node and node["id"]
        assert "label" in node
        assert "type" in node
        assert "val" in node
        if node.get("type") == "Entity":
            assert not _entity_label_is_junk(str(node.get("label") or "")), (
                f"neighborhood returned junk entity {node!r}"
            )
    for link in links:
        assert "source" in link and link["source"]
        assert "target" in link and link["target"]
        assert "type" in link
        assert "strength" in link

    node_ids = {node["id"] for node in nodes}
    assert origin in node_ids, f"origin {origin!r} missing from neighborhood nodes"

    doc_graph = neighborhood(document_id, hops=2)
    doc_ids = {n["id"] for n in doc_graph["nodes"]}
    assert document_id in doc_ids
    assert len(doc_graph["nodes"]) >= 1
    junk_entities = [
        n
        for n in doc_graph["nodes"]
        if n.get("type") == "Entity" and _entity_label_is_junk(str(n.get("label") or ""))
    ]
    assert not junk_entities, f"document neighborhood leaked junk entities: {junk_entities}"

    delete_document_cascade(document_id)
