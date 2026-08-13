"""Bug thật (mini-spec V35, docs/PLAN.md Phase G): `_encode_one()` trước
đây KHÔNG kiểm tra độ dài clip thật — ngưỡng duy nhất tồn tại
(`_kaldi_fbank_numpy`'s window-size guard, ~25ms) bị báo nhầm thành
"cần ≥ 1 giây" trong khi thật ra chỉ chặn dưới 25ms, sai lệch ~40 lần.
Clip vài chục mili-giây (gần như câm) lọt qua và "học" thành công.
"""
from __future__ import annotations

import numpy as np
import pytest

from autodub.speech.tts.vieneu_worker import MIN_ENROLL_SECONDS, _encode_one


class _BoomIfCalled:
    """Bất kỳ thuộc tính/lệnh gọi nào cũng ném lỗi — dùng để xác nhận
    _encode_one() dừng lại (ValueError) TRƯỚC khi chạm tới bất kỳ việc xử
    lý nặng nào (khử ồn, mã hóa giọng...) khi clip quá ngắn."""

    def __getattr__(self, name):
        raise AssertionError(
            f"không được gọi '{name}' khi clip đã bị từ chối vì quá ngắn")


class _FakeEngine:
    def __init__(self, wav: np.ndarray, sr: int):
        self._wav = wav
        self._sr = sr

    def _load_mono(self, path, _target_sr):
        return self._wav, self._sr

    denoiser = _BoomIfCalled()

    def _encode_ref_wav(self, *a, **kw):
        raise AssertionError("không được mã hóa khi clip quá ngắn")


class _FakeTts:
    def __init__(self, engine):
        self.engine = engine


def test_min_enroll_seconds_is_a_real_second_scale_threshold():
    """Khoá lại đúng ngưỡng thật — không phải ~25ms như bug cũ."""
    assert MIN_ENROLL_SECONDS >= 1.0


def test_clip_shorter_than_minimum_raises_before_any_heavy_work():
    sr = 16000
    too_short = np.zeros(int(0.25 * sr), dtype=np.float32)  # 0.25 giây
    engine = _FakeEngine(too_short, sr)
    tts = _FakeTts(engine)

    with pytest.raises(ValueError, match="quá ngắn"):
        _encode_one(tts, "fake.wav", style="tu_nhien", no_denoise=True, meta={})


def test_error_message_reports_real_duration_and_real_threshold():
    sr = 16000
    too_short = np.zeros(int(0.25 * sr), dtype=np.float32)
    engine = _FakeEngine(too_short, sr)
    tts = _FakeTts(engine)

    with pytest.raises(ValueError) as exc_info:
        _encode_one(tts, "fake.wav", style="tu_nhien", no_denoise=True, meta={})
    message = str(exc_info.value)
    assert "1" in message  # ngưỡng thật (MIN_ENROLL_SECONDS = 1.0)
    assert "0.25" in message  # độ dài thật của clip


def test_clip_at_exactly_25ms_used_to_pass_old_buggy_check_now_rejected():
    """Đúng trường hợp bug cũ: clip 25ms lọt qua ngưỡng nội bộ cũ
    (window-size ~25ms) nhưng phải bị từ chối bởi ngưỡng thật mới."""
    sr = 16000
    borderline_old_bug = np.zeros(int(0.03 * sr), dtype=np.float32)  # 30ms
    engine = _FakeEngine(borderline_old_bug, sr)
    tts = _FakeTts(engine)

    with pytest.raises(ValueError, match="quá ngắn"):
        _encode_one(tts, "fake.wav", style="tu_nhien", no_denoise=True, meta={})
