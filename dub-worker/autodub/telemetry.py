"""Gửi trạng thái tiến trình lồng tiếng về máy chủ (mini-spec V13, xem
docs/PLAN.md) — CHỈ khi ``saas_client.is_configured()`` (chế độ SaaS).
KHÔNG BAO GIỜ gọi mạng ở chế độ local-only (guardrail 5) — ``is_configured()``
là cổng CẦN VÀ ĐỦ, không thêm cờ bật/tắt riêng gây rối logic (đúng nguyên
tắc đã dùng xuyên suốt sản phẩm, xem ``autodub.cloud_render``/
``autodub.text.translate_local`` cho các cổng tương tự).

Event CHỈ chứa (fingerprint — tự động qua token thiết bị, không phải app
tự khai, runId, stage, status, timestamp) — KHÔNG BAO GIỜ nội dung video/
transcript/audio/đường dẫn file (guardrail 2; máy chủ chặn field lạ ở
tầng validate, xem control_server/src/routes/telemetry.js).

Best-effort: mọi lỗi mạng lúc gửi bị NUỐT trong luồng nền riêng — không
được làm chậm/hỏng lượt dubbing đang chạy (guardrail 3).

BẮT BUỘC (guardrail 1, đã thực hiện — xem docs/TEST_LOG.md mục V13): banner
minh bạch (autodub_gui/first_run.py, help_page.py) đã cập nhật nói rõ việc
gửi event này TRƯỚC KHI tính năng này được bật.
"""
from __future__ import annotations

import threading

from autodub.progress import ProgressEvent, ProgressFn
from autodub.utils import setup_logging

logger = setup_logging("autodub.telemetry")

#: Trạng thái ProgressEvent coi là "đã qua xong 1 giai đoạn" — bỏ qua
#: "progress" (tiến độ chi tiết trong 1 bước, vd % TTS) và "error" (đã có
#: đường xử lý lỗi riêng ở tầng run(), không lặp lại ở đây).
_STAGE_REACHED_STATUSES = ("done", "skip")


def _send_async(run_id: str, status: str, stage: str, error_stage: str = "") -> None:
    """Gửi 1 event trong luồng nền — KHÔNG BAO GIỜ chặn luồng gọi
    (guardrail 3), mọi lỗi bị nuốt và chỉ ghi log mức debug."""
    def _worker() -> None:
        try:
            from autodub.saas_client import get_client
            get_client().send_pipeline_event(
                run_id=run_id, status=status, stage=stage, error_stage=error_stage)
        except Exception as e:  # noqa: BLE001 — best-effort, không được vỡ pipeline
            logger.debug(f"Gửi telemetry tiến trình lỗi (bỏ qua): {e}")
    threading.Thread(target=_worker, daemon=True).start()


def make_progress_listener(pipeline) -> ProgressFn:
    """1 listener gắn thêm vào progress callback hiện có của ``pipeline``
    (đúng Design Choice của V13: tái dùng ``rep.emit()`` đã có, không thêm
    hook mới trong logic pipeline.py).

    Đọc ``pipeline._telemetry_run_id`` động (được ``DubPipeline.run()``
    gán một ID mới mỗi lượt chạy) — chưa có run nào đang chạy thì bỏ qua.
    Local-only (``is_configured()==False``) trả về no-op ngay từ đầu: 0
    overhead, 0 network, quyết định MỘT LẦN lúc dựng pipeline, không kiểm
    tra lại mỗi event (guardrail 5).
    """
    from autodub.saas_client import is_configured
    if not is_configured():
        def _noop(event: ProgressEvent) -> None:
            return None
        return _noop

    def _listener(event: ProgressEvent) -> None:
        run_id = getattr(pipeline, "_telemetry_run_id", None)
        if not run_id:
            return
        if event.step == "acquire" and event.status == "start":
            pipeline._telemetry_last_stage = event.step
            _send_async(run_id, "started", event.step)
        elif event.step == "done" and event.status == "done":
            pipeline._telemetry_last_stage = "done"
            _send_async(run_id, "completed", "done")
        elif event.status in _STAGE_REACHED_STATUSES:
            pipeline._telemetry_last_stage = event.step
            _send_async(run_id, "started", event.step)

    return _listener


def note_failed(pipeline) -> None:
    """Gọi từ ``DubPipeline.run()`` khi pipeline ném lỗi (bao gồm huỷ) —
    báo ``failed`` kèm ``errorStage`` = giai đoạn cuối cùng đã ghi nhận
    (không rõ giai đoạn nào thì rơi về "acquire", tối thiểu vẫn có 1 event
    terminal thay vì để run treo mãi ở "started" chờ sweeper "bỏ dở" tự
    suy đoán — ta ĐÃ BIẾT chắc nó thất bại, không cần ước lượng)."""
    run_id = getattr(pipeline, "_telemetry_run_id", None)
    if not run_id:
        return
    stage = getattr(pipeline, "_telemetry_last_stage", "") or "acquire"
    _send_async(run_id, "failed", stage, error_stage=stage)
