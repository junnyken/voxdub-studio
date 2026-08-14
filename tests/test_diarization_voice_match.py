"""Mini-spec V36 (docs/PLAN.md, Phase G) — ước lượng giới tính người nói
từ pitch (F0), thuần numpy, dữ liệu tổng hợp (không cần audio thật)."""
from __future__ import annotations

import wave

import numpy as np

from autodub.speech.diarization_voice_match import (
    estimate_speaker_genders, load_wav_mono,
)

SR = 16000


def _sine(freq: float, duration_s: float, amp: float = 0.3, sr: int = SR) -> np.ndarray:
    t = np.linspace(0, duration_s, int(duration_s * sr), endpoint=False)
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_low_pitch_classified_male():
    wav = _sine(110.0, 2.0)
    diar = [{"start": 0.0, "end": 2.0, "speaker": "S1"}]
    assert estimate_speaker_genders(wav, SR, diar) == {"S1": "male"}


def test_high_pitch_classified_female():
    wav = _sine(220.0, 2.0)
    diar = [{"start": 0.0, "end": 2.0, "speaker": "S1"}]
    assert estimate_speaker_genders(wav, SR, diar) == {"S1": "female"}


def test_ambiguous_pitch_in_gap_returns_empty_not_a_guess():
    """160Hz nằm giữa ngưỡng nam (<=145) và nữ (>=175) -> không đoán."""
    wav = _sine(160.0, 2.0)
    diar = [{"start": 0.0, "end": 2.0, "speaker": "S1"}]
    assert estimate_speaker_genders(wav, SR, diar) == {"S1": ""}


def test_silence_returns_empty():
    wav = np.zeros(2 * SR, dtype=np.float32)
    diar = [{"start": 0.0, "end": 2.0, "speaker": "S1"}]
    assert estimate_speaker_genders(wav, SR, diar) == {"S1": ""}


def test_too_short_returns_empty_not_a_guess():
    wav = _sine(110.0, 0.1)
    diar = [{"start": 0.0, "end": 0.1, "speaker": "S1"}]
    assert estimate_speaker_genders(wav, SR, diar) == {"S1": ""}


def test_multiple_speakers_independent():
    male = _sine(110.0, 2.0)
    female = _sine(220.0, 2.0)
    wav = np.concatenate([male, female])
    diar = [
        {"start": 0.0, "end": 2.0, "speaker": "S1"},
        {"start": 2.0, "end": 4.0, "speaker": "S2"},
    ]
    assert estimate_speaker_genders(wav, SR, diar) == {"S1": "male", "S2": "female"}


def test_speaker_with_no_valid_segments_missing_from_result():
    wav = _sine(110.0, 2.0)
    diar = [{"start": 5.0, "end": 6.0, "speaker": "S1"}]   # ngoài phạm vi wav
    assert estimate_speaker_genders(wav, SR, diar) == {}


def test_unknown_speaker_field_skipped():
    wav = _sine(110.0, 2.0)
    diar = [{"start": 0.0, "end": 2.0, "speaker": ""}]
    assert estimate_speaker_genders(wav, SR, diar) == {}


def test_multiple_segments_same_speaker_concatenated():
    """1 người nói xuất hiện nhiều đoạn rời rạc -> gộp lại để có đủ dữ liệu
    ước lượng, không phân tích riêng lẻ từng đoạn ngắn."""
    male = _sine(110.0, 0.3)
    silence = np.zeros(int(0.5 * SR), dtype=np.float32)
    wav = np.concatenate([male, silence, male])
    diar = [
        {"start": 0.0, "end": 0.3, "speaker": "S1"},
        {"start": 0.8, "end": 1.1, "speaker": "S1"},
    ]
    assert estimate_speaker_genders(wav, SR, diar) == {"S1": "male"}


# --------------------------------------------------------- load_wav_mono --

def test_load_wav_mono_reads_real_pcm16_file(tmp_path):
    sr = 22050
    pcm = (np.sin(2 * np.pi * 440 * np.linspace(0, 1, sr)) * 32767).astype(np.int16)
    path = str(tmp_path / "test.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())

    wav, loaded_sr = load_wav_mono(path)
    assert loaded_sr == sr
    assert wav.dtype == np.float32
    assert -1.0 <= wav.min() and wav.max() <= 1.0
    assert len(wav) == len(pcm)


def test_load_wav_mono_downmixes_stereo(tmp_path):
    sr = 16000
    left = np.full(sr, 10000, dtype=np.int16)
    right = np.full(sr, -10000, dtype=np.int16)
    stereo = np.empty(sr * 2, dtype=np.int16)
    stereo[0::2] = left
    stereo[1::2] = right
    path = str(tmp_path / "stereo.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(stereo.tobytes())

    wav, _ = load_wav_mono(path)
    assert len(wav) == sr   # gộp về mono, không phải 2x mẫu gốc
    assert np.allclose(wav, 0.0, atol=1e-3)   # (10000 + -10000)/2 ~ 0
