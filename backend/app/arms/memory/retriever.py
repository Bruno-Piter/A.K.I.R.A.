"""Hybrid / vector / multi-hop retrieval over the Neo4j memory graph."""

from __future__ import annotations

import math
import re
from typing import Any, Literal

from app.api.schemas import GraphLink, GraphNode, GraphPayload
from app.arms.memory import embeddings as embeddings_mod
from app.arms.memory.graph_db import get_driver

SearchMode = Literal["chunk", "entity", "hybrid", "multi_hop"]

_KNOWN_LABELS = (
    "Document",
    "Chunk",
    "Entity",
    "ConversationSession",
    "Message",
)
_RRF_K = 60
_LUCENE_SPECIAL = re.compile(r'([+\-!(){}\[\]^"~*?:\\/|&])')


def hybrid_search(query: str, top_k: int = 8) -> list[dict[str, Any]]:
    return search(query, mode="hybrid", top_k=top_k)


def search(
    query: str,
    mode: SearchMode = "hybrid",
    top_k: int = 8,
    hops: int = 2,
) -> list[dict[str, Any]]:
    """Retrieve ranked memory hits for ``query``.

    Each hit: {chunk_id?, document_id?, entity_id?, title, excerpt, score, mode}
    """
    top_k = max(int(top_k), 1)
    hops = max(int(hops), 1)
    q = (query or "").strip()
    if not q:
        return []
    query_vec = embeddings_mod.embed_query(q)
    driver = get_driver()
    with driver.session() as session:
        if mode == "chunk":
            hits = _search_chunks(session, query_vec, top_k)
            return [_annotate(h, "chunk") for h in hits[:top_k]]
        if mode == "entity":
            hits = _search_entity_chunks(session, query_vec, q, top_k)
            return [_annotate(h, "entity") for h in hits[:top_k]]
        if mode == "multi_hop":
            hits = _search_multi_hop(session, query_vec, q, top_k, hops)
            return [_annotate(h, "multi_hop") for h in hits[:top_k]]
        # hybrid (default)
        chunk_hits = _search_chunks(session, query_vec, max(top_k, 10))
        entity_hits = _search_entity_chunks(session, query_vec, q, max(top_k, 10))
        merged = _rrf_hits([chunk_hits, entity_hits], top_k)
        return [_annotate(h, "hybrid") for h in merged]


def neighborhood(id: str, hops: int = 2) -> dict[str, Any]:
    """Undirected subgraph around a node id, shaped as GraphPayload."""
    nid = str(id or "").strip()
    hops = max(0, min(int(hops), 6))
    if not nid:
        return GraphPayload().model_dump()
    driver = get_driver()
    with driver.session() as session:
        origin = session.run(
            "MATCH (origin {id: $nid}) RETURN origin LIMIT 1",
            nid=nid,
        ).single()
        if origin is None:
            return GraphPayload().model_dump()

        hop_hi = max(hops, 0)
        node_rows = list(
            session.run(
                f"""
                MATCH (origin {{id: $nid}})
                OPTIONAL MATCH (origin)-[*0..{hop_hi}]-(n)
                WITH collect(DISTINCT origin) + collect(DISTINCT n) AS bag
                UNWIND bag AS node
                WITH node WHERE node IS NOT NULL
                RETURN DISTINCT node
                """,
                nid=nid,
            )
        )
        rel_rows = []
        if hop_hi >= 1:
            rel_rows = list(
                session.run(
                    f"""
                    MATCH (origin {{id: $nid}})
                    OPTIONAL MATCH path = (origin)-[*1..{hop_hi}]-(n)
                    WITH path WHERE path IS NOT NULL
                    UNWIND relationships(path) AS rel
                    WITH DISTINCT rel
                    RETURN startNode(rel).id AS source,
                           endNode(rel).id AS target,
                           type(rel) AS rel_name,
                           coalesce(rel.rel_type, rel.type, type(rel)) AS rel_prop,
                           coalesce(rel.strength, 1.0) AS strength
                    """,
                    nid=nid,
                )
            )

    nodes_out: list[GraphNode] = []
    seen_nodes: set[str] = set()
    degrees: dict[str, int] = {}
    links_raw: list[tuple[str, str, str, float]] = []
    seen_links: set[tuple[str, str, str]] = set()

    for rec in rel_rows:
        source = rec["source"]
        target = rec["target"]
        if not source or not target:
            continue
        rel_name = str(rec["rel_name"] or "RELATED_TO")
        if rel_name == "RELATED_TO":
            link_type = str(rec["rel_prop"] or "RELATED_TO")
        else:
            link_type = rel_name
        try:
            strength = float(rec["strength"] if rec["strength"] is not None else 1.0)
        except (TypeError, ValueError):
            strength = 1.0
        key = (str(source), str(target), link_type)
        if key in seen_links:
            continue
        seen_links.add(key)
        links_raw.append((str(source), str(target), link_type, strength))
        degrees[str(source)] = degrees.get(str(source), 0) + 1
        degrees[str(target)] = degrees.get(str(target), 0) + 1

    for rec in node_rows:
        node = rec["node"]
        if node is None:
            continue
        props = dict(node)
        node_id = str(props.get("id") or "")
        if not node_id or node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)
        ntype = _primary_label(node)
        label = _display_label(props, ntype)
        val = float(degrees.get(node_id, 0) or 1.0)
        nodes_out.append(
            GraphNode(id=node_id, label=label, type=ntype, val=val)
        )

    if nid not in seen_nodes:
        origin_node = origin["origin"]
        props = dict(origin_node)
        ntype = _primary_label(origin_node)
        nodes_out.insert(
            0,
            GraphNode(
                id=nid,
                label=_display_label(props, ntype),
                type=ntype,
                val=float(degrees.get(nid, 0) or 1.0),
            ),
        )
        seen_nodes.add(nid)

    links_out = [
        GraphLink(source=s, target=t, type=lt, strength=st)
        for s, t, lt, st in links_raw
        if s in seen_nodes and t in seen_nodes
    ]
    return GraphPayload(nodes=nodes_out, links=links_out).model_dump()


def _annotate(hit: dict[str, Any], mode: str) -> dict[str, Any]:
    out = dict(hit)
    out["mode"] = mode
    out.setdefault("title", "")
    out.setdefault("excerpt", "")
    out.setdefault("score", 0.0)
    return out


def _search_chunks(session: Any, query_vec: list[float], top_k: int) -> list[dict[str, Any]]:
    recs = _vector_query(session, "chunk_embedding", top_k, query_vec)
    if recs is None:
        return _scan_chunks_cosine(session, query_vec, top_k)
    hits: list[dict[str, Any]] = []
    for rec in recs:
        node = rec["node"]
        props = dict(node)
        score = float(rec["score"] or 0.0)
        hits.append(_chunk_hit_from_props(session, props, score))
    return hits


def _scan_chunks_cosine(
    session: Any, query_vec: list[float], top_k: int
) -> list[dict[str, Any]]:
    rows = list(
        session.run(
            """
            MATCH (c:Chunk)
            WHERE c.embedding IS NOT NULL
            OPTIONAL MATCH (d:Document)-[:HAS_CHUNK]->(c)
            RETURN c.id AS chunk_id, c.text AS text, c.embedding AS embedding,
                   d.id AS document_id, d.filename AS title
            """
        )
    )
    scored: list[dict[str, Any]] = []
    for rec in rows:
        emb = rec["embedding"]
        vec = [float(x) for x in emb] if emb is not None else []
        score = cosine_similarity(query_vec, vec)
        text = rec["text"] or ""
        scored.append(
            {
                "chunk_id": rec["chunk_id"],
                "document_id": rec["document_id"],
                "title": rec["title"] or "",
                "excerpt": _excerpt(text),
                "score": score,
            }
        )
    scored.sort(key=lambda h: h["score"], reverse=True)
    return scored[:top_k]


def _search_entities(
    session: Any, query_vec: list[float], query_text: str, top_k: int
) -> list[dict[str, Any]]:
    vector_hits: list[dict[str, Any]] = []
    recs = _vector_query(session, "entity_embedding", top_k, query_vec)
    if recs is None:
        vector_hits = _scan_entities_cosine(session, query_vec, top_k)
    else:
        for rec in recs:
            props = dict(rec["node"])
            vector_hits.append(
                {
                    "entity_id": props.get("id"),
                    "title": props.get("name") or props.get("id") or "",
                    "excerpt": props.get("description") or props.get("name") or "",
                    "score": float(rec["score"] or 0.0),
                }
            )

    fulltext_hits = _fulltext_entities(session, query_text, top_k)
    merged = _rrf_hits([vector_hits, fulltext_hits], top_k, id_key="entity_id")
    return merged


def _scan_entities_cosine(
    session: Any, query_vec: list[float], top_k: int
) -> list[dict[str, Any]]:
    rows = list(
        session.run(
            """
            MATCH (e:Entity)
            WHERE e.embedding IS NOT NULL
            RETURN e.id AS entity_id, e.name AS name,
                   e.description AS description, e.embedding AS embedding
            """
        )
    )
    scored: list[dict[str, Any]] = []
    for rec in rows:
        emb = rec["embedding"]
        vec = [float(x) for x in emb] if emb is not None else []
        scored.append(
            {
                "entity_id": rec["entity_id"],
                "title": rec["name"] or rec["entity_id"] or "",
                "excerpt": rec["description"] or rec["name"] or "",
                "score": cosine_similarity(query_vec, vec),
            }
        )
    scored.sort(key=lambda h: h["score"], reverse=True)
    return scored[:top_k]


def _fulltext_entities(session: Any, query_text: str, top_k: int) -> list[dict[str, Any]]:
    lucene = _to_lucene(query_text)
    if not lucene:
        return []
    try:
        rows = list(
            session.run(
                """
                CALL db.index.fulltext.queryNodes('entity_name_description', $q)
                YIELD node, score
                RETURN node, score
                LIMIT $k
                """,
                q=lucene,
                k=int(top_k),
            )
        )
    except Exception:
        # Fallback: naive name/description CONTAINS scan.
        rows = list(
            session.run(
                """
                MATCH (e:Entity)
                WHERE toLower(coalesce(e.name, '')) CONTAINS toLower($q)
                   OR toLower(coalesce(e.description, '')) CONTAINS toLower($q)
                RETURN e AS node, 1.0 AS score
                LIMIT $k
                """,
                q=query_text,
                k=int(top_k),
            )
        )
    hits: list[dict[str, Any]] = []
    for rec in rows:
        props = dict(rec["node"])
        hits.append(
            {
                "entity_id": props.get("id"),
                "title": props.get("name") or props.get("id") or "",
                "excerpt": props.get("description") or props.get("name") or "",
                "score": float(rec["score"] or 0.0),
            }
        )
    return hits


def _search_entity_chunks(
    session: Any, query_vec: list[float], query_text: str, top_k: int
) -> list[dict[str, Any]]:
    entities = _search_entities(session, query_vec, query_text, top_k)
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ent in entities:
        eid = ent.get("entity_id")
        if not eid:
            continue
        rows = list(
            session.run(
                """
                MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e:Entity {id: $eid})
                OPTIONAL MATCH (d:Document)-[:HAS_CHUNK]->(c)
                RETURN c.id AS chunk_id, c.text AS text,
                       d.id AS document_id, d.filename AS title
                """,
                eid=eid,
            )
        )
        for rec in rows:
            cid = rec["chunk_id"]
            if not cid or cid in seen:
                continue
            seen.add(cid)
            text = rec["text"] or ""
            hits.append(
                {
                    "chunk_id": cid,
                    "document_id": rec["document_id"],
                    "entity_id": eid,
                    "title": rec["title"] or ent.get("title") or "",
                    "excerpt": _excerpt(text),
                    "score": float(ent.get("score") or 0.0),
                }
            )
        if not rows:
            hits.append(
                {
                    "entity_id": eid,
                    "title": ent.get("title") or "",
                    "excerpt": ent.get("excerpt") or "",
                    "score": float(ent.get("score") or 0.0),
                }
            )
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[: max(top_k, len(hits))]


def _search_multi_hop(
    session: Any,
    query_vec: list[float],
    query_text: str,
    top_k: int,
    hops: int,
) -> list[dict[str, Any]]:
    seeds = _search_entities(session, query_vec, query_text, max(top_k, 5))
    if not seeds:
        return []
    node_score = {
        str(s["entity_id"]): float(s.get("score") or 0.0)
        for s in seeds
        if s.get("entity_id")
    }
    beam = [
        (eid, score, [eid])
        for eid, score in list(node_score.items())[:5]
    ]
    best = dict(node_score)
    for _depth in range(max(hops, 1)):
        nxt: list[tuple[str, float, list[str]]] = []
        for eid, path_score, path in beam:
            rows = list(
                session.run(
                    """
                    MATCH (e:Entity {id: $id})-[r:RELATED_TO]-(o:Entity)
                    RETURN o.id AS oid,
                           coalesce(r.strength, 1.0) AS strength
                    """,
                    id=eid,
                )
            )
            for rec in rows:
                oid = rec["oid"]
                if not oid or oid in path:
                    continue
                try:
                    strength = float(rec["strength"] if rec["strength"] is not None else 1.0)
                except (TypeError, ValueError):
                    strength = 1.0
                neighbor_score = max(node_score.get(oid, 0.0), 0.05)
                new_score = path_score * max(strength, 0.05) * neighbor_score
                new_score = new_score + (path_score + strength * neighbor_score) * 0.1
                nxt.append((oid, new_score, path + [oid]))
                best[oid] = max(best.get(oid, 0.0), new_score)
        nxt.sort(key=lambda item: item[1], reverse=True)
        beam = nxt[:5]
        if not beam:
            break

    ranked_ids = sorted(best, key=lambda k: best[k], reverse=True)[:top_k]
    hits: list[dict[str, Any]] = []
    for eid in ranked_ids:
        rec = session.run(
            """
            MATCH (e:Entity {id: $eid})
            OPTIONAL MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e)
            OPTIONAL MATCH (d:Document)-[:HAS_CHUNK]->(c)
            RETURN e.name AS name, e.description AS description,
                   collect(DISTINCT {
                       chunk_id: c.id,
                       text: c.text,
                       document_id: d.id,
                       title: d.filename
                   }) AS chunks
            """,
            eid=eid,
        ).single()
        if rec is None:
            continue
        chunks = [c for c in (rec["chunks"] or []) if c and c.get("chunk_id")]
        if chunks:
            for ch in chunks:
                hits.append(
                    {
                        "chunk_id": ch.get("chunk_id"),
                        "document_id": ch.get("document_id"),
                        "entity_id": eid,
                        "title": ch.get("title") or rec["name"] or eid,
                        "excerpt": _excerpt(ch.get("text") or rec["description"] or ""),
                        "score": float(best[eid]),
                    }
                )
        else:
            hits.append(
                {
                    "entity_id": eid,
                    "title": rec["name"] or eid,
                    "excerpt": rec["description"] or rec["name"] or "",
                    "score": float(best[eid]),
                }
            )
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:top_k]


def _vector_query(
    session: Any, index_name: str, k: int, embedding: list[float]
) -> list[Any] | None:
    """Native Neo4j 5 vector query. Returns None if the index is not ready."""
    if index_name not in {"chunk_embedding", "entity_embedding"}:
        return None
    try:
        return list(
            session.run(
                f"CALL db.index.vector.queryNodes('{index_name}', $k, $embedding) "
                "YIELD node, score RETURN node, score",
                k=int(k),
                embedding=[float(x) for x in embedding],
            )
        )
    except Exception:
        return None


def _chunk_hit_from_props(session: Any, props: dict[str, Any], score: float) -> dict[str, Any]:
    chunk_id = props.get("id")
    document_id = props.get("document_id")
    title = ""
    if chunk_id:
        rec = session.run(
            """
            MATCH (c:Chunk {id: $cid})
            OPTIONAL MATCH (d:Document)-[:HAS_CHUNK]->(c)
            RETURN d.id AS document_id, d.filename AS title
            """,
            cid=chunk_id,
        ).single()
        if rec is not None:
            document_id = document_id or rec["document_id"]
            title = rec["title"] or ""
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "title": title,
        "excerpt": _excerpt(props.get("text") or ""),
        "score": score,
    }


def _rrf_hits(
    rankings: list[list[dict[str, Any]]],
    top_k: int,
    id_key: str = "chunk_id",
) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    payload: dict[str, dict[str, Any]] = {}
    for ranking in rankings:
        ordered: list[str] = []
        for hit in ranking:
            hid = hit.get(id_key) or hit.get("chunk_id") or hit.get("entity_id")
            if not hid:
                continue
            hid = str(hid)
            if hid in ordered:
                continue
            ordered.append(hid)
            if hid not in payload:
                payload[hid] = dict(hit)
            else:
                payload[hid] = {**hit, **{k: v for k, v in payload[hid].items() if v not in (None, "")}}
        for rank, hid in enumerate(ordered, start=1):
            scores[hid] = scores.get(hid, 0.0) + 1.0 / (_RRF_K + rank)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    out: list[dict[str, Any]] = []
    for hid, score in ranked[:top_k]:
        hit = dict(payload[hid])
        hit["score"] = score
        out.append(hit)
    return out


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(n):
        x = float(a[i])
        y = float(b[i])
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _excerpt(text: str, limit: int = 240) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _to_lucene(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_.-]+", query or "")
    cleaned = []
    for tok in tokens:
        esc = _LUCENE_SPECIAL.sub(r"\\\1", tok)
        if esc:
            cleaned.append(esc)
    return " OR ".join(cleaned)


def _primary_label(node: Any) -> str:
    labels = list(getattr(node, "labels", []) or [])
    for known in _KNOWN_LABELS:
        if known in labels:
            return known
    return labels[0] if labels else "Node"


def _display_label(props: dict[str, Any], ntype: str) -> str:
    if ntype == "Entity":
        return str(props.get("name") or props.get("id") or "")
    if ntype == "Document":
        return str(props.get("filename") or props.get("id") or "")
    if ntype == "Chunk":
        return _excerpt(str(props.get("text") or ""), limit=80) or str(props.get("id") or "")
    if ntype == "ConversationSession":
        return str(props.get("title") or props.get("id") or "")
    if ntype == "Message":
        return _excerpt(str(props.get("content") or ""), limit=80) or str(props.get("id") or "")
    return str(props.get("id") or "")


def list_documents() -> list[dict[str, Any]]:
    """Return Document nodes as HTTP DocumentSummary dicts."""
    driver = get_driver()
    with driver.session() as session:
        rows = list(
            session.run(
                """
                MATCH (d:Document)
                RETURN d.id AS id,
                       coalesce(d.filename, d.id) AS filename,
                       coalesce(d.status, '') AS status,
                       toString(d.created_at) AS created_at,
                       coalesce(d.hashtags, []) AS hashtags
                ORDER BY d.updated_at DESC, d.created_at DESC
                """
            )
        )
    documents: list[dict[str, Any]] = []
    for rec in rows:
        hashtags = rec["hashtags"] or []
        if not isinstance(hashtags, list):
            hashtags = list(hashtags)
        documents.append(
            {
                "id": str(rec["id"] or ""),
                "filename": str(rec["filename"] or ""),
                "status": str(rec["status"] or ""),
                "created_at": rec["created_at"],
                "hashtags": [str(h) for h in hashtags],
            }
        )
    return documents


def graph_overview(hops: int = 2) -> dict[str, Any]:
    """Union of document neighborhoods plus label counts."""
    docs = list_documents()
    nodes_by_id: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []
    seen_links: set[tuple[Any, Any, Any]] = set()
    for doc in docs:
        payload = neighborhood(str(doc.get("id") or ""), hops=hops)
        for node in payload.get("nodes") or []:
            item = node if isinstance(node, dict) else node.model_dump()
            nid = str(item.get("id") or "")
            if nid:
                nodes_by_id[nid] = item
        for link in payload.get("links") or []:
            item = link if isinstance(link, dict) else link.model_dump()
            key = (item.get("source"), item.get("target"), item.get("type"))
            if key in seen_links:
                continue
            seen_links.add(key)
            links.append(item)
    nodes = list(nodes_by_id.values())

    def type_of(n: dict[str, Any]) -> str:
        return str(n.get("type") or "")

    return {
        "nodes": nodes,
        "links": links,
        "document_count": sum(1 for n in nodes if type_of(n) in ("Document", "document")),
        "entity_count": sum(1 for n in nodes if type_of(n) in ("Entity", "entity")),
        "chunk_count": sum(1 for n in nodes if type_of(n) in ("Chunk", "chunk")),
    }
