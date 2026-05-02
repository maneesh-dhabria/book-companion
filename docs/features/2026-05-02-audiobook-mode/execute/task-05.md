# A5 — AudioFileRepository

**Spec refs:** FR-22, FR-23, FR-24, FR-26
**Files:**
- `backend/app/db/repositories/audio_file_repo.py`
- `backend/tests/unit/repositories/test_audio_file_repo.py`

## Decisions
- File path is deterministic: `audio/{book_id}/{content_type}_{content_id}__{voice}.mp3`. Same (book_id, ct, cid, voice) → same path → atomic overwrite via `os.replace(tmp, final)`.
- `upsert` writes to `*.tmp`, fsyncs, atomic-renames, then either updates the existing ORM row in-place or inserts a new one. Old file unlink only fires when path differs (paranoia for future voice/extension changes).
- Added `delete_orphans(book_id, surviving_section_ids)` ahead of A17 — cheap to include now.
- `delete_one` accepts optional `voice` so per-voice or all-voices delete is one method.

## Verification
- GREEN on first run: 6/6 (`upsert_creates`, `upsert_replaces`, `list_by_book`, `delete_all_for_book`, `delete_one`, `lookup`).

## Deviations
- Plan said "INSERT ... ON CONFLICT DO UPDATE"; used the cheaper find-and-update-or-add pattern since SQLAlchemy ORM gives row identity for free.
