"""Integration tests for backup API endpoints.

These tests require a pg_dump version >= 16 (matching the server) and
a running PostgreSQL test database. They are skipped if pg_dump is
unavailable or has a version mismatch.
"""

import re
import shutil
import subprocess

import pytest


def _pg_dump_compatible() -> bool:
    """Check if local pg_dump version is compatible with the server (v16+)."""
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        return False
    try:
        result = subprocess.run([pg_dump, "--version"], capture_output=True, text=True)
        match = re.search(r"(\d+)\.", result.stdout)
        if match and int(match.group(1)) >= 16:
            return True
    except Exception:
        pass
    return False


pytestmark = pytest.mark.skipif(
    not _pg_dump_compatible(),
    reason="pg_dump >= 16 not available (version mismatch with server)",
)


@pytest.mark.asyncio
async def test_create_backup(client):
    resp = await client.post("/api/v1/backup/create")
    assert resp.status_code == 200
    data = resp.json()
    assert "backup_id" in data
    assert "filename" in data
    assert data["size_bytes"] > 0


@pytest.mark.asyncio
async def test_list_backups(client):
    await client.post("/api/v1/backup/create")
    resp = await client.get("/api/v1/backup/list")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "filename" in data[0]
    assert "size_bytes" in data[0]


@pytest.mark.asyncio
async def test_download_backup(client):
    create_resp = await client.post("/api/v1/backup/create")
    backup_id = create_resp.json()["backup_id"]
    resp = await client.get(f"/api/v1/backup/{backup_id}/download")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_backup(client):
    create_resp = await client.post("/api/v1/backup/create")
    backup_id = create_resp.json()["backup_id"]
    resp = await client.delete(f"/api/v1/backup/{backup_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_nonexistent_backup(client):
    resp = await client.delete("/api/v1/backup/nonexistent_file")
    assert resp.status_code == 404
