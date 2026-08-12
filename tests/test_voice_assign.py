"""Mini-spec V26 (docs/PLAN.md, Phase G) — gán giọng theo người nói
(round-robin), tái dùng cơ chế multi-voice per-segment có sẵn."""
from __future__ import annotations

import pytest

from autodub.speech.tts.voice_assign import (
    apply_segment_voices, assign_voices_round_robin,
)


def test_assigns_one_voice_per_speaker_when_enough_voices():
    mapping = assign_voices_round_robin(
        ["SPEAKER_00", "SPEAKER_01"], ["Minh Trang", "Phạm Tuyên"])
    assert mapping == {"SPEAKER_00": "Minh Trang", "SPEAKER_01": "Phạm Tuyên"}


def test_round_robin_when_more_speakers_than_voices():
    """Constraint 4: số speaker > số giọng khả dụng -> vòng lại, không crash."""
    mapping = assign_voices_round_robin(
        ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"], ["Minh Trang"])
    assert mapping == {
        "SPEAKER_00": "Minh Trang",
        "SPEAKER_01": "Minh Trang",
        "SPEAKER_02": "Minh Trang",
    }


def test_empty_catalog_raises_clear_error_not_crash():
    with pytest.raises(ValueError, match="rỗng"):
        assign_voices_round_robin(["SPEAKER_00"], [])


def test_apply_segment_voices_writes_voice_field():
    segments = [
        {"id": 1, "text": "a", "speaker_label": "SPEAKER_00"},
        {"id": 2, "text": "b", "speaker_label": "SPEAKER_01"},
    ]
    apply_segment_voices(segments, {"SPEAKER_00": "Minh Trang", "SPEAKER_01": "Phạm Tuyên"})
    assert segments[0]["voice"] == "Minh Trang"
    assert segments[1]["voice"] == "Phạm Tuyên"


def test_segment_without_speaker_label_untouched_0_regression():
    """Segment không có speaker_label (diarization tắt/bỏ sót) giữ nguyên —
    không set seg["voice"], pipeline dùng giọng mặc định toàn video như cũ."""
    segments = [{"id": 1, "text": "a"}]
    apply_segment_voices(segments, {"SPEAKER_00": "Minh Trang"})
    assert "voice" not in segments[0]


def test_segment_with_unknown_speaker_label_untouched():
    segments = [{"id": 1, "text": "a", "speaker_label": "SPEAKER_99"}]
    apply_segment_voices(segments, {"SPEAKER_00": "Minh Trang"})
    assert "voice" not in segments[0]
