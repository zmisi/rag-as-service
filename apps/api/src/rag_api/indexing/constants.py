"""F04 indexing constants (shared embedding dim with pgvector column)."""

CHUNK_TARGET_TOKENS = 800
CHUNK_OVERLAP_TOKENS = 100
# Approx chars per token for Phase-1 char-budget chunking (CJK-friendly).
CHARS_PER_TOKEN = 2

EMBEDDING_DIM = 1024
# DashScope text-embedding-v4 default dim is 1024 (also supports 2048/1536/…).
QWEN_EMBEDDING_MODEL = "text-embedding-v4"
