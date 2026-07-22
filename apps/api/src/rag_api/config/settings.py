from functools import lru_cache
from getpass import getuser
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_API_ROOT = Path(__file__).resolve().parents[3]


def _resolve_repo_root(api_root: Path) -> Path:
    """Monorepo: repo root is parent of ``apps/``. Docker: API root is ``/app``."""
    if api_root.name == "api" and api_root.parent.name == "apps":
        return api_root.parent.parent
    return api_root


_REPO_ROOT = _resolve_repo_root(_API_ROOT)


def _env_files() -> tuple[Path, ...] | None:
    candidates = (_REPO_ROOT / ".env", _API_ROOT / ".env")
    existing = tuple(path for path in candidates if path.is_file())
    return existing or None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default=f"postgresql+psycopg://{getuser()}@127.0.0.1:5432/lxzxai_rag",
        alias="DATABASE_URL",
    )
    auto_migrate: bool = Field(default=True, alias="AUTO_MIGRATE")
    secret_key: str = Field(default="change_me", alias="SECRET_KEY")
    session_cookie_name: str = Field(default="pb_session", alias="SESSION_COOKIE_NAME")
    session_cookie_domain: str = Field(
        default=".lxzxai.com",
        alias="SESSION_COOKIE_DOMAIN",
    )
    session_ttl_days: int = Field(default=14, alias="SESSION_TTL_DAYS")
    session_slide_renew_threshold_days: int = Field(
        default=7,
        alias="SESSION_SLIDE_RENEW_THRESHOLD_DAYS",
    )
    apex_host: str = Field(default="lxzxai.com", alias="APEX_HOST")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    # Dev-only: accept X-Test-User-Id instead of F02 cookie auth (F05 UI).
    auth_stub_enabled: bool = Field(default=False, alias="AUTH_STUB_ENABLED")
    storage_root: Path = Field(
        default=_API_ROOT / "var" / "storage",
        alias="STORAGE_ROOT",
    )
    qwen_api_key: str = Field(default="", alias="QWEN_API_KEY")
    qwen_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="QWEN_BASE_URL",
    )
    qwen_model: str = Field(default="qwen-plus", alias="QWEN_MODEL")
    # F04: when true and QWEN_API_KEY set, use DashScope embeddings; else hashing.
    qwen_embedding_enabled: bool = Field(default=False, alias="QWEN_EMBEDDING_ENABLED")
    qwen_embedding_model: str = Field(
        default="text-embedding-v4",
        alias="QWEN_EMBEDDING_MODEL",
    )
    embedding_dim: int = Field(default=1024, alias="EMBEDDING_DIM")
    chunk_target_tokens: int = Field(default=800, alias="CHUNK_TARGET_TOKENS")
    chunk_overlap_tokens: int = Field(default=100, alias="CHUNK_OVERLAP_TOKENS")
    # F04: process index_job inline after publish (convenient for local e2e).
    index_sync_on_publish: bool = Field(default=True, alias="INDEX_SYNC_ON_PUBLISH")
    # F04 PDF PyMuPDF fast-path quality gate (conservative defaults).
    pdf_fast_min_chars: int = Field(default=80, alias="PDF_FAST_MIN_CHARS")
    pdf_fast_min_chars_per_page: float = Field(
        default=40.0,
        alias="PDF_FAST_MIN_CHARS_PER_PAGE",
    )
    pdf_fast_min_printable_ratio: float = Field(
        default=0.85,
        alias="PDF_FAST_MIN_PRINTABLE_RATIO",
    )
    pdf_fast_max_empty_page_ratio: float = Field(
        default=0.50,
        alias="PDF_FAST_MAX_EMPTY_PAGE_RATIO",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
