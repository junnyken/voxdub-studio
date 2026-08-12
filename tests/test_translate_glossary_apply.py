"""Mini-spec V27 (docs/PLAN.md, Phase G) — sửa bug glossary không hoạt
động trên nhánh dịch local NLLB (`autodub/text/translate_glossary_apply.py`).
"""
from __future__ import annotations

from autodub.text.translate_glossary_apply import apply_glossary, parse_glossary


# --------------------------------------------------------------------- #
# parse_glossary()

def test_parses_source_equals_target_lines():
    pairs = parse_glossary("AI = Trí tuệ nhân tạo\nSaigon = Sài Gòn")
    assert pairs == [("AI", "Trí tuệ nhân tạo"), ("Saigon", "Sài Gòn")]


def test_skips_blank_lines():
    pairs = parse_glossary("AI = Trí tuệ nhân tạo\n\n\nSaigon = Sài Gòn")
    assert len(pairs) == 2


def test_skips_malformed_lines_without_equals():
    """Dòng lỗi định dạng không được làm hỏng cả danh sách — glossary do
    người dùng tự gõ tay."""
    pairs = parse_glossary("AI = Trí tuệ nhân tạo\nkhông có dấu bằng\nSaigon = Sài Gòn")
    assert pairs == [("AI", "Trí tuệ nhân tạo"), ("Saigon", "Sài Gòn")]


def test_empty_glossary_returns_empty_list():
    assert parse_glossary("") == []
    assert parse_glossary("   \n  \n") == []


def test_strips_whitespace_around_terms():
    pairs = parse_glossary("  AI  =  Trí tuệ nhân tạo  ")
    assert pairs == [("AI", "Trí tuệ nhân tạo")]


def test_handles_multiple_equals_signs_in_target():
    """Thuật ngữ đích có dấu "=" bên trong (hiếm nhưng không được vỡ) —
    chỉ tách ở dấu "=" ĐẦU TIÊN."""
    pairs = parse_glossary("E=MC2 = phương trình E bằng MC bình")
    assert pairs == [("E", "MC2 = phương trình E bằng MC bình")]


# --------------------------------------------------------------------- #
# apply_glossary()

def test_replaces_source_term_kept_untranslated_by_nllb():
    """NLLB thường GIỮ NGUYÊN tên riêng không dịch — thuật ngữ nguồn còn
    nguyên văn trong bản dịch, cần thay bằng thuật ngữ đích."""
    result = apply_glossary(
        "Chúng tôi dùng AI để phân tích.",
        "We use AI to analyze.",
        [("AI", "Trí Tuệ Nhân Tạo")])
    assert "Trí Tuệ Nhân Tạo" in result
    assert "AI" not in result


def test_does_not_replace_when_source_term_not_in_source_text():
    result = apply_glossary(
        "Câu này không có thuật ngữ.", "This sentence has no term.",
        [("AI", "Trí Tuệ Nhân Tạo")])
    assert result == "This sentence has no term."


def test_does_not_double_replace_when_target_already_present():
    """NLLB tình cờ đã dịch đúng thuật ngữ — không thay/chèn thêm lần 2."""
    result = apply_glossary(
        "Chúng tôi dùng AI.", "We use Trí Tuệ Nhân Tạo.",
        [("AI", "Trí Tuệ Nhân Tạo")])
    assert result == "We use Trí Tuệ Nhân Tạo."
    assert result.count("Trí Tuệ Nhân Tạo") == 1


def test_does_not_match_substring_inside_another_word():
    """Guardrail 3: glossary "AI" không được thay bên trong "SAIGON"."""
    result = apply_glossary(
        "Tôi ở Saigon và dùng AI.", "I live in Saigon and use AI.",
        [("AI", "Trí Tuệ Nhân Tạo")])
    assert "Saigon" in result  # không bị phá thành "STrí Tuệ Nhân TạoGON" hay tương tự
    assert "Trí Tuệ Nhân Tạo" in result


def test_case_insensitive_match():
    result = apply_glossary(
        "Dùng ai để xử lý.", "Use ai to process.",
        [("AI", "Trí Tuệ Nhân Tạo")])
    assert "Trí Tuệ Nhân Tạo" in result


def test_term_translated_differently_gets_appended_not_lost():
    """Thuật ngữ nguồn ĐÃ bị NLLB dịch thành từ khác (không giữ nguyên văn)
    — Success Criteria chỉ đòi hỏi thuật ngữ đích XUẤT HIỆN, không đòi hỏi
    thay thế ngữ pháp hoàn hảo (Constraint 2 của V27)."""
    result = apply_glossary(
        "Chúng tôi dùng AI.", "We use artificial intelligence.",
        [("AI", "Trí Tuệ Nhân Tạo")])
    assert "Trí Tuệ Nhân Tạo" in result


def test_cjk_target_term_appended_not_word_boundary_matched():
    """CJK không có ranh giới từ rõ ràng (bài học V19) — chèn thêm thay vì
    cố dùng \\b (sẽ không hoạt động đúng cho CJK)."""
    result = apply_glossary(
        "我们使用AI来分析。", "We use AI to analyze.",
        [("AI", "人工智能")])
    assert "人工智能" in result


def test_empty_glossary_pairs_leaves_translation_untouched_0_regression():
    result = apply_glossary("Câu gốc.", "Original sentence.", [])
    assert result == "Original sentence."


def test_multiple_glossary_terms_all_applied():
    result = apply_glossary(
        "AI và ML đều quan trọng.", "AI and ML are both important.",
        [("AI", "Trí Tuệ Nhân Tạo"), ("ML", "Học Máy")])
    assert "Trí Tuệ Nhân Tạo" in result
    assert "Học Máy" in result
