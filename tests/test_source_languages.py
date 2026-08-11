"""Mini-spec V4 (docs/PLAN.md) — mở rộng ngôn ngữ nguồn ASR trong GUI."""
from __future__ import annotations

import pytest

from autodub.languages import SOURCE_LANG_MAP, WHISPER_LANG_MAP, resolve_source_lang
from autodub_gui.dub_constants import SOURCE_LANGS, paraformer_language_mismatch


def test_source_langs_has_at_least_the_four_new_languages():
    keys = {key for _label, key in SOURCE_LANGS}
    assert {"zh-CN", "en-US", "zh-HK", "zh-TW"} <= keys, "4 lựa chọn cũ phải giữ nguyên"
    assert {"ko-KR", "ja-JP", "th-TH", "id-ID"} <= keys, "4 ngôn ngữ mới phải có mặt"


def test_every_gui_source_lang_resolves_to_a_whisper_code():
    """Mỗi lựa chọn trong dropdown GUI phải map được sang code Whisper thật —
    nếu không, chọn ngôn ngữ đó sẽ âm thầm chạy sai (whisper_lang rơi về
    split('-')[0], vẫn đúng vì mọi code ở đây theo đúng dạng BCP-47 xx-YY,
    nhưng assert tường minh ở đây để bắt lỗi ngay nếu ai thêm code sai định
    dạng sau này)."""
    for _label, key in SOURCE_LANGS:
        resolved = resolve_source_lang(key)
        assert resolved == key, f"{key} phải tự ánh xạ về chính nó trong SOURCE_LANG_MAP"
        assert resolved in WHISPER_LANG_MAP, f"thiếu {resolved} trong WHISPER_LANG_MAP"
        whisper_code = WHISPER_LANG_MAP[resolved]
        assert whisper_code == resolved.split("-")[0].lower()


@pytest.mark.parametrize("engine,lang,expected", [
    ("whisper", "zh-CN", False),
    ("whisper", "ko-KR", False),
    ("paraformer", "zh-CN", False),
    ("paraformer", "zh-HK", False),
    ("paraformer", "zh-TW", False),
    ("paraformer", "en-US", True),
    ("paraformer", "ko-KR", True),
    ("paraformer", "ja-JP", True),
    ("paraformer", "th-TH", True),
    ("paraformer", "id-ID", True),
])
def test_paraformer_language_mismatch(engine, lang, expected):
    assert paraformer_language_mismatch(engine, lang) is expected
