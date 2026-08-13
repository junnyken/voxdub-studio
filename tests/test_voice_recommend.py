"""Gợi ý giọng đọc theo nội dung video — mini-spec V33, docs/PLAN.md Phase G."""
from __future__ import annotations

from autodub.speech.tts.voice_recommend import recommend_voices
from autodub.speech.tts.voices import Voice


def _catalog():
    return [
        Voice(name="Minh Trang", gender="female", style="tu_nhien"),
        Voice(name="Bảo Long", gender="male", style="tu_nhien"),
        Voice(name="Thu Hà (tin tức)", gender="female", style="tin_tuc"),
        Voice(name="Quốc Anh (kể chuyện)", gender="male", style="doc_truyen"),
        Voice(name="Lan Phương", gender="female", style="tu_nhien"),
    ]


def test_empty_hint_returns_nothing():
    assert recommend_voices({}, _catalog()) == []
    assert recommend_voices(None, _catalog()) == []


def test_hint_with_only_default_style_and_no_gender_returns_nothing():
    """"tu_nhien"/"" không phải tín hiệu đáng tin — gần như mọi giọng đều
    mặc định vậy, khớp theo giá trị này là vô nghĩa (Constraint 2)."""
    assert recommend_voices({"gender": "", "style": "tu_nhien"}, _catalog()) == []
    assert recommend_voices({"gender": "", "style": ""}, _catalog()) == []


def test_empty_catalog_returns_nothing():
    assert recommend_voices({"gender": "male"}, []) == []


def test_gender_only_hint_filters_correctly():
    result = recommend_voices({"gender": "female", "style": ""}, _catalog())
    assert result
    assert all(r.voice.gender == "female" for r in result)
    assert all(r.reasons == ("giọng nữ",) for r in result)


def test_gender_hard_filter_never_recommends_wrong_gender():
    result = recommend_voices({"gender": "male", "style": "tin_tuc"}, _catalog())
    assert result
    assert all(r.voice.gender == "male" for r in result)


def test_style_ranks_matching_voice_first_within_same_gender():
    result = recommend_voices({"gender": "female", "style": "tin_tuc"}, _catalog())
    assert result[0].voice.name == "Thu Hà (tin tức)"
    assert "phong cách tin tức" in result[0].reasons


def test_style_does_not_exclude_voices_without_that_style():
    """Không loại giọng thiếu dữ liệu style — chỉ xếp SAU giọng khớp style,
    vẫn còn trong danh sách đề xuất (đa số giọng thiếu dữ liệu style thật)."""
    result = recommend_voices({"gender": "female", "style": "tin_tuc"}, _catalog(), n=10)
    names = [r.voice.name for r in result]
    assert "Minh Trang" in names
    assert "Lan Phương" in names


def test_no_gender_match_in_catalog_returns_nothing():
    """Đề xuất giới tính không có giọng nào trong catalog khớp -> KHÔNG gợi
    ý sai giới tính, thà im lặng còn hơn (Constraint 5)."""
    only_male = [Voice(name="Bảo Long", gender="male")]
    result = recommend_voices({"gender": "female", "style": ""}, only_male)
    assert result == []


def test_respects_n_limit():
    result = recommend_voices({"gender": "female", "style": ""}, _catalog(), n=1)
    assert len(result) == 1


def test_unknown_gender_value_treated_as_no_signal():
    """Giá trị lạ (không phải male/female) không được coi là tín hiệu —
    tránh crash/lọc sai nếu LLM trả giá trị ngoài enum."""
    result = recommend_voices({"gender": "unknown", "style": "tin_tuc"}, _catalog())
    # gender bị bỏ qua, chỉ còn style làm tín hiệu -> vẫn đề xuất được
    assert result
    assert all(r.reasons == ("phong cách tin tức",) for r in result if r.voice.style == "tin_tuc")


def test_reason_text_property():
    result = recommend_voices({"gender": "female", "style": "tin_tuc"}, _catalog())
    assert result[0].reason_text == "giọng nữ, phong cách tin tức"
