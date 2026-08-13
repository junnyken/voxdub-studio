"""Mini-spec V35 (docs/PLAN.md, Phase G) — nối `audio_quality.analyze()`
vào `_encode_one()`: fail → ValueError trước khi mã hóa nặng; warn → vẫn
enroll nhưng kèm cảnh báo tạm thời; giọng thư viện (`source="library"`)
KHÔNG bị đụng (Constraint 4)."""
from __future__ import annotations

import json

import numpy as np
import pytest

from autodub.speech.tts.vieneu_worker import (
    _TRANSIENT_WARNING_KEYS, _encode_one, enroll_voice,
)

SR = 16000


def _sine(duration_s: float = 3.0, amp: float = 0.3, sr: int = SR) -> np.ndarray:
    t = np.linspace(0, duration_s, int(duration_s * sr), endpoint=False)
    return (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


class _BoomIfCalled:
    def __getattr__(self, name):
        raise AssertionError(f"không được gọi '{name}' khi đã bị từ chối trước đó")


class _FakeEngine:
    """Encode giả — trả embedding/codes cố định, không cần model thật."""

    def __init__(self, wav: np.ndarray, sr: int, denoiser=None):
        self._wav = wav
        self._sr = sr
        self.denoiser = denoiser
        self.use_speaker_embedding = False

    def _load_mono(self, path, _target_sr):
        return self._wav, self._sr

    def _encode_ref_wav(self, wav, sr):
        return np.zeros((4, 4), dtype=np.int64)


class _FakeTts:
    def __init__(self, engine):
        self.engine = engine


def _meta(**extra) -> dict:
    base = {"description": "", "gender": "", "region": "", "country": "vn"}
    base.update(extra)
    return base


# --------------------------------------------------------------- fail ----

def test_fail_quality_raises_before_encoding_custom_voice():
    wav = np.zeros(2 * SR, dtype=np.float32)   # đủ dài nhưng câm hoàn toàn
    engine = _FakeEngine(wav, SR, denoiser=_BoomIfCalled())
    engine._encode_ref_wav = _BoomIfCalled()
    tts = _FakeTts(engine)

    with pytest.raises(ValueError, match="[Cc]hất lượng"):
        _encode_one(tts, "fake.wav", style="tu_nhien", no_denoise=True,
                   meta=_meta(source="custom"))


def test_fail_quality_raises_when_source_unspecified_defaults_to_checked():
    """Không truyền source (vd _enroll() người dùng thật không set field
    này) phải VẪN bị kiểm — mặc định an toàn, không phải mặc định bỏ qua."""
    wav = np.zeros(2 * SR, dtype=np.float32)
    engine = _FakeEngine(wav, SR)
    tts = _FakeTts(engine)

    with pytest.raises(ValueError, match="[Cc]hất lượng"):
        _encode_one(tts, "fake.wav", style="tu_nhien", no_denoise=True, meta=_meta())


# --------------------------------------------------------------- warn ----

def test_warn_quality_still_enrolls_with_warning_attached():
    wav = _sine(amp=0.012)   # rất nhỏ — warn, không fail
    engine = _FakeEngine(wav, SR)
    tts = _FakeTts(engine)

    entry = _encode_one(tts, "fake.wav", style="tu_nhien", no_denoise=True,
                        meta=_meta(source="custom"))
    assert entry["codes"] is not None   # vẫn mã hóa thật, không bị chặn
    assert "quality_warning" in entry
    assert entry["quality_warning"]


def test_ok_quality_has_no_warning_keys():
    wav = _sine(amp=0.3)
    engine = _FakeEngine(wav, SR)
    tts = _FakeTts(engine)

    entry = _encode_one(tts, "fake.wav", style="tu_nhien", no_denoise=True,
                        meta=_meta(source="custom"))
    for key in _TRANSIENT_WARNING_KEYS:
        assert key not in entry


def test_clip_longer_than_8s_warns_truncation_not_silent():
    wav = _sine(duration_s=12.0, amp=0.3)   # dài hơn trần 8 giây
    engine = _FakeEngine(wav, SR)
    tts = _FakeTts(engine)

    entry = _encode_one(tts, "fake.wav", style="tu_nhien", no_denoise=True,
                        meta=_meta(source="custom"))
    assert "truncated_warning" in entry
    assert "8" in entry["truncated_warning"]
    assert "12" in entry["truncated_warning"]   # báo đúng độ dài gốc thật


# --------------------------------------------------- giọng thư viện ----

def test_library_source_bypasses_quality_check_entirely():
    """Constraint 4: giọng thư viện KHÔNG bị đụng — kể cả audio câm hoàn
    toàn (lẽ ra fail nếu là custom) cũng phải enroll được bình thường."""
    wav = np.zeros(2 * SR, dtype=np.float32)
    engine = _FakeEngine(wav, SR)
    tts = _FakeTts(engine)

    entry = _encode_one(tts, "fake.wav", style="tu_nhien", no_denoise=True,
                        meta=_meta(source="library"))
    assert entry["codes"] is not None
    for key in _TRANSIENT_WARNING_KEYS:
        assert key not in entry


def test_library_source_bypasses_truncation_warning_too():
    wav = _sine(duration_s=12.0, amp=0.3)
    engine = _FakeEngine(wav, SR)
    tts = _FakeTts(engine)

    entry = _encode_one(tts, "fake.wav", style="tu_nhien", no_denoise=True,
                        meta=_meta(source="library"))
    assert "truncated_warning" not in entry


# ------------------------------------------- enroll_voice() end-to-end ----

class _Args:
    def __init__(self, custom_voices):
        self.enroll = "fake.wav"
        self.enroll_name = "Giọng Test"
        self.enroll_no_denoise = True
        self.enroll_desc = ""
        self.enroll_gender = "female"
        self.enroll_region = ""
        self.enroll_country = "vn"
        self.custom_voices = custom_voices
        self.style = "tu_nhien"


def test_enroll_voice_reports_warning_in_stdout_but_not_in_saved_file(tmp_path, capsys):
    custom_voices = str(tmp_path / "custom_voices.json")
    wav = _sine(amp=0.012)   # warn
    engine = _FakeEngine(wav, SR)
    tts = _FakeTts(engine)
    args = _Args(custom_voices)

    enroll_voice(tts, args, __import__("sys").stdout)
    out = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(out)

    assert payload["ok"] is True
    assert "quality_warning" in payload   # GUI thấy ngay lúc này

    with open(custom_voices, encoding="utf-8") as f:
        saved = json.load(f)
    entry = saved["presets"]["Giọng Test"]
    for key in _TRANSIENT_WARNING_KEYS:
        assert key not in entry   # KHÔNG lưu vĩnh viễn vào file
