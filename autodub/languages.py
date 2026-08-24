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

# Mini-spec V17 (docs/PLAN.md, Phase E) — mở rộng đích theo đúng catalog
# giọng CapCut THẬT đã có sẵn trong autodub/speech/tts/capcut_api/Voice.json
# (không suy đoán — 8 ngôn ngữ dưới đây đều có >=3 giọng thật, xem TEST_LOG
# mục V17 cho số liệu audit). Toàn bộ hạ tầng (voices.catalog/GUI target-
# aware, resolveTargetLang generic phía control_server) đã tổng quát hoá từ
# V11 — thêm entry registry là đủ, KHÔNG cần sửa code khác. Tất cả đánh dấu
# "thử nghiệm" cho tới khi có live-verify riêng (đúng nguyên tắc V4/V11: mở
# rộng có kiểm chứng) — xem docs/dub_constants.py cho nhãn hiển thị GUI.
_V17_TARGETS = [
    # (key, code, iso639_2, name, capcut_voice_count_thật)
    ("ja", "ja-JP", "jpn", "Japanese"),      # 19 giọng
    ("zh", "zh-CN", "zho", "Chinese"),       # 16 giọng
    ("es", "es-ES", "spa", "Spanish"),       # 9 giọng
    ("th", "th-TH", "tha", "Thai"),          # 6 giọng
    ("id", "id-ID", "ind", "Indonesian"),    # 5 giọng
    ("pt", "pt-BR", "por", "Portuguese"),    # 4 giọng
    ("fr", "fr-FR", "fra", "French"),        # 3 giọng
    ("de", "de-DE", "deu", "German"),        # 3 giọng
]
for _key, _code, _iso, _name in _V17_TARGETS:
    TARGETS[_key] = TargetLang(
        key=_key, code=_code, iso639_2=_iso, name=_name,
        text_field=f"text_{_key}",
        transcript_name=f"transcript_{_key}.json",
        srt_name=f"transcript_{_key}.srt",
        audio_name=f"audio_{_key}_full.wav",
        folder_suffix=f"_{_key}",
    )
del _key, _code, _iso, _name


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

#: Mã nguồn (BCP-47) → khoá đích tương ứng.
#:
#: Nằm ở LÕI chứ không ở gói giao diện (mini-spec C22): dòng lệnh cũng cần
#: phép so này, mà dòng lệnh không được nhập `autodub_gui`. Trước đây phép so
#: chỉ có ở trang Tạo dự án, nên Xử lý hàng loạt và `voxdub dub` vẫn nhận
#: nguồn trùng đích — và trả tiền cho một lượt gọi mô hình để nhận lại gần
#: đúng câu cũ.
NGUON_SANG_DICH = {
    "vi-VN": "vi", "en-US": "en", "ja-JP": "ja", "th-TH": "th",
    "id-ID": "id", "ko-KR": "ko",
    "zh-CN": "zh", "zh-HK": "zh", "zh-TW": "zh",
}


def cung_ngon_ngu(source_lang: str, target_key: str) -> bool:
    """Nguồn và đích có cùng một ngôn ngữ không.

    Dịch tiếng Việt sang tiếng Việt thì không có gì để dịch: người dùng mất
    tiền cho một lượt gọi mô hình chỉ để nhận lại gần đúng câu cũ.

    Tự nhận dạng ngôn ngữ (`source_lang` rỗng hoặc "auto") thì KHÔNG kết luận
    được — trả `False`, vì chặn oan còn tệ hơn không chặn.
    """
    if not source_lang or not target_key or source_lang == "auto":
        return False
    return NGUON_SANG_DICH.get(source_lang, "") == target_key
