# F04temp — temporary indexing for F06 end-to-end

This branch is **not** Spec-approved F04. It exists so F06 chat can retrieve
real `published` chunks locally.

## What it adds

- `document_chunks` table + pgvector (`vector(1024)`)
- Parse (txt first) → chunk → embed → index_job worker
- Default **HashingEmbedder** (no DashScope needed); optional `QWEN_EMBEDDING_ENABLED=true` → `text-embedding-v4` @ dim 1024
- `PgKnowledgeSearcher` wired into F06 `get_knowledge_searcher()`
- Publish runs index **inline** when `INDEX_SYNC_ON_PUBLISH=true` (default)
- `POST /v1/documents/index/run-pending` to drain pending jobs
- Soft-delete document deactivates chunks

## Local e2e

1. Ensure Postgres has the `vector` extension available (Homebrew / Docker image).
2. Restart API (`AUTO_MIGRATE=true` applies `20260722_f04temp`).
3. Publish a `.txt` via Admin, or seed:

```bash
cd apps/api
python scripts/seed_f04temp_kb.py \
  --user-id "$NEXT_PUBLIC_DEV_USER_ID" \
  --host tenant-a.lxzxai.com \
  --base-url http://127.0.0.1:8000
```

4. In chat ask:「退货窗口是多少天？」— Agent should call `search_knowledge` and cite 30 天.

## Limits (intentional)

- PDF/Word/PPT full parsers deferred (upload `.txt` / `.md` for e2e)
- Hash embeddings ≠ production quality; toggle real QWen emb when needed
- Do not merge to `main` as “F04 done” without Spec `approved` + full Test Cases
