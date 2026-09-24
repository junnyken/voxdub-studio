"""Dịch 1 file phụ đề rời (`.srt`/`.vtt`) — mini-spec V14 (docs/PLAN.md).

Orchestrate: đọc file → dịch text từng cue (local NLLB qua
:func:`autodub.text.translate_local.run_local_worker`, hoặc SaaS qua
:meth:`autodub.saas_client.SaasClient.translate_subtitle`) → ghép lại GIỮ
NGUYÊN timestamp gốc (đúng nguyên tắc `subtitle_parse.py`) → ghi ra file MỚI
`<tên>_<mã đích>.<đuôi gốc>` (Constraint 4 của V14 — không bao giờ ghi đè).

Khác pipeline dub: không dùng :func:`ensure_terminal_punct` (chuẩn hoá cho
TTS — ép dấu chấm cuối câu, cắt dấu phẩy/gạch ngang cuối dòng) vì đây là
phụ đề THUẦN ĐỌC, không có TTS nào đọc theo — ép dấu câu kiểu lồng tiếng sẽ
làm sai văn bản gốc của người dùng.

Ngôn ngữ = mã FLORES-200 (vd `"vie_Latn"`) xuyên suốt, KHÔNG dùng
`TargetLang`/`LANG_TO_FLORES` hẹp của pipeline dub — xem Constraint 1 của V14
và `flores200.py`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from autodub.progress import ProgressReporter
from autodub.text.flores200 import display_name, is_known_flores_code
from autodub.text.subtitle_parse import Cue, parse_subtitle, serialize_subtitle
from autodub.utils import setup_logging

logger = setup_logging("autodub.subtitle_translate")


class SubtitleTranslateError(Exception):
    """Không dịch được file phụ đề (đầu vào hỏng hoặc mã ngôn ngữ không hợp lệ).

    Lỗi PHÁT SINH TỪ chính bước dịch (worker local crash, máy chủ SaaS lỗi)
    KHÔNG bọc ở đây — :class:`autodub.text.translate_local.LocalTranslateError`
    và :class:`autodub.saas_client.SaasError` bay thẳng ra, để bên gọi phân
    biệt được nguyên nhân (đầu vào sai vs. lỗi vận hành bước dịch).
    """


@dataclass
class SubtitleTranslateResult:
    output_path: str
    cue_count: int
    skipped_block_count: int
    credit_charged: int = 0
    balance_after: int = 0


def _detect_format(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext not in ("srt", "vtt"):
        raise SubtitleTranslateError(
            f"Định dạng file không hỗ trợ: {ext!r} (chỉ .srt/.vtt).")
    return ext


def _output_path(input_path: str, target_flores: str, fmt: str) -> str:
    base, _ = os.path.splitext(input_path)
    return f"{base}_{target_flores}.{fmt}"


def _validate_codes(source_flores: str, target_flores: str) -> None:
    for code in (source_flores, target_flores):
        if not is_known_flores_code(code):
            raise SubtitleTranslateError(
                f"Mã ngôn ngữ FLORES-200 không hợp lệ: {code!r}.")
    if source_flores == target_flores:
        raise SubtitleTranslateError(
            "Ngôn ngữ nguồn và đích giống nhau — không có gì để dịch.")


def _read_and_parse(input_path: str, fmt: str) -> tuple[list[Cue], int]:
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()
    return parse_subtitle(text, fmt)


def _write_translated(input_path: str, target_flores: str, fmt: str,
                       cues: list[Cue], by_id: dict) -> str:
    translated = [
        Cue(index=c.index, start=c.start, end=c.end,
            text=str(by_id.get(c.index, c.text)).strip() or c.text)
        for c in cues
    ]
    out_path = _output_path(input_path, target_flores, fmt)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(serialize_subtitle(translated, fmt))
    return out_path


def translate_subtitle_file_local(
    input_path: str, source_flores: str, target_flores: str, settings,
    reporter: ProgressReporter | None = None,
) -> SubtitleTranslateResult:
    """Dịch local (NLLB offline) — không cần `saas_client.is_configured()`
    (Constraint 5 của V14, giữ triết lý offline-first)."""
    _validate_codes(source_flores, target_flores)
    fmt = _detect_format(input_path)
    cues, skipped = _read_and_parse(input_path, fmt)

    from autodub.text.translate_local import run_local_worker

    items = [(c.index, c.text) for c in cues]
    by_id = run_local_worker(items, source_flores, target_flores, settings,
                              reporter, progress_step="subtitle_translate")
    out_path = _write_translated(input_path, target_flores, fmt, cues, by_id)

    logger.info(f"Dịch phụ đề local xong: {len(cues)} cue -> {out_path}")
    return SubtitleTranslateResult(output_path=out_path, cue_count=len(cues),
                                    skipped_block_count=skipped)


def translate_subtitle_file_saas(
    input_path: str, source_flores: str, target_flores: str,
    *, job_id: str, hold_id: str | None = None,
) -> SubtitleTranslateResult:
    """Dịch qua SaaS (LLM thật qua control_server, endpoint riêng
    `/v1/ai/translate-subtitle`) — cần `saas_client.is_configured()`, tốn Vox
    theo `credit.cost.segment.autotranslate` mỗi dòng (Constraint 4 của V14)."""
    _validate_codes(source_flores, target_flores)
    fmt = _detect_format(input_path)
    cues, skipped = _read_and_parse(input_path, fmt)

    from autodub.saas_client import get_client
    from autodub.saas_retry import call_with_retry

    items = [{"id": c.index, "text": c.text} for c in cues]
    client = get_client()
    # mini-spec V16 (docs/PLAN.md, Phase E) — 1 lượt gọi DUY NHẤT cho cả
    # file trước đây (không retry): 1 chớp mạng làm hỏng cả file dù job_id
    # ổn định theo nội dung (idempotent, máy chủ không tính phí 2 lần) —
    # an toàn để thử lại nguyên văn.
    data = call_with_retry(
        lambda: client.translate_subtitle(
            items, job_id=job_id, source_flores=source_flores,
            target_flores=target_flores, source_name=display_name(source_flores),
            target_name=display_name(target_flores), hold_id=hold_id),
        label="Dịch phụ đề qua SaaS")
    by_id = {seg.get("id"): seg.get("text", "") for seg in data.get("segments", [])}
    out_path = _write_translated(input_path, target_flores, fmt, cues, by_id)

    logger.info(f"Dịch phụ đề SaaS xong: {len(cues)} cue -> {out_path}")
    return SubtitleTranslateResult(
        output_path=out_path, cue_count=len(cues), skipped_block_count=skipped,
        credit_charged=int(data.get("creditCharged") or 0),
        balance_after=int(data.get("balanceAfter") or 0))
