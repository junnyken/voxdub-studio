"""Mini-spec V37 (docs/PLAN.md, Phase G) — phát hiện điểm nhấn ứng viên
cho hiệu ứng âm thanh, dùng dữ liệu transcript giả (dấu câu/khoảng lặng)."""
from __future__ import annotations

from autodub.media.emphasis_points import detect_emphasis_points


def test_exclamation_mark_produces_a_point():
    segments = [{"id": 1, "text": "Tuyệt vời quá!", "start": 0.0, "end": 2.0}]
    points = detect_emphasis_points(segments)
    assert len(points) == 1
    assert points[0].time == 2.0
    assert "dấu nhấn mạnh" in points[0].reason


def test_question_mark_produces_a_point():
    segments = [{"id": 1, "text": "Bạn có biết không?", "start": 0.0, "end": 2.0}]
    points = detect_emphasis_points(segments)
    assert len(points) == 1


def test_plain_sentence_no_gap_produces_no_point():
    segments = [
        {"id": 1, "text": "Câu bình thường.", "start": 0.0, "end": 2.0},
        {"id": 2, "text": "Câu tiếp theo.", "start": 2.2, "end": 4.0},
    ]
    assert detect_emphasis_points(segments) == []


def test_long_pause_between_segments_produces_a_point():
    segments = [
        {"id": 1, "text": "Câu một.", "start": 0.0, "end": 2.0},
        {"id": 2, "text": "Câu hai, sau khoảng lặng dài.", "start": 5.0, "end": 7.0},
    ]
    points = detect_emphasis_points(segments)
    assert len(points) == 1
    assert points[0].time == 2.0
    assert "Khoảng lặng dài" in points[0].reason


def test_short_pause_below_threshold_produces_no_point():
    segments = [
        {"id": 1, "text": "Câu một.", "start": 0.0, "end": 2.0},
        {"id": 2, "text": "Câu hai, gần ngay sau.", "start": 2.5, "end": 4.0},
    ]
    assert detect_emphasis_points(segments) == []


def test_last_segment_has_no_next_gap_check():
    """Segment cuối cùng không có segment kế tiếp -> không lỗi index."""
    segments = [{"id": 1, "text": "Câu cuối.", "start": 0.0, "end": 2.0}]
    assert detect_emphasis_points(segments) == []


def test_punctuation_and_pause_at_same_point_merge_into_one():
    segments = [
        {"id": 1, "text": "Thật không thể tin được!", "start": 0.0, "end": 2.0},
        {"id": 2, "text": "Sau khoảng lặng dài.", "start": 5.0, "end": 7.0},
    ]
    points = detect_emphasis_points(segments)
    assert len(points) == 1
    assert "dấu nhấn mạnh" in points[0].reason
    assert "Khoảng lặng dài" in points[0].reason


def test_points_sorted_by_time():
    segments = [
        {"id": 1, "text": "Câu 1?", "start": 0.0, "end": 1.0},
        {"id": 2, "text": "Câu 2.", "start": 4.0, "end": 5.0},
        {"id": 3, "text": "Câu 3!", "start": 8.0, "end": 9.0},
    ]
    points = detect_emphasis_points(segments)
    times = [p.time for p in points]
    assert times == sorted(times)


def test_translated_text_field_used_when_specified():
    segments = [{"id": 1, "text": "no punctuation here", "text_vi": "Ôi không!",
                "start": 0.0, "end": 2.0}]
    assert detect_emphasis_points(segments, text_field="text_vi") != []
    assert detect_emphasis_points(segments, text_field="text") == []


def test_empty_segments_returns_empty_list():
    assert detect_emphasis_points([]) == []
