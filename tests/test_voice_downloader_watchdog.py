"""Mini-spec V24 (docs/PLAN.md, Phase F, đợt 2) — watchdog áp dụng cho
``_run_enroll_worker()`` (autodub/speech/tts/voice_downloader.py).

Worker giả THẬT — script này KHÔNG dùng giao thức theo dòng như 3 nơi
khác đã vá: nó chỉ ghi ĐÚNG 1 khối JSON kết quả rồi thoát, đọc qua
``proc.stdout.read()`` (nay là ``read_all_with_timeout``).
"""
from __future__ import annotations

import sys
import textwrap

from autodub.config import Settings
from autodub.speech.tts import voice_downloader


def _fake_worker(tmp_path, body: str) -> str:
    path = tmp_path / "fake_enroll_worker.py"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return str(path)


def _settings(tmp_path):
    return Settings(vieneu_model_dir=str(tmp_path / "vieneu"))


def test_worker_responds_normally_still_works_through_watchdog(monkeypatch, tmp_path):
    worker = _fake_worker(tmp_path, body="""
        import json
        print(json.dumps({"ok": True, "added": ["Minh Trang"]}))
    """)
    monkeypatch.setattr("autodub.speech.tts.vieneu_vi._WORKER_SCRIPT", worker)
    settings = _settings(tmp_path)
    monkeypatch.setattr(settings, "vieneu_venv_python_path", lambda: sys.executable)

    batch_file = str(tmp_path / "batch.json")
    open(batch_file, "w", encoding="utf-8").write("[]")

    result = voice_downloader._run_enroll_worker(settings, batch_file)
    assert result["ok"] is True
    assert result["added"] == ["Minh Trang"]


def test_worker_hangs_raises_timeout_within_bounded_time(monkeypatch, tmp_path):
    """Bug thật đã audit: `proc.stdout.read()` trần chặn vô thời hạn nếu
    worker treo trước khi ghi kết quả — trước khi vá, không có cách nào
    thoát ra ngoài `proc.wait(timeout=3600)` (chưa bao giờ chạy tới)."""
    monkeypatch.setattr(voice_downloader, "_ENROLL_READ_TIMEOUT_S", 0.3)
    worker = _fake_worker(tmp_path, body="import time\ntime.sleep(60)\n")
    monkeypatch.setattr("autodub.speech.tts.vieneu_vi._WORKER_SCRIPT", worker)
    settings = _settings(tmp_path)
    monkeypatch.setattr(settings, "vieneu_venv_python_path", lambda: sys.executable)

    batch_file = str(tmp_path / "batch.json")
    open(batch_file, "w", encoding="utf-8").write("[]")

    result = voice_downloader._run_enroll_worker(settings, batch_file)
    assert result["ok"] is False
    assert "timeout" in result["error"].lower() or "Timeout" in result["error"]
