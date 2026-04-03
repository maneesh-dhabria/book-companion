"""Backup/restore service -- pg_dump/pg_restore via subprocess."""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from app.config import Settings
from app.exceptions import BookCompanionError

DEFAULT_BACKUP_DIR = os.path.expanduser("~/.config/bookcompanion/backups")


class BackupError(BookCompanionError):
    """Backup/restore-related errors."""


class BackupService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.backup_dir = Path(DEFAULT_BACKUP_DIR)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _parse_db_url(self) -> dict:
        """Parse the async database URL into pg_dump-compatible components."""
        url = self.settings.database.url
        # Convert asyncpg URL to standard postgres URL for parsing
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        parsed = urlparse(url)
        return {
            "host": parsed.hostname or "localhost",
            "port": str(parsed.port or 5432),
            "database": parsed.path.lstrip("/") if parsed.path else "bookcompanion",
            "username": parsed.username or "bookcompanion",
            "password": parsed.password or "bookcompanion",
        }

    async def create_backup(self, output_path: str | None = None) -> Path:
        """Create a database backup using pg_dump."""
        db = self._parse_db_url()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bookcompanion_backup_{timestamp}.sql"

        if output_path:
            backup_path = Path(output_path)
        else:
            backup_path = self.backup_dir / filename

        backup_path.parent.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["PGPASSWORD"] = db["password"]

        cmd = [
            "pg_dump",
            "-h",
            db["host"],
            "-p",
            db["port"],
            "-U",
            db["username"],
            "-d",
            db["database"],
            "-F",
            "p",  # Plain-text SQL format
            "-f",
            str(backup_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode().strip() if stderr else "Unknown error"
            raise BackupError(f"pg_dump failed (exit {proc.returncode}): {error_msg}")

        return backup_path

    async def restore_backup(self, backup_file: str) -> None:
        """Restore a database from a backup file using psql."""
        backup_path = Path(backup_file)
        if not backup_path.exists():
            raise BackupError(f"Backup file not found: {backup_file}")

        db = self._parse_db_url()
        env = os.environ.copy()
        env["PGPASSWORD"] = db["password"]

        cmd = [
            "psql",
            "-h",
            db["host"],
            "-p",
            db["port"],
            "-U",
            db["username"],
            "-d",
            db["database"],
            "-f",
            str(backup_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode().strip() if stderr else "Unknown error"
            raise BackupError(f"psql restore failed (exit {proc.returncode}): {error_msg}")

    def list_backups(self) -> list[dict]:
        """List backup files in the default backup directory."""
        if not self.backup_dir.exists():
            return []

        backups = []
        for f in sorted(self.backup_dir.glob("bookcompanion_backup_*.sql"), reverse=True):
            stat = f.stat()
            # Extract timestamp from filename
            match = re.search(r"(\d{8}_\d{6})", f.name)
            created = None
            if match:
                try:
                    created = datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
                except ValueError:
                    pass

            backups.append(
                {
                    "path": str(f),
                    "filename": f.name,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created": created.isoformat() if created else None,
                }
            )
        return backups
