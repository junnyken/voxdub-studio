"""Mini-spec V35 (docs/PLAN.md, Phase G) — Regression thật (Constraint 4):
kiểm tra `audio_quality.analyze()` KHÔNG lỡ tay từ chối bất kỳ file nào
trong 121 giọng thư viện thật (`voices/preset_voices_vn/`), dùng đúng file
âm thanh thật đã curate sẵn — không phải dữ liệu tổng hợp.

Đây KHÔNG phải bằng chứng "luồng thư viện an toàn" (luồng đó đã BỎ QUA
hoàn toàn bước kiểm tra này khi `meta["source"] == "library"`, xem
`_encode_one()` trong vieneu_worker.py) — test này xác nhận THÊM: kể cả
NẾU kiểm tra có chạy trên các file thật này, ngưỡng đã chọn cũng không vô
lý tới mức từ chối nhầm nội dung đã qua tuyển chọn của con người.
"""
from __future__ import annotations

import glob
import os
import wave

import numpy as np
import pytest

from autodub.speech.tts.audio_quality import analyze

_VOICES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "voices", "preset_voices_vn")
_WAV_FILES = sorted(glob.glob(os.path.join(_VOICES_DIR, "*.wav")))


def _read_wav_mono_float32(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        sampwidth = wf.getsampwidth()
        nchannels = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())
    assert sampwidth == 2, f"{path}: chỉ hỗ trợ PCM 16-bit trong test này"
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if nchannels > 1:
        pcm = pcm.reshape(-1, nchannels).mean(axis=1)
    return pcm, sr


@pytest.mark.skipif(not _WAV_FILES, reason=(
    "Không thấy file .wav thật trong voices/preset_voices_vn/ — "
    "bỏ qua (môi trường chưa tải thư viện giọng)."))
def test_no_real_library_voice_would_be_rejected_by_quality_check():
    fails = []
    warns = []
    for path in _WAV_FILES:
        wav, sr = _read_wav_mono_float32(path)
        result = analyze(wav, sr)
        if result.level == "fail":
            fails.append((os.path.basename(path), result.reasons))
        elif result.level == "warn":
            warns.append((os.path.basename(path), result.reasons))

    assert not fails, (
        f"{len(fails)}/{len(_WAV_FILES)} file thư viện thật lẽ ra bị FAIL "
        f"nếu áp dụng kiểm tra chất lượng — ngưỡng cần điều chỉnh: {fails}")
    # warn thì không assert cứng (chỉ log qua message nếu pytest -v) — 1 vài
    # giọng biên trong 121 giọng không sao, miễn không giọng nào FAIL thật.


@pytest.mark.skipif(not _WAV_FILES, reason="cần voices/preset_voices_vn/")
def test_library_wav_count_matches_expected_scale():
    """Không phải test chất lượng — chỉ xác nhận đang thật sự đọc được cả
    thư viện (121 file) chứ không phải glob rỗng/sai đường dẫn."""
    assert len(_WAV_FILES) >= 100
