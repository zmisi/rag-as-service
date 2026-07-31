"""P3-F01 runtime path tests for installed backend images."""

from pathlib import Path

from rag_api.runtime_paths import get_api_root, get_repo_root


def test_p3_f01_runtime_root_uses_explicit_container_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """P3-F01-T06: an installed wheel resolves resources from RAG_API_ROOT."""
    monkeypatch.setenv("RAG_API_ROOT", str(tmp_path))

    assert get_api_root() == tmp_path.resolve()
    assert get_repo_root() == tmp_path.resolve()


def test_p3_f01_source_checkout_resolves_repository_root(monkeypatch) -> None:
    """P3-F01-T06: source checkouts continue to locate repository resources."""
    monkeypatch.delenv("RAG_API_ROOT", raising=False)

    api_root = get_api_root()

    assert api_root.name == "api"
    assert get_repo_root(api_root) == api_root.parent.parent
