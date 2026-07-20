from functools import lru_cache
from getpass import getuser
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_API_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT = _API_ROOT.parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _API_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Local Homebrew Postgres usually authenticates as the OS user (no password).
    database_url: str = (
        f"postgresql+psycopg://{getuser()}@127.0.0.1:5432/lxzxai_rag"
    )
    # When True (default), run `alembic upgrade head` during app startup.
    auto_migrate: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
