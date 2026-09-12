"""Xếp hạng câu đáng sửa nhất trong quality_report (mini-spec V64).

Trang Báo cáo chất lượng đang liệt kê MỌI câu có vấn đề — video 300 câu có
thể ra 40 dòng, và người dùng không biết bắt đầu từ đâu. Thứ họ cần là "sửa
5 câu này trước".

Hàm thuần, tách hẳn khỏi GUI: quy tắc xếp hạng là thứ đáng test kỹ và đáng
chỉnh về sau, không nên chôn trong code dựng bảng.

Thang điểm CỐ Ý thô và giải thích được — không phải công thức tinh vi mà
không ai kiểm chứng nổi. Ba loại lỗi, xếp theo mức khó chịu khi XEM:

1. Chồng tiếng: hai câu nói đè lên nhau — nghe là biết ngay, tệ nhất.
2. Đọc nhanh (atempo): giọng bị ép tăng tốc để vừa chỗ; >1.3 là nghe rõ méo.
3. Dài quá chỗ trống: chỉ ảnh hưởng nếu câu bị cắt/đọc vội, nhẹ nhất.
"""
from __future__ import annotations

#: Trọng số mỗi loại lỗi — số nào lớn hơn nghĩa là "khó chịu hơn khi xem".
W_OVERLAP = 10.0        # mỗi giây chồng tiếng
W_ATEMPO = 8.0          # mỗi 0.1 vượt mức 1.0
W_OVER_BUDGET = 0.05    # mỗi ký tự vượt


def severity(segment: dict) -> float:
    """Điểm "đáng sửa" của một câu. Càng cao càng nên sửa trước."""
    score = 0.0

    overlap = segment.get("overlap_prev_s")
    if isinstance(overlap, (int, float)) and overlap > 0:
        score += float(overlap) * W_OVERLAP

    atempo = segment.get("atempo")
    if isinstance(atempo, (int, float)) and atempo > 1.0:
        score += (float(atempo) - 1.0) * 10 * W_ATEMPO

    over = segment.get("over_budget_chars")
    if isinstance(over, (int, float)) and over > 0:
        score += float(over) * W_OVER_BUDGET

    return round(score, 3)


def describe(segment: dict) -> str:
    """Một câu tiếng Việt nói rõ câu này bị gì — để người dùng quyết có sửa không."""
    parts = []
    overlap = segment.get("overlap_prev_s")
    if isinstance(overlap, (int, float)) and overlap > 0:
        parts.append(f"chồng tiếng {overlap:.2f}s")
    atempo = segment.get("atempo")
    if isinstance(atempo, (int, float)) and atempo > 1.0:
        parts.append(f"đọc nhanh ×{atempo:.2f}")
    over = segment.get("over_budget_chars")
    if isinstance(over, (int, float)) and over > 0:
        parts.append(f"dài hơn chỗ trống {int(over)} ký tự")
    return ", ".join(parts) or "không rõ"


def worst_segments(segments: list[dict], limit: int = 5) -> list[dict]:
    """``limit`` câu đáng sửa nhất, kèm ``severity``/``issue`` đã tính sẵn.

    Câu KHÔNG có lỗi nào (điểm 0) bị loại hẳn — đưa vào danh sách "đáng sửa
    nhất" một câu không có gì để sửa là làm người dùng mất thời gian vô ích.

    Thứ tự ổn định: cùng điểm thì theo số câu tăng dần, để hai lần mở cùng
    một báo cáo không ra hai thứ tự khác nhau.
    """
    scored = []
    for seg in segments:
        score = severity(seg)
        if score <= 0:
            continue
        scored.append({**seg, "severity": score, "issue": describe(seg)})
    scored.sort(key=lambda s: (-s["severity"], _seg_id(s)))
    return scored[:limit]


def _seg_id(segment: dict) -> float:
    raw = segment.get("id")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float("inf")
