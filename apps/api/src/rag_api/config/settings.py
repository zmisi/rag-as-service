from functools import lru_cache
from getpass import getuser
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_API_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT = _API_ROOT.parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _API_ROOT / ".env"),
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
    apex_host: str = Field(default="lxzxai.com", alias="APEX_HOST")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")


@lru_cache
def get_settings() -> Settings:
    return Settings()
