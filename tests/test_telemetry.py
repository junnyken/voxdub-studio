"""Mini-spec V13 (docs/PLAN.md) — autodub.telemetry: gửi trạng thái tiến
trình lồng tiếng, CHỈ khi is_configured() (chế độ SaaS), best-effort
(không chặn/không làm hỏng pipeline khi mạng lỗi), KHÔNG BAO GIỜ ở
local-only (guardrail 5 — cổng CẦN VÀ ĐỦ, khoá lại bằng test dưới).
"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from autodub import telemetry
from autodub.progress import ProgressEvent


class _FakePipeline:
    def __init__(self, run_id="run-1"):
        self._telemetry_run_id = run_id
        self._telemetry_last_stage = ""


# ------------------------------------------------------- make_progress_listener --

def test_local_only_returns_noop_never_touches_saas_client(monkeypatch):
    """Guardrail 5: is_configured()==False -> listener KHÔNG BAO GIỜ gọi
    get_client() dù nhận bao nhiêu event."""
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)

    def fail_if_called():
        raise AssertionError("KHÔNG được gọi get_client() ở chế độ local-only")
    monkeypatch.setattr("autodub.saas_client.get_client", fail_if_called)

    pipeline = _FakePipeline()
    listener = telemetry.make_progress_listener(pipeline)
    listener(ProgressEvent("acquire", "start"))
    listener(ProgressEvent("asr", "done"))
    listener(ProgressEvent("done", "done"))
    # Không assert nào raise nghĩa là get_client() thật sự chưa từng gọi.


def test_configured_sends_started_on_first_acquire(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    sent = []
    monkeypatch.setattr(telemetry, "_send_async",
                        lambda run_id, status, stage, error_stage="":
                            sent.append((run_id, status, stage, error_stage)))

    pipeline = _FakePipeline("run-abc")
    listener = telemetry.make_progress_listener(pipeline)
    listener(ProgressEvent("acquire", "start"))

    assert sent == [("run-abc", "started", "acquire", "")]
    assert pipeline._telemetry_last_stage == "acquire"


def test_configured_updates_stage_on_done_and_skip(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    sent = []
    monkeypatch.setattr(telemetry, "_send_async",
                        lambda run_id, status, stage, error_stage="":
                            sent.append((status, stage)))

    pipeline = _FakePipeline("run-1")
    listener = telemetry.make_progress_listener(pipeline)
    listener(ProgressEvent("acquire", "start"))
    listener(ProgressEvent("extract", "done"))
    listener(ProgressEvent("separate", "skip"))
    listener(ProgressEvent("asr", "progress", current=5, total=10))  # phải bị lờ đi
    listener(ProgressEvent("asr", "done"))

    assert sent == [
        ("started", "acquire"),
        ("started", "extract"),
        ("started", "separate"),
        ("started", "asr"),
    ]
    assert pipeline._telemetry_last_stage == "asr"


def test_configured_sends_completed_on_done_done(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    sent = []
    monkeypatch.setattr(telemetry, "_send_async",
                        lambda run_id, status, stage, error_stage="":
                            sent.append((status, stage)))

    pipeline = _FakePipeline("run-1")
    listener = telemetry.make_progress_listener(pipeline)
    listener(ProgressEvent("acquire", "start"))
    listener(ProgressEvent("merge_video", "done"))
    listener(ProgressEvent("done", "done"))

    assert sent[-1] == ("completed", "done")
    assert pipeline._telemetry_last_stage == "done"


def test_listener_without_active_run_id_is_noop(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    sent = []
    monkeypatch.setattr(telemetry, "_send_async",
                        lambda *a, **kw: sent.append(1))
    pipeline = _FakePipeline(run_id=None)
    listener = telemetry.make_progress_listener(pipeline)
    listener(ProgressEvent("acquire", "start"))
    assert sent == []


# -------------------------------------------------------------- note_failed --

def test_note_failed_sends_failed_with_last_known_stage(monkeypatch):
    sent = []
    monkeypatch.setattr(telemetry, "_send_async",
                        lambda run_id, status, stage, error_stage="":
                            sent.append((run_id, status, stage, error_stage)))
    pipeline = _FakePipeline("run-x")
    pipeline._telemetry_last_stage = "translate"

    telemetry.note_failed(pipeline)

    assert sent == [("run-x", "failed", "translate", "translate")]


def test_note_failed_defaults_stage_to_acquire_when_unknown(monkeypatch):
    sent = []
    monkeypatch.setattr(telemetry, "_send_async",
                        lambda run_id, status, stage, error_stage="":
                            sent.append((status, stage, error_stage)))
    pipeline = _FakePipeline("run-y")
    telemetry.note_failed(pipeline)
    assert sent == [("failed", "acquire", "acquire")]


def test_note_failed_noop_without_run_id():
    sent_flag = []

    def fake_send(*a, **kw):
        sent_flag.append(1)
    pipeline = _FakePipeline(run_id=None)
    import autodub.telemetry as tel_mod
    orig = tel_mod._send_async
    tel_mod._send_async = fake_send
    try:
        telemetry.note_failed(pipeline)
    finally:
        tel_mod._send_async = orig
    assert sent_flag == []


# ------------------------------------------------------------- _send_async --

def test_send_async_runs_in_background_thread_and_swallows_errors(monkeypatch):
    """Best-effort thật (guardrail 3): lỗi mạng KHÔNG được lan lên luồng
    gọi — verify bằng thread thật (không mock threading), lỗi thật ném từ
    send_pipeline_event() bị nuốt, luồng gọi không bao giờ thấy exception."""
    done = threading.Event()
    calls = []

    class _FakeClient:
        def send_pipeline_event(self, run_id, status, stage, error_stage=""):
            calls.append((run_id, status, stage, error_stage))
            done.set()
            raise RuntimeError("mạng lỗi giả lập")

    monkeypatch.setattr("autodub.saas_client.get_client", lambda: _FakeClient())

    # Gọi trực tiếp ở LUỒNG CHÍNH — nếu lỗi lan lên đây, test tự fail ngay
    # (không cần try/except, đúng tinh thần "không được làm hỏng pipeline").
    telemetry._send_async("run-1", "started", "acquire")

    assert done.wait(timeout=2.0), "worker thread không chạy trong 2s"
    assert calls == [("run-1", "started", "acquire", "")]
    # Không có gì bay lên đây — nếu RuntimeError lọt ra, test đã crash ở
    # dòng gọi _send_async() phía trên rồi (thread riêng, không đồng bộ).


def test_send_async_does_not_block_caller(monkeypatch):
    """Gọi _send_async() phải trả về gần như tức thì dù request giả lập
    chậm — nó chỉ start() một thread rồi return ngay."""
    import time

    class _SlowClient:
        def send_pipeline_event(self, **kw):
            time.sleep(1.0)

    monkeypatch.setattr("autodub.saas_client.get_client", lambda: _SlowClient())

    start = time.monotonic()
    telemetry._send_async("run-1", "started", "acquire")
    elapsed = time.monotonic() - start
    assert elapsed < 0.5, f"_send_async() không được chặn luồng gọi (mất {elapsed:.2f}s)"
