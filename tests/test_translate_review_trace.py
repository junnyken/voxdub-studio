"""Mini-spec V29 (docs/PLAN.md, Phase G) — lộ trace của
`review_translations()` (`autodub/text/translate_review.py`) qua tham số
TUỲ CHỌN ``trace_out``.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from autodub.config import Settings
from autodub.languages import get_target
from autodub.text.translate_review import review_translations


def _settings():
    s = Settings()
    s.translate_review = True
    return s


def _segment(seg_id, src, translated, duration=10.0):
    # duration=10.0 -> max_chars=125 (effective_cps mặc định 12.5) — đủ
    # rộng để câu tiếng Việt ngắn bình thường không vô tình bị cờ
    # "over_budget", chỉ những câu ta CHỦ ĐÍCH kiểm tra mới bị cờ.
    return {"id": seg_id, "text": src, "text_vi": translated, "duration": duration}


def _clean_segment(seg_id):
    """1 câu chắc chắn KHÔNG bị cờ bởi bất kỳ rule nào — dùng để pha loãng
    tỉ lệ câu bị cờ xuống dưới ngưỡng 35% khi cần ép server thật sự được gọi."""
    return _segment(seg_id, "你好朋友", "Xin chào bạn.")


def test_trace_out_none_by_default_no_crash_0_regression():
    """Không truyền trace_out (mọi caller cũ) -> hành vi y hệt trước V29."""
    target = get_target("vi")
    segments = [_segment(1, "你好", "Xin chào.")]
    result = review_translations(segments, target, "zh-CN", _settings())
    assert result == segments  # không có câu nào bị cờ, không đụng gì


def test_trace_records_entry_for_each_flagged_segment(monkeypatch):
    target = get_target("vi")
    # "too_short": bản dịch < 25% độ dài nguồn (nguồn > 20 ký tự). Thêm 3
    # câu sạch để tỉ lệ bị cờ (1/4 = 25%) dưới ngưỡng bail-out 35% — server
    # thật sự được gọi.
    long_source = "这是一个很长很长的句子用来测试翻译审核功能是否正常工作"
    segments = [_segment(1, long_source, "Ngắn."),
               _clean_segment(2), _clean_segment(3), _clean_segment(4)]

    fake_client = MagicMock()
    fake_client.review.return_value = [{"id": 1, target.text_field: "Bản dịch đã sửa dài hơn."}]
    monkeypatch.setattr("autodub.text.translate_review.get_client", lambda: fake_client)

    trace = []
    result = review_translations(segments, target, "zh-CN", _settings(),
                                 trace_out=trace)

    assert len(trace) == 1
    assert trace[0]["id"] == 1
    assert trace[0]["reason"] == "too_short"
    assert trace[0]["before"] == "Ngắn."
    assert trace[0]["after"] == "Bản dịch đã sửa dài hơn."
    assert trace[0]["improved"] is True
    assert result[0][target.text_field] == "Bản dịch đã sửa dài hơn."


def test_trace_records_not_improved_when_server_does_not_fix(monkeypatch):
    target = get_target("vi")
    long_source = "这是一个很长很长的句子用来测试翻译审核功能是否正常工作"
    segments = [_segment(1, long_source, "Ngắn."),
               _clean_segment(2), _clean_segment(3), _clean_segment(4)]

    fake_client = MagicMock()
    fake_client.review.return_value = []  # máy chủ không sửa được câu nào
    monkeypatch.setattr("autodub.text.translate_review.get_client", lambda: fake_client)

    trace = []
    review_translations(segments, target, "zh-CN", _settings(), trace_out=trace)

    assert len(trace) == 1
    assert trace[0]["improved"] is False
    assert trace[0]["after"] == trace[0]["before"] == "Ngắn."


def test_no_flagged_segments_leaves_trace_empty():
    target = get_target("vi")
    segments = [_segment(1, "你好", "Xin chào bạn, hôm nay trời rất đẹp.")]
    trace = []
    review_translations(segments, target, "zh-CN", _settings(), trace_out=trace)
    assert trace == []


def test_too_many_flagged_segments_still_traces_but_skips_server_call(monkeypatch):
    """Constraint thật của module: >35% câu bị cờ -> bỏ qua gọi máy chủ
    hoàn toàn (đốt Vox vô ích) — nhưng V29 vẫn phải trace ĐÚNG các câu bị
    cờ, kể cả khi không gọi server."""
    target = get_target("vi")
    long_source = "这是一个很长很长的句子用来测试翻译审核功能是否正常工作"
    # 4/4 câu bị cờ = 100% > 35% -> bail-out sớm, KHÔNG gọi client.review()
    segments = [_segment(i, long_source, "Ngắn.") for i in range(1, 5)]

    fake_client = MagicMock()
    monkeypatch.setattr("autodub.text.translate_review.get_client", lambda: fake_client)

    trace = []
    result = review_translations(segments, target, "zh-CN", _settings(),
                                 trace_out=trace)

    fake_client.review.assert_not_called()
    assert len(trace) == 4
    assert all(t["improved"] is False for t in trace)
    assert result == segments


def test_untranslated_english_segment_flagged_and_retried(monkeypatch):
    """Bug thật (2026-08-15): nguồn không phải tiếng Trung, câu dịch thiếu
    (`_merge()` giữ y nguyên bản gốc) không có ký tự CJK để `contains_cjk`
    bắt được — phải bắt bằng tín hiệu "dịch == gốc" thay vì chỉ dựa vào CJK."""
    target = get_target("vi")
    long_source = "This is a fairly long English sentence used to test the review pass."
    segments = [_segment(1, long_source, long_source),  # "dịch" = y nguyên gốc
               _clean_segment(2), _clean_segment(3), _clean_segment(4)]

    fake_client = MagicMock()
    fake_client.review.return_value = [
        {"id": 1, target.text_field: "Đây là một câu tiếng Anh khá dài."}]
    monkeypatch.setattr("autodub.text.translate_review.get_client", lambda: fake_client)

    trace = []
    result = review_translations(segments, target, "en-US", _settings(),
                                 trace_out=trace)

    assert len(trace) == 1
    assert trace[0]["id"] == 1
    assert trace[0]["reason"] == "untranslated"
    assert result[0][target.text_field] == "Đây là một câu tiếng Anh khá dài."


def test_short_identical_segment_not_flagged_untranslated():
    """Câu ngắn (<=5 ký tự) giữ nguyên gốc không bị cờ nhầm — vd tên riêng/số
    hợp lệ giữ nguyên qua bản dịch thật, không phải dấu hiệu dịch thiếu."""
    target = get_target("vi")
    segments = [_segment(1, "2026", "2026")]
    trace = []
    result = review_translations(segments, target, "en-US", _settings(),
                                 trace_out=trace)
    assert trace == []
    assert result == segments


def test_review_disabled_returns_early_no_trace():
    target = get_target("vi")
    settings = Settings()
    settings.translate_review = False
    segments = [_segment(1, "你好", "Ngắn.")]
    trace = []
    result = review_translations(segments, target, "zh-CN", settings, trace_out=trace)
    assert result == segments
    assert trace == []
