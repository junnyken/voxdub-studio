"""Tách nhạc nền qua máy chủ (mini-spec V9 → V12, xem docs/PLAN.md) — thay
thế Demucs chạy trên máy bằng một job xử lý trên cloud. TUỲ CHỌN, TẮT mặc
định — chỉ có nghĩa khi ``saas_client.is_configured()`` (chế độ SaaS); chế
độ local-only không bao giờ gọi module này (``is_available()`` là cổng duy
nhất, cùng nguyên tắc ``is_configured()`` xuyên suốt sản phẩm).

V12: job xử lý BẤT ĐỒNG BỘ thật — nộp file, nhận ``jobId`` ngay, tự poll
``GET /v1/jobs/:id`` tới khi ``done``/``failed``, rồi tải 2 stem. Vox đã bị
trừ NGAY lúc nộp (giống nguyên tắc hold — máy chủ tốn tài nguyên là tốn,
không hoàn khi job lỗi phía máy chủ).

Fallback khi cloud lỗi (mạng, job lỗi phía máy chủ, quá hạn chờ): rơi về
Demucs CHẠY TRÊN MÁY — đúng nguyên tắc "degrade trung thực" đã có sẵn trong
sản phẩm (vd Paraformer lỗi → fallback Whisper, xem CLAUDE.md), không phải
phát minh mới cho V12. Vox đã trả cho lượt cloud lỗi chấp nhận mất (rủi ro
nhỏ, cùng mức chấp nhận được như hold hết hạn) — người dùng vẫn nhận được
kết quả tách nhạc, không phải chờ lỗi rồi tự chạy lại thủ công.
"""
from __future__ import annotations

import os
import time

from autodub.progress import ProgressReporter
from autodub.utils import setup_logging

logger = setup_logging("autodub.cloud_render")

POLL_INTERVAL_S = 3.0
#: Video dài thật (hàng chục phút) vẫn phải xong trong ngưỡng này — quá hạn
#: thì coi là treo, rơi về Demucs máy thay vì chờ vô thời hạn.
MAX_WAIT_S = 30 * 60


def is_available(settings) -> bool:
    """Cổng duy nhất — cùng nguyên tắc ``is_configured()`` toàn sản phẩm."""
    from autodub.saas_client import is_configured
    return bool(settings.cloud_render_enabled) and is_configured()


def pricing(settings) -> dict | None:
    """Giá + trạng thái bật/tắt từ máy chủ, hoặc ``None`` nếu không dùng
    được lúc này. GỌI TRƯỚC khi chạy để GUI hiện đúng giá (guardrail 4 của
    mini-spec V12) — không suy đoán bằng hằng số cứng trong app, giá đổi ở
    Admin server-side không cần cập nhật app.
    """
    if not is_available(settings):
        return None
    from autodub.saas_client import SaasError, get_client
    try:
        cfg = get_client().app_config()
    except SaasError:
        return None
    if not cfg:
        return None
    return {
        "enabled": bool(cfg.get("cloudRenderEnabled")),
        "cost_vox": int((cfg.get("pricing") or {}).get("cloudRenderDemucs") or 0),
    }


def separate_vocals_cloud(
    input_wav: str, output_dir: str,
    sample_rate: int = 16000, channels: int = 1,
    reporter: ProgressReporter | None = None,
) -> dict[str, str | None]:
    """Tách nhạc nền qua máy chủ — CÙNG chữ ký trả về với
    :func:`autodub.media.vocal_separator.separate_vocals` (drop-in thay
    thế, cùng cặp tên file output): ``{"vocals": path, "no_vocals": path}``
    khi thành công, ném lỗi khi thất bại (caller tự quyết định fallback).
    """
    vocals_out = os.path.join(output_dir, "vocals.wav")
    no_vocals_out = os.path.join(output_dir, "no_vocals.wav")
    if (os.path.exists(no_vocals_out) and os.path.getsize(no_vocals_out) > 0
            and os.path.exists(vocals_out) and os.path.getsize(vocals_out) > 0):
        logger.info(f"Dùng lại kết quả tách nhạc đã có: {no_vocals_out}")
        return {"vocals": vocals_out, "no_vocals": no_vocals_out}

    from autodub.saas_client import SaasError, get_client

    client = get_client()
    submitted = client.submit_demucs_job(input_wav)
    job_id = submitted["jobId"]
    logger.info(f"Đã nộp job tách nhạc lên cloud (jobId={job_id})")
    if reporter is not None:
        reporter.emit("separate", "progress", detail="Đang chờ máy chủ xử lý…",
                      current=0, total=1)

    deadline = time.monotonic() + MAX_WAIT_S
    status = submitted.get("status", "queued")
    last_status = None
    info = submitted
    while status not in ("done", "failed"):
        if time.monotonic() > deadline:
            raise SaasError(
                f"Job tách nhạc trên cloud quá hạn chờ ({int(MAX_WAIT_S)}s) — jobId={job_id}")
        if reporter is not None:
            reporter.check_cancelled()
        time.sleep(POLL_INTERVAL_S)
        info = client.job_status(job_id)
        status = info.get("status", status)
        if status != last_status:
            logger.info(f"Job tách nhạc cloud: {status}")
            last_status = status

    if status == "failed":
        raise SaasError(f"Máy chủ tách nhạc lỗi: {info.get('error') or 'không rõ lý do'}")

    raw_vocals = os.path.join(output_dir, "_vocals_cloud_raw.wav")
    raw_no_vocals = os.path.join(output_dir, "_no_vocals_cloud_raw.wav")
    try:
        client.download_job_result(job_id, "vocals", raw_vocals)
        client.download_job_result(job_id, "no_vocals", raw_no_vocals)

        from autodub.media.vocal_separator import _normalize
        _normalize(raw_vocals, vocals_out, str(sample_rate), channels)
        _normalize(raw_no_vocals, no_vocals_out, str(sample_rate), channels)
    finally:
        for p in (raw_vocals, raw_no_vocals):
            if os.path.exists(p):
                os.remove(p)

    logger.info(f"Tách nhạc trên cloud xong: {no_vocals_out}")
    return {"vocals": vocals_out, "no_vocals": no_vocals_out}
