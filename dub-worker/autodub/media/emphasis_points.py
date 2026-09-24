"""Phát hiện "điểm nhấn" ứng viên để đặt hiệu ứng âm thanh — mini-spec V37,
docs/PLAN.md Phase G, Scope B. Heuristic RẺ dựa trên dữ liệu transcript ĐÃ
CÓ SẴN (dấu câu, khoảng lặng giữa câu) — KHÔNG thêm model AI phân tích
cảm xúc/hành động nặng nào (Constraint 3 của V37).

CHỈ trả về DANH SÁCH ỨNG VIÊN, KHÔNG xếp hạng "quan trọng nhất" (Scope B:
"không suy đoán 'quan trọng' — chỉ đưa danh sách candidate cho người dùng
chọn ở GUI") — quyết định điểm nào thật sự đáng chèn SFX là của người dùng.

`PySceneDetect` (phát hiện chuyển cảnh từ hình ảnh) nằm trong Scope B gốc
nhưng CHƯA làm ở PoC này — để dành, xem Remaining Limits trong
docs/TEST_LOG.md mục V37.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Khoảng lặng giữa 2 câu dài hơn ngưỡng này (giây) được coi là điểm nghỉ
#: đáng chú ý — không phải benchmark, chỉ ngưỡng hợp lý để lọc khoảng lặng
#: tự nhiên bình thường (giữa các từ) khỏi khoảng nghỉ thật sự dài.
_LONG_PAUSE_S = 1.5

#: Dấu câu coi là tín hiệu nhấn mạnh — câu hỏi/cảm thán.
_EMPHASIS_PUNCTUATION = ("!", "?", "！", "？")


@dataclass(frozen=True)
class EmphasisPoint:
    """1 điểm ứng viên — `time` tính bằng giây từ đầu video."""

    time: float
    reason: str
    segment_id: int | None = None


def detect_emphasis_points(
    segments: list[dict], text_field: str = "text",
) -> list[EmphasisPoint]:
    """Tìm điểm ứng viên từ dữ liệu transcript đã có (không đọc audio/video
    lại, không cần I/O thêm — `segments` đã có `start`/`end`/text field).

    Trả về danh sách sắp theo thời gian, KHÔNG trùng lặp điểm quá gần nhau
    (dưới 1 giây — 1 câu vừa kết thúc bằng dấu cảm thán vừa đứng trước
    khoảng lặng dài chỉ tính 1 điểm, không phải 2).
    """
    points: list[EmphasisPoint] = []

    for i, seg in enumerate(segments):
        text = str(seg.get(text_field, seg.get("text", ""))).strip()
        end = float(seg.get("end", 0.0))
        if text.endswith(_EMPHASIS_PUNCTUATION):
            points.append(EmphasisPoint(
                time=end, reason="Câu kết bằng dấu nhấn mạnh (! hoặc ?)",
                segment_id=seg.get("id")))

        if i + 1 < len(segments):
            next_start = float(segments[i + 1].get("start", end))
            gap = next_start - end
            if gap >= _LONG_PAUSE_S:
                points.append(EmphasisPoint(
                    time=end, reason=f"Khoảng lặng dài ({gap:.1f}s) trước câu tiếp theo",
                    segment_id=seg.get("id")))

    points.sort(key=lambda p: p.time)
    return _dedupe_close_points(points)


def _dedupe_close_points(points: list[EmphasisPoint], min_gap_s: float = 1.0) -> list[EmphasisPoint]:
    """Gộp các điểm cách nhau dưới `min_gap_s` — giữ điểm ĐẦU TIÊN của cụm
    (đã sắp theo thời gian), gộp lý do lại thành 1 chuỗi đọc được."""
    if not points:
        return []
    result = [points[0]]
    reasons = [points[0].reason]
    for p in points[1:]:
        if p.time - result[-1].time < min_gap_s:
            reasons.append(p.reason)
            result[-1] = EmphasisPoint(
                time=result[-1].time, reason="; ".join(reasons),
                segment_id=result[-1].segment_id)
        else:
            result.append(p)
            reasons = [p.reason]
    return result
