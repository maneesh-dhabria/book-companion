"""TTSProvider ABC + dataclass shape tests."""

import pytest

from app.services.tts.provider import (
    FfmpegEncodeError,
    KokoroModelDownloadError,
    SynthesisResult,
    TTSProvider,
    VoiceInfo,
)


def test_synthesis_result_shape():
    r = SynthesisResult(audio_bytes=b"ID3", sample_rate=24000, sentence_offsets=[0.0, 4.2])
    assert r.audio_bytes == b"ID3"
    assert r.sample_rate == 24000
    assert r.sentence_offsets == [0.0, 4.2]


def test_voice_info_default_gender():
    v = VoiceInfo(name="af_sarah", language="en")
    assert v.gender is None


def test_provider_abc_cannot_instantiate():
    with pytest.raises(TypeError):
        TTSProvider()


class _Fake(TTSProvider):
    name = "fake"

    def synthesize(self, text, voice, speed=1.0):
        return SynthesisResult(audio_bytes=b"FAKE", sample_rate=24000, sentence_offsets=[0.0])

    def list_voices(self):
        return [VoiceInfo(name="fake_v1", language="en")]


def test_concrete_subclass_works():
    p = _Fake()
    assert p.name == "fake"
    assert p.synthesize("hi", "fake_v1").audio_bytes == b"FAKE"
    assert p.list_voices()[0].name == "fake_v1"


def test_terminate_default_is_noop():
    _Fake().terminate()


def test_kokoro_model_download_error_carries_retry_hint():
    e = KokoroModelDownloadError("net down", retry_after_seconds=30)
    assert e.retry_after_seconds == 30


def test_ffmpeg_encode_error_carries_stderr_tail():
    e = FfmpegEncodeError("bad", stderr_tail="lame: error")
    assert e.stderr_tail == "lame: error"
