"""Unit tests for H1/H2 section tree (F04)."""

from __future__ import annotations

from rag_api.indexing.sections import (
    build_section_tree,
    infer_chunk_type,
    normalize_numbered_outline,
    sanitize_index_text,
)


def test_no_headings_single_section() -> None:
    drafts = build_section_tree("plain body text", title_fallback="FAQ")
    assert len(drafts) == 1
    assert drafts[0].level == 1
    assert drafts[0].title == "FAQ"
    assert drafts[0].path == "FAQ"
    assert "plain body" in drafts[0].content


def test_empty_markdown() -> None:
    assert build_section_tree("") == []
    assert build_section_tree("   \n") == []


def test_two_h2_under_h1_paths_and_isolation() -> None:
    md = """# 退款政策

导言段落。

## 时效

ALPHA_ONLY_PHRASE 三十天

## 流程

BETA_ONLY_PHRASE 提交工单
"""
    drafts = build_section_tree(md, title_fallback="doc")
    paths = [d.path for d in drafts]
    assert "退款政策" in paths
    assert "退款政策 > 时效" in paths
    assert "退款政策 > 流程" in paths
    by_path = {d.path: d for d in drafts}
    assert "ALPHA_ONLY_PHRASE" in by_path["退款政策 > 时效"].content
    assert "ALPHA_ONLY_PHRASE" not in by_path["退款政策 > 流程"].content
    assert "BETA_ONLY_PHRASE" in by_path["退款政策 > 流程"].content
    assert "导言段落" in by_path["退款政策"].content


def test_h3_merges_into_h2() -> None:
    md = """# Doc

## Section

### Deep

deep body here
"""
    drafts = build_section_tree(md)
    assert len(drafts) == 1
    assert drafts[0].path == "Doc > Section"
    assert "deep body" in drafts[0].content
    assert "### Deep" in drafts[0].content


def test_h1_only_no_h2() -> None:
    md = """# Title

only body
"""
    drafts = build_section_tree(md)
    assert len(drafts) == 1
    assert drafts[0].level == 1
    assert drafts[0].path == "Title"
    assert "only body" in drafts[0].content


def test_f04_t18_numbered_outline_gets_parent_paths() -> None:
    """Flat ## 2.1.1 / ## 2.1.2 → hierarchical paths with parent prefix."""
    md = """## 2.1.1 B-Tree 索引适用场景

B-Tree 索引适用于等值查询（ &gt; ， &lt; ）。

## 2.1.2 部分索引（Partial Index）的使用

CREATE INDEX idx\\_orders\\_pending ON orders (order\\_date) WHERE status = 'pending';

## 2.2.1 解读EXPLAIN ANALYZE

EXPLAIN ANALYZE 会真实执行 SQL。

## 2.2.2 自动分析（AutoVacuum）调优

将 autovacuum\\_vacuum\\_scale\\_factor 调整为 0.05。
"""
    drafts = build_section_tree(md, title_fallback="PostgreSQL性能优化实战")
    paths = [d.path for d in drafts]
    assert len(drafts) == 4
    assert all(" > " in p for p in paths)
    assert any(p.startswith("2.1 > ") for p in paths)
    assert any(p.startswith("2.2 > ") for p in paths)
    btree = next(d for d in drafts if "2.1.1" in d.path)
    assert ">" in btree.content or "<" in btree.content
    assert "&gt;" not in btree.content
    partial = next(d for d in drafts if "2.1.2" in d.path)
    assert "idx_orders_pending" in partial.content
    assert "\\_" not in partial.content


def test_sanitize_index_text() -> None:
    assert sanitize_index_text("a &gt; b &lt; c") == "a > b < c"
    assert sanitize_index_text(r"idx\_orders\_pending") == "idx_orders_pending"


def test_normalize_inserts_synthetic_parents() -> None:
    out = normalize_numbered_outline("## 2.1.1 Foo\n\nbody\n")
    assert "# 2.1" in out or out.startswith("# 2")
    assert "## 2.1.1 Foo" in out


def test_infer_chunk_type() -> None:
    assert infer_chunk_type("plain") == "text"
    table = "| a | b |\n|---|---|\n| 1 | 2 |"
    assert infer_chunk_type(table) == "table"
    mixed = "intro\n\n" + table
    assert infer_chunk_type(mixed) == "mixed"
