"""Unit tests for F04 parse + section-aware chunking helpers."""

from __future__ import annotations

import pytest

from rag_api.indexing.chunker import chunk_text
from rag_api.indexing.constants import EMBEDDING_DIM
from rag_api.indexing.embedding import HashingEmbedder
from rag_api.indexing.parse import (
    ParseError,
    ScriptedDocumentParser,
    TextDocumentParser,
    parse_files_to_markdown,
)
from rag_api.indexing.search import ChunkHit, dedupe_hits_by_section
from rag_api.indexing.sections import build_section_tree


def test_text_parser_txt_md() -> None:
    p = TextDocumentParser()
    assert p.parse_to_markdown("a.txt", "hello".encode()) == "hello"
    assert "x" in p.parse_to_markdown("a.md", "# x\n".encode())


def test_text_parser_rejects_binary_pdf() -> None:
    p = TextDocumentParser()
    with pytest.raises(ParseError):
        p.parse_to_markdown("x.pdf", b"%PDF-1.4 binary \x00\xff")


def test_scripted_empty_pdf_suffix() -> None:
    p = ScriptedDocumentParser(empty_suffixes=frozenset({".pdf"}))
    assert p.parse_to_markdown("scan.pdf", b"anything") == ""


def test_parse_files_merge_separator() -> None:
    p = ScriptedDocumentParser(
        mapping={"a.txt": "AAA", "b.txt": "BBB"},
    )
    out = parse_files_to_markdown(
        [("a.txt", b""), ("b.txt", b"")],
        parser=p,
    )
    assert "AAA" in out and "BBB" in out
    assert "---" in out


def test_section_chunk_no_cross_boundary() -> None:
    md = """# H

## A

""" + ("aaaa " * 200) + """

## B

""" + ("bbbb " * 200)
    drafts = build_section_tree(md)
    assert len(drafts) == 2
    leaves_a = chunk_text(drafts[0].content, target_tokens=20, overlap_tokens=2)
    leaves_b = chunk_text(drafts[1].content, target_tokens=20, overlap_tokens=2)
    assert leaves_a and leaves_b
    assert all("bbbb" not in x for x in leaves_a)
    assert all("aaaa" not in x for x in leaves_b)


def test_empty_section_no_leaf() -> None:
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_f04_t23_table_aware_split_when_over_budget() -> None:
    """F04-T23: over budget → split before/after table; table stays intact."""
    prose = ("正文说明段落。关于部分索引的用法。" * 80)
    table = (
        "| 索引类型 | 使用范围 | 注意事项 | 备注 |\n"
        "| --- | --- | --- | --- |\n"
        "| B-Tree 索引 | 使用范围最高 | 111233 | abc |\n"
        "| 位图索引 | 使用范围比较低 | 3333444 | cdb |"
    )
    body = f"{prose}\n\n{table}\n\n尾部补充说明。"
    # Budget fits the small table alone, but not prose+table together.
    table_tokens = max(1, (len(table) // 2) + 5)
    assert len(body) > table_tokens * 2
    leaves = chunk_text(body, target_tokens=table_tokens, overlap_tokens=5)
    assert len(leaves) >= 2
    table_leaves = [x for x in leaves if "| B-Tree 索引 |" in x]
    assert len(table_leaves) == 1
    tbl = table_leaves[0]
    assert "| 索引类型 |" in tbl
    assert "| 位图索引 |" in tbl
    assert "---" in tbl
    # Table leaf is not mid-cell char-sliced (starts at header).
    assert tbl.lstrip().startswith("| 索引类型 |")
    # Prose-only leaves must not be mid-table row fragments.
    for leaf in leaves:
        if leaf.strip().startswith("|") and "索引类型" not in leaf:
            pytest.fail(f"unexpected severed table fragment: {leaf!r}")


def test_under_budget_keeps_mixed_single_leaf() -> None:
    body = (
        "短正文。\n\n"
        "| a | b |\n"
        "| --- | --- |\n"
        "| 1 | 2 |"
    )
    leaves = chunk_text(body, target_tokens=800, overlap_tokens=100)
    assert leaves == [body.strip()]


def test_f04_t19_embedding_text_includes_heading_path() -> None:
    from rag_api.indexing.worker import build_embedding_text

    text = build_embedding_text(
        ["2.1 索引类型与选择", "2.1.1 B-Tree 索引适用场景"],
        "B-Tree 适用于等值查询。",
    )
    assert text.startswith("2.1 索引类型与选择 > 2.1.1 B-Tree 索引适用场景")
    assert "B-Tree 适用于等值查询。" in text
    assert build_embedding_text([], "only body") == "only body"


def test_hashing_embedder_dim_and_deterministic() -> None:
    emb = HashingEmbedder(dim=EMBEDDING_DIM)
    a = emb.embed(["退货窗口 30 天"])[0]
    b = emb.embed(["退货窗口 30 天"])[0]
    assert len(a) == EMBEDDING_DIM
    assert a == b


def test_dedupe_hits_by_section() -> None:
    hits = [
        ChunkHit("c1", "d", "sec-full", 0.9, section_id="s1", path="A > B"),
        ChunkHit("c2", "d", "sec-full", 0.8, section_id="s1", path="A > B"),
        ChunkHit("c3", "d", "other", 0.7, section_id="s2", path="A > C"),
    ]
    out = dedupe_hits_by_section(hits, top_k=5)
    assert len(out) == 2
    assert out[0].chunk_id == "c1"
    assert out[1].section_id == "s2"
