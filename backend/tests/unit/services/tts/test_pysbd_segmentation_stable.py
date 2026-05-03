"""pysbd version-drift guard — corpus + expected segmentation locked at 0.3.4."""

import json
from pathlib import Path

import pysbd

FIXTURE = (
    Path(__file__).parent.parent.parent.parent / "fixtures" / "tts" / "segmentation_expected.json"
)


def test_pysbd_corpus_stable():
    payload = json.loads(FIXTURE.read_text())
    seg = pysbd.Segmenter(language="en", clean=False)
    actual = seg.segment(payload["corpus"])
    assert actual == payload["expected"], (
        "pysbd output drift detected — bump SANITIZER_VERSION + refresh "
        "tests/fixtures/tts/segmentation_expected.json after manual review."
    )
