"""Bug thật tìm+sửa trong lúc audit V34a (docs/PLAN.md, docs/TEST_LOG.md):
``scripts/setup_whisper.py`` gọi worker smoke test với ``input=""`` — nhưng
``autodub/speech/asr_whisper_worker.py`` LUÔN đọc 1 dòng JSON request từ
stdin trước khi transcribe (``sys.stdin.readline()`` rồi ``json.loads()``),
``--audio`` trên CLI chỉ là giá trị dự phòng khi request thiếu field đó.

``input=""`` không phải JSON hợp lệ → worker luôn thoát lỗi "Request JSON
không hợp lệ" TRƯỚC KHI chạm tới model — smoke test không bao giờ pass được
trên máy thật (tái hiện thật lúc build Docker image cho V34a, xem
docs/TEST_LOG.md). Test này khoá lại hành vi ĐÚNG: subprocess phải nhận
input là 1 dòng JSON hợp lệ (rỗng cũng được — worker tự fallback về
``args.audio``), không phải chuỗi rỗng.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

import pytest

_SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "setup_whisper.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("setup_whisper_under_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod(tmp_path, monkeypatch):
    m = _load_module()
    # Cách ly hoàn toàn khỏi models/whisper thật của repo — trỏ mọi
    # đường dẫn ghi vào tmp_path.
    monkeypatch.setattr(m, "MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(m, "MARKER", str(tmp_path / "installed_ok.json"))
    monkeypatch.setattr(m, "WORKER", str(tmp_path / "fake_worker.py"))
    (tmp_path / "fake_worker.py").write_text("# fake worker for test\n")
    return m


def test_smoke_sends_valid_json_on_stdin_not_empty_string(mod, monkeypatch):
    captured = {}

    def fake_run(cmd, input=None, **kwargs):  # noqa: A002 - matches subprocess.run signature
        captured["cmd"] = cmd
        captured["input"] = input
        return subprocess.CompletedProcess(cmd, 0, stdout='{"done": true}\n', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    mod.step_smoke()

    assert "input" in captured, "step_smoke() phải gọi subprocess.run với input="
    # Bug thật: input="" từng được truyền — không parse được thành JSON.
    assert captured["input"] not in (None, ""), (
        "input rỗng khiến asr_whisper_worker.py luôn báo lỗi "
        "'Request JSON không hợp lệ' — xem docstring module này")
    parsed = json.loads(captured["input"])
    assert isinstance(parsed, dict), "worker cần 1 JSON object trên stdin"


def test_smoke_still_passes_audio_via_cli_as_fallback(mod, monkeypatch):
    """`--audio` trên CLI vẫn phải còn — worker dùng nó khi request JSON
    không có field "audio" (``req.get("audio") or args.audio``)."""
    captured = {}

    def fake_run(cmd, input=None, **kwargs):  # noqa: A002
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout='{"done": true}\n', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    mod.step_smoke()

    assert "--audio" in captured["cmd"]
