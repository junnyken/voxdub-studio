"""Cổng chất lượng tự động — mini-spec V23 (docs/PLAN.md, Phase F).

Hàm THUẦN đọc ``quality_report.json`` đã có sẵn (xem
:meth:`autodub.pipeline.DubPipeline._build_quality_report`) và áp ngưỡng —
KHÔNG tính lại bất kỳ số liệu nào. Tách khỏi CLI để V24 (retry logic)/V25
(watch-folder) gọi lại được trực tiếp mà không cần qua subprocess.

Thiết kế pass/warn/fail: "pass" = video sạch hoàn toàn (không câu nào có
vấn đề); "warn" = có vấn đề nhưng dưới mọi ngưỡng chặn (đáng xem tay,
không chặn); "fail" = ít nhất 1 ngưỡng bị vượt (cần xem lại trước khi coi
là xong).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QualityThresholds:
    max_over_budget_ratio: float = 0.15
    max_speed_fallback_ratio: float = 0.10
    max_postprocess_fallback_ratio: float = 0.10
    max_shift_s: float = 1.0

    @classmethod
    def from_settings(cls, settings) -> "QualityThresholds":
        return cls(
            max_over_budget_ratio=settings.quality_gate_max_over_budget_ratio,
            max_speed_fallback_ratio=settings.quality_gate_max_speed_fallback_ratio,
            max_postprocess_fallback_ratio=settings.quality_gate_max_postprocess_fallback_ratio,
            max_shift_s=settings.quality_gate_max_shift_s,
        )


@dataclass
class QualityVerdict:
    status: str                              # "pass" | "warn" | "fail"
    reasons: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status != "fail"

    def to_dict(self) -> dict:
        return {"status": self.status, "reasons": list(self.reasons)}


def _ratio(count: int, total: int) -> float:
    return (count / total) if total else 0.0


def evaluate(report: dict, thresholds: QualityThresholds | None = None) -> QualityVerdict:
    """Đánh giá 1 ``quality_report.json`` theo ``thresholds``.

    Báo cáo rỗng/thiếu ``summary`` (vd video chưa từng render) → "pass" một
    cách trung thực (không có gì để đánh giá), không phải "fail" ngầm định.
    """
    thresholds = thresholds or QualityThresholds()
    summary = (report or {}).get("summary") or {}
    total = int(summary.get("segments_total", 0) or 0)
    if total == 0:
        return QualityVerdict("pass", [])

    reasons: list[str] = []

    over_budget_ratio = _ratio(int(summary.get("segments_over_budget", 0) or 0), total)
    if over_budget_ratio > thresholds.max_over_budget_ratio:
        reasons.append(
            f"{over_budget_ratio:.0%} câu vượt ngân sách ký tự "
            f"(ngưỡng {thresholds.max_over_budget_ratio:.0%})")

    speed_ratio = _ratio(int(summary.get("segments_speed_fallback", 0) or 0), total)
    if speed_ratio > thresholds.max_speed_fallback_ratio:
        reasons.append(
            f"{speed_ratio:.0%} câu dùng dự phòng tốc độ "
            f"(ngưỡng {thresholds.max_speed_fallback_ratio:.0%})")

    postprocess_ratio = _ratio(int(summary.get("segments_postprocess_fallback", 0) or 0), total)
    if postprocess_ratio > thresholds.max_postprocess_fallback_ratio:
        reasons.append(
            f"{postprocess_ratio:.0%} câu dùng dự phòng hậu kỳ "
            f"(ngưỡng {thresholds.max_postprocess_fallback_ratio:.0%})")

    max_shift_s = float(summary.get("max_shift_s", 0.0) or 0.0)
    if max_shift_s > thresholds.max_shift_s:
        reasons.append(
            f"lệch timeline tối đa {max_shift_s:.2f}s "
            f"(ngưỡng {thresholds.max_shift_s:.2f}s)")

    if reasons:
        return QualityVerdict("fail", reasons)

    segments_ok = int(summary.get("segments_ok", total) or total)
    if segments_ok < total:
        return QualityVerdict("warn", [
            f"{total - segments_ok}/{total} câu có ghi chú (dưới mọi ngưỡng chặn)"])

    return QualityVerdict("pass", [])
