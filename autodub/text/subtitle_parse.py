"""Đọc/ghi file phụ đề `.srt`/`.vtt` RỜI — mini-spec V14 (docs/PLAN.md),
dùng cho tính năng "Dịch phụ đề rời" (khác `srt.py`, vốn chỉ SINH file từ
segment nội bộ của pipeline dub, không đọc được file phụ đề từ nguồn khác).

Không phụ thuộc thư viện ngoài — thuần regex, giữ nguyên timestamp GỐC dạng
chuỗi (không parse rồi format lại) trừ khi cần tính CPS cho QA.

Thuật toán theo đúng thiết kế đã kiểm chứng thật ở một công cụ khác (VidGrab,
2026-08, xem FEATURE_SPEC_transcript_translate.md do chủ dự án cung cấp —
mục 4.2), chuyển sang quy ước module của dự án này: khối hỏng bị BỎ QUA (đếm
lại qua ``skipped_block_count``), không làm hỏng cả file; khối NOTE/STYLE/
REGION của VTT không tính là "bỏ qua" (nội dung không phải cue, có chủ đích).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_BOM = "﻿"

_SRT_ARROW_RE = re.compile(
    r"^\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*"
    r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})(.*)$")
_VTT_ARROW_RE = re.compile(
    r"^\s*(\d{1,2}:\d{2}:\d{2}\.\d{1,3}|\d{2}:\d{2}\.\d{1,3})\s*-->\s*"
    r"(\d{1,2}:\d{2}:\d{2}\.\d{1,3}|\d{2}:\d{2}\.\d{1,3})(.*)$")

_TS_RE = re.compile(
    r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{1,2})[.,](\d{1,3})$")


@dataclass
class Cue:
    """1 dòng phụ đề. ``start``/``end`` giữ NGUYÊN chuỗi timestamp gốc —
    không round-trip qua số thực trừ khi cần (QA reading-speed)."""
    index: int
    start: str
    end: str
    text: str


class SubtitleParseError(Exception):
    """Không đọc được file — KHÔNG 1 cue nào hợp lệ (khác với việc BỎ QUA
    từng khối hỏng lẻ tẻ, vẫn cho qua nếu còn cue khác đọc được)."""


def _strip_bom(text: str) -> str:
    return text[1:] if text.startswith(_BOM) else text


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_srt_with_skip_count(text: str) -> tuple[list[Cue], int]:
    """Trả về ``(cues, skipped_block_count)``. Không ném lỗi vì 1 khối hỏng —
    chỉ ném khi KHÔNG khối nào đọc được (xem :class:`SubtitleParseError`)."""
    text = _normalize_newlines(_strip_bom(text))
    blocks = re.split(r"\n\s*\n", text.strip())
    cues: list[Cue] = []
    skipped = 0
    auto_index = 0
    for block in blocks:
        lines = [ln for ln in block.split("\n")]
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            continue

        idx = 0
        # Dòng đầu là số thứ tự thuần thì bỏ qua (tự đánh số lại), không thì
        # rơi thẳng vào dòng mốc thời gian ngay dòng đầu.
        if lines[0].strip().isdigit():
            idx = 1

        if idx >= len(lines):
            skipped += 1
            continue
        m = _SRT_ARROW_RE.match(lines[idx])
        if not m:
            skipped += 1
            continue

        auto_index += 1
        start, end, _rest = m.group(1), m.group(2), m.group(3)
        body = "\n".join(lines[idx + 1:]).strip()
        cues.append(Cue(index=auto_index, start=start, end=end, text=body))

    if not cues:
        raise SubtitleParseError("Không đọc được cue phụ đề hợp lệ nào trong file SRT.")
    return cues, skipped


def parse_vtt_with_skip_count(text: str) -> tuple[list[Cue], int]:
    text = _normalize_newlines(_strip_bom(text))
    blocks = re.split(r"\n\s*\n", text.strip())
    cues: list[Cue] = []
    skipped = 0
    auto_index = 0
    for i, block in enumerate(blocks):
        lines = [ln for ln in block.split("\n")]
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            continue
        if i == 0 and lines[0].strip().upper().startswith("WEBVTT"):
            lines = lines[1:]
            if not lines:
                continue
        first = lines[0].strip().upper()
        if first.startswith(("NOTE", "STYLE", "REGION")):
            continue  # nội dung không phải cue, có chủ đích — không tính "bỏ qua"

        idx = 0
        if idx < len(lines) and not _VTT_ARROW_RE.match(lines[idx]):
            idx = 1  # dòng định danh cue tuỳ chọn đứng trước dòng mốc thời gian
        if idx >= len(lines):
            skipped += 1
            continue
        m = _VTT_ARROW_RE.match(lines[idx])
        if not m:
            skipped += 1
            continue

        auto_index += 1
        start, end, _rest = m.group(1), m.group(2), m.group(3)
        body = "\n".join(lines[idx + 1:]).strip()
        cues.append(Cue(index=auto_index, start=start, end=end, text=body))

    if not cues:
        raise SubtitleParseError("Không đọc được cue phụ đề hợp lệ nào trong file VTT.")
    return cues, skipped


def parse_srt(text: str) -> list[Cue]:
    cues, _skipped = parse_srt_with_skip_count(text)
    return cues


def parse_vtt(text: str) -> list[Cue]:
    cues, _skipped = parse_vtt_with_skip_count(text)
    return cues


def parse_subtitle(text: str, fmt: str) -> tuple[list[Cue], int]:
    """``fmt`` = ``"srt"`` hoặc ``"vtt"``."""
    if fmt == "srt":
        return parse_srt_with_skip_count(text)
    if fmt == "vtt":
        return parse_vtt_with_skip_count(text)
    raise SubtitleParseError(f"Định dạng không hỗ trợ: {fmt!r} (chỉ srt/vtt).")


def serialize_srt(cues: list[Cue]) -> str:
    blocks = [f"{c.index}\n{c.start} --> {c.end}\n{c.text}" for c in cues]
    return "\n\n".join(blocks) + "\n"


def serialize_vtt(cues: list[Cue]) -> str:
    blocks = [f"{c.index}\n{c.start} --> {c.end}\n{c.text}" for c in cues]
    return "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"


def serialize_subtitle(cues: list[Cue], fmt: str) -> str:
    if fmt == "srt":
        return serialize_srt(cues)
    if fmt == "vtt":
        return serialize_vtt(cues)
    raise SubtitleParseError(f"Định dạng không hỗ trợ: {fmt!r} (chỉ srt/vtt).")


# ------------------------------------------------------- QA / thời lượng -- #

def timestamp_to_seconds(ts: str) -> float:
    """Đổi timestamp SRT/VTT (``HH:MM:SS,mmm`` hoặc ``MM:SS.mmm``) ra giây.
    Chỉ dùng cho tính toán QA — không dùng để ghi lại file (giữ chuỗi gốc)."""
    m = _TS_RE.match(ts.strip())
    if not m:
        raise ValueError(f"Timestamp không hợp lệ: {ts!r}")
    h, mnt, sec, frac = m.groups()
    h = int(h) if h else 0
    millis = int((frac + "000")[:3])
    return h * 3600 + int(mnt) * 60 + int(sec) + millis / 1000.0
