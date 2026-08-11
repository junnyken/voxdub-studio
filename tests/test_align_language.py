"""Mini-spec V11 (docs/PLAN.md) — bug thật tìm ra khi audit: align.py hardcode
language="vi" khi nghe lại clip TTS để canh mốc chữ karaoke, khiến mọi target
khác tiếng Việt bị Whisper nghe SAI ngôn ngữ, alignment luôn hỏng/rớt về ước
lượng thô. Test này khoá lại hành vi ĐÚNG: language phải thread từ
refresh_subtitles(target) → build_karaoke_ass → resolve_word_times →
align_segments → Whisper.transcribe(language=...).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from autodub.languages import get_target
from autodub.speech.align import _asr_words, align_segments


def test_asr_words_passes_language_to_whisper():
    model = MagicMock()
    model.transcribe.return_value = ([], None)
    _asr_words(model, "/tmp/x.wav", language="en")
    kwargs = model.transcribe.call_args.kwargs
    assert kwargs["language"] == "en"


def test_asr_words_default_is_vi_for_backward_compat():
    model = MagicMock()
    model.transcribe.return_value = ([], None)
    _asr_words(model, "/tmp/x.wav")
    assert model.transcribe.call_args.kwargs["language"] == "vi"


def test_align_segments_threads_language_through_to_asr_words(tmp_path, monkeypatch):
    """Không cần audio thật — chỉ xác nhận đường dây language đi tới đúng
    _asr_words(), đúng bug thật đã tìm thấy (trước đây hardcode 'vi' ở tận
    _asr_words, bất kể align_segments() được gọi thế nào)."""
    from autodub.speech import align as align_mod

    wav = tmp_path / "seg1.wav"
    wav.write_bytes(b"RIFF....WAVEfmt ")   # nội dung không quan trọng, mock hết

    seen_languages = []

    def fake_asr_words(model, wav_path, language="vi"):
        seen_languages.append(language)
        return [("hello", 0.0, 1.0), ("world", 1.0, 2.0)]

    monkeypatch.setattr(align_mod, "_asr_words", fake_asr_words)
    monkeypatch.setattr(align_mod, "_load_align_model",
                        lambda: (MagicMock(), "cpu", 1))
    # align.py import seg_wav_path VÀO namespace của chính nó lúc load module
    # (from autodub.utils import ... seg_wav_path) — phải patch đúng tham
    # chiếu đã bind đó, patch autodub.utils.seg_wav_path không có tác dụng.
    monkeypatch.setattr(align_mod, "seg_wav_path", lambda d, sid: str(wav))
    monkeypatch.setattr("autodub.media.audio.wav_duration_s", lambda p: 2.0)

    segments = [{"id": 1, "text_en": "hello world", "start": 0.0, "end": 2.0}]
    align_segments(segments, str(tmp_path), "text_en", language="en")

    assert seen_languages == ["en"], "align_segments phải truyền đúng language='en' xuống _asr_words"


def test_target_en_resolves_to_whisper_code_en_not_vi():
    """Xác nhận mapping WHISPER_LANG_MAP dùng trong subtitles.py cho ra đúng
    mã Whisper 'en' cho target tiếng Anh — không rơi về 'vi' mặc định."""
    from autodub.languages import WHISPER_LANG_MAP

    target = get_target("en")
    whisper_lang = WHISPER_LANG_MAP.get(target.code, target.code.split("-")[0].lower())
    assert whisper_lang == "en"

    target_vi = get_target("vi")
    whisper_lang_vi = WHISPER_LANG_MAP.get(target_vi.code, target_vi.code.split("-")[0].lower())
    assert whisper_lang_vi == "vi"
