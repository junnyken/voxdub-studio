"""Mini-spec V24 (docs/PLAN.md, Phase F, đợt 2) — watchdog áp dụng cho
``_transcribe_whisper_subprocess()`` (autodub/speech/transcriber.py).

Cùng cách tiếp cận đã dùng cho `run_local_worker()` — 1 worker giả THẬT
(script Python nhỏ, đúng giao thức JSON qua stdout mà asr_whisper_worker.py
thật dùng), không mock ``Popen``.
"""
from __future__ import annotations

import sys
import textwrap

import pytest

from autodub.config import Settings
from autodub.speech import transcriber as transcriber_module


def _fake_worker(tmp_path, body: str) -> str:
    preamble = textwrap.dedent("""
        import json, sys
        print(json.dumps({"ready": True}), flush=True)
        line = sys.stdin.readline()
        request = json.loads(line)
    """)
    path = tmp_path / "fake_whisper_worker.py"
    path.write_text(preamble + textwrap.dedent(body), encoding="utf-8")
    return str(path)


def _settings(monkeypatch):
    settings = Settings()
    monkeypatch.setattr(settings, "whisper_venv_python_path", lambda: sys.executable)
    monkeypatch.setattr(settings, "whisper_model_dir_path", lambda: "/tmp/fake-model")
    return settings


def test_worker_responds_normally_still_works_through_watchdog(monkeypatch, tmp_path):
    worker = _fake_worker(tmp_path, body=textwrap.dedent("""
        print(json.dumps({"seg": True, "id": 1, "text": "xin chao",
                          "start": 0.0, "end": 1.0}), flush=True)
        print(json.dumps({"done": True, "language": "vi", "language_prob": 0.99}),
              flush=True)
    """))
    monkeypatch.setattr(transcriber_module, "_WHISPER_WORKER_SCRIPT", worker)
    settings = _settings(monkeypatch)

    segments = transcriber_module._transcribe_whisper_subprocess(
        "/tmp/fake.wav", "vi", settings)

    assert len(segments) == 1
    assert segments[0]["text"] == "xin chao"


def test_worker_hangs_before_ready_raises_within_bounded_time(monkeypatch, tmp_path):
    monkeypatch.setattr(transcriber_module, "_WHISPER_READY_TIMEOUT_S", 0.3)
    path = tmp_path / "fake_whisper_worker.py"
    path.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    monkeypatch.setattr(transcriber_module, "_WHISPER_WORKER_SCRIPT", str(path))
    settings = _settings(monkeypatch)

    with pytest.raises(RuntimeError, match="không phản hồi"):
        transcriber_module._transcribe_whisper_subprocess("/tmp/fake.wav", "vi", settings)


def test_worker_hangs_mid_transcription_raises_within_bounded_time(monkeypatch, tmp_path):
    """Bug thật đã audit ở V24: worker nhận dạng xong 1 đoạn rồi treo ->
    trước khi vá, pipeline treo vô thời hạn, không timeout, không log."""
    monkeypatch.setattr(transcriber_module, "_WHISPER_SEGMENT_TIMEOUT_S", 0.3)
    worker = _fake_worker(tmp_path, body=textwrap.dedent("""
        import time
        print(json.dumps({"seg": True, "id": 1, "text": "doan 1",
                          "start": 0.0, "end": 1.0}), flush=True)
        time.sleep(60)
    """))
    monkeypatch.setattr(transcriber_module, "_WHISPER_WORKER_SCRIPT", worker)
    settings = _settings(monkeypatch)

    with pytest.raises(RuntimeError, match="không phản hồi.*giữa lúc nhận dạng"):
        transcriber_module._transcribe_whisper_subprocess("/tmp/fake.wav", "vi", settings)
