"""Mini-spec V28 (docs/PLAN.md, Phase G) — wiring emotion/tone-aware voice
vào `DubPipeline._apply_emotion_styles()`. Gọi thẳng phương thức (cùng cách
`test_pipeline_diarization.py`/`test_pipeline_telemetry_wiring.py` đã làm).
"""
from __future__ import annotations

from autodub.config import Settings
from autodub.languages import get_target
from autodub.pipeline import DubPipeline


def _pipeline():
    return DubPipeline(Settings())


class _FakeVoice:
    def __init__(self, name, source="builtin"):
        self.name = name
        self.source = source


def test_disabled_by_default_does_nothing_0_regression():
    pipeline = _pipeline()
    segments = [{"id": 1, "text_vi": "Tuyệt vời quá!"}]
    pipeline._apply_emotion_styles(segments, get_target("vi"), "Minh Trang")
    assert "style" not in segments[0]


def test_enabled_assigns_style_from_tone(monkeypatch):
    pipeline = _pipeline()
    pipeline.settings.emotion_voice_enabled = True
    monkeypatch.setattr(
        "autodub.speech.tts.voices.catalog",
        lambda settings, target: [_FakeVoice("Minh Trang")])

    segments = [
        {"id": 1, "text_vi": "Tuyệt vời quá!"},       # excited
        {"id": 2, "text_vi": "Cảnh báo nguy hiểm."},   # serious
        {"id": 3, "text_vi": "Hôm nay trời đẹp."},     # neutral
    ]
    pipeline._apply_emotion_styles(segments, get_target("vi"), "Minh Trang")

    assert segments[0]["style"] == "doc_truyen"
    assert segments[1]["style"] == "tin_tuc"
    assert segments[2]["style"] == "tu_nhien"


def test_capcut_voice_is_skipped(monkeypatch):
    """Constraint 4: chỉ áp cho VieNeu — giọng CapCut (source="capcut")
    không được gán style."""
    pipeline = _pipeline()
    pipeline.settings.emotion_voice_enabled = True
    monkeypatch.setattr(
        "autodub.speech.tts.voices.catalog",
        lambda settings, target: [_FakeVoice("Hatunemiku", source="capcut")])

    segments = [{"id": 1, "text_vi": "Tuyệt vời quá!", "voice": "Hatunemiku"}]
    pipeline._apply_emotion_styles(segments, get_target("vi"), "Hatunemiku")

    assert "style" not in segments[0]


def test_per_segment_voice_override_from_diarization_respected(monkeypatch):
    """Segment có seg["voice"] riêng (vd từ V26 diarization) -> tra cứu
    ĐÚNG giọng đó trong catalog, không phải giọng mặc định toàn video."""
    pipeline = _pipeline()
    pipeline.settings.emotion_voice_enabled = True
    monkeypatch.setattr(
        "autodub.speech.tts.voices.catalog",
        lambda settings, target: [
            _FakeVoice("Minh Trang"), _FakeVoice("Hatunemiku", source="capcut")])

    segments = [
        {"id": 1, "text_vi": "Tuyệt vời!", "voice": "Minh Trang"},
        {"id": 2, "text_vi": "Tuyệt vời!", "voice": "Hatunemiku"},
    ]
    pipeline._apply_emotion_styles(segments, get_target("vi"), "Minh Trang")

    assert segments[0]["style"] == "doc_truyen"
    assert "style" not in segments[1]


def test_unknown_voice_not_in_catalog_still_gets_style():
    """Giọng không tìm thấy trong catalog (lỗi tra cứu/tên lạ) -> mặc định
    XỬ LÝ NHƯ VieNeu (an toàn hơn bỏ sót một giọng VieNeu thật vì lỗi tra
    cứu tạm thời) thay vì âm thầm bỏ qua."""
    pipeline = _pipeline()
    pipeline.settings.emotion_voice_enabled = True
    segments = [{"id": 1, "text_vi": "Tuyệt vời!", "voice": "Tên Không Tồn Tại"}]
    pipeline._apply_emotion_styles(segments, get_target("vi"), "Tên Không Tồn Tại")
    assert segments[0]["style"] == "doc_truyen"
