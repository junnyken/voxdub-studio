"""Mini-spec V24 (docs/PLAN.md, Phase F) — watchdog áp dụng cho
``run_local_worker()`` (autodub/text/translate_local.py).

Dùng 1 worker THẬT giả lập (script Python nhỏ, cùng giao thức JSON qua
stdout mà translate_local_worker.py thật dùng) thay vì mock `Popen` — kiểm
tra đúng hành vi subprocess THẬT bị treo, không phải hành vi giả lập của
mock.
"""
from __future__ import annotations

import sys
import textwrap

import pytest

from autodub.config import Settings
from autodub.text.translate_local import LocalTranslateError, run_local_worker


def _fake_worker(tmp_path, body: str) -> str:
    preamble = textwrap.dedent("""
        import json, sys
        print(json.dumps({"ready": True}), flush=True)
        line = sys.stdin.readline()
        request = json.loads(line)
    """)
    path = tmp_path / "fake_worker.py"
    path.write_text(preamble + textwrap.dedent(body), encoding="utf-8")
    return str(path)


def _settings_for(monkeypatch, worker_path, model_dir="/tmp/fake-model"):
    settings = Settings()
    monkeypatch.setattr(settings, "translate_local_venv_python_path",
                        lambda: sys.executable)
    monkeypatch.setattr(settings, "translate_local_model_dir_path",
                        lambda: model_dir)
    monkeypatch.setattr("autodub.text.translate_local.bundled_file",
                        lambda *a, **k: worker_path)
    return settings


def test_worker_responds_normally_still_works_through_watchdog(monkeypatch, tmp_path):
    """0 regression: worker khoẻ mạnh vẫn hoạt động y hệt qua đường watchdog mới."""
    worker = _fake_worker(tmp_path, body=textwrap.dedent("""
        for seg in request["segments"]:
            print(json.dumps({"seg": True, "id": seg["id"], "text": "dịch: " + seg["text"]}), flush=True)
        print(json.dumps({"done": True, "translated": len(request["segments"])}), flush=True)
    """))
    settings = _settings_for(monkeypatch, worker)
    result = run_local_worker([(1, "hello"), (2, "world")], "eng_Latn", "vie_Latn", settings)
    assert result == {1: "dịch: hello", 2: "dịch: world"}


def test_worker_hangs_before_ready_raises_within_bounded_time(monkeypatch, tmp_path):
    """Bug thật đã audit: model treo lúc nạp -> trước V24 chặn vô thời hạn."""
    import autodub.text.translate_local as tl
    monkeypatch.setattr(tl, "_READY_TIMEOUT_S", 0.3)

    worker = _fake_worker(tmp_path, body="")  # không bao giờ in "ready"
    # Ghi đè: worker không in gì cả trước khi đọc stdin -> treo ở bước ready.
    path = tmp_path / "fake_worker.py"
    path.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")

    settings = _settings_for(monkeypatch, str(path))
    with pytest.raises(LocalTranslateError, match="không phản hồi"):
        run_local_worker([(1, "hello")], "eng_Latn", "vie_Latn", settings)


def test_worker_hangs_mid_translation_raises_within_bounded_time_and_reports_progress(
        monkeypatch, tmp_path):
    """Bug thật đã audit: worker dịch xong câu 1 rồi treo ở câu 2 -> trước
    V24 pipeline treo vô thời hạn, không timeout, không log."""
    import autodub.text.translate_local as tl
    monkeypatch.setattr(tl, "_TRANSLATE_LINE_TIMEOUT_S", 0.3)

    worker = _fake_worker(tmp_path, body=textwrap.dedent("""
        import time
        print(json.dumps({"seg": True, "id": 1, "text": "câu 1 xong"}), flush=True)
        time.sleep(60)
    """))
    settings = _settings_for(monkeypatch, worker)
    with pytest.raises(LocalTranslateError, match="không phản hồi.*giữa lúc dịch"):
        run_local_worker([(1, "a"), (2, "b")], "eng_Latn", "vie_Latn", settings)
