"""Mini-spec V8 (docs/PLAN.md) — proof-of-concept đa ngôn ngữ đích.

Phạm vi ĐÃ verify trong đợt này: registry TARGETS + capcut_catalog đọc
đúng theo ngôn ngữ + CapCut TTS engine thật sự tạo được audio tiếng Anh
(test riêng, có gọi mạng thật — xem docs/TEST_LOG.md mục V8 cho log đầy
đủ, không lặp lại ở đây để không phụ thuộc mạng khi chạy CI thường xuyên).

Phạm vi đóng tiếp ở mini-spec V11 (xem docs/PLAN.md/TEST_LOG.md mục V11):
GUI chọn ngôn ngữ đích, voices.catalog() target-aware, audit đầy đủ
timing/ass_karaoke/editor.py + fix bug align.py hardcode language="vi" —
test riêng cho các phần đó nằm ở tests/test_voices_target_language.py và
tests/test_align_language.py, không lặp lại ở đây.
"""
from __future__ import annotations

from autodub.languages import TARGETS, get_target
from autodub.speech.tts import capcut_catalog


def test_vietnamese_target_unchanged():
    """0 regression — giá trị TargetLang("vi") phải giữ nguyên y hệt trước V8."""
    vi = get_target("vi")
    assert vi.code == "vi-VN"
    assert vi.text_field == "text_vi"
    assert vi.transcript_name == "transcript_vi.json"
    assert vi.folder_suffix == "_vi"


def test_english_target_registered():
    en = get_target("en")
    assert en.code == "en-US"
    assert en.text_field == "text_en"
    assert en.transcript_name == "transcript_en.json"
    assert en.folder_suffix == "_en"


def test_targets_registry_has_exactly_vi_and_en():
    assert set(TARGETS) == {"vi", "en"}


# ------------------------------------------------- capcut_catalog theo lang --

def test_entries_default_lang_matches_old_behavior():
    """Không truyền lang -> đúng hành vi cũ (vi-VN), 0 regression."""
    vi_entries = capcut_catalog.entries()
    assert len(vi_entries) > 0
    for e in vi_entries:
        assert e["voice_type"]
        assert e["resource_id"]


def test_entries_en_us_returns_different_voices_than_vi():
    vi_entries = capcut_catalog.entries(lang="vi-VN")
    en_entries = capcut_catalog.entries(lang="en-US")
    assert len(en_entries) > 0, "Voice.json phải có giọng en-US (đã xác nhận thật)"
    vi_names = {e["name"] for e in vi_entries}
    en_names = {e["name"] for e in en_entries}
    assert not (vi_names & en_names), "tên giọng vi/en không được trùng nhau"


def test_names_and_lookup_respect_lang_param():
    en_names = capcut_catalog.names(lang="en-US")
    assert en_names, "phải có ít nhất 1 giọng en-US"
    some_name = next(iter(en_names))
    assert capcut_catalog.lookup(some_name, lang="en-US") is not None
    # Tên giọng en-US không được lookup thấy trong catalog vi-VN (mặc định).
    assert capcut_catalog.lookup(some_name) is None


def test_unknown_lang_returns_empty_not_error():
    assert capcut_catalog.entries(lang="xx-XX") == []
