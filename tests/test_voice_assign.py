"""Mini-spec V26 (docs/PLAN.md, Phase G) — gán giọng theo người nói
(round-robin), tái dùng cơ chế multi-voice per-segment có sẵn. Mini-spec
V36 mở rộng: gán theo giới tính ước lượng, round-robin làm lối thoát an
toàn khi không chắc."""
from __future__ import annotations

import pytest

from autodub.speech.tts.voice_assign import (
    apply_segment_voices, assign_voices_by_gender, assign_voices_round_robin,
)
from autodub.speech.tts.voices import Voice


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


# ------------------------------------------ assign_voices_by_gender ----

_CATALOG_BOTH = [
    Voice("Nam A", gender="male"), Voice("Nam B", gender="male"),
    Voice("Nu A", gender="female"),
]


def test_assigns_matching_gender_when_estimated():
    mapping = assign_voices_by_gender(
        ["S1", "S2"], {"S1": "male", "S2": "female"},
        _CATALOG_BOTH, fallback_names=["Fallback"])
    assert mapping["S1"] in ("Nam A", "Nam B")
    assert mapping["S2"] == "Nu A"


def test_same_gender_speakers_round_robin_within_group():
    """2 người nói cùng giới tính -> không cả 2 ra đúng 1 giọng nếu catalog
    có đủ hơn 1 giọng cho giới tính đó."""
    mapping = assign_voices_by_gender(
        ["S1", "S2"], {"S1": "male", "S2": "male"},
        _CATALOG_BOTH, fallback_names=["Fallback"])
    assert mapping["S1"] != mapping["S2"]
    assert {mapping["S1"], mapping["S2"]} == {"Nam A", "Nam B"}


def test_unknown_gender_falls_back_to_round_robin():
    mapping = assign_voices_by_gender(
        ["S1"], {"S1": ""}, _CATALOG_BOTH, fallback_names=["Fallback"])
    assert mapping["S1"] == "Fallback"


def test_missing_gender_key_falls_back_to_round_robin():
    """Speaker không có trong dict genders (không ước lượng được gì) ->
    vẫn phải được gán, không bị bỏ sót."""
    mapping = assign_voices_by_gender(
        ["S1"], {}, _CATALOG_BOTH, fallback_names=["Fallback"])
    assert mapping["S1"] == "Fallback"


def test_catalog_missing_gender_entirely_still_assigns_via_fallback():
    """Constraint: catalog CHỈ có 1 giới tính -> người nói giới tính kia
    vẫn phải được gán 1 giọng nào đó, không loại bỏ hoàn toàn."""
    male_only_catalog = [Voice("Nam A", gender="male")]
    mapping = assign_voices_by_gender(
        ["S1"], {"S1": "female"}, male_only_catalog, fallback_names=["Nam A"])
    assert mapping["S1"] == "Nam A"


def test_mixed_estimated_and_unresolved_speakers():
    mapping = assign_voices_by_gender(
        ["S1", "S2"], {"S1": "male"}, _CATALOG_BOTH, fallback_names=["Fallback"])
    assert mapping["S1"] in ("Nam A", "Nam B")
    assert mapping["S2"] == "Fallback"
