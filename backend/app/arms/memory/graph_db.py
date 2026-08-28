"""Synchronous Neo4j driver singleton and idempotent MERGE helpers."""

from __future__ import annotations

from typing import Any, Iterable

from neo4j import Driver, GraphDatabase

_driver: Driver | None = None


def get_driver() -> Driver:
    """Return a process-wide Bolt driver created from settings."""
    global _driver
    if _driver is None:
        from app.core.settings import settings

        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
    return _driver


def close_driver() -> None:
    """Close and drop the singleton driver."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def _session_run(cypher: str, **params: Any) -> list[Any]:
    driver = get_driver()
    with driver.session() as session:
        return list(session.run(cypher, **params))


def merge_document(
    document_id: str,
    *,
    filename: str,
    status: str,
    checksum: str | None = None,
    source: str | None = None,
    hashtags: list[str] | None = None,
) -> None:
    _session_run(
        """
        MERGE (d:Document {id: $id})
        ON CREATE SET
            d.filename = $filename,
            d.status = $status,
            d.checksum = $checksum,
            d.source = $source,
            d.hashtags = $hashtags,
            d.created_at = datetime(),
            d.updated_at = datetime()
        ON MATCH SET
            d.filename = $filename,
            d.status = $status,
            d.checksum = $checksum,
            d.source = $source,
            d.hashtags = $hashtags,
            d.updated_at = datetime()
        """,
        id=document_id,
        filename=filename,
        status=status,
        checksum=checksum,
        source=source,
        hashtags=list(hashtags or []),
    )


def merge_chunk(
    chunk_id: str,
    *,
    document_id: str,
    index: int,
    text: str,
    embedding: list[float] | None = None,
) -> None:
    _session_run(
        """
        MERGE (c:Chunk {id: $id})
        ON CREATE SET
            c.document_id = $document_id,
            c.index = $index,
            c.text = $text,
            c.created_at = datetime(),
            c.updated_at = datetime()
        ON MATCH SET
            c.document_id = $document_id,
            c.index = $index,
            c.text = $text,
            c.updated_at = datetime()
        WITH c
        MATCH (d:Document {id: $document_id})
        MERGE (d)-[:HAS_CHUNK {index: $index}]->(c)
        """,
        id=chunk_id,
        document_id=document_id,
        index=int(index),
        text=text,
    )
    if embedding is not None:
        _session_run(
            """
            MATCH (c:Chunk {id: $id})
            SET c.embedding = $embedding, c.updated_at = datetime()
            """,
            id=chunk_id,
            embedding=[float(x) for x in embedding],
        )


def merge_entity(
    entity_id: str,
    *,
    name: str,
    type: str,
    description: str = "",
    embedding: list[float] | None = None,
) -> None:
    _session_run(
        """
        MERGE (e:Entity {id: $id})
        ON CREATE SET
            e.name = $name,
            e.type = $type,
            e.description = $description,
            e.created_at = datetime(),
            e.updated_at = datetime()
        ON MATCH SET
            e.name = $name,
            e.type = $type,
            e.description = CASE
                WHEN $description <> '' THEN $description
                ELSE e.description
            END,
            e.updated_at = datetime()
        """,
        id=entity_id,
        name=name,
        type=type,
        description=description or "",
    )
    if embedding is not None:
        _session_run(
            """
            MATCH (e:Entity {id: $id})
            SET e.embedding = $embedding, e.updated_at = datetime()
            """,
            id=entity_id,
            embedding=[float(x) for x in embedding],
        )


def merge_contains_entity(chunk_id: str, entity_id: str) -> None:
    _session_run(
        """
        MATCH (c:Chunk {id: $chunk_id})
        MATCH (e:Entity {id: $entity_id})
        MERGE (c)-[:CONTAINS_ENTITY]->(e)
        """,
        chunk_id=chunk_id,
        entity_id=entity_id,
    )


def merge_related_to(
    source_id: str,
    target_id: str,
    *,
    rel_type: str = "RELATED_TO",
    strength: float = 1.0,
) -> None:
    _session_run(
        """
        MATCH (a:Entity {id: $src})
        MATCH (b:Entity {id: $tgt})
        MERGE (a)-[r:RELATED_TO]->(b)
        ON CREATE SET
            r.rel_type = $rel_type,
            r.type = $rel_type,
            r.strength = $strength
        ON MATCH SET
            r.rel_type = $rel_type,
            r.type = $rel_type,
            r.strength = $strength
        """,
        src=source_id,
        tgt=target_id,
        rel_type=rel_type or "RELATED_TO",
        strength=float(strength),
    )


def merge_conversation_session(
    session_id: str,
    *,
    title: str | None = None,
) -> None:
    _session_run(
        """
        MERGE (s:ConversationSession {id: $id})
        ON CREATE SET
            s.title = $title,
            s.created_at = datetime(),
            s.updated_at = datetime()
        ON MATCH SET
            s.title = CASE WHEN $title IS NULL THEN s.title ELSE $title END,
            s.updated_at = datetime()
        """,
        id=session_id,
        title=title,
    )


def merge_message(
    message_id: str,
    *,
    session_id: str,
    role: str,
    content: str,
    index: int = 0,
) -> None:
    _session_run(
        """
        MERGE (m:Message {id: $id})
        ON CREATE SET
            m.session_id = $session_id,
            m.role = $role,
            m.content = $content,
            m.created_at = datetime(),
            m.updated_at = datetime()
        ON MATCH SET
            m.session_id = $session_id,
            m.role = $role,
            m.content = $content,
            m.updated_at = datetime()
        WITH m
        MERGE (s:ConversationSession {id: $session_id})
        ON CREATE SET s.created_at = datetime(), s.updated_at = datetime()
        MERGE (s)-[:HAS_MESSAGE {index: $index}]->(m)
        """,
        id=message_id,
        session_id=session_id,
        role=role,
        content=content,
        index=int(index),
    )


def delete_chunks_for_document(document_id: str) -> None:
    """Detach-delete every Chunk belonging to a document (keep the Document)."""
    _session_run(
        """
        MATCH (d:Document {id: $id})-[:HAS_CHUNK]->(c:Chunk)
        DETACH DELETE c
        """,
        id=document_id,
    )


def delete_document_cascade(document_id: str) -> None:
    """Delete a document, its chunks, and entities that become orphaned."""
    _session_run(
        """
        MATCH (d:Document {id: $id})
        OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
        OPTIONAL MATCH (c)-[:CONTAINS_ENTITY]->(e:Entity)
        WITH d, collect(DISTINCT c) AS chunks, collect(DISTINCT e) AS ents
        FOREACH (c IN chunks | DETACH DELETE c)
        DETACH DELETE d
        WITH ents
        UNWIND ents AS e
        WITH e
        WHERE e IS NOT NULL AND NOT (e)<-[:CONTAINS_ENTITY]-()
        DETACH DELETE e
        """,
        id=document_id,
    )


def merge_chunks_batch(
    rows: Iterable[dict[str, Any]],
) -> None:
    """MERGE many chunks + HAS_CHUNK in one round-trip."""
    payload = list(rows)
    if not payload:
        return
    _session_run(
        """
        UNWIND $rows AS row
        MERGE (c:Chunk {id: row.id})
        ON CREATE SET
            c.document_id = row.document_id,
            c.index = row.index,
            c.text = row.text,
            c.created_at = datetime(),
            c.updated_at = datetime()
        ON MATCH SET
            c.document_id = row.document_id,
            c.index = row.index,
            c.text = row.text,
            c.updated_at = datetime()
        WITH c, row
        MATCH (d:Document {id: row.document_id})
        MERGE (d)-[:HAS_CHUNK {index: row.index}]->(c)
        WITH c, row
        FOREACH (_ IN CASE WHEN row.embedding IS NULL THEN [] ELSE [1] END |
            SET c.embedding = row.embedding
        )
        """,
        rows=payload,
    )
