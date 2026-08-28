"""Unit tests for markdown chunking (no Neo4j)."""

from app.arms.memory.chunking import split_text


def test_split_text_overlap_and_no_empty_chunks():
    text = " ".join(f"word{i:03d}" for i in range(220))
    chunks = split_text(text, chunk_size=120, chunk_overlap=30)
    assert chunks, "expected at least one chunk"
    assert all(chunk.strip() for chunk in chunks)
    assert len(chunks) >= 2

    reconstructed_tokens = set()
    for chunk in chunks:
        reconstructed_tokens.update(chunk.split())
    original_tokens = set(text.split())
    missing = original_tokens - reconstructed_tokens
    assert not missing, f"chunking dropped tokens: {sorted(missing)[:8]}"

    for left, right in zip(chunks, chunks[1:]):
        tail_tokens = [tok for tok in left.split()[-8:] if len(tok) > 3]
        head = " ".join(right.split()[:16])
        assert any(tok in head for tok in tail_tokens), (
            "expected overlap between consecutive chunks\n"
            f"left tail={left[-60]!r}\nright head={right[:60]!r}"
        )


def test_split_text_preserves_heading_blocks():
    text = (
        "# Title\n\n"
        "Intro paragraph about A.K.I.R.A.\n\n"
        "## Hybrid search\n\n"
        "Hybrid search mixes vector and entity retrieval over Neo4j.\n"
    )
    chunks = split_text(text, chunk_size=800, chunk_overlap=40)
    assert chunks
    assert all(c.strip() for c in chunks)
    blob = "\n".join(chunks)
    assert "Hybrid search" in blob
    assert "Neo4j" in blob
