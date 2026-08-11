"""Mini-spec V14 (docs/PLAN.md) — autodub.text.subtitle_parse: đọc/ghi
.srt/.vtt RỜI cho tính năng "Dịch phụ đề rời". Thuật toán tham khảo từ
FEATURE_SPEC_transcript_translate.md (VidGrab) — test các ca biên đã biết
gây lỗi thật ở công cụ gốc: BOM, khối hỏng, khối NOTE/STYLE của VTT, cue
nhiều dòng.
"""
from __future__ import annotations

import pytest

from autodub.text.subtitle_parse import (
    Cue,
    SubtitleParseError,
    parse_srt,
    parse_srt_with_skip_count,
    parse_subtitle,
    parse_vtt,
    parse_vtt_with_skip_count,
    serialize_srt,
    serialize_subtitle,
    serialize_vtt,
    timestamp_to_seconds,
)

# ------------------------------------------------------------------ SRT -- #

SRT_BASIC = """1
00:00:01,000 --> 00:00:04,000
Xin chào các bạn.

2
00:00:04,500 --> 00:00:07,200
Hôm nay trời đẹp.
"""


def test_parse_srt_basic():
    cues = parse_srt(SRT_BASIC)
    assert len(cues) == 2
    assert cues[0] == Cue(1, "00:00:01,000", "00:00:04,000", "Xin chào các bạn.")
    assert cues[1].text == "Hôm nay trời đẹp."


def test_parse_srt_strips_bom():
    bom = "﻿" + SRT_BASIC
    cues = parse_srt(bom)
    assert len(cues) == 2
    assert cues[0].text == "Xin chào các bạn."


def test_parse_srt_normalizes_crlf():
    crlf = SRT_BASIC.replace("\n", "\r\n")
    cues = parse_srt(crlf)
    assert len(cues) == 2


def test_parse_srt_multiline_cue_preserved():
    text = "1\n00:00:01,000 --> 00:00:04,000\nDòng một\nDòng hai\n"
    cues = parse_srt(text)
    assert cues[0].text == "Dòng một\nDòng hai"


def test_parse_srt_reindexes_sequentially_ignoring_original_numbers():
    text = "5\n00:00:01,000 --> 00:00:02,000\nA\n\n99\n00:00:02,000 --> 00:00:03,000\nB\n"
    cues = parse_srt(text)
    assert [c.index for c in cues] == [1, 2]


def test_parse_srt_malformed_block_is_skipped_not_fatal():
    text = (SRT_BASIC + "\n3\nkhông phải mốc thời gian\nrác\n")
    cues, skipped = parse_srt_with_skip_count(text)
    assert len(cues) == 2, "khối hỏng phải bị bỏ qua, không làm hỏng cả file"
    assert skipped == 1


def test_parse_srt_all_blocks_malformed_raises():
    with pytest.raises(SubtitleParseError):
        parse_srt("1\nkhông có mốc thời gian nào\nrác\n")


def test_parse_srt_dot_decimal_separator_also_accepted():
    text = "1\n00:00:01.000 --> 00:00:04.000\nText\n"
    cues = parse_srt(text)
    assert len(cues) == 1


# ------------------------------------------------------------------ VTT -- #

VTT_BASIC = """WEBVTT

1
00:00:01.000 --> 00:00:04.000
Hello there.

2
00:00:04.500 --> 00:00:07.200
Nice weather today.
"""


def test_parse_vtt_basic_strips_header():
    cues = parse_vtt(VTT_BASIC)
    assert len(cues) == 2
    assert cues[0].text == "Hello there."


def test_parse_vtt_short_mmss_timestamp():
    text = "WEBVTT\n\n00:01.000 --> 00:04.000\nHi\n"
    cues = parse_vtt(text)
    assert len(cues) == 1
    assert cues[0].start == "00:01.000"


def test_parse_vtt_note_style_region_blocks_not_counted_as_skipped():
    text = (
        "WEBVTT\n\n"
        "NOTE this is a comment, not a cue\n\n"
        "STYLE\n::cue { color: white; }\n\n"
        "1\n00:00:01.000 --> 00:00:04.000\nReal cue\n"
    )
    cues, skipped = parse_vtt_with_skip_count(text)
    assert len(cues) == 1
    assert skipped == 0, "NOTE/STYLE không phải cue — không được tính là khối hỏng"


def test_parse_vtt_cue_identifier_line_before_arrow():
    text = "WEBVTT\n\nintro-cue\n00:00:01.000 --> 00:00:04.000\nWith identifier\n"
    cues = parse_vtt(text)
    assert len(cues) == 1
    assert cues[0].text == "With identifier"


def test_parse_vtt_malformed_block_skipped():
    text = VTT_BASIC + "\nnot-a-timestamp-block\ngarbage\n"
    cues, skipped = parse_vtt_with_skip_count(text)
    assert len(cues) == 2
    assert skipped == 1


def test_parse_subtitle_dispatches_by_format():
    cues, _ = parse_subtitle(SRT_BASIC, "srt")
    assert len(cues) == 2
    cues, _ = parse_subtitle(VTT_BASIC, "vtt")
    assert len(cues) == 2
    with pytest.raises(SubtitleParseError):
        parse_subtitle("x", "ass")


# ------------------------------------------------------------ serialize -- #

def test_serialize_srt_round_trip():
    cues = parse_srt(SRT_BASIC)
    out = serialize_srt(cues)
    reparsed = parse_srt(out)
    assert reparsed == cues


def test_serialize_vtt_has_webvtt_header():
    cues = parse_vtt(VTT_BASIC)
    out = serialize_vtt(cues)
    assert out.startswith("WEBVTT\n")
    reparsed = parse_vtt(out)
    assert reparsed == cues


def test_serialize_subtitle_dispatches_by_format():
    cues = parse_srt(SRT_BASIC)
    assert serialize_subtitle(cues, "srt") == serialize_srt(cues)
    assert serialize_subtitle(cues, "vtt") == serialize_vtt(cues)


# --------------------------------------------------------- timestamp_to_seconds -- #

def test_timestamp_to_seconds_hhmmss_comma():
    assert timestamp_to_seconds("00:01:02,500") == pytest.approx(62.5)


def test_timestamp_to_seconds_mmss_dot():
    assert timestamp_to_seconds("01:02.500") == pytest.approx(62.5)


def test_timestamp_to_seconds_invalid_raises():
    with pytest.raises(ValueError):
        timestamp_to_seconds("not-a-timestamp")
