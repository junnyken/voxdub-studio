"""Mini-spec V12 (docs/PLAN.md) — DubPipeline._resolve_background() nhánh
cloud rendering: dùng cloud khi khả dụng, fallback Demucs máy khi cloud lỗi
(đúng nguyên tắc "degrade trung thực"), và KHÔNG được nuốt PipelineCancelled
làm fallback nhầm khi người dùng hủy giữa lúc chờ job cloud.
"""
from __future__ import annotations

import wave

import pytest

from autodub.config import Settings
from autodub.pipeline import DubPipeline
from autodub.progress import PipelineCancelled


def write_wav(path: str, seconds: float = 0.2) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))


@pytest.fixture
def audio_path(tmp_path):
    path = str(tmp_path / "audio.wav")
    write_wav(path)
    return path


def test_uses_cloud_when_available(tmp_path, audio_path, monkeypatch):
    settings = Settings(cloud_render_enabled=True)
    pipeline = DubPipeline(settings)

    monkeypatch.setattr("autodub.cloud_render.is_available", lambda s: True)
    called = {}

    def fake_cloud(input_wav, output_dir, sample_rate=16000, channels=1, reporter=None):
        called["used"] = True
        return {"vocals": "/tmp/v.wav", "no_vocals": "/tmp/nv.wav"}
    monkeypatch.setattr("autodub.cloud_render.separate_vocals_cloud", fake_cloud)

    def fail_local(*a, **kw):
        raise AssertionError("không được chạy Demucs máy khi cloud thành công")
    monkeypatch.setattr("autodub.media.vocal_separator.separate_vocals", fail_local)

    bg_path, duck = pipeline._resolve_background(
        "demucs", -12.0, audio_path, str(tmp_path))
    assert called.get("used") is True
    assert bg_path == "/tmp/nv.wav"


def test_falls_back_to_local_when_cloud_errors(tmp_path, audio_path, monkeypatch):
    settings = Settings(cloud_render_enabled=True)
    pipeline = DubPipeline(settings)

    monkeypatch.setattr("autodub.cloud_render.is_available", lambda s: True)

    def failing_cloud(*a, **kw):
        raise RuntimeError("mất mạng giữa chừng")
    monkeypatch.setattr("autodub.cloud_render.separate_vocals_cloud", failing_cloud)

    called = {}

    def fake_local(input_wav, output_dir, sample_rate=16000, channels=1,
                   demucs_cache=None, cancel_event=None):
        called["used"] = True
        return {"vocals": "/tmp/v-local.wav", "no_vocals": "/tmp/nv-local.wav"}
    monkeypatch.setattr("autodub.media.vocal_separator.separate_vocals", fake_local)

    bg_path, duck = pipeline._resolve_background(
        "demucs", -12.0, audio_path, str(tmp_path))
    assert called.get("used") is True
    assert bg_path == "/tmp/nv-local.wav"


def test_cancellation_during_cloud_wait_is_not_swallowed(tmp_path, audio_path, monkeypatch):
    settings = Settings(cloud_render_enabled=True)
    pipeline = DubPipeline(settings)

    monkeypatch.setattr("autodub.cloud_render.is_available", lambda s: True)

    def cancelling_cloud(*a, **kw):
        raise PipelineCancelled("người dùng bấm Hủy")
    monkeypatch.setattr("autodub.cloud_render.separate_vocals_cloud", cancelling_cloud)

    def fail_local(*a, **kw):
        raise AssertionError("hủy pipeline không được rơi về Demucs máy")
    monkeypatch.setattr("autodub.media.vocal_separator.separate_vocals", fail_local)

    with pytest.raises(PipelineCancelled):
        pipeline._resolve_background("demucs", -12.0, audio_path, str(tmp_path))


def test_local_only_mode_never_touches_cloud_render(tmp_path, audio_path, monkeypatch):
    """cloud_render_enabled=False (mặc định) — is_available() False, nhánh
    cloud không được gọi tới dù có định nghĩa sẵn trong module."""
    settings = Settings(cloud_render_enabled=False)
    pipeline = DubPipeline(settings)

    def fail_cloud(*a, **kw):
        raise AssertionError("không được gọi cloud khi cloud_render_enabled=False")
    monkeypatch.setattr("autodub.cloud_render.separate_vocals_cloud", fail_cloud)

    def fake_local(input_wav, output_dir, sample_rate=16000, channels=1,
                   demucs_cache=None, cancel_event=None):
        return {"vocals": "/tmp/v.wav", "no_vocals": "/tmp/nv.wav"}
    monkeypatch.setattr("autodub.media.vocal_separator.separate_vocals", fake_local)

    bg_path, duck = pipeline._resolve_background(
        "demucs", -12.0, audio_path, str(tmp_path))
    assert bg_path == "/tmp/nv.wav"
