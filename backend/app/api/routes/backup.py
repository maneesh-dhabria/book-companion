"""Backup API endpoints — wraps BackupService for create, list, download, restore, delete."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_backup_service
from app.services.backup_service import BackupError, BackupService

router = APIRouter(prefix="/api/v1/backup", tags=["backup"])


@router.post("/create")
async def create_backup(
    backup_service: BackupService = Depends(get_backup_service),
):
    """Create a new database backup."""
    try:
        backup_path = await backup_service.create_backup()
    except BackupError as e:
        raise HTTPException(status_code=500, detail=str(e)) from None

    stat = backup_path.stat()
    return {
        "backup_id": backup_path.stem,
        "filename": backup_path.name,
        "size_bytes": stat.st_size,
        "created_at": None,
    }


@router.get("/list")
async def list_backups(
    backup_service: BackupService = Depends(get_backup_service),
):
    """List all available backups."""
    backups = backup_service.list_backups()
    return [
        {
            "backup_id": Path(b["filename"]).stem,
            "filename": b["filename"],
            "size_bytes": b["size_bytes"],
            "size_mb": b["size_mb"],
            "created_at": b.get("created"),
        }
        for b in backups
    ]


@router.get("/{backup_id}/download")
async def download_backup(
    backup_id: str,
    backup_service: BackupService = Depends(get_backup_service),
):
    """Download a backup file."""
    backup_path = backup_service.backup_dir / f"{backup_id}.sql"
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail=f"Backup not found: {backup_id}")
    return FileResponse(
        path=str(backup_path),
        filename=backup_path.name,
        media_type="application/sql",
    )


@router.post("/restore")
async def restore_backup(
    file: UploadFile,
    backup_service: BackupService = Depends(get_backup_service),
):
    """Restore database from an uploaded backup file."""
    temp_path = backup_service.backup_dir / f"restore_temp_{file.filename}"
    try:
        content = await file.read()
        temp_path.write_bytes(content)
        await backup_service.restore_backup(str(temp_path))
        return {"status": "restored", "filename": file.filename}
    except BackupError as e:
        raise HTTPException(status_code=500, detail=str(e)) from None
    finally:
        temp_path.unlink(missing_ok=True)


@router.delete("/{backup_id}", status_code=204)
async def delete_backup(
    backup_id: str,
    backup_service: BackupService = Depends(get_backup_service),
):
    """Delete a backup file."""
    backup_path = backup_service.backup_dir / f"{backup_id}.sql"
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail=f"Backup not found: {backup_id}")
    backup_path.unlink()
