"""Mini-spec V13 (docs/PLAN.md) — DubPipeline wiring cho telemetry: mỗi
run() gán run_id mới, rep.emit() thật sự chạm listener telemetry, lỗi ở
callback GUI gốc không được chặn telemetry, và pipeline.run() báo "failed"
khi ném lỗi.
"""
from __future__ import annotations

from autodub.config import Settings
from autodub.pipeline import DubPipeline, DubRequest


def test_run_assigns_fresh_run_id_each_call(monkeypatch):
    """Batch dùng lại 1 DubPipeline cho nhiều video — run_id KHÔNG được
    lặp lại giữa các lượt (mỗi lượt là 1 run độc lập trong dashboard)."""
    pipeline = DubPipeline(Settings())
    seen_ids = []

    def fake_run_impl(req):
        seen_ids.append(pipeline._telemetry_run_id)
        raise RuntimeError("dừng sớm để test, không cần chạy pipeline thật")
    monkeypatch.setattr(pipeline, "_run_impl", fake_run_impl)

    for _ in range(3):
        try:
            pipeline.run(DubRequest())
        except RuntimeError:
            pass

    assert len(seen_ids) == 3
    assert len(set(seen_ids)) == 3, "mỗi run() phải có run_id riêng, không trùng"
    assert all(seen_ids)


def test_local_only_reporter_emit_never_touches_saas_client(monkeypatch):
    """Guardrail 5 ở tầng tích hợp thật (không chỉ unit telemetry.py riêng):
    dựng DubPipeline thật, gọi rep.emit() thật nhiều lần, xác nhận
    get_client() không bao giờ được gọi khi local-only."""
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)

    def fail_if_called():
        raise AssertionError("KHÔNG được gọi get_client() ở chế độ local-only")
    monkeypatch.setattr("autodub.saas_client.get_client", fail_if_called)

    received = []
    pipeline = DubPipeline(Settings(), progress=lambda e: received.append(e))
    pipeline._telemetry_run_id = "run-local"

    pipeline._reporter.emit("acquire", "start")
    pipeline._reporter.emit("asr", "done")
    pipeline._reporter.emit("done", "done")

    assert len(received) == 3, "callback GUI gốc vẫn phải nhận đủ event như trước V13"


def test_configured_reporter_emit_reaches_telemetry_listener(monkeypatch):
    """Chế độ SaaS: rep.emit() thật phải chạm được saas_client thật (qua
    listener), không chỉ gọi callback GUI gốc."""
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    calls = []

    class _FakeClient:
        def send_pipeline_event(self, run_id, status, stage, error_stage=""):
            calls.append((run_id, status, stage))
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: _FakeClient())

    pipeline = DubPipeline(Settings(), progress=lambda e: None)
    pipeline._telemetry_run_id = "run-saas"

    pipeline._reporter.emit("acquire", "start")
    pipeline._reporter.emit("done", "done")

    # _send_async chạy nền — chờ ngắn cho thread kịp xong (best-effort thật,
    # không mock threading).
    import time
    for _ in range(50):
        if len(calls) >= 2:
            break
        time.sleep(0.05)

    assert ("run-saas", "started", "acquire") in calls
    assert ("run-saas", "completed", "done") in calls


def test_broken_gui_callback_does_not_block_telemetry(monkeypatch):
    """Callback GUI tự ném lỗi (bug ở tầng UI) không được chặn telemetry
    chạy tiếp — đúng thiết kế 'độc lập với UI progress hiện có'."""
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    calls = []

    class _FakeClient:
        def send_pipeline_event(self, run_id, status, stage, error_stage=""):
            calls.append(stage)
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: _FakeClient())

    def broken_progress(event):
        raise RuntimeError("bug trong handler GUI")

    pipeline = DubPipeline(Settings(), progress=broken_progress)
    pipeline._telemetry_run_id = "run-broken-gui"

    # Không được ném lỗi ra ngoài — ProgressReporter.emit() vốn đã nuốt lỗi
    # callback, và wrapper của DubPipeline phải giữ nguyên tính chất đó.
    pipeline._reporter.emit("acquire", "start")

    import time
    for _ in range(50):
        if calls:
            break
        time.sleep(0.05)
    assert calls == ["acquire"], "telemetry phải chạy dù callback GUI gốc lỗi"


def test_run_reports_failed_on_exception(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    reported = []
    monkeypatch.setattr("autodub.telemetry.note_failed",
                        lambda pipeline: reported.append(pipeline._telemetry_run_id))

    pipeline = DubPipeline(Settings())

    def fake_run_impl(req):
        raise RuntimeError("lỗi giả lập giữa pipeline")
    monkeypatch.setattr(pipeline, "_run_impl", fake_run_impl)

    try:
        pipeline.run(DubRequest())
    except RuntimeError:
        pass

    assert len(reported) == 1
    assert reported[0] == pipeline._telemetry_run_id
