"""Mini-spec V64 — xếp hạng câu đáng sửa nhất.

Trang Báo cáo chất lượng vốn liệt kê MỌI câu có vấn đề — video 300 câu ra 40
dòng và người dùng không biết bắt đầu từ đâu. Quy tắc xếp hạng ở đây trả lời
đúng câu hỏi thật của họ: "sửa cái nào trước?".

Test cả quy tắc lẫn những chỗ dễ hỏng âm thầm: câu không có lỗi lọt vào danh
sách, thứ tự đảo lộn giữa hai lần mở, dữ liệu rác làm nổ.

Chạy:  pytest tests/test_quality_rank.py
"""
from __future__ import annotations

from autodub.quality_rank import describe, severity, worst_segments


def test_overlapping_speech_outranks_a_slightly_long_line():
    """Chồng tiếng nghe là biết ngay; dài hơn chỗ trống vài ký tự thì không."""
    overlap = {"id": 1, "overlap_prev_s": 0.5}
    slightly_long = {"id": 2, "over_budget_chars": 10}

    assert severity(overlap) > severity(slightly_long)


def test_faster_speech_scores_higher_than_slower_speech():
    assert severity({"atempo": 1.5}) > severity({"atempo": 1.1})


def test_clean_segment_scores_zero():
    assert severity({"id": 1, "text": "câu bình thường"}) == 0.0
    assert severity({"id": 2, "atempo": 1.0}) == 0.0, "đúng 1.0 là không ép tốc độ"


def test_clean_segments_never_appear_in_the_worst_list():
    """Đưa một câu không có gì để sửa vào danh sách «đáng sửa nhất» là làm
    người dùng mất thời gian vô ích."""
    segments = [{"id": 1}, {"id": 2, "atempo": 1.0}, {"id": 3, "overlap_prev_s": 0.4}]

    worst = worst_segments(segments)

    assert [s["id"] for s in worst] == [3]


def test_limit_is_respected():
    segments = [{"id": i, "overlap_prev_s": i * 0.1} for i in range(1, 20)]

    assert len(worst_segments(segments, limit=5)) == 5


def test_order_is_stable_for_equal_scores():
    """Hai lần mở cùng một báo cáo phải ra cùng thứ tự — nếu không, người
    dùng tưởng dữ liệu đang đổi."""
    segments = [{"id": 9, "overlap_prev_s": 0.3}, {"id": 2, "overlap_prev_s": 0.3},
                {"id": 5, "overlap_prev_s": 0.3}]

    first = [s["id"] for s in worst_segments(segments)]
    second = [s["id"] for s in worst_segments(list(reversed(segments)))]

    assert first == second == [2, 5, 9], "cùng điểm thì theo số câu tăng dần"


def test_garbage_values_do_not_crash():
    """quality_report do pipeline ghi, nhưng file cũ/hỏng vẫn phải đọc được."""
    segments = [
        {"id": "x", "overlap_prev_s": "nhiều"},
        {"id": None, "atempo": None},
        {"id": 3, "over_budget_chars": "12"},
        {},
    ]

    worst = worst_segments(segments)

    assert worst == [], "giá trị không phải số thì bỏ qua, không nổ"


def test_description_lists_every_problem_found():
    text = describe({"overlap_prev_s": 0.25, "atempo": 1.35,
                     "over_budget_chars": 12})

    assert "chồng tiếng" in text
    assert "đọc nhanh" in text
    assert "dài hơn chỗ trống" in text


def test_description_of_a_clean_segment_is_explicit():
    assert describe({"id": 1}) == "không rõ"


def test_worst_segments_keeps_original_fields_for_display():
    """Thẻ trên GUI cần `text` để hiện nội dung câu — không được rơi mất."""
    worst = worst_segments([{"id": 7, "atempo": 1.4, "text": "xin chào"}])

    assert worst[0]["text"] == "xin chào"
    assert worst[0]["severity"] > 0
    assert "đọc nhanh" in worst[0]["issue"]
