"""Unit tests for H1/H2 section tree (F04)."""

from __future__ import annotations

from rag_api.indexing.sections import build_section_tree


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
