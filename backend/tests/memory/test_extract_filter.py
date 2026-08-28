"""Unit tests for post-LLM entity sanitization (no Neo4j, no LLM)."""

from app.arms.memory.extract import (
    GraphExtraction,
    is_noise_entity,
    normalize_entity_name,
    sanitize_extraction,
)


def test_rejects_stopwords_articles_and_tiny_names():
    assert is_noise_entity("the")
    assert is_noise_entity("The")
    assert is_noise_entity("  a  ")
    assert is_noise_entity("of")
    assert is_noise_entity("to")
    assert is_noise_entity("da")
    assert is_noise_entity("o")
    assert is_noise_entity("x")
    assert is_noise_entity("AI")  # 2 chars
    assert is_noise_entity("")
    assert is_noise_entity("   ")
    assert is_noise_entity('"the"')
    assert is_noise_entity("the of a")
    assert not is_noise_entity("Neo4j")
    assert not is_noise_entity("A.K.I.R.A.")
    assert not is_noise_entity("Memory Kernel")
    assert not is_noise_entity("FastAPI")


def test_normalize_strips_quotes_and_whitespace():
    assert normalize_entity_name('  "Neo4j"  ') == "Neo4j"
    assert normalize_entity_name("  Memory   Kernel  ") == "Memory Kernel"


def test_sanitize_drops_junk_and_dangling_relations():
    graph = GraphExtraction.model_validate(
        {
            "entities": [
                {"name": "the", "type": "Concept", "description": "article"},
                {"name": "a", "type": "Concept", "description": ""},
                {"name": "of", "type": "Concept", "description": ""},
                {"name": "  ", "type": "Concept", "description": ""},
                {"name": "x", "type": "Concept", "description": "tiny"},
                {"name": "Neo4j", "type": "Technology", "description": "graph db"},
                {"name": "A.K.I.R.A.", "type": "Technology", "description": "platform"},
                {"name": '"the"', "type": "Concept", "description": "quoted article"},
            ],
            "relations": [
                {
                    "source": "the",
                    "target": "Neo4j",
                    "type": "MENTIONS",
                    "strength": 1.0,
                },
                {
                    "source": "A.K.I.R.A.",
                    "target": "Neo4j",
                    "type": "USES",
                    "strength": 0.9,
                },
                {
                    "source": "of",
                    "target": "a",
                    "type": "RELATED_TO",
                    "strength": 1.0,
                },
            ],
        }
    )
    cleaned = sanitize_extraction(graph)
    names = {ent.name for ent in cleaned.entities}
    assert names == {"Neo4j", "A.K.I.R.A."}
    assert {(rel.source, rel.target, rel.type) for rel in cleaned.relations} == {
        ("A.K.I.R.A.", "Neo4j", "USES")
    }

def test_rejects_fragments_snippets_and_prompt_junk():
    assert is_noise_entity("rsationSession")
    assert is_noise_entity("ed with Python")
    assert is_noise_entity("schema-vocab")
    assert is_noise_entity("otherwise")
    assert is_noise_entity("ing Neo4j")
    assert is_noise_entity("used by FastAPI")
    assert is_noise_entity("json-object")
    assert not is_noise_entity("Neo4j")
    assert not is_noise_entity("A.K.I.R.A.")
    assert not is_noise_entity("Memory Kernel")
    assert not is_noise_entity("FastAPI")
    assert is_noise_entity("ConversationSession")
    assert not is_noise_entity("iPhone")
    assert not is_noise_entity("scikit-learn")
    assert not is_noise_entity("Bank of America")


def test_sanitize_drops_llm_fragments_and_prompt_leakage():
    graph = GraphExtraction.model_validate(
        {
            "entities": [
                {"name": "rsationSession", "type": "Concept", "description": "fragment"},
                {"name": "ed with Python", "type": "Concept", "description": "snippet"},
                {"name": "schema-vocab", "type": "Concept", "description": "prompt leak"},
                {"name": "otherwise", "type": "Concept", "description": "discourse"},
                {"name": "Neo4j", "type": "Technology", "description": "graph db"},
                {"name": "Memory Kernel", "type": "Concept", "description": "memory arm"},
            ],
            "relations": [
                {
                    "source": "rsationSession",
                    "target": "Neo4j",
                    "type": "RELATED_TO",
                    "strength": 1.0,
                },
                {
                    "source": "Memory Kernel",
                    "target": "Neo4j",
                    "type": "USES",
                    "strength": 0.9,
                },
                {
                    "source": "schema-vocab",
                    "target": "otherwise",
                    "type": "RELATED_TO",
                    "strength": 1.0,
                },
            ],
        }
    )
    cleaned = sanitize_extraction(graph)
    names = {ent.name for ent in cleaned.entities}
    assert names == {"Neo4j", "Memory Kernel"}
    assert {(rel.source, rel.target, rel.type) for rel in cleaned.relations} == {
        ("Memory Kernel", "Neo4j", "USES")
    }

def test_rejects_schema_labels_and_retriever_tokens():
    assert is_noise_entity("ConversationSession")
    assert is_noise_entity("Person")
    assert is_noise_entity("HAS_CHUNK")
    assert is_noise_entity("HYBRID_SEARCH")
    assert is_noise_entity("Document")
    assert is_noise_entity("Chunk")
    assert is_noise_entity("Entity")
    assert is_noise_entity("Message")
    assert is_noise_entity("CONTAINS_ENTITY")
    assert is_noise_entity("RELATED_TO")
    assert is_noise_entity("HAS_MESSAGE")
    assert is_noise_entity("MULTI_HOP")
    assert not is_noise_entity("Neo4j")
    assert not is_noise_entity("Memory Kernel")
    assert not is_noise_entity("FastAPI")
    assert not is_noise_entity("A.K.I.R.A.")


def test_sanitize_drops_schema_label_entities_and_rel_types():
    graph = GraphExtraction.model_validate(
        {
            "entities": [
                {"name": "ConversationSession", "type": "Concept", "description": "schema"},
                {"name": "Person", "type": "Person", "description": "enum leak"},
                {"name": "HAS_CHUNK", "type": "Concept", "description": "rel type"},
                {"name": "HYBRID_SEARCH", "type": "Concept", "description": "retriever"},
                {"name": "Neo4j", "type": "Technology", "description": "graph db"},
                {"name": "FastAPI", "type": "Technology", "description": "http"},
            ],
            "relations": [
                {
                    "source": "Neo4j",
                    "target": "FastAPI",
                    "type": "HAS_CHUNK",
                    "strength": 1.0,
                },
                {
                    "source": "Neo4j",
                    "target": "FastAPI",
                    "type": "USES",
                    "strength": 0.8,
                },
                {
                    "source": "ConversationSession",
                    "target": "Neo4j",
                    "type": "RELATED_TO",
                    "strength": 1.0,
                },
            ],
        }
    )
    cleaned = sanitize_extraction(graph)
    names = {ent.name for ent in cleaned.entities}
    assert names == {"Neo4j", "FastAPI"}
    assert {(rel.source, rel.target, rel.type) for rel in cleaned.relations} == {
        ("Neo4j", "FastAPI", "USES")
    }
