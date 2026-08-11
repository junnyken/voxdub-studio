import os
from autodub.text.srt import generate_srt


def test_generate_srt_original_text(tmp_path):
    segments = [
        {"id": 1, "text": "Hello everyone", "start": 0.5, "end": 3.2, "duration": 2.7},
        {"id": 2, "text": "Welcome to the lesson", "start": 3.5, "end": 6.8, "duration": 3.3},
    ]
    output_path = str(tmp_path / "test.srt")
    result = generate_srt(segments, output_path, text_field="text")

    assert os.path.exists(result)
    content = open(result, encoding="utf-8").read()
    assert "1\n00:00:00,500 --> 00:00:03,200\nHello everyone" in content
    assert "2\n00:00:03,500 --> 00:00:06,800\nWelcome to the lesson" in content


def test_generate_srt_unicode_text(tmp_path):
    segments = [
        {
            "id": 1,
            "text": "你好",
            "text_vi": "Xin chào các bạn",
            "start": 0.0,
            "end": 2.0,
            "duration": 2.0,
        },
    ]
    output_path = str(tmp_path / "test_vi.srt")
    result = generate_srt(segments, output_path, text_field="text_vi")

    content = open(result, encoding="utf-8").read()
    assert "Xin chào các bạn" in content


def test_generate_srt_empty_segments(tmp_path):
    output_path = str(tmp_path / "empty.srt")
    result = generate_srt([], output_path, text_field="text")
    content = open(result, encoding="utf-8").read()
    assert content.strip() == ""


# ----------------------- display splitting (merged segments) --------------- #

from autodub.text.srt import split_for_display, MAX_LINE_CHARS, MAX_LINES_PER_CUE


def test_short_segment_single_cue():
    seg = {"start": 0.0, "end": 2.0, "text_vi": "Xin chào các bạn."}
    cues = split_for_display(seg, "text_vi")
    assert len(cues) == 1
    assert cues[0]["text"] == "Xin chào các bạn."


def test_long_segment_splits_into_cues():
    text = ("Nhưng khi giải mã nội dung bức bích họa, các nhà khoa học phát "
            "hiện một điều kỳ lạ, loài này không giống các loài động vật "
            "khác mà chúng ta từng biết.")
    seg = {"start": 10.0, "end": 17.4, "text_vi": text}
    cues = split_for_display(seg, "text_vi")
    assert len(cues) >= 2
    # every line respects the width cap
    for c in cues:
        for line in c["text"].split("\n"):
            assert len(line) <= MAX_LINE_CHARS
        assert len(c["text"].split("\n")) <= MAX_LINES_PER_CUE
    # cues tile the segment: continuous, ordered, exact ends
    assert cues[0]["start"] == 10.0
    assert cues[-1]["end"] == 17.4
    for a, b in zip(cues, cues[1:]):
        assert a["end"] == b["start"]


def test_cue_time_proportional_to_text():
    text = "ngắn thôi, " + "còn vế sau này thì dài hơn hẳn so với vế trước đó nhiều lắm luôn nhé bạn ơi."
    seg = {"start": 0.0, "end": 10.0, "text_vi": text}
    cues = split_for_display(seg, "text_vi")
    if len(cues) >= 2:
        assert (cues[0]["end"] - cues[0]["start"]) < (cues[-1]["end"] - cues[-1]["start"])


def test_empty_text_no_cues():
    assert split_for_display({"start": 0, "end": 1, "text_vi": " "}, "text_vi") == []


# ---------------------- V19 (docs/PLAN.md, Phase E): ngắt dòng CJK/Thái ---- #
# Bug thật: text.split() coi cả câu tiếng Trung/Nhật (không dấu cách) là 1
# "từ" duy nhất -> _wrap_lines cũ không bao giờ ngắt -> phụ đề tràn khung
# hình. Tiếng Thái chỉ có dấu cách giữa CỤM (không phải từ) -> ngắt thô.

from autodub.text.srt import is_char_wrap_lang


def test_is_char_wrap_lang_true_for_cjk_and_thai():
    assert is_char_wrap_lang("ja") is True
    assert is_char_wrap_lang("zh") is True
    assert is_char_wrap_lang("th") is True


def test_is_char_wrap_lang_false_for_word_spaced_languages():
    for key in ("vi", "en", "es", "id", "pt", "fr", "de", None, ""):
        assert is_char_wrap_lang(key) is False


def test_chinese_long_sentence_without_lang_key_never_wraps_bug_reproduced():
    """Tái tạo đúng bug cũ: KHÔNG truyền lang_key (hành vi trước V19) —
    câu tiếng Trung dài vẫn ra 1 dòng duy nhất, vượt xa MAX_LINE_CHARS."""
    text = "你好，这是一段非常长的中文句子，用来测试没有空格的语言在没有指定语言时是否还会正确换行显示。"
    seg = {"start": 0.0, "end": 8.0, "text_zh": text}
    cues = split_for_display(seg, "text_zh")  # lang_key mặc định None
    # Không lang_key -> coi như ngôn ngữ ngắt-theo-từ -> .split() ra 1 "từ"
    # -> không bao giờ ngắt -> đúng bug đã phát hiện.
    assert len(cues) == 1
    assert "\n" not in cues[0]["text"]
    assert len(cues[0]["text"]) > MAX_LINE_CHARS


def test_chinese_long_sentence_with_lang_key_wraps_by_character():
    text = "你好，这是一段非常长的中文句子，用来测试没有空格的语言在指定语言之后是否可以正确换行显示。"
    seg = {"start": 0.0, "end": 8.0, "text_zh": text}
    cues = split_for_display(seg, "text_zh", lang_key="zh")
    # Đúng theo thiết kế: ngắt được thành nhiều cue/dòng, mỗi dòng nằm trong
    # giới hạn ký tự — không còn 1 dòng tràn khung hình.
    for c in cues:
        for line in c["text"].split("\n"):
            assert len(line) <= MAX_LINE_CHARS
        assert len(c["text"].split("\n")) <= MAX_LINES_PER_CUE
    # Ghép lại đúng nguyên văn (không mất/thêm ký tự khi ngắt).
    rejoined = "".join(c["text"].replace("\n", "") for c in cues)
    assert rejoined == text


def test_japanese_short_sentence_no_spaces_still_wraps_correctly():
    text = "これは日本語のテストです"
    seg = {"start": 0.0, "end": 3.0, "text_ja": text}
    cues = split_for_display(seg, "text_ja", lang_key="ja")
    assert len(cues) == 1
    assert cues[0]["text"] == text


def test_thai_long_sentence_wraps_by_character_not_by_phrase():
    text = "สวัสดีครับ นี่คือประโยคภาษาไทยที่ยาวมากสำหรับทดสอบการตัดบรรทัดที่ไม่มีการเว้นวรรคระหว่างคำจริงๆ"
    seg = {"start": 0.0, "end": 8.0, "text_th": text}
    cues = split_for_display(seg, "text_th", lang_key="th")
    for c in cues:
        for line in c["text"].split("\n"):
            assert len(line) <= MAX_LINE_CHARS


def test_line_words_setting_ignored_for_char_wrap_languages():
    """"Số chữ mỗi dòng" (line_words) không có nghĩa cho CJK — char_wrap
    phải bỏ qua nó, luôn ngắt theo MAX_LINE_CHARS ký tự thay vì "5 từ"."""
    text = "你好，这是一段非常长的中文句子，用来测试线宽设置在中文中应当被忽略而不是继续使用。"
    seg = {"start": 0.0, "end": 8.0, "text_zh": text}
    cues = split_for_display(seg, "text_zh", lang_key="zh", line_words=5)
    for c in cues:
        for line in c["text"].split("\n"):
            assert len(line) <= MAX_LINE_CHARS


def test_cjk_uses_tighter_line_width_than_latin():
    """Chữ CJK render rộng hơn Latin cùng cỡ chữ — ngưỡng ký tự/dòng cho
    char_wrap phải THẤP hơn hẳn MAX_LINE_CHARS (42), không dùng chung."""
    from autodub.text.srt import MAX_LINE_CHARS_CJK
    assert MAX_LINE_CHARS_CJK < MAX_LINE_CHARS
    text = "你" * 30  # 30 ký tự, không dấu câu -> phải ngắt vì > 20
    seg = {"start": 0.0, "end": 5.0, "text_zh": text}
    cues = split_for_display(seg, "text_zh", lang_key="zh")
    for c in cues:
        for line in c["text"].split("\n"):
            assert len(line) <= MAX_LINE_CHARS_CJK


def test_vietnamese_unaffected_by_char_wrap_logic_0_regression():
    text = ("Nhưng khi giải mã nội dung bức bích họa, các nhà khoa học phát "
            "hiện một điều kỳ lạ, loài này không giống các loài động vật "
            "khác mà chúng ta từng biết.")
    seg = {"start": 10.0, "end": 17.4, "text_vi": text}
    without_lang = split_for_display(seg, "text_vi")
    with_lang = split_for_display(seg, "text_vi", lang_key="vi")
    assert without_lang == with_lang
