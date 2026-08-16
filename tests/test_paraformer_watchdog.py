"""Mini-spec V24 (docs/PLAN.md, Phase F, đợt 2) — watchdog áp dụng cho
``transcribe_paraformer()`` (autodub/speech/paraformer_transcriber.py).

Worker giả THẬT (không mock ``Popen``) — không có bước "ready" riêng, phát
thẳng segment JSON qua stdout khi khởi động (đúng giao thức worker thật).
"""
from __future__ import annotations

import sys
import textwrap

import pytest

from autodub.config import Settings
from autodub.speech import paraformer_transcriber as pf_module


def _fake_worker(tmp_path, body: str) -> str:
    path = tmp_path / "fake_paraformer_worker.py"
    path.write_text("import json, sys\n" + textwrap.dedent(body), encoding="utf-8")
    return str(path)


def _settings(monkeypatch):
    settings = Settings()
    monkeypatch.setattr(settings, "asr_venv_python_path", lambda: sys.executable)
    monkeypatch.setattr(settings, "paraformer_model_dir_path", lambda: "/tmp/fake-model")
    return settings


def test_worker_responds_normally_still_works_through_watchdog(monkeypatch, tmp_path):
    worker = _fake_worker(tmp_path, body="""
        print(json.dumps({"seg": True, "text": "ni hao", "start": 0.0, "end": 1.0}),
              flush=True)
        print(json.dumps({"done": True}), flush=True)
    """)
    monkeypatch.setattr(pf_module, "_WORKER_SCRIPT", worker)
    settings = _settings(monkeypatch)

    segments = pf_module.transcribe_paraformer("/tmp/fake.wav", settings)
    assert len(segments) == 1
    assert segments[0]["text"] == "ni hao"


def test_worker_hangs_immediately_raises_within_bounded_time(monkeypatch, tmp_path):
    """Bug thật đã audit: worker treo NGAY từ đầu (không phát dòng nào) ->
    trước khi vá, pipeline treo vô thời hạn."""
    monkeypatch.setattr(pf_module, "_PARAFORMER_SEGMENT_TIMEOUT_S", 0.3)
    path = tmp_path / "fake_paraformer_worker.py"
    path.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    monkeypatch.setattr(pf_module, "_WORKER_SCRIPT", str(path))
    settings = _settings(monkeypatch)

    with pytest.raises(RuntimeError, match="không phản hồi"):
        pf_module.transcribe_paraformer("/tmp/fake.wav", settings)


def test_worker_hangs_mid_transcription_raises_within_bounded_time(monkeypatch, tmp_path):
    monkeypatch.setattr(pf_module, "_PARAFORMER_SEGMENT_TIMEOUT_S", 0.3)
    worker = _fake_worker(tmp_path, body="""
        import time
        print(json.dumps({"seg": True, "text": "doan 1", "start": 0.0, "end": 1.0}),
              flush=True)
        time.sleep(60)
    """)
    monkeypatch.setattr(pf_module, "_WORKER_SCRIPT", worker)
    settings = _settings(monkeypatch)

    with pytest.raises(RuntimeError, match="không phản hồi.*giữa lúc nhận dạng"):
        pf_module.transcribe_paraformer("/tmp/fake.wav", settings)


# ------------------------------------------- mini-spec V41: punctuation ----
# Bug thật (audit 2026-08-16): model chấm câu tải lỗi lúc cài đặt trước đây
# chỉ log ở stderr của worker con (GUI không đọc) — không có tín hiệu nào
# tới người dùng rằng transcript tiếng Trung đang thiếu dấu câu, có thể ảnh
# hưởng chất lượng dịch (nhiều câu gộp làm một). Worker giờ báo qua "done".

def test_missing_punctuation_model_logs_clear_warning(monkeypatch, tmp_path, caplog):
    worker = _fake_worker(tmp_path, body="""
        print(json.dumps({"seg": True, "text": "ni hao", "start": 0.0, "end": 1.0}),
              flush=True)
        print(json.dumps({"done": True, "punctuation_available": False}), flush=True)
    """)
    monkeypatch.setattr(pf_module, "_WORKER_SCRIPT", worker)
    settings = _settings(monkeypatch)

    with caplog.at_level("WARNING", logger="autodub.paraformer"):
        pf_module.transcribe_paraformer("/tmp/fake.wav", settings)

    assert any("chấm câu" in r.message for r in caplog.records)


def test_punctuation_available_no_warning_0_regression(monkeypatch, tmp_path, caplog):
    """Worker báo có model chấm câu (hoặc worker cũ không gửi field này —
    mặc định True) -> KHÔNG cảnh báo giả."""
    worker = _fake_worker(tmp_path, body="""
        print(json.dumps({"seg": True, "text": "ni hao", "start": 0.0, "end": 1.0}),
              flush=True)
        print(json.dumps({"done": True, "punctuation_available": True}), flush=True)
    """)
    monkeypatch.setattr(pf_module, "_WORKER_SCRIPT", worker)
    settings = _settings(monkeypatch)

    with caplog.at_level("WARNING", logger="autodub.paraformer"):
        pf_module.transcribe_paraformer("/tmp/fake.wav", settings)

    assert not any("chấm câu" in r.message for r in caplog.records)
