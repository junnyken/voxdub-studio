"""Kiểm tra chất lượng tín hiệu số học của 1 đoạn ghi âm TRƯỚC khi học
giọng (mini-spec V35, docs/PLAN.md Phase G) — hàm thuần, KHÔNG phụ thuộc
torch/model AI đánh giá chất lượng riêng nào (Constraint 1): chỉ đo tỷ lệ
mẫu bị cắt tiếng (clipping), năng lượng RMS trung bình (phát hiện gần-như-
câm), và tỷ lệ khoảng lặng liên tục dài nhất so với tổng thời lượng.

Không thay thế bước khử ồn ONNX đã có (``engine.denoiser`` trong
``vieneu_worker.py``) — module này chỉ ĐO và BÁO trước khi xử lý, để người
dùng biết ngay file có đáng học hay không thay vì phải tự bấm "Nghe thử"
sau khi đã lưu (Goal của mini-spec).

Ba mức, đúng khuôn ``autodub/preflight.py::CheckResult``:
- ``fail``: rõ ràng không dùng được (gần như câm hoàn toàn, cắt tiếng nặng).
- ``warn``: có vấn đề nhưng vẫn học được — người dùng tự quyết định
  (Constraint 2, KHÔNG chặn cứng trường hợp biên).
- ``ok``:   đạt.

Ngưỡng chọn theo nguyên tắc "bắt lỗi RÕ RÀNG nhất" (Design Choice của mini-
spec), KHÔNG phải benchmark thống kê chính thức trên tập dữ liệu lớn — xem
Remaining Limits trong docs/TEST_LOG.md mục V35.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Mẫu coi là "chạm biên" (cắt tiếng) — biên độ chuẩn hoá ±1.0.
_CLIP_THRESHOLD = 0.999
_CLIP_WARN_RATIO = 0.001    # 0.1% mẫu chạm biên — đáng ngờ
_CLIP_FAIL_RATIO = 0.01     # 1% mẫu chạm biên — cắt tiếng rõ ràng

_RMS_FAIL = 0.001           # gần như câm hoàn toàn
_RMS_WARN = 0.01            # rất nhỏ — có thể ồn nền lấn át giọng nói

_LONGEST_SILENCE_WARN_RATIO = 0.5    # hơn nửa clip là khoảng lặng liên tục
_LONGEST_SILENCE_FAIL_RATIO = 0.85   # gần như toàn bộ clip là im lặng

#: Biên độ dưới ngưỡng này coi là "lặng" khi đo khoảng lặng liên tục dài
#: nhất — độc lập với ngưỡng RMS toàn cục (1 clip có thể RMS trung bình ổn
#: nhưng vẫn có 1 đoạn dài im lặng ở đầu/cuối do bấm ghi âm sớm/trễ).
_SILENCE_SAMPLE_THRESHOLD = 0.01


@dataclass(frozen=True)
class AudioQualityResult:
    """Kết quả kiểm tra, đủ chữ để hiện thẳng lên giao diện."""

    level: str                              # "ok" | "warn" | "fail"
    reasons: list[str] = field(default_factory=list)
    clip_ratio: float = 0.0
    rms: float = 0.0
    longest_silence_ratio: float = 0.0

    @property
    def ok(self) -> bool:
        return self.level == "ok"


def _longest_silence_ratio(wav: np.ndarray) -> float:
    """Tỷ lệ khoảng lặng liên tục DÀI NHẤT so với tổng số mẫu."""
    if wav.size == 0:
        return 1.0
    is_silent = np.abs(wav) < _SILENCE_SAMPLE_THRESHOLD
    longest = 0
    current = 0
    for silent in is_silent:
        if silent:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest / wav.size


def analyze(wav: np.ndarray, sr: int) -> AudioQualityResult:
    """Phân tích 1 đoạn ghi âm mono (float32, biên độ chuẩn hoá ±1.0).

    ``sr`` hiện chưa dùng trực tiếp trong phép tính (mọi chỉ số đều là tỷ
    lệ mẫu, không phụ thuộc tần số lấy mẫu) — vẫn giữ tham số để chữ ký hàm
    khớp cách gọi thật ở ``_encode_one()`` (đã có ``wav, sr`` sẵn) và để
    ngỏ cho phép đo sau này cần tần số (vd phát hiện tần số cắt lọc).
    """
    wav = np.asarray(wav, dtype=np.float32).reshape(-1)
    reasons: list[str] = []
    level = "ok"

    if wav.size == 0:
        return AudioQualityResult(
            level="fail", reasons=["Đoạn ghi âm rỗng — không có dữ liệu âm thanh."])

    clip_ratio = float(np.mean(np.abs(wav) >= _CLIP_THRESHOLD))
    rms = float(np.sqrt(np.mean(np.square(wav))))
    silence_ratio = _longest_silence_ratio(wav)

    if clip_ratio >= _CLIP_FAIL_RATIO:
        level = "fail"
        reasons.append(
            f"Cắt tiếng nặng: {clip_ratio:.1%} số mẫu chạm biên biên độ — "
            "ghi âm lại với âm lượng nhỏ hơn.")
    elif clip_ratio >= _CLIP_WARN_RATIO:
        if level != "fail":
            level = "warn"
        reasons.append(
            f"Có dấu hiệu cắt tiếng: {clip_ratio:.2%} số mẫu chạm biên biên "
            "độ — giọng nhân bản có thể bị rè ở những đoạn to.")

    if rms <= _RMS_FAIL:
        level = "fail"
        reasons.append(
            "Gần như không có âm thanh (gần như câm hoàn toàn) — kiểm tra "
            "lại micro/file ghi âm.")
    elif rms <= _RMS_WARN:
        if level != "fail":
            level = "warn"
        reasons.append(
            "Âm lượng rất nhỏ — giọng nhân bản có thể yếu hoặc lẫn nhiều "
            "tạp âm nền.")

    if silence_ratio >= _LONGEST_SILENCE_FAIL_RATIO:
        level = "fail"
        reasons.append(
            f"Phần lớn clip ({silence_ratio:.0%}) là khoảng lặng liên tục — "
            "gần như không có lời nói để học.")
    elif silence_ratio >= _LONGEST_SILENCE_WARN_RATIO:
        if level != "fail":
            level = "warn"
        reasons.append(
            f"Hơn nửa clip ({silence_ratio:.0%}) là khoảng lặng liên tục — "
            "cắt bớt phần im lặng đầu/cuối để học chính xác hơn.")

    return AudioQualityResult(
        level=level, reasons=reasons, clip_ratio=clip_ratio, rms=rms,
        longest_silence_ratio=silence_ratio)
