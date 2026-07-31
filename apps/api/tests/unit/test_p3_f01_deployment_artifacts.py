"""P3-F01 deployment artifact checks."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]


def test_p3_f01_integration_compose_uses_prebuilt_images() -> None:
    """P3-F01-T06: integration deployment must not build or mount source."""
    compose = (
        _REPO_ROOT / "deploy" / "docker-compose.integration.yml"
    ).read_text(encoding="utf-8")

    assert "build:" not in compose
    assert "../apps/" not in compose
    assert "--reload" not in compose
    assert "rag-as-service-backend:${IMAGE_TAG:" in compose
    assert "rag-as-service-web:${IMAGE_TAG:" in compose
    assert "rag-as-service-db:${IMAGE_TAG:" in compose


def test_p3_f01_images_use_production_install_and_commands() -> None:
    """P3-F01-T06: server images use installed packages and production commands."""
    api_dockerfile = (_REPO_ROOT / "apps" / "api" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    web_dockerfile = (_REPO_ROOT / "apps" / "web" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "pip_retry -e ." not in api_dockerfile
    assert "FROM python:3.12-slim AS runtime" in api_dockerfile
    assert "RAG_API_ROOT=/app" in api_dockerfile
    assert "USER rag" in api_dockerfile
    assert "FROM dependencies AS builder" in web_dockerfile
    assert "FROM node:22-alpine AS runtime" in web_dockerfile
    assert 'CMD ["node", "server.js"]' in web_dockerfile


def test_p3_f01_runbook_documents_logs_and_rollback() -> None:
    """P3-F01-T06: runbook includes logs, rollback, secrets, and volume warnings."""
    runbook = (_REPO_ROOT / "deploy" / "integration.md").read_text(encoding="utf-8")
    gitignore = (_REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    upload_script = (
        _REPO_ROOT / "scripts" / "upload-integration-images.sh"
    ).read_text(encoding="utf-8")

    assert "检查日志" in runbook
    assert "更新与回滚" in runbook
    assert "upload-integration-images.sh" in runbook
    assert "不得提交真实密钥" in (
        _REPO_ROOT / "deploy" / ".env.integration.example"
    ).read_text(encoding="utf-8")
    assert "deploy/.env.integration" in gitignore
    assert "scripts/integration_env.conf" in gitignore
    assert 'source "$config_file"' in upload_script
    assert "sshpass -e ssh" in upload_script
    assert "sshpass -e scp" in upload_script
    assert "docker compose down -v" in runbook
