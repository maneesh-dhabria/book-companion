"""Backup/restore service — SQLite file copy with retention."""

import re
import shutil
from datetime import datetime
from pathlib import Path

from app.exceptions import BookCompanionError

SQLITE_HEADER = b"SQLite format 3\x00"


class BackupError(BookCompanionError):
    """Backup/restore-related errors."""


class BackupService:
    def __init__(self, db_path: Path, backup_dir: Path, max_backups: int = 5):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def create_backup(self, output_path: str | None = None) -> Path:
        """Create a backup by copying the SQLite database file."""
        if not self.db_path.exists():
            raise BackupError(f"Database file not found: {self.db_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if output_path:
            backup_path = Path(output_path)
        else:
            backup_path = self.backup_dir / f"library-{timestamp}.db"

        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(self.db_path), str(backup_path))
        self._prune()
        return backup_path

    async def restore_backup(self, backup_file: str) -> None:
        """Restore database from a backup file."""
        backup_path = Path(backup_file)
        if not backup_path.exists():
            raise BackupError(f"Backup file not found: {backup_file}")

        # Validate it's a real SQLite database
        with open(backup_path, "rb") as f:
            header = f.read(16)
        if header[:16] != SQLITE_HEADER:
            raise BackupError(f"Invalid SQLite backup: {backup_file}")

        shutil.copy2(str(backup_path), str(self.db_path))

    def list_backups(self) -> list[dict]:
        """List backup files sorted by newest first."""
        if not self.backup_dir.exists():
            return []

        backups = []
        for f in sorted(self.backup_dir.glob("library-*.db"), reverse=True):
            stat = f.stat()
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

    def _prune(self) -> None:
        """Remove oldest backups beyond max_backups."""
        backups = sorted(self.backup_dir.glob("library-*.db"), key=lambda f: f.stat().st_mtime)
        while len(backups) > self.max_backups:
            oldest = backups.pop(0)
            oldest.unlink()
