"""Mini-spec V32b (docs/PLAN.md, Phase G) — `autodub/media/lipsync.py`
(gọi worker `.venv-lipsync` qua subprocess). KHÔNG có GPU/MuseTalk cài trong
môi trường test (đúng thực tế CI/sandbox — xem docs/TEST_LOG.md mục V32a) —
mọi test dưới đây mock `subprocess.Popen`, không chạy MuseTalk thật. Đường
"chạy thật trên GPU thật" phải live-verify riêng bởi chủ dự án, xem
scripts/setup_lipsync.py.
"""
from __future__ import annotations

import json
import subprocess as sp
from unittest import mock

import pytest

from autodub.config import Settings
from autodub.media import lipsync


def _settings(**overrides):
    s = Settings()
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _configured_settings():
    s = _settings()
    s.lipsync_configured = lambda: True
    s.lipsync_gpu_available = lambda: True
    s.lipsync_venv_python_path = lambda: "/fake/.venv-lipsync/bin/python"
    return s


def test_available_false_when_not_configured():
    s = _settings()
    s.lipsync_configured = lambda: False
    s.lipsync_gpu_available = lambda: True
    assert lipsync.available(s) is False


def test_available_false_when_no_gpu():
    s = _settings()
    s.lipsync_configured = lambda: True
    s.lipsync_gpu_available = lambda: False
    assert lipsync.available(s) is False


def test_available_true_when_both():
    assert lipsync.available(_configured_settings()) is True


def test_check_duration_none_never_blocks():
    s = _settings(lipsync_max_duration_s=12.0)
    lipsync.check_duration(s, None)   # không raise


def test_check_duration_under_cap_ok():
    s = _settings(lipsync_max_duration_s=12.0)
    lipsync.check_duration(s, 10.7)   # không raise


def test_check_duration_over_cap_blocks():
    s = _settings(lipsync_max_duration_s=12.0)
    with pytest.raises(lipsync.LipsyncBlocked) as exc:
        lipsync.check_duration(s, 30.0)
    assert exc.value.reason == "duration_exceeded"


def test_run_raises_unavailable_when_not_configured():
    s = _settings()
    s.lipsync_configured = lambda: False
    s.lipsync_gpu_available = lambda: False
    with pytest.raises(lipsync.LipsyncUnavailable):
        lipsync.run("v.mp4", "a.wav", "out", s)


def test_run_blocks_on_duration_before_spawning_subprocess():
    s = _configured_settings()
    s.lipsync_max_duration_s = 12.0
    with mock.patch("autodub.media.lipsync.subprocess.Popen") as popen:
        with pytest.raises(lipsync.LipsyncBlocked) as exc:
            lipsync.run("v.mp4", "a.wav", "out", s, video_duration_s=99.0)
        popen.assert_not_called()
    assert exc.value.reason == "duration_exceeded"


def _fake_proc(stdout_lines: list[dict], returncode: int = 0):
    proc = mock.Mock()
    stdout = "\n".join(json.dumps(ln) for ln in stdout_lines)
    proc.communicate.return_value = (stdout, "")
    proc.returncode = returncode
    return proc


def test_run_success_returns_output_video_and_manages_atexit():
    s = _configured_settings()
    done = {
        "stage": "done", "ok": True, "output_video": "/tmp/out/lipsync_watermarked.mp4",
        "elapsed_seconds": 42.0, "vram_peak_mb": 3900,
        "consent_check": {"ok": True, "total_frames": 268, "no_face_frames": 0, "no_face_ratio": 0.0},
    }
    fake_proc = _fake_proc([
        {"stage": "consent_check", "ok": True, "total_frames": 268, "no_face_frames": 0, "no_face_ratio": 0.0},
        done,
    ])
    with mock.patch("autodub.media.lipsync.subprocess.Popen", return_value=fake_proc), \
         mock.patch("autodub.media.lipsync.atexit.register") as reg, \
         mock.patch("autodub.media.lipsync.atexit.unregister") as unreg, \
         mock.patch("autodub.media.lipsync.os.path.isfile", return_value=True):
        result = lipsync.run("v.mp4", "a.wav", "out", s, video_duration_s=10.7)
    assert result == "/tmp/out/lipsync_watermarked.mp4"
    reg.assert_called_once_with(fake_proc.kill)
    unreg.assert_called_once_with(fake_proc.kill)


def test_run_consent_blocked_raises_lipsync_blocked():
    s = _configured_settings()
    fake_proc = _fake_proc([
        {"stage": "consent_check", "ok": True, "total_frames": 100, "no_face_frames": 12, "no_face_ratio": 0.12},
        {"stage": "done", "ok": False, "reason": "consent_blocked",
         "consent_check": {"total_frames": 100, "no_face_frames": 12, "no_face_ratio": 0.12}},
    ])
    with mock.patch("autodub.media.lipsync.subprocess.Popen", return_value=fake_proc):
        with pytest.raises(lipsync.LipsyncBlocked) as exc:
            lipsync.run("v.mp4", "a.wav", "out", s)
    assert exc.value.reason == "consent_blocked"
    assert "12/100" in str(exc.value)


def test_run_inference_failed_raises_lipsync_failed():
    s = _configured_settings()
    fake_proc = _fake_proc([
        {"stage": "consent_check", "ok": True, "total_frames": 10, "no_face_frames": 0, "no_face_ratio": 0.0},
        {"stage": "done", "ok": False, "reason": "inference_failed", "output_tail": "CUDA out of memory"},
    ])
    with mock.patch("autodub.media.lipsync.subprocess.Popen", return_value=fake_proc):
        with pytest.raises(lipsync.LipsyncFailed, match="inference_failed"):
            lipsync.run("v.mp4", "a.wav", "out", s)


def test_run_no_done_line_raises_lipsync_failed():
    s = _configured_settings()
    fake_proc = mock.Mock()
    fake_proc.communicate.return_value = ("not json at all\n", "")
    fake_proc.returncode = 1
    with mock.patch("autodub.media.lipsync.subprocess.Popen", return_value=fake_proc):
        with pytest.raises(lipsync.LipsyncFailed):
            lipsync.run("v.mp4", "a.wav", "out", s)


def test_run_success_but_missing_output_file_raises_failed():
    s = _configured_settings()
    fake_proc = _fake_proc([
        {"stage": "done", "ok": True, "output_video": "/tmp/does_not_exist_ever.mp4",
         "elapsed_seconds": 1.0, "vram_peak_mb": 100},
    ])
    with mock.patch("autodub.media.lipsync.subprocess.Popen", return_value=fake_proc), \
         mock.patch("autodub.media.lipsync.os.path.isfile", return_value=False):
        with pytest.raises(lipsync.LipsyncFailed, match="không thấy file"):
            lipsync.run("v.mp4", "a.wav", "out", s)


def test_run_timeout_kills_process_and_raises_failed():
    fake_proc = mock.Mock()
    fake_proc.communicate.side_effect = sp.TimeoutExpired("cmd", 3600)
    s = _configured_settings()
    with mock.patch("autodub.media.lipsync.subprocess.Popen", return_value=fake_proc):
        with pytest.raises(lipsync.LipsyncFailed, match="quá"):
            lipsync.run("v.mp4", "a.wav", "out", s)
    fake_proc.kill.assert_called_once()
    fake_proc.wait.assert_called_once()
