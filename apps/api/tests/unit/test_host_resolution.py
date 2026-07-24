"""Unit tests for public Host resolution / proxy secret."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from rag_api.api.dependencies.auth import resolve_public_host
from rag_api.config import Settings


def _settings(**kwargs: object) -> Settings:
    base = {
        "apex_host": "lxzxai.com",
        "proxy_shared_secret": "",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)  # type: ignore[return-value]


def test_prefer_public_host_over_spoofed_xfh() -> None:
    request = MagicMock()
    request.headers = {"host": "tenant-a.lxzxai.com"}
    host = resolve_public_host(
        request,
        host="tenant-a.lxzxai.com",
        x_forwarded_host="evil.lxzxai.com",
        settings=_settings(proxy_shared_secret="secret"),
    )
    assert host == "tenant-a.lxzxai.com"


def test_ignore_xfh_without_proxy_secret() -> None:
    request = MagicMock()
    request.headers = {"host": "api:8000", "x-forwarded-host": "tenant-a.lxzxai.com"}
    host = resolve_public_host(
        request,
        host="api:8000",
        x_forwarded_host="tenant-a.lxzxai.com",
        settings=_settings(proxy_shared_secret=""),
    )
    assert host == "api:8000"


def test_trust_xfh_with_matching_proxy_secret() -> None:
    request = MagicMock()
    request.headers.get = lambda key, default=None: {
        "host": "api:8000",
        "x-forwarded-host": "tenant-a.lxzxai.com",
        "X-Rag-Proxy-Secret": "s3cret",
        "x-rag-proxy-secret": "s3cret",
    }.get(key, default)
    host = resolve_public_host(
        request,
        host="api:8000",
        x_forwarded_host="tenant-a.lxzxai.com",
        settings=_settings(proxy_shared_secret="s3cret"),
    )
    assert host == "tenant-a.lxzxai.com"


def test_reject_xfh_with_wrong_proxy_secret() -> None:
    request = MagicMock()
    request.headers.get = lambda key, default=None: {
        "host": "api:8000",
        "X-Rag-Proxy-Secret": "wrong",
    }.get(key, default)
    host = resolve_public_host(
        request,
        host="api:8000",
        x_forwarded_host="tenant-a.lxzxai.com",
        settings=_settings(proxy_shared_secret="s3cret"),
    )
    assert host == "api:8000"
