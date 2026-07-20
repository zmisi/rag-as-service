from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg://rag_app:change_me@localhost:5432/rag_service",
        alias="DATABASE_URL",
    )
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
