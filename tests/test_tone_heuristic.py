"""Mini-spec V28 (docs/PLAN.md, Phase G) — heuristic văn bản cho tone
local-only (`autodub/text/tone_heuristic.py`). ĐỘ CHÍNH XÁC THẤP HƠN đường
LLM có chủ đích — test chỉ khoá đúng RULES đã viết, không kỳ vọng "đúng"
theo nghĩa hiểu ngôn ngữ tự nhiên.
"""
from __future__ import annotations

from autodub.text.tone_heuristic import (
    VIENEU_STYLES, guess_tone, tone_to_vieneu_style,
)


def test_exclamation_mark_is_excited():
    assert guess_tone("Tuyệt quá!") == "excited"


def test_plain_sentence_is_neutral():
    assert guess_tone("Hôm nay trời đẹp.") == "neutral"


def test_serious_keyword_detected():
    assert guess_tone("Cảnh báo nguy hiểm phía trước.") == "serious"


def test_serious_takes_priority_over_excited_keyword():
    """Câu có cả từ khoá "serious" và dấu "!" -> ưu tiên serious (an toàn
    hơn khi có tín hiệu cảnh báo thật)."""
    assert guess_tone("Cảnh báo! Nguy hiểm phía trước!") == "serious"


def test_excited_keyword_without_exclamation_mark():
    assert guess_tone("Trời ơi, tuyệt vời quá.") == "excited"


def test_all_caps_long_enough_is_excited():
    assert guess_tone("KHÔNG THỂ TIN ĐƯỢC") == "excited"


def test_all_caps_too_short_stays_neutral():
    """Chữ hoa quá ngắn dễ nhầm viết tắt (OK/TV) — không suy đoán bừa."""
    assert guess_tone("OK") == "neutral"


def test_empty_text_is_neutral():
    assert guess_tone("") == "neutral"
    assert guess_tone("   ") == "neutral"


def test_tone_to_style_only_returns_real_vieneu_styles():
    for tone in ("neutral", "excited", "serious"):
        assert tone_to_vieneu_style(tone) in VIENEU_STYLES


def test_unknown_tone_falls_back_to_natural_style_safely():
    assert tone_to_vieneu_style("khong-ton-tai") == "tu_nhien"


def test_neutral_maps_to_tu_nhien():
    assert tone_to_vieneu_style("neutral") == "tu_nhien"


def test_excited_maps_to_doc_truyen():
    assert tone_to_vieneu_style("excited") == "doc_truyen"


def test_serious_maps_to_tin_tuc():
    assert tone_to_vieneu_style("serious") == "tin_tuc"
