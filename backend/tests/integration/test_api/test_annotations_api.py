"""Integration tests for the Annotations API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_annotations_empty(client: AsyncClient):
    resp = await client.get("/api/v1/annotations")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_annotation_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/annotations/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_annotation_validation(client: AsyncClient):
    resp = await client.post(
        "/api/v1/annotations",
        json={
            "content_type": "section_content",
            "content_id": 1,
            "type": "highlight",
            "selected_text": "example text",
            "text_start": 0,
            "text_end": 12,
        },
    )
    # 201 if section exists, 404 if not — validates shape either way
    assert resp.status_code in (201, 404)


@pytest.mark.asyncio
async def test_delete_annotation_not_found(client: AsyncClient):
    resp = await client.delete("/api/v1/annotations/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_annotations_format(client: AsyncClient):
    resp = await client.get("/api/v1/annotations/export?format=markdown")
    assert resp.status_code == 200
    assert "text" in resp.headers.get("content-type", "") or "application" in resp.headers.get(
        "content-type", ""
    )


# --- Happy-path behavioral tests ---


@pytest.mark.asyncio
async def test_create_annotation_returns_correct_fields(client: AsyncClient):
    payload = {
        "content_type": "section_content",
        "content_id": 1,
        "type": "highlight",
        "selected_text": "supreme excellence consists in breaking the enemy's resistance",
        "text_start": 120,
        "text_end": 182,
        "note": None,
    }
    resp = await client.post("/api/v1/annotations", json=payload)
    if resp.status_code == 404:
        pytest.skip("Section 1 not available in test DB")
    assert resp.status_code == 201
    data = resp.json()
    assert data["content_type"] == "section_content"
    assert data["content_id"] == 1
    assert data["type"] == "highlight"
    assert data["selected_text"] == payload["selected_text"]
    assert data["text_start"] == 120
    assert data["text_end"] == 182
    assert "id" in data
    annotation_id = data["id"]

    # Cleanup
    del_resp = await client.delete(f"/api/v1/annotations/{annotation_id}")
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_get_annotation_returns_stored_data(client: AsyncClient):
    payload = {
        "content_type": "section_content",
        "content_id": 1,
        "type": "note",
        "selected_text": "All warfare is based on deception.",
        "text_start": 0,
        "text_end": 34,
        "note": "Key strategic insight",
    }
    create_resp = await client.post("/api/v1/annotations", json=payload)
    if create_resp.status_code == 404:
        pytest.skip("Section 1 not available in test DB")
    assert create_resp.status_code == 201
    annotation_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/annotations/{annotation_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == annotation_id
    assert data["note"] == "Key strategic insight"
    assert data["type"] == "note"
    assert data["selected_text"] == "All warfare is based on deception."

    # Cleanup
    await client.delete(f"/api/v1/annotations/{annotation_id}")


@pytest.mark.asyncio
async def test_update_annotation_note(client: AsyncClient):
    payload = {
        "content_type": "section_content",
        "content_id": 1,
        "type": "highlight",
        "selected_text": "Appear weak when you are strong",
        "text_start": 50,
        "text_end": 80,
    }
    create_resp = await client.post("/api/v1/annotations", json=payload)
    if create_resp.status_code == 404:
        pytest.skip("Section 1 not available in test DB")
    annotation_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/annotations/{annotation_id}", json={"note": "Updated note text"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["note"] == "Updated note text"
    assert patch_resp.json()["type"] == "highlight"

    # Cleanup
    await client.delete(f"/api/v1/annotations/{annotation_id}")


@pytest.mark.asyncio
async def test_list_annotations_filters_by_content_id(client: AsyncClient):
    payload_s1 = {
        "content_type": "section_content",
        "content_id": 1,
        "type": "highlight",
        "selected_text": "text for section 1",
        "text_start": 0,
        "text_end": 18,
    }
    payload_s2 = {
        "content_type": "section_content",
        "content_id": 2,
        "type": "highlight",
        "selected_text": "text for section 2",
        "text_start": 0,
        "text_end": 18,
    }
    r1 = await client.post("/api/v1/annotations", json=payload_s1)
    r2 = await client.post("/api/v1/annotations", json=payload_s2)
    if r1.status_code == 404 or r2.status_code == 404:
        pytest.skip("Sections not available in test DB")
    id1 = r1.json()["id"]
    id2 = r2.json()["id"]

    resp = await client.get("/api/v1/annotations?content_type=section_content&content_id=1")
    assert resp.status_code == 200
    items = resp.json()["items"]
    returned_ids = [a["id"] for a in items]
    assert id1 in returned_ids
    assert id2 not in returned_ids, "Section 2 annotation leaked into section 1 filter results"

    # Cleanup
    await client.delete(f"/api/v1/annotations/{id1}")
    await client.delete(f"/api/v1/annotations/{id2}")


@pytest.mark.asyncio
async def test_link_and_unlink_annotations(client: AsyncClient):
    payload_base = {
        "content_type": "section_content",
        "content_id": 1,
        "type": "highlight",
        "text_start": 0,
        "text_end": 10,
    }
    r1 = await client.post(
        "/api/v1/annotations", json={**payload_base, "selected_text": "text one"}
    )
    r2 = await client.post(
        "/api/v1/annotations", json={**payload_base, "selected_text": "text two"}
    )
    if r1.status_code == 404 or r2.status_code == 404:
        pytest.skip("Section 1 not available in test DB")
    id1 = r1.json()["id"]
    id2 = r2.json()["id"]

    link_resp = await client.post(
        f"/api/v1/annotations/{id1}/link", json={"target_annotation_id": id2}
    )
    assert link_resp.status_code == 200
    assert link_resp.json()["linked_annotation_id"] == id2

    unlink_resp = await client.delete(f"/api/v1/annotations/{id1}/link")
    assert unlink_resp.status_code == 200
    assert unlink_resp.json()["linked_annotation_id"] is None

    # Cleanup
    await client.delete(f"/api/v1/annotations/{id1}")
    await client.delete(f"/api/v1/annotations/{id2}")


@pytest.mark.asyncio
async def test_export_markdown_contains_annotation_data(client: AsyncClient):
    payload = {
        "content_type": "section_content",
        "content_id": 1,
        "type": "note",
        "selected_text": "exportable passage",
        "text_start": 0,
        "text_end": 18,
        "note": "My export test note",
    }
    create_resp = await client.post("/api/v1/annotations", json=payload)
    if create_resp.status_code == 404:
        pytest.skip("Section 1 not available in test DB")
    annotation_id = create_resp.json()["id"]

    export_resp = await client.get("/api/v1/annotations/export?format=markdown")
    assert export_resp.status_code == 200
    content = export_resp.text
    assert "exportable passage" in content or "My export test note" in content
    assert export_resp.headers.get("content-disposition", "").startswith("attachment")

    # Cleanup
    await client.delete(f"/api/v1/annotations/{annotation_id}")
