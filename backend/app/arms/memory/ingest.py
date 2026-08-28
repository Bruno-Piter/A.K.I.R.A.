"""Markdown ingest pipeline: chunk, embed, extract, MERGE into Neo4j."""

from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path
from typing import Any

from app.arms.memory import embeddings as embeddings_mod
from app.arms.memory import extract as extract_mod
from app.arms.memory.chunking import split_text
from app.arms.memory.graph_db import (
    delete_chunks_for_document,
    get_driver,
    merge_chunks_batch,
    merge_contains_entity,
    merge_document,
    merge_entity,
    merge_related_to,
)
from app.arms.memory.schema import ensure_schema

_HASHTAG = re.compile(r"(?:^|\s)#([A-Za-z][A-Za-z0-9_-]*)")
_NON_SLUG = re.compile(r"[^a-z0-9]+")


def ingest_markdown(
    path: str | Path,
    document_id: str | None = None,
    *,
    filename: str | None = None,
    extract: bool = True,
    embed: bool = True,
) -> dict[str, Any]:
    """Read a UTF-8 markdown file and upsert it into the memory graph.

    Idempotent on ``document_id``: existing chunks for that document are
    replaced. Returns document_id, chunk_count, entity_count.
    """
    md_path = Path(path)
    text = md_path.read_text(encoding="utf-8")
    filename = filename or md_path.name
    if not document_id:
        document_id = _slug(md_path.stem) or str(uuid.uuid4())

    driver = get_driver()
    ensure_schema(driver)

    checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
    hashtags = _HASHTAG.findall(text)
    merge_document(
        document_id,
        filename=filename,
        status="ingesting",
        checksum=checksum,
        source=str(md_path),
        hashtags=hashtags,
    )

    try:
        chunks = split_text(text)
        embeddings: list[list[float] | None]
        if embed and chunks:
            embeddings = embeddings_mod.embed_texts(chunks)  # type: ignore[assignment]
        else:
            embeddings = [None] * len(chunks)

        delete_chunks_for_document(document_id)
        rows = []
        chunk_ids: list[str] = []
        for index, chunk_text in enumerate(chunks):
            chunk_id = f"{document_id}::chunk::{index}"
            chunk_ids.append(chunk_id)
            vector = embeddings[index] if index < len(embeddings) else None
            rows.append(
                {
                    "id": chunk_id,
                    "document_id": document_id,
                    "index": index,
                    "text": chunk_text,
                    "embedding": vector,
                }
            )
        merge_chunks_batch(rows)

        entities_by_id: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []
        mentions: list[tuple[str, str]] = []  # (chunk_id, entity_id)

        if extract:
            doc_graph = extract_mod.extract_graph(text)
            _absorb_graph(doc_graph, entities_by_id, relations)

            for chunk_id, chunk_text in zip(chunk_ids, chunks):
                graph = extract_mod.extract_graph(chunk_text)
                new_ids = _absorb_graph(graph, entities_by_id, relations)
                for eid in new_ids:
                    mentions.append((chunk_id, eid))

            # Name-based linking so CONTAINS_ENTITY is robust even when the
            # document-level extract produced extra entities.
            for eid, ent in entities_by_id.items():
                name = str(ent.get("name") or "")
                if not name:
                    continue
                needle = name.lower()
                compact = needle.replace(".", "")
                for chunk_id, chunk_text in zip(chunk_ids, chunks):
                    hay = chunk_text.lower()
                    if needle in hay or compact in hay.replace(".", ""):
                        mentions.append((chunk_id, eid))

        # Persist entities (with embeddings) then relationships.
        if entities_by_id:
            ordered = list(entities_by_id.values())
            entity_vectors: list[list[float] | None]
            if embed:
                sources = [
                    f"{item['name']}. {item.get('description') or ''}".strip()
                    for item in ordered
                ]
                entity_vectors = embeddings_mod.embed_texts(sources)  # type: ignore[assignment]
            else:
                entity_vectors = [None] * len(ordered)
            for item, vector in zip(ordered, entity_vectors):
                merge_entity(
                    item["id"],
                    name=item["name"],
                    type=item["type"],
                    description=item.get("description") or "",
                    embedding=vector,
                )

        seen_mentions: set[tuple[str, str]] = set()
        for chunk_id, entity_id in mentions:
            key = (chunk_id, entity_id)
            if key in seen_mentions:
                continue
            seen_mentions.add(key)
            merge_contains_entity(chunk_id, entity_id)

        seen_rels: set[tuple[str, str, str]] = set()
        for rel in relations:
            src_id = _resolve_entity_id(rel.get("source"), entities_by_id)
            tgt_id = _resolve_entity_id(rel.get("target"), entities_by_id)
            if not src_id or not tgt_id or src_id == tgt_id:
                continue
            rel_type = str(rel.get("type") or "RELATED_TO")
            key = (src_id, tgt_id, rel_type)
            if key in seen_rels:
                continue
            seen_rels.add(key)
            try:
                strength = float(rel.get("strength", 1.0))
            except (TypeError, ValueError):
                strength = 1.0
            merge_related_to(src_id, tgt_id, rel_type=rel_type, strength=strength)

        merge_document(
            document_id,
            filename=filename,
            status="ready",
            checksum=checksum,
            source=str(md_path),
            hashtags=hashtags,
        )
    except Exception:
        merge_document(
            document_id,
            filename=filename,
            status="error",
            checksum=checksum,
            source=str(md_path),
            hashtags=hashtags,
        )
        raise

    return {
        "document_id": document_id,
        "chunk_count": len(chunks),
        "entity_count": len(entities_by_id),
    }


def _absorb_graph(
    graph: dict[str, Any] | None,
    entities_by_id: dict[str, dict[str, Any]],
    relations: list[dict[str, Any]],
) -> list[str]:
    if not graph:
        return []
    new_ids: list[str] = []
    for raw in graph.get("entities") or []:
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        etype = str(raw.get("type") or "Concept").strip() or "Concept"
        eid = stable_entity_id(etype, name)
        if eid not in entities_by_id:
            entities_by_id[eid] = {
                "id": eid,
                "name": name,
                "type": etype,
                "description": str(raw.get("description") or ""),
            }
        new_ids.append(eid)
    for raw in graph.get("relations") or []:
        relations.append(dict(raw))
    return new_ids


def _resolve_entity_id(
    ref: Any,
    entities_by_id: dict[str, dict[str, Any]],
) -> str | None:
    if ref is None:
        return None
    text = str(ref).strip()
    if not text:
        return None
    if text in entities_by_id:
        return text
    lowered = text.lower()
    for eid, ent in entities_by_id.items():
        if str(ent.get("name") or "").lower() == lowered:
            return eid
        if stable_entity_id(str(ent.get("type") or "Concept"), text) == eid:
            return eid
    return None


def stable_entity_id(entity_type: str, name: str) -> str:
    return f"{_slug(entity_type)}::{_slug(name)}"


def _slug(value: str) -> str:
    text = _NON_SLUG.sub("-", (value or "").lower()).strip("-")
    return text
