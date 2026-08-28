# A.K.I.R.A. Memory Kernel Overview

A.K.I.R.A. (Agentic Knowledge Integration and Retrieval Architecture) is a local-first
agent platform. It stores documents, conversations, and a knowledge graph in Neo4j so
that later questions can be answered with grounded context rather than a stateless
prompt. The Memory Kernel is the subsystem that turns markdown into a graph of Chunk
and Entity nodes joined by RELATED_TO edges, then serves hybrid search and neighborhood
expansion to the rest of the stack.

## Why Neo4j

Neo4j is the system of record. Each ingested markdown file becomes a Document. The
Memory Kernel splits that Document into overlapping Chunk nodes that preserve headings
and paragraphs. Named ideas in those chunks become Entity nodes (Person, Organization,
Concept, Place, or Technology). A Chunk points at the entities it mentions through
CONTAINS_ENTITY. Entities point at each other through RELATED_TO, carrying a relation
type and a numeric strength. ConversationSession and Message nodes live in the same
graph so a chat thread can be retrieved beside the documents it cited.

Vector search uses Neo4j 5 native vector indexes on Chunk.embedding and
Entity.embedding with cosine similarity. There is no FAISS store and no Graph Data
Science plugin. When a vector index is still coming online, the retriever falls back
to a Cypher scan scored with Python cosine. Full-text search on Entity.name and
Entity.description complements the vectors.

## Hybrid search

Hybrid search is the default retrieval mode. It runs a vector query over Chunk
embeddings and a combined vector-plus-full-text query over Entity nodes. Entity hits
are mapped back to the chunks that contain them. Reciprocal rank fusion (RRF) merges
the two ranked lists so a passage that is both lexically and semantically close to the
question rises to the top. Callers can also request chunk-only or entity-only modes.

Multi-hop retrieval starts from the best Entity matches and walks RELATED_TO with a
small beam (about five candidates per layer) up to a hop depth. Path scores combine
relationship strength with node scores, which is useful when the answer lives one or
two relations away from the terms in the question.

## Neighborhood

The neighborhood API takes any node id (Document, Chunk, Entity, ConversationSession,
or Message) and an integer hop count. It returns an undirected subgraph as a payload
of nodes and links that a force-directed view can render. Each node has id, label,
type, and val. Each link has source, target, type, and strength. The origin node is
always included. Link type is the RELATED_TO relation name when present, otherwise the
Neo4j relationship type such as HAS_CHUNK, CONTAINS_ENTITY, RELATED_TO, or HAS_MESSAGE.

## Serving layer

FastAPI exposes health, chat, document, and graph routes on top of this kernel. The
HTTP contracts stay frozen: GraphPayload is always nodes plus links. LangGraph
orchestrates the agent loop, deciding when to call hybrid search, when to expand a
neighborhood, and when to write a new Message into a ConversationSession. LangGraph
checkpoints keep thread state so a user can resume a conversation without losing the
graph context assembled on earlier turns.

## Design notes

The Memory Kernel is deterministic where it can be. Chunk ids are
`{document_id}::chunk::{index}`. Entity ids are a stable slug of `type::normalized name`,
so re-ingesting the same markdown MERGEs instead of duplicating. Document ingest is
idempotent: existing chunks for that document are replaced, entities are merged, and
the Document status moves from ingesting to ready. Embeddings come from OpenAI
(text-embedding-3-small, 1536 dimensions) or Ollama (nomic-embed-text, 768 dimensions).
Extraction asks the LLM for strict JSON, never a pipe table or CSV.

Taken together, Neo4j, the Memory Kernel, Chunk and Entity graphs, RELATED_TO,
hybrid search, neighborhood, FastAPI, and LangGraph give A.K.I.R.A. a durable
memory it can traverse instead of a pile of isolated vectors.
