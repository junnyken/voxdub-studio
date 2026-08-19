"""Lip-sync stage (MuseTalk) — mini-spec V32b, docs/PLAN.md Phase G.

NGOẠI LỆ KIẾN TRÚC ĐẦU TIÊN so với "GPU-optional" của mọi tính năng khác
(chốt chính sách 2026-08-12, xem docs/TEST_LOG.md mục V32a) — GPU-ONLY,
opt-in (``DubRequest.lipsync``), mặc định TẮT. Chạy trong venv riêng
``.venv-lipsync`` qua subprocess (``lipsync_worker.py``) — cùng nguyên tắc
cô lập engine nặng của mọi bộ Whisper/VieNeu/Paraformer/Demucs GPU khác.

**Phạm vi hiện tại CHỈ đúng những gì V32a đã benchmark thật**: 1 khuôn mặt
phát hiện được ở MỌI frame (``Settings.lipsync_max_no_face_ratio``, mặc
định 0.0 — mẫu benchmark thành công duy nhất đạt đúng 0%), video ngắn
(``Settings.lipsync_max_duration_s``, mặc định 12.0s — mẫu duy nhất dài
10.7s, VRAM đỉnh đã 96% trên card 4GB). Góc nghiêng/nhiều người/video dài
CHƯA có số liệu benchmark — KHÔNG tự nới các ngưỡng này, xem "Remaining
Limits" mục V32a trong docs/TEST_LOG.md trước khi thay đổi.

**CHƯA live-verify trên GPU thật với ĐƯỜNG CODE PRODUCTION này** — chỉ
harness nghiên cứu (``scripts/research/lipsync_poc.py``) đã live-verify
thật (8 bug môi trường tìm+sửa, xem V32a). Module này chuyển thể lại logic
ĐÃ CHỨNG MINH đó thành ``lipsync_worker.py`` (worker) + module này (gọi
worker) — chủ dự án PHẢI tự chạy ``scripts/setup_lipsync.py`` rồi 1 lượt
pipeline có bật lip-sync trên GPU thật trước khi coi đây là tính năng đã
kiểm chứng production, không chỉ "code xong".
"""
from __future__ import annotations

import atexit
import json
import os
import subprocess

from autodub.cancel_guard import giet_khi_dung
from autodub.resources import GPU_LOCK
from autodub.utils import setup_logging

logger = setup_logging("autodub.lipsync")

# Video 10.7s đã chạy trót lọt (V32a) mất 794s — nhân rộng cho trần cấu
# hình (12s mặc định) rồi thêm biên an toàn lớn cho tải model + watermark.
_WORKER_TIMEOUT_S = 3600


class LipsyncUnavailable(Exception):
    """venv/GPU/weights chưa sẵn sàng — degrade trung thực (Constraint 2),
    không phải lỗi crash."""


class LipsyncBlocked(Exception):
    """Consent-check hoặc trần video chặn — chính sách CHỦ ĐÍCH (Constraint
    3/6), không phải lỗi kỹ thuật."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class LipsyncFailed(Exception):
    """Worker chạy nhưng lỗi thật (inference/watermark/giao thức)."""


def available(settings) -> bool:
    """venv + mã nguồn vendor + weights + GPU đều sẵn sàng chưa."""
    return settings.lipsync_configured() and settings.lipsync_gpu_available()


def check_duration(settings, video_duration_s: float | None) -> None:
    """Chặn SỚM trước khi tốn công mở subprocess nếu video ngoài phạm vi đã
    benchmark (Constraint 6 — không mở rộng case chưa kiểm chứng). Không đo
    được thời lượng (``None``) thì KHÔNG chặn — thà chạy thử (worker vẫn còn
    consent-check) hơn từ chối oan vì thiếu dữ liệu."""
    if video_duration_s is None:
        return
    if video_duration_s > settings.lipsync_max_duration_s:
        raise LipsyncBlocked(
            "duration_exceeded",
            f"Video dài {video_duration_s:.1f}s, vượt trần "
            f"{settings.lipsync_max_duration_s:.1f}s đã kiểm chứng (mini-spec "
            "V32a chỉ benchmark thành công 1 mẫu ~10.7s) — chưa bật cho video "
            "dài hơn cho tới khi có số liệu benchmark mới.")


def run(video_path: str, audio_path: str, output_dir: str, settings,
       video_duration_s: float | None = None, cancel_event=None) -> str:
    """Chạy lip-sync THẬT qua worker trong ``.venv-lipsync``, trả về đường
    dẫn video kết quả (đã watermark). Ném ``LipsyncUnavailable``/
    ``LipsyncBlocked``/``LipsyncFailed`` — caller (``pipeline.py``) quyết
    định cách báo người dùng, hàm này KHÔNG tự nuốt lỗi."""
    if not available(settings):
        raise LipsyncUnavailable(
            "Đồng bộ khẩu hình chưa sẵn sàng — cần chạy "
            "scripts/setup_lipsync.py trên máy có GPU NVIDIA thật trước.")

    check_duration(settings, video_duration_s)

    python = settings.lipsync_venv_python_path()
    cmd = [
        python, "-m", "autodub.media.lipsync_worker",
        "--video", os.path.abspath(video_path),
        "--audio", os.path.abspath(audio_path),
        "--output-dir", os.path.abspath(output_dir),
        "--max-no-face-ratio", str(settings.lipsync_max_no_face_ratio),
    ]

    logger.info("Đang chạy đồng bộ khẩu hình AI (GPU) — có thể mất nhiều "
               "phút, không phải bị treo...")
    proc = None
    try:
        # Cùng lý do GPU_LOCK của vocal_separator.py: pipeline dự đoán
        # ASR/Demucs của video này đã xong trước khi tới lip-sync (chạy ở
        # cuối pipeline), nhưng lock vẫn là lưới an toàn cho lúc dự đoán sai.
        with GPU_LOCK:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace")
            # Đóng app giữa lúc lip-sync chạy (có thể tới hàng chục phút)
            # không được để lại tiến trình con mồ côi — cùng pattern V40 đã
            # áp cho Whisper/Demucs GPU worker.
            atexit.register(proc.kill)
            try:
                # Lip-sync chạy hàng chục phút — nút Dừng phải cắt ngang
                # được (V79).
                with giet_khi_dung(proc, cancel_event):
                    stdout, _ = proc.communicate(timeout=_WORKER_TIMEOUT_S)
            finally:
                atexit.unregister(proc.kill)
    except subprocess.TimeoutExpired:
        if proc is not None:
            proc.kill()
            proc.wait()
        raise LipsyncFailed(
            f"Lip-sync worker chạy quá {_WORKER_TIMEOUT_S}s — đã hủy.")

    events = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    done = next((e for e in reversed(events) if e.get("stage") == "done"), None)
    if done is None:
        raise LipsyncFailed(
            f"Worker không trả kết quả hợp lệ: {(stdout or '')[-500:]}")

    if not done.get("ok"):
        reason = done.get("reason", "unknown")
        if reason == "consent_blocked":
            consent = done.get("consent_check") or {}
            raise LipsyncBlocked(
                "consent_blocked",
                "Không phát hiện đủ khuôn mặt ở "
                f"{consent.get('no_face_frames', '?')}/"
                f"{consent.get('total_frames', '?')} frame — video này ngoài "
                "phạm vi đã kiểm chứng (chỉ 1 khuôn mặt, luôn phát hiện "
                "được ở mọi frame).")
        detail = done.get("error") or done.get("output_tail") or done.get("stderr_tail") or ""
        raise LipsyncFailed(f"Lip-sync lỗi ({reason}): {detail}"[:1200])

    output_video = done.get("output_video")
    if not output_video or not os.path.isfile(output_video):
        raise LipsyncFailed(
            "Worker báo thành công nhưng không thấy file kết quả.")

    logger.info(
        f"Đồng bộ khẩu hình xong: {output_video} "
        f"({done.get('elapsed_seconds', '?')}s, "
        f"VRAM đỉnh {done.get('vram_peak_mb', '?')}MB)")
    return output_video
