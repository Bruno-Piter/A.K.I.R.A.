"""Neo4j schema: uniqueness constraints, native vector indexes, full-text."""

from __future__ import annotations

import time
from neo4j import Driver


def ensure_schema(driver: Driver) -> None:
    """Create constraints and indexes if they do not already exist.

    Existing indexes with a different configuration are left untouched
    (IF NOT EXISTS). After creation, wait until indexes are online.
    """
    from app.arms.memory.embeddings import embedding_dimensions

    dims = int(embedding_dimensions())
    statements = [
        "CREATE CONSTRAINT document_id IF NOT EXISTS "
        "FOR (n:Document) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS "
        "FOR (n:Chunk) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT entity_id IF NOT EXISTS "
        "FOR (n:Entity) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT conversation_session_id IF NOT EXISTS "
        "FOR (n:ConversationSession) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT message_id IF NOT EXISTS "
        "FOR (n:Message) REQUIRE n.id IS UNIQUE",
        (
            "CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS "
            "FOR (c:Chunk) ON (c.embedding) "
            "OPTIONS {indexConfig: {"
            f"`vector.dimensions`: {dims}, "
            "`vector.similarity_function`: 'cosine'"
            "}}"
        ),
        (
            "CREATE VECTOR INDEX entity_embedding IF NOT EXISTS "
            "FOR (e:Entity) ON (e.embedding) "
            "OPTIONS {indexConfig: {"
            f"`vector.dimensions`: {dims}, "
            "`vector.similarity_function`: 'cosine'"
            "}}"
        ),
        (
            "CREATE FULLTEXT INDEX entity_name_description IF NOT EXISTS "
            "FOR (e:Entity) ON EACH [e.name, e.description]"
        ),
    ]
    with driver.session() as session:
        for cypher in statements:
            session.run(cypher)
    _await_indexes_online(driver)


def _await_indexes_online(driver: Driver, timeout_s: float = 45.0) -> None:
    """Block until Neo4j reports indexes ONLINE (best-effort)."""
    deadline = time.time() + timeout_s
    with driver.session() as session:
        try:
            session.run("CALL db.awaitIndexes()")
            return
        except Exception:
            pass
    watched = {"chunk_embedding", "entity_embedding", "entity_name_description"}
    while time.time() < deadline:
        states: dict[str, str] = {}
        try:
            with driver.session() as session:
                for rec in session.run("SHOW INDEXES YIELD name, state"):
                    states[str(rec["name"])] = str(rec["state"])
        except Exception:
            time.sleep(0.5)
            continue
        pending = [
            name
            for name in watched
            if name in states and states[name].upper() not in {"ONLINE", "READY"}
        ]
        missing = [name for name in watched if name not in states]
        if not pending and not missing:
            return
        # Names may differ slightly; if everything present is ONLINE, stop.
        if not pending and states:
            known = [states[n] for n in watched if n in states]
            if known and all(s.upper() in {"ONLINE", "READY"} for s in known):
                return
        time.sleep(0.4)
