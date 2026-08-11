"""Language definitions: dubbing targets and source-language code maps."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetLang:
    """Static spec of a dubbing target language.

    Vietnamese is the only supported dub target.
    """
    key: str              # short key: "vi"
    code: str             # BCP-47 code: "vi-VN"
    iso639_2: str         # ISO 639-2 code used for MP4 subtitle track metadata
    name: str             # English name used in prompts/hints
    text_field: str       # translated-text field in transcript JSON
    transcript_name: str  # translated transcript filename
    srt_name: str         # translated SRT filename
    audio_name: str       # merged dub audio filename
    folder_suffix: str    # suffix for timestamped work dirs


TARGETS: dict[str, TargetLang] = {
    "vi": TargetLang(
        key="vi",
        code="vi-VN",
        iso639_2="vie",
        name="Vietnamese",
        text_field="text_vi",
        transcript_name="transcript_vi.json",
        srt_name="transcript_vi.srt",
        audio_name="audio_vi_full.wav",
        folder_suffix="_vi",
    ),
    # Mini-spec V8 (docs/PLAN.md) — engine ban đầu chỉ PROOF OF CONCEPT.
    # Mini-spec V11 đóng gap: voices.catalog()/GUI đã target-aware,
    # timing/ass_karaoke/editor.py đã audit hết + fix bug align.py hardcode
    # language="vi" — live-verify 2 lượt pipeline thật (target=en, không
    # crash, xem docs/TEST_LOG.md mục V11). Hạn chế còn lại (chất lượng
    # dịch NLLB khi ASR nhiễu, chưa video dài) ghi trong "Remaining Limits"
    # mục V11 — không phải giả định tiếng Việt còn sót.
    "en": TargetLang(
        key="en",
        code="en-US",
        iso639_2="eng",
        name="English",
        text_field="text_en",
        transcript_name="transcript_en.json",
        srt_name="transcript_en.srt",
        audio_name="audio_en_full.wav",
        folder_suffix="_en",
    ),
}


def get_target(key: str) -> TargetLang:
    """Resolve a target language from a short key or BCP-47 code."""
    k = key.strip().lower()
    if k in TARGETS:
        return TARGETS[k]
    for t in TARGETS.values():
        if t.code.lower() == k:
            return t
    raise ValueError(f"Unknown target language: {key!r} (supported: {', '.join(TARGETS)})")


# Source-language shorthand → BCP-47 locale (for ASR của video GỐC).
#
# ko-KR/ja-JP/th-TH/id-ID thêm ở mini-spec V4 (docs/PLAN.md) — CHỈ mở rộng
# NGUỒN (ASR), không đụng TARGETS (đích luôn là tiếng Việt). Whisper vốn đã
# nhận mọi language code này (chỉ bị GUI giới hạn cứng 4 lựa chọn trước đây),
# nhưng chất lượng ASR thực tế của 4 ngôn ngữ mới CHƯA được live-verify bằng
# video thật trong đợt này (không có audio/GPU trong môi trường build) — xem
# docs/TEST_LOG.md mục V4 trước khi coi đây là "đã kiểm chứng chất lượng".
SOURCE_LANG_MAP = {
    "en": "en-US",
    "vi": "vi-VN",
    "zh": "zh-CN",
    "ko": "ko-KR",
    "ja": "ja-JP",
    "th": "th-TH",
    "id": "id-ID",
    "en-US": "en-US",
    "vi-VN": "vi-VN",
    "zh-CN": "zh-CN",
    "zh-HK": "zh-HK",
    "zh-TW": "zh-TW",
    "ko-KR": "ko-KR",
    "ja-JP": "ja-JP",
    "th-TH": "th-TH",
    "id-ID": "id-ID",
}

# BCP-47 locale → Whisper language code
WHISPER_LANG_MAP = {
    "en-US": "en",
    "zh-CN": "zh",
    "zh-HK": "zh",
    "zh-TW": "zh",
    "vi-VN": "vi",
    "ko-KR": "ko",
    "ja-JP": "ja",
    "th-TH": "th",
    "id-ID": "id",
}


def resolve_source_lang(lang: str) -> str:
    """Normalize a source-language shorthand to a BCP-47 locale."""
    return SOURCE_LANG_MAP.get(lang, lang)
