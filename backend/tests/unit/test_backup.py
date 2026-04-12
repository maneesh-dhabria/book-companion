"""Tests for SQLite backup service."""

import sqlite3

import pytest

from app.services.backup_service import BackupService


@pytest.fixture
def backup_env(tmp_path):
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO test VALUES (1, 'original')")
    conn.commit()
    conn.close()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    return db_path, backup_dir


@pytest.mark.asyncio
async def test_create_backup_copies_db(backup_env):
    db_path, backup_dir = backup_env
    svc = BackupService(db_path=db_path, backup_dir=backup_dir, max_backups=5)
    result = await svc.create_backup()
    assert result.exists()
    assert result.suffix == ".db"
    # Verify backup is a valid SQLite DB with our test data
    conn = sqlite3.connect(str(result))
    rows = conn.execute("SELECT * FROM test").fetchall()
    assert rows == [(1, "original")]
    conn.close()


@pytest.mark.asyncio
async def test_prune_keeps_max_backups(backup_env):
    db_path, backup_dir = backup_env
    svc = BackupService(db_path=db_path, backup_dir=backup_dir, max_backups=2)
    # Use explicit unique filenames to avoid timestamp collision
    await svc.create_backup(str(backup_dir / "library-20260101_000001.db"))
    await svc.create_backup(str(backup_dir / "library-20260101_000002.db"))
    await svc.create_backup(str(backup_dir / "library-20260101_000003.db"))
    backups = svc.list_backups()
    assert len(backups) == 2


@pytest.mark.asyncio
async def test_restore_backup_overwrites_db(backup_env):
    db_path, backup_dir = backup_env
    svc = BackupService(db_path=db_path, backup_dir=backup_dir, max_backups=5)
    backup_path = await svc.create_backup()
    # Modify the original DB
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO test VALUES (2, 'modified')")
    conn.commit()
    conn.close()
    # Restore
    await svc.restore_backup(str(backup_path))
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT * FROM test").fetchall()
    assert rows == [(1, "original")]  # Only original data
    conn.close()


@pytest.mark.asyncio
async def test_restore_rejects_invalid_file(backup_env):
    db_path, backup_dir = backup_env
    svc = BackupService(db_path=db_path, backup_dir=backup_dir, max_backups=5)
    # Create a non-SQLite file
    bad_file = backup_dir / "bad.db"
    bad_file.write_text("not a database")
    from app.services.backup_service import BackupError

    with pytest.raises(BackupError, match="Invalid SQLite"):
        await svc.restore_backup(str(bad_file))


def test_list_backups_empty(tmp_path):
    svc = BackupService(db_path=tmp_path / "db.db", backup_dir=tmp_path / "empty")
    backups = svc.list_backups()
    assert backups == []
