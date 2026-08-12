"""Mini-spec V26 (docs/PLAN.md, Phase G) — driver diarization
(`autodub/speech/diarization.py`).

Worker giả THẬT (script Python nhỏ, đúng giao thức JSON của
diarize_worker.py thật) — không mock `Popen`, cùng cách đã làm cho
run_local_worker()/Whisper/Paraformer ở V24.
"""
from __future__ import annotations

import sys
import textwrap

import pytest

from autodub.config import Settings
from autodub.speech.diarization import DiarizationError, assign_speakers, diarize


def _fake_worker(tmp_path, body: str) -> str:
    path = tmp_path / "fake_diarize_worker.py"
    path.write_text("import json\n" + textwrap.dedent(body), encoding="utf-8")
    return str(path)


def _settings(monkeypatch, worker_path):
    settings = Settings()
    monkeypatch.setattr(settings, "diarization_venv_python_path", lambda: sys.executable)
    monkeypatch.setattr(settings, "diarization_model_dir_path", lambda: "/tmp/fake-model")
    monkeypatch.setattr("autodub.speech.diarization._WORKER_SCRIPT", worker_path)
    return settings


# --------------------------------------------------------------------- #
# diarize()

def test_parses_segments_from_worker_normally(monkeypatch, tmp_path):
    worker = _fake_worker(tmp_path, body="""
        print(json.dumps({"segment": True, "start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"}))
        print(json.dumps({"segment": True, "start": 2.0, "end": 5.0, "speaker": "SPEAKER_01"}))
        print(json.dumps({"done": True, "num_speakers": 2}))
    """)
    settings = _settings(monkeypatch, worker)

    segments = diarize("/tmp/fake.wav", settings)

    assert segments == [
        {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
        {"start": 2.0, "end": 5.0, "speaker": "SPEAKER_01"},
    ]


def test_worker_error_raises_diarization_error(monkeypatch, tmp_path):
    worker = _fake_worker(tmp_path, body="""
        print(json.dumps({"error": "thiếu HF token"}))
    """)
    settings = _settings(monkeypatch, worker)

    with pytest.raises(DiarizationError, match="thiếu HF token"):
        diarize("/tmp/fake.wav", settings)


def test_worker_hangs_raises_within_bounded_time(monkeypatch, tmp_path):
    """Bug thật đã audit + sửa ở V24 cho các worker khác — diarization worker
    mới PHẢI dùng watchdog ngay từ đầu, không lặp lại lỗi cũ."""
    import autodub.speech.diarization as diar_module
    monkeypatch.setattr(diar_module, "_DIARIZE_TIMEOUT_S", 0.3)

    path = tmp_path / "fake_diarize_worker.py"
    path.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    settings = _settings(monkeypatch, str(path))

    with pytest.raises(DiarizationError, match="không phản hồi"):
        diarize("/tmp/fake.wav", settings)


def test_worker_exits_without_done_raises_clear_error(monkeypatch, tmp_path):
    worker = _fake_worker(tmp_path, body="""
        print(json.dumps({"segment": True, "start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}))
    """)  # thoát mà không có "done" — worker crash bất thường
    settings = _settings(monkeypatch, worker)

    with pytest.raises(DiarizationError, match="bất thường"):
        diarize("/tmp/fake.wav", settings)


# --------------------------------------------------------------------- #
# assign_speakers() — map ASR segment -> speaker theo overlap lớn nhất

def test_assigns_speaker_with_largest_overlap():
    asr_segments = [
        {"id": 1, "start": 0.0, "end": 2.0},
        {"id": 2, "start": 2.5, "end": 5.0},
    ]
    diar_segments = [
        {"start": 0.0, "end": 2.2, "speaker": "SPEAKER_00"},
        {"start": 2.2, "end": 6.0, "speaker": "SPEAKER_01"},
    ]
    assign_speakers(asr_segments, diar_segments)
    assert asr_segments[0]["speaker_label"] == "SPEAKER_00"
    assert asr_segments[1]["speaker_label"] == "SPEAKER_01"


def test_segment_spanning_two_speakers_picks_larger_overlap():
    asr_segments = [{"id": 1, "start": 0.0, "end": 10.0}]
    diar_segments = [
        {"start": 0.0, "end": 3.0, "speaker": "SPEAKER_00"},   # overlap 3.0
        {"start": 3.0, "end": 10.0, "speaker": "SPEAKER_01"},  # overlap 7.0
    ]
    assign_speakers(asr_segments, diar_segments)
    assert asr_segments[0]["speaker_label"] == "SPEAKER_01"


def test_segment_with_no_overlap_left_untouched():
    asr_segments = [{"id": 1, "start": 100.0, "end": 105.0}]
    diar_segments = [{"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"}]
    assign_speakers(asr_segments, diar_segments)
    assert "speaker_label" not in asr_segments[0]


def test_does_not_mutate_unrelated_fields():
    asr_segments = [{"id": 1, "text": "xin chào", "start": 0.0, "end": 2.0}]
    assign_speakers(asr_segments, [{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"}])
    assert asr_segments[0]["text"] == "xin chào"
    assert asr_segments[0]["id"] == 1
