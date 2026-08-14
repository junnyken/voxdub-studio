"""Mini-spec V26 (docs/PLAN.md, Phase G) — wiring diarization vào
`DubPipeline._apply_diarization()`. Mini-spec V36 mở rộng: gán giọng theo
giới tính ước lượng thay vì round-robin thuần (audio giả `/tmp/fake.wav`
không tồn tại nên `load_wav_mono()` luôn lỗi trong các test dưới đây —
đúng đường "không đọc được audio -> round-robin toàn bộ" trừ test riêng có
mock `estimate_speaker_genders`). Test gọi thẳng phương thức (cùng cách
`test_pipeline_telemetry_wiring.py` đã làm) — không chạy pipeline.run() đầy
đủ (cần tải video/ASR/TTS thật).
"""
from __future__ import annotations

from autodub.config import Settings
from autodub.languages import get_target
from autodub.pipeline import DubPipeline
from autodub.speech.tts.voices import Voice


def _pipeline():
    return DubPipeline(Settings())


def test_disabled_by_default_does_nothing_0_regression():
    """diarization_enabled=False (mặc định) -> segments không đổi gì cả."""
    pipeline = _pipeline()
    segments = [{"id": 1, "text": "a", "start": 0.0, "end": 2.0}]
    pipeline._apply_diarization(segments, "/tmp/fake.wav", get_target("vi"))
    assert segments == [{"id": 1, "text": "a", "start": 0.0, "end": 2.0}]


def test_enabled_but_not_installed_degrades_honestly(monkeypatch, caplog):
    """Bật cờ nhưng .venv-diar chưa cài -> giữ nguyên segments, có log rõ
    ràng (Constraint 2: không giả vờ có mà gán bừa)."""
    pipeline = _pipeline()
    pipeline.settings.diarization_enabled = True
    monkeypatch.setattr(pipeline.settings, "diarization_configured", lambda: False)

    segments = [{"id": 1, "text": "a", "start": 0.0, "end": 2.0}]
    import logging
    with caplog.at_level(logging.INFO, logger="autodub.pipeline"):
        pipeline._apply_diarization(segments, "/tmp/fake.wav", get_target("vi"))

    assert "voice" not in segments[0]
    assert any("chưa cài" in r.message for r in caplog.records)


def test_diarization_error_degrades_to_single_voice_not_crash(monkeypatch):
    """Lỗi thật trong lượt diarize() -> không crash cả lượt dub, segments
    giữ nguyên (rơi về 1 giọng toàn video như trước V26)."""
    pipeline = _pipeline()
    pipeline.settings.diarization_enabled = True
    monkeypatch.setattr(pipeline.settings, "diarization_configured", lambda: True)

    from autodub.speech.diarization import DiarizationError

    def _boom(audio_path, settings):
        raise DiarizationError("worker treo")
    monkeypatch.setattr("autodub.speech.diarization.diarize", _boom)

    segments = [{"id": 1, "text": "a", "start": 0.0, "end": 2.0}]
    pipeline._apply_diarization(segments, "/tmp/fake.wav", get_target("vi"))
    assert "voice" not in segments[0]  # không crash, không gán bừa


def test_successful_diarization_assigns_distinct_voices(monkeypatch):
    pipeline = _pipeline()
    pipeline.settings.diarization_enabled = True
    monkeypatch.setattr(pipeline.settings, "diarization_configured", lambda: True)
    monkeypatch.setattr(
        "autodub.speech.diarization.diarize",
        lambda audio_path, settings: [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
            {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_01"},
        ])

    monkeypatch.setattr(
        "autodub.speech.tts.voices.catalog",
        lambda settings, target: [Voice("Minh Trang"), Voice("Phạm Tuyên")])

    segments = [
        {"id": 1, "text": "a", "start": 0.0, "end": 2.0},
        {"id": 2, "text": "b", "start": 2.0, "end": 4.0},
    ]
    # /tmp/fake.wav không tồn tại -> load_wav_mono() lỗi -> round-robin
    # thuần (V36 fallback, xem docstring module) — vẫn đúng hành vi V26 cũ.
    pipeline._apply_diarization(segments, "/tmp/fake.wav", get_target("vi"))

    assert segments[0]["speaker_label"] == "SPEAKER_00"
    assert segments[1]["speaker_label"] == "SPEAKER_01"
    assert segments[0]["voice"] != segments[1]["voice"]
    assert segments[0]["voice"] in ("Minh Trang", "Phạm Tuyên")


def test_gender_estimated_assigns_matching_voices(monkeypatch):
    """Mini-spec V36: người nói ước lượng được giới tính phải nhận đúng
    giọng cùng giới tính từ catalog, không phải round-robin mù."""
    pipeline = _pipeline()
    pipeline.settings.diarization_enabled = True
    monkeypatch.setattr(pipeline.settings, "diarization_configured", lambda: True)
    monkeypatch.setattr(
        "autodub.speech.diarization.diarize",
        lambda audio_path, settings: [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
            {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_01"},
        ])
    monkeypatch.setattr(
        "autodub.speech.tts.voices.catalog",
        lambda settings, target: [
            Voice("Nam A", gender="male"), Voice("Nu A", gender="female")])
    monkeypatch.setattr(
        "autodub.speech.diarization_voice_match.load_wav_mono",
        lambda path: (__import__("numpy").zeros(1), 16000))
    monkeypatch.setattr(
        "autodub.speech.diarization_voice_match.estimate_speaker_genders",
        lambda wav, sr, diar: {"SPEAKER_00": "male", "SPEAKER_01": "female"})

    segments = [
        {"id": 1, "text": "a", "start": 0.0, "end": 2.0},
        {"id": 2, "text": "b", "start": 2.0, "end": 4.0},
    ]
    pipeline._apply_diarization(segments, "/tmp/fake.wav", get_target("vi"))

    assert segments[0]["voice"] == "Nam A"
    assert segments[1]["voice"] == "Nu A"


def test_no_speakers_detected_leaves_segments_untouched(monkeypatch):
    """diarize() thành công nhưng không map được speaker nào (audio quá
    ngắn/im lặng) -> không set seg["voice"], không lỗi."""
    pipeline = _pipeline()
    pipeline.settings.diarization_enabled = True
    monkeypatch.setattr(pipeline.settings, "diarization_configured", lambda: True)
    monkeypatch.setattr("autodub.speech.diarization.diarize",
                        lambda audio_path, settings: [])

    segments = [{"id": 1, "text": "a", "start": 0.0, "end": 2.0}]
    pipeline._apply_diarization(segments, "/tmp/fake.wav", get_target("vi"))
    assert "voice" not in segments[0]
