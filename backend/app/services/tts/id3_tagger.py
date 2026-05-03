"""ID3v2.3 tagging for generated MP3s via mutagen."""

from __future__ import annotations

from pathlib import Path

from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, TRCK


def tag_mp3(
    mp3_path: Path | str,
    *,
    title: str,
    artist: str,
    album: str,
    track_n: int,
    track_total: int,
    cover_jpg: bytes | None = None,
) -> None:
    path = str(mp3_path)
    try:
        tags = ID3(path)
    except Exception:
        tags = ID3()

    tags.delall("TIT2")
    tags.delall("TPE1")
    tags.delall("TALB")
    tags.delall("TRCK")
    tags.delall("APIC")

    tags.add(TIT2(encoding=3, text=title))
    tags.add(TPE1(encoding=3, text=artist))
    tags.add(TALB(encoding=3, text=album))
    tags.add(TRCK(encoding=3, text=f"{track_n:02d}/{track_total}"))
    if cover_jpg:
        tags.add(APIC(encoding=0, mime="image/jpeg", type=3, desc="Cover", data=cover_jpg))

    tags.save(path, v2_version=3)
