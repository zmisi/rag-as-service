"""F04temp unit tests: chunker + hashing embedder."""

from __future__ import annotations

from rag_api.indexing.chunker import chunk_text
from rag_api.indexing.constants import EMBEDDING_DIM
from rag_api.indexing.embedding import HashingEmbedder


def test_chunk_empty_document_yields_zero_chunks() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\t  ") == []


def test_chunk_short_text_single_chunk() -> None:
    text = "退货窗口 30 天"
    assert chunk_text(text) == [text]


def test_chunk_long_text_overlaps() -> None:
    # Force multiple chunks with tiny budgets
    text = "abcdefghij" * 50  # 500 chars
    chunks = chunk_text(text, target_tokens=20, overlap_tokens=5)  # 40 / 10 chars
    assert len(chunks) >= 2
    assert all(c for c in chunks)


def test_hashing_embedder_dim_and_deterministic() -> None:
    emb = HashingEmbedder(dim=EMBEDDING_DIM)
    a = emb.embed(["退货窗口 30 天"])[0]
    b = emb.embed(["退货窗口 30 天"])[0]
    assert len(a) == EMBEDDING_DIM
    assert a == b
    # Similar phrases should be closer than unrelated (cosine via dot of L2 norms)
    c = emb.embed(["完全不相关的话题 xyz"])[0]
    sim_ab = sum(x * y for x, y in zip(a, b, strict=True))
    sim_ac = sum(x * y for x, y in zip(a, c, strict=True))
    assert sim_ab > sim_ac
