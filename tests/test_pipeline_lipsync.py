"""Mini-spec V32b (docs/PLAN.md, Phase G) — wiring "Đồng bộ khẩu hình" vào
`DubPipeline._apply_lipsync()`. Test gọi thẳng phương thức (cùng cách
`test_pipeline_diarization.py` đã làm) — không chạy pipeline.run() đầy đủ.
"""
from __future__ import annotations

import logging

from autodub.config import Settings
from autodub.media import lipsync as lipsync_module
from autodub.pipeline import DubPipeline


def _pipeline():
    return DubPipeline(Settings())


def test_disabled_by_default_never_touches_lipsync_module(monkeypatch):
    """DubRequest.lipsync=False (mặc định) -> _apply_lipsync() không được
    gọi từ luồng export thật; xác nhận ở đây mức thấp hơn: module lipsync
    không hề bị đụng khi tự gọi trực tiếp với settings mặc định KHÔNG cấu
    hình gì (available() phải False, không crash)."""
    settings = Settings()
    assert lipsync_module.available(settings) is False


def test_not_configured_degrades_honestly_keeps_original_video(caplog):
    pipeline = _pipeline()
    with caplog.at_level(logging.INFO, logger="autodub.pipeline"):
        video, state = pipeline._apply_lipsync(
            "/tmp/orig.mp4", "/tmp/dub_audio.wav", "/tmp/work", pipeline.settings)
    assert video == "/tmp/orig.mp4"
    assert state == {"status": "unavailable"}
    assert any("chưa cài" in r.message for r in caplog.records)


def test_blocked_by_consent_check_keeps_original_video_no_crash(monkeypatch, caplog):
    pipeline = _pipeline()
    monkeypatch.setattr(pipeline.settings, "lipsync_configured", lambda: True)
    monkeypatch.setattr(pipeline.settings, "lipsync_gpu_available", lambda: True)
    monkeypatch.setattr("autodub.media.video.probe_duration_s", lambda p: 10.0)

    def _boom(*a, **kw):
        raise lipsync_module.LipsyncBlocked(
            "consent_blocked", "Không phát hiện đủ khuôn mặt ở 5/100 frame")
    monkeypatch.setattr("autodub.media.lipsync.run", _boom)

    with caplog.at_level(logging.WARNING, logger="autodub.pipeline"):
        video, state = pipeline._apply_lipsync(
            "/tmp/orig.mp4", "/tmp/dub_audio.wav", "/tmp/work", pipeline.settings)
    assert video == "/tmp/orig.mp4"
    assert state["status"] == "blocked"
    assert state["reason"] == "consent_blocked"
    assert any("bị chặn" in r.message for r in caplog.records)


def test_failed_lipsync_keeps_original_video_no_crash(monkeypatch, caplog):
    pipeline = _pipeline()
    monkeypatch.setattr(pipeline.settings, "lipsync_configured", lambda: True)
    monkeypatch.setattr(pipeline.settings, "lipsync_gpu_available", lambda: True)
    monkeypatch.setattr("autodub.media.video.probe_duration_s", lambda p: 10.0)

    def _boom(*a, **kw):
        raise lipsync_module.LipsyncFailed("CUDA out of memory")
    monkeypatch.setattr("autodub.media.lipsync.run", _boom)

    with caplog.at_level(logging.WARNING, logger="autodub.pipeline"):
        video, state = pipeline._apply_lipsync(
            "/tmp/orig.mp4", "/tmp/dub_audio.wav", "/tmp/work", pipeline.settings)
    assert video == "/tmp/orig.mp4"
    assert state == {"status": "failed", "message": "CUDA out of memory"}
    assert any("lỗi" in r.message for r in caplog.records)


def test_success_returns_lipsynced_video_path(monkeypatch):
    pipeline = _pipeline()
    monkeypatch.setattr(pipeline.settings, "lipsync_configured", lambda: True)
    monkeypatch.setattr(pipeline.settings, "lipsync_gpu_available", lambda: True)
    monkeypatch.setattr("autodub.media.video.probe_duration_s", lambda p: 10.7)
    monkeypatch.setattr("autodub.media.lipsync.run",
                        lambda *a, **kw: "/tmp/work/lipsync/lipsync_watermarked.mp4")

    video, state = pipeline._apply_lipsync(
        "/tmp/orig.mp4", "/tmp/dub_audio.wav", "/tmp/work", pipeline.settings)
    assert video == "/tmp/work/lipsync/lipsync_watermarked.mp4"
    assert state == {"status": "applied"}


def test_quality_report_lipsync_field_empty_by_default():
    """Chưa bật lip-sync -> field `lipsync` trong quality_report.json rỗng
    (0 regression cho video không dùng tính năng này)."""
    from autodub.languages import get_target
    report = DubPipeline._build_quality_report(get_target("vi"), [], {}, Settings())
    assert report["lipsync"] == {}


def test_quality_report_lipsync_field_reflects_state():
    from autodub.languages import get_target
    report = DubPipeline._build_quality_report(
        get_target("vi"), [], {}, Settings(),
        lipsync_state={"status": "applied"})
    assert report["lipsync"] == {"status": "applied"}


def test_reset_per_run_state_clears_stale_data_from_previous_video():
    """Bug thật tìm được khi build V32b: pipeline dùng chung cho cả batch
    (batch.py::run_batch không tạo mới mỗi video), nhưng 3 field dưới đây
    trước đó chỉ khởi tạo 1 lần trong __init__ — video B không bật tính
    năng tương ứng vẫn lộ dữ liệu CŨ của video A liền trước. `_run_impl()`
    giờ gọi `_reset_per_run_state()` ngay đầu mỗi lượt (xem pipeline.py)."""
    pipeline = _pipeline()
    pipeline._last_lipsync_state = {"status": "applied"}
    pipeline._last_vocals_quality = {"clipped": True}
    pipeline._last_review_trace = [{"id": 1}]

    pipeline._reset_per_run_state()

    assert pipeline._last_lipsync_state == {}
    assert pipeline._last_vocals_quality == {}
    assert pipeline._last_review_trace == []
