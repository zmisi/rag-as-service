"""Unit tests for H1–H6 section tree (F04)."""

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


def test_f04_t20_h3_is_own_section() -> None:
    """F04-T20: H3 becomes its own leaf; phrase not merged into H2."""
    md = """# Doc

## Section

### Deep

DEEP_ONLY_PHRASE here
"""
    drafts = build_section_tree(md)
    paths = [d.path for d in drafts]
    assert "Doc > Section > Deep" in paths
    by_path = {d.path: d for d in drafts}
    deep = by_path["Doc > Section > Deep"]
    assert deep.level == 3
    assert "DEEP_ONLY_PHRASE" in deep.content
    assert deep.parent_path == "Doc > Section"
    # H2 empty → discarded; only H3 (and maybe H1 if it had body)
    assert all("DEEP_ONLY_PHRASE" not in d.content or d.path.endswith("Deep") for d in drafts)


def test_h4_to_h6_and_sibling_switch() -> None:
    md = """# L1

## L2

### L3

#### L4

l4 body

##### L5

l5 body

###### L6

l6 body

#### L4b

l4b body

## L2b

l2b body
"""
    drafts = build_section_tree(md)
    by_path = {d.path: d for d in drafts}
    assert by_path["L1 > L2 > L3 > L4"].level == 4
    assert "l4 body" in by_path["L1 > L2 > L3 > L4"].content
    assert by_path["L1 > L2 > L3 > L4 > L5"].level == 5
    assert "l5 body" in by_path["L1 > L2 > L3 > L4 > L5"].content
    assert by_path["L1 > L2 > L3 > L4 > L5 > L6"].level == 6
    assert "l6 body" in by_path["L1 > L2 > L3 > L4 > L5 > L6"].content
    assert "l4b body" in by_path["L1 > L2 > L3 > L4b"].content
    assert "l2b body" in by_path["L1 > L2b"].content
    # Returning to H2 flushed deeper sections already
    assert by_path["L1 > L2b"].parent_path == "L1"


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
    assert any(p.startswith("2 > 2.1 > ") for p in paths)
    assert any(p.startswith("2 > 2.2 > ") for p in paths)
    btree = next(d for d in drafts if "2.1.1" in d.path)
    assert btree.level == 3
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
    assert "# 2" in out
    assert "## 2.1" in out
    assert "### 2.1.1 Foo" in out


def test_f04_t22_named_chapter_not_replaced_by_synthetic_number() -> None:
    """F04-T22: real H1 chapter keeps path; no synthetic ``# 2``."""
    md = """# 第二章 索引优化策略

## 2.1 索引类型与选择

## 2.1.1 B-Tree索引适用场景

BTREE_ONLY body

## 2.1.2 部分索引的使用

PARTIAL_ONLY body

## 2.2 执行计划与统计信息

## 2.2.1 解读EXPLAIN ANALYZE

EXPLAIN body
"""
    out = normalize_numbered_outline(md)
    assert "# 第二章 索引优化策略" in out
    assert "# 2\n" not in out and not out.startswith("# 2\n")
    assert not any(line.strip() == "# 2" for line in out.splitlines())

    drafts = build_section_tree(md)
    assert drafts
    assert all(d.path.startswith("第二章 索引优化策略") for d in drafts)
    assert not any(d.path.startswith("2 >") for d in drafts)
    # Empty chapter row may be absent; leaf paths still carry the title.
    assert not any(d.path == "第二章 索引优化策略" for d in drafts)
    btree = next(d for d in drafts if "2.1.1" in d.path)
    assert "BTREE_ONLY" in btree.content
    assert "PARTIAL_ONLY" not in btree.content


def test_f04_t24_docling_flat_h2_chapter_promoted() -> None:
    """F04-T24: Docling-flat ## 第二章 still wins over synthetic # 2."""
    md = """## 《 PostgreSQL 性能调优实战指南》

## 第二章 索引优化策略

## 2.1 索引类型与选择

## 2.1.1 B-Tree 索引适用场景

BTREE_ONLY body

## 2.1.2 部分索引（Partial Index）的使用

PARTIAL_ONLY body

## 2.2 执行计划与统计信息

## 2.2.1 解读EXPLAIN ANALYZE

EXPLAIN body

## 2.2.2 自动分析（AutoVacuum）调优

VACUUM body
"""
    out = normalize_numbered_outline(md)
    assert any(line.strip() == "# 第二章 索引优化策略" for line in out.splitlines())
    assert not any(line.strip() == "# 2" for line in out.splitlines())

    drafts = build_section_tree(md, title_fallback="PostgreSQL性能优化实战")
    assert drafts
    assert all(d.path.startswith("第二章 索引优化策略") for d in drafts)
    assert not any(d.path.startswith("2 >") for d in drafts)
    btree = next(d for d in drafts if "2.1.1" in d.path)
    assert "BTREE_ONLY" in btree.content
    assert btree.path.startswith("第二章 索引优化策略 > 2.1")


def test_drafts_emitted_shallow_first() -> None:
    md = """# A

a body

## B

b body

### C

c body
"""
    drafts = build_section_tree(md)
    assert [d.path for d in drafts] == ["A", "A > B", "A > B > C"]
    assert drafts[1].parent_path == "A"
    assert drafts[2].parent_path == "A > B"


def test_infer_chunk_type() -> None:
    assert infer_chunk_type("plain") == "text"
    table = "| a | b |\n|---|---|\n| 1 | 2 |"
    assert infer_chunk_type(table) == "table"
    mixed = "intro\n\n" + table
    assert infer_chunk_type(mixed) == "mixed"
