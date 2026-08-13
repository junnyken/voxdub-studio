"""Mini-spec V35 (docs/PLAN.md, Phase G) — kiểm tra chất lượng đầu vào
trước khi học giọng, dữ liệu tổng hợp (không cần audio thật)."""
from __future__ import annotations

import numpy as np
import pytest

from autodub.speech.tts.audio_quality import analyze

SR = 16000


def _sine(duration_s: float = 3.0, freq: float = 220.0, amp: float = 0.3,
         sr: int = SR) -> np.ndarray:
    t = np.linspace(0, duration_s, int(duration_s * sr), endpoint=False)
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_clean_sine_wave_is_ok():
    result = analyze(_sine(), SR)
    assert result.level == "ok"
    assert result.reasons == []


def test_all_zeros_fails_as_silence():
    wav = np.zeros(3 * SR, dtype=np.float32)
    result = analyze(wav, SR)
    assert result.level == "fail"
    assert any("câm" in r for r in result.reasons)


def test_near_silent_low_amplitude_warns():
    wav = _sine(amp=0.005)   # trên ngưỡng fail nhưng dưới ngưỡng warn RMS
    result = analyze(wav, SR)
    assert result.level in ("warn", "fail")
    assert result.reasons


def test_heavily_clipped_noise_fails():
    rng = np.random.default_rng(42)
    # Nhiễu biên độ lớn rồi clip cứng ở ±1.0 — mô phỏng ghi âm quá to thật.
    raw = rng.uniform(-3.0, 3.0, 3 * SR).astype(np.float32)
    wav = np.clip(raw, -1.0, 1.0)
    result = analyze(wav, SR)
    assert result.level == "fail"
    assert any("cắt tiếng" in r.lower() for r in result.reasons)


def test_mild_clipping_warns_not_fails():
    wav = _sine(amp=0.3)
    # Chèn đúng 0.5% mẫu chạm biên — dưới ngưỡng fail (1%) nhưng trên ngưỡng warn (0.1%).
    n_clip = int(0.005 * wav.size)
    idx = np.linspace(0, wav.size - 1, n_clip, dtype=int)
    wav[idx] = 1.0
    result = analyze(wav, SR)
    assert result.level == "warn"
    assert any("cắt tiếng" in r.lower() for r in result.reasons)


def test_long_leading_silence_warns():
    silence = np.zeros(4 * SR, dtype=np.float32)
    speech = _sine(duration_s=2.0, amp=0.3)
    wav = np.concatenate([silence, speech])
    result = analyze(wav, SR)
    assert result.level in ("warn", "fail")
    assert any("lặng" in r.lower() for r in result.reasons)


def test_empty_array_fails():
    result = analyze(np.array([], dtype=np.float32), SR)
    assert result.level == "fail"


def test_result_exposes_raw_metrics_not_just_verdict():
    result = analyze(_sine(), SR)
    assert 0.0 <= result.clip_ratio <= 1.0
    assert result.rms > 0.0
    assert 0.0 <= result.longest_silence_ratio <= 1.0


@pytest.mark.parametrize("level", ["ok", "warn", "fail"])
def test_ok_property_matches_level(level):
    from autodub.speech.tts.audio_quality import AudioQualityResult
    result = AudioQualityResult(level=level)
    assert result.ok == (level == "ok")
