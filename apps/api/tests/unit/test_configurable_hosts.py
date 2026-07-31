from pathlib import Path

from rag_api.api.dependencies.auth import is_public_hostname, parse_subdomain
from rag_api.config.settings import Settings

_REPO_ROOT = Path(__file__).resolve().parents[4]


def test_p3_f01_t07_custom_apex_host_controls_host_parsing() -> None:
    settings = Settings(APEX_HOST="lxzai.dev.com")

    assert is_public_hostname("lxzai.dev.com:3000", settings)
    assert is_public_hostname("tenant-a.lxzai.dev.com:3000", settings)
    assert parse_subdomain(
        "tenant-a.lxzai.dev.com:3000",
        settings.apex_host,
    ) == "tenant-a"
    assert parse_subdomain("tenant-a.lxzxai.com", settings.apex_host) is None


def test_p3_f01_t07_rejects_nested_or_invalid_tenant_labels() -> None:
    apex_host = "lxzai.dev.com"

    assert parse_subdomain(apex_host, apex_host) is None
    assert parse_subdomain(f"a.b.{apex_host}", apex_host) is None
    assert parse_subdomain(f"-tenant.{apex_host}", apex_host) is None


def test_p3_f01_t07_web_and_compose_receive_configured_apex_host() -> None:
    hosts_source = (_REPO_ROOT / "apps/web/lib/hosts.ts").read_text(encoding="utf-8")
    api_source = (_REPO_ROOT / "apps/web/lib/api.ts").read_text(encoding="utf-8")
    compose = (_REPO_ROOT / "deploy/docker-compose.yml").read_text(encoding="utf-8")

    assert "process.env.APEX_HOST" in hosts_source
    assert "process.env.NEXT_PUBLIC_APEX_HOST" in api_source
    assert "APEX_HOST: ${APEX_HOST:-lxzxai.com}" in compose
    assert "NEXT_PUBLIC_APEX_HOST: ${APEX_HOST:-lxzxai.com}" in compose
