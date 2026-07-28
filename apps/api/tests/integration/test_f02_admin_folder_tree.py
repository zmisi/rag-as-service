"""P2-F02 admin folder tree integration tests."""

from __future__ import annotations

import pytest
from sqlalchemy import delete

from rag_api.db.models import Document, Folder
from tests.helpers import tenant_host_headers

HEADERS_A = tenant_host_headers("pytest-a")
HEADERS_B = tenant_host_headers("pytest-b")


@pytest.fixture(autouse=True)
def wipe_folders_and_docs(db):
    db.execute(delete(Document))
    db.execute(delete(Folder))
    db.commit()


def _create_folder(client, name: str, parent_id: str | None = None) -> str:
    payload = {"name": name}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    r = client.post("/v1/folders", headers=HEADERS_A, json=payload)
    assert r.status_code == 201, r.text
    return r.json()["folder_id"]


def _create_doc(client) -> str:
    r = client.post("/v1/documents", headers=HEADERS_A)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _list_layer(client, folder_id: str | None = None, headers=HEADERS_A):
    q = f"?folder_id={folder_id}" if folder_id else ""
    r = client.get(f"/v1/folders/list{q}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_p2_f02_t01_create_root_folder_visible_in_tree(client_a):
    folder_id = _create_folder(client_a, "A")

    r = client_a.get("/v1/folders/tree", headers=HEADERS_A)
    assert r.status_code == 200, r.text
    body = r.json()
    assert any(node["folder_id"] == folder_id and node["name"] == "A" for node in body)


def test_p2_f02_t02_duplicate_name_under_same_parent_rejected(client_a):
    _create_folder(client_a, "A")
    r = client_a.post("/v1/folders", headers=HEADERS_A, json={"name": "a"})
    assert r.status_code == 409, r.text


def test_p2_f02_t03_move_document_from_root_into_folder(client_a):
    folder_id = _create_folder(client_a, "A")
    doc_id = _create_doc(client_a)

    r = client_a.patch(
        f"/v1/folders/documents/{doc_id}/move",
        headers=HEADERS_A,
        json={"folder_id": folder_id},
    )
    assert r.status_code == 200, r.text

    layer_a = _list_layer(client_a, folder_id)
    assert any(doc["doc_id"] == doc_id for doc in layer_a["documents"])

    root_layer = _list_layer(client_a)
    assert all(doc["doc_id"] != doc_id for doc in root_layer["documents"])


def test_p2_f02_t04_delete_non_empty_folder_rejected(client_a):
    folder_id = _create_folder(client_a, "A")
    doc_id = _create_doc(client_a)
    moved = client_a.patch(
        f"/v1/folders/documents/{doc_id}/move",
        headers=HEADERS_A,
        json={"folder_id": folder_id},
    )
    assert moved.status_code == 200, moved.text

    r = client_a.delete(f"/v1/folders/{folder_id}", headers=HEADERS_A)
    assert r.status_code == 409, r.text

    tree = client_a.get("/v1/folders/tree", headers=HEADERS_A).json()
    assert any(node["folder_id"] == folder_id for node in tree)


def test_p2_f02_t05_delete_empty_folder_success(client_a):
    folder_id = _create_folder(client_a, "A")
    r = client_a.delete(f"/v1/folders/{folder_id}", headers=HEADERS_A)
    assert r.status_code == 204, r.text

    tree = client_a.get("/v1/folders/tree", headers=HEADERS_A).json()
    assert all(node["folder_id"] != folder_id for node in tree)


def test_p2_f02_t06_depth_limit_10(client_a):
    parent_id = None
    for idx in range(10):
        parent_id = _create_folder(client_a, f"L{idx + 1}", parent_id)
    r = client_a.post(
        "/v1/folders",
        headers=HEADERS_A,
        json={"name": "TooDeep", "parent_id": parent_id},
    )
    assert r.status_code == 422, r.text


def test_p2_f02_t07_reject_cycle_move(client_a):
    folder_a = _create_folder(client_a, "A")
    folder_b = _create_folder(client_a, "B", folder_a)

    r = client_a.patch(
        f"/v1/folders/{folder_a}/move",
        headers=HEADERS_A,
        json={"parent_id": folder_b},
    )
    assert r.status_code == 422, r.text

    tree = client_a.get("/v1/folders/tree", headers=HEADERS_A).json()
    node_a = next(node for node in tree if node["folder_id"] == folder_a)
    assert node_a["parent_id"] is None


def test_p2_f02_t08_cross_tenant_folder_read_forbidden_or_not_found(client_a, switch_to_b):
    folder_id = _create_folder(client_a, "A")
    client_b = switch_to_b()
    r = client_b.get(f"/v1/folders/list?folder_id={folder_id}", headers=HEADERS_B)
    assert r.status_code in (403, 404), r.text
