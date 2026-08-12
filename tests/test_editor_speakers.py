"""Mini-spec V26 (docs/PLAN.md, Phase G) — `list_speakers()`/
`set_speaker_voice()` (`autodub/editor.py`), backend cho panel GUI "Xem
trước người nói"."""
from __future__ import annotations

import json

import pytest

from autodub.editor import EditorError, list_speakers, set_speaker_voice

_TEXT_FIELD = "text_vi"


def _segments():
    return [
        {"id": 1, "start": 0.0, "end": 2.0, "text": "a",
         _TEXT_FIELD: "Xin chào.", "speaker_label": "SPEAKER_00", "voice": "Minh Trang"},
        {"id": 2, "start": 2.0, "end": 4.0, "text": "b",
         _TEXT_FIELD: "Câu hai.", "speaker_label": "SPEAKER_00", "voice": "Minh Trang"},
        {"id": 3, "start": 4.0, "end": 6.0, "text": "c",
         _TEXT_FIELD: "Câu ba.", "speaker_label": "SPEAKER_01", "voice": "Phạm Tuyên"},
        {"id": 4, "start": 6.0, "end": 8.0, "text": "d",
         _TEXT_FIELD: "Câu bốn — không thuộc speaker nào (diarization bỏ sót)."},
    ]


@pytest.fixture()
def work_dir(tmp_path):
    work = tmp_path / "20260812_vi"
    data = work / "data"
    data.mkdir(parents=True)
    (data / "transcript_vi.json").write_text(
        json.dumps(_segments(), ensure_ascii=False), encoding="utf-8")
    return str(work)


def test_list_speakers_groups_correctly(work_dir):
    speakers = list_speakers(work_dir)
    assert len(speakers) == 2
    assert speakers[0]["speaker_label"] == "SPEAKER_00"
    assert speakers[0]["segment_count"] == 2
    assert speakers[0]["voice"] == "Minh Trang"
    assert speakers[1]["speaker_label"] == "SPEAKER_01"
    assert speakers[1]["segment_count"] == 1
    assert speakers[1]["voice"] == "Phạm Tuyên"


def test_list_speakers_ignores_segments_without_speaker_label(work_dir):
    """Câu 4 (không có speaker_label) không được tính vào speaker nào."""
    speakers = list_speakers(work_dir)
    total_counted = sum(s["segment_count"] for s in speakers)
    assert total_counted == 3  # không tính câu 4


def test_list_speakers_empty_when_diarization_not_used(tmp_path):
    """Dự án không bật diarization (không câu nào có speaker_label) -> danh
    sách RỖNG, không phải lỗi."""
    work = tmp_path / "20260812_vi"
    data = work / "data"
    data.mkdir(parents=True)
    segs = [{"id": 1, "start": 0.0, "end": 2.0, "text": "a", _TEXT_FIELD: "Xin chào."}]
    (data / "transcript_vi.json").write_text(json.dumps(segs), encoding="utf-8")
    assert list_speakers(str(work)) == []


def test_list_speakers_missing_transcript_raises():
    with pytest.raises(EditorError):
        list_speakers("/tmp/khong-ton-tai-thu-muc-nay")


def test_set_speaker_voice_changes_only_that_speakers_segments(work_dir):
    changed = set_speaker_voice(work_dir, "SPEAKER_00", "Trúc Ly")
    assert changed == 2

    with open(f"{work_dir}/data/transcript_vi.json", encoding="utf-8") as f:
        segments = json.load(f)
    by_id = {s["id"]: s for s in segments}
    assert by_id[1]["voice"] == "Trúc Ly"
    assert by_id[2]["voice"] == "Trúc Ly"
    assert by_id[3]["voice"] == "Phạm Tuyên"  # speaker khác không đổi


def test_set_speaker_voice_empty_string_removes_override(work_dir):
    changed = set_speaker_voice(work_dir, "SPEAKER_00", "")
    assert changed == 2
    with open(f"{work_dir}/data/transcript_vi.json", encoding="utf-8") as f:
        segments = json.load(f)
    by_id = {s["id"]: s for s in segments}
    assert "voice" not in by_id[1]
    assert "voice" not in by_id[2]


def test_set_speaker_voice_no_change_returns_zero(work_dir):
    """Gán ĐÚNG giọng đã có sẵn -> không đổi gì, trả về 0 (không ghi file
    thừa)."""
    changed = set_speaker_voice(work_dir, "SPEAKER_00", "Minh Trang")
    assert changed == 0


def test_set_speaker_voice_unknown_speaker_returns_zero(work_dir):
    changed = set_speaker_voice(work_dir, "SPEAKER_99", "Trúc Ly")
    assert changed == 0
