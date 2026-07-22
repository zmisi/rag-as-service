# F04temp — superseded by F04 doc indexing

> **Status:** superseded (2026-07-22). Use `document_sections` + section-aware leaf chunks per [F04 spec](../../docs/specs/phase1/features/F04-doc-indexing.md).

The temporary flat-chunk stack (`20260722_f04temp` migration, `F04temp` tests) was replaced by:

- `document_sections` (H1/H2 tree) + `document_chunks.section_id`
- Migration `20260722_f04_sections`
- `parse → build_section_tree → leaf chunk → embed → search(section full text + path)`
- Tests: `tests/unit/test_f04_*.py`, `tests/integration/test_f04_doc_indexing.py`

Local e2e after publish: ensure `AUTO_MIGRATE=true`, optional `INDEX_SYNC_ON_PUBLISH=true`, then chat with a indexed `.txt` / `.md` doc.

For PDF/Office parsing install Docling: `pip install -e ".[docling]"` or `uv sync --extra docling`.
