"""ID3 round-trip via mutagen."""

import struct
from pathlib import Path

from mutagen.id3 import ID3

from app.services.tts.id3_tagger import tag_mp3

# A minimal MP3 frame (1152 samples, MPEG1 Layer III, 32 kbps, 44.1 kHz, mono).
# This is a single all-zero frame; mutagen will accept it as MP3-shaped.
_MP3_HEADER = bytes.fromhex("fffb1064") + b"\x00" * 414


def _write_minimal_mp3(path: Path) -> None:
    path.write_bytes(_MP3_HEADER * 4)


def test_tag_round_trip(tmp_path):
    mp3 = tmp_path / "track.mp3"
    _write_minimal_mp3(mp3)
    cover = struct.pack("BBB", 0xFF, 0xD8, 0xFF) + b"COVERDATA"  # JPEG-ish header
    tag_mp3(
        mp3,
        title="Anchoring",
        artist="Daniel Kahneman",
        album="Thinking, Fast and Slow",
        track_n=1,
        track_total=47,
        cover_jpg=cover,
    )
    tags = ID3(str(mp3))
    assert tags["TIT2"].text[0] == "Anchoring"
    assert tags["TPE1"].text[0] == "Daniel Kahneman"
    assert tags["TALB"].text[0] == "Thinking, Fast and Slow"
    assert tags["TRCK"].text[0] == "01/47"
    apic = tags.getall("APIC")[0]
    assert apic.data == cover
    assert apic.mime == "image/jpeg"


def test_tag_overwrites_existing(tmp_path):
    mp3 = tmp_path / "track.mp3"
    _write_minimal_mp3(mp3)
    tag_mp3(mp3, title="A", artist="X", album="L", track_n=1, track_total=1)
    tag_mp3(mp3, title="B", artist="Y", album="M", track_n=2, track_total=3)
    tags = ID3(str(mp3))
    assert tags["TIT2"].text[0] == "B"
    assert tags["TPE1"].text[0] == "Y"
    assert tags["TRCK"].text[0] == "02/3"
