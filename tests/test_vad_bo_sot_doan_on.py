"""G3 (docs/MINI-SPEC_G3_VAD_Bo_Sot_Doan_On.md) — Silero VAD mặc định
(``threshold=0.5``) bỏ sót cả đoạn thoại thật khi nhạc nền/hiệu ứng dồn dập.
Tái hiện thật trên video *Sing 2* (cảnh cả nhóm chạy trốn): bản VAD BẬT (đúng
đường app dùng) mất TRẮNG 38 giây, 6 câu, dù âm lượng đoạn đó không khác gì
đoạn nghe bình thường (đo bằng ``ffmpeg volumedetect`` — không phải do quá
to). Đo trực tiếp bằng ``faster_whisper.vad.get_speech_timestamps``: hạ
``threshold`` xuống 0.3 giúp phát hiện thêm audio nói, và trên video nói liên
tục (16 phút, 99% có tiếng) hạ threshold KHÔNG làm phình thêm audio "phát
hiện được" (961,3s → 962,6s, +0,1%) — an toàn, không sinh thêm đoạn giả.

Ba nơi dùng chung một model Silero VAD, phải khớp threshold (lớp lỗi #2 của
dự án — sửa một đường quên đường kia): ``asr_whisper_worker.py`` (Whisper,
đường subprocess — đường THẬT của bản .exe), ``transcriber.py`` (Whisper,
đường in-process — chỉ dùng khi chạy từ mã nguồn), ``asr_paraformer_worker.py``
(Paraformer, tiếng Trung — CÙNG rủi ro vì cùng model Silero VAD).
"""
from __future__ import annotations

import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*parts: str) -> str:
    return open(os.path.join(REPO, *parts), encoding="utf-8").read()


# --------------------------------------------------------------------- #
# Canh cấu hình — rẻ, không cần model, chạy luôn trong CI.

def test_whisper_subprocess_ha_threshold_vad():
    src = _doc("autodub", "speech", "asr_whisper_worker.py")
    assert '"threshold": 0.3' in src, (
        "threshold VAD phải hạ xuống 0.3 (G3) — mặc định 0.5 bỏ sót cả đoạn "
        "thoại thật khi nhạc nền/hiệu ứng dồn dập")


def test_whisper_in_process_khop_threshold_voi_subprocess():
    """Hai đường Whisper (subprocess + in-process) PHẢI cùng threshold — sửa
    một đường quên đường kia là đúng lớp lỗi #2 đã lặp lại nhiều lần."""
    src = _doc("autodub", "speech", "transcriber.py")
    assert '"threshold": 0.3' in src


def test_paraformer_khop_threshold_voi_whisper():
    """Paraformer dùng CHUNG model Silero VAD — cùng bug, cùng ngưỡng."""
    src = _doc("autodub", "speech", "asr_paraformer_worker.py")
    assert "vad_cfg.silero_vad.threshold = 0.3" in src


def test_khong_ha_threshold_qua_thap_ma_khong_ban_ghi():
    """0.3 là ngưỡng ĐÃ ĐO — không phải số đoán. Nếu ai đó đổi tiếp (vd 0.1),
    phải kèm số liệu đo lại (giống G3), không chỉnh tay theo cảm tính. Test
    này chỉ khoá giá trị hiện tại, không cấm đổi — đổi thì phải sửa test
    cùng lúc, đúng nghĩa "chỉnh có chủ đích, không phải quên"."""
    for path, needle in (
        ("autodub/speech/asr_whisper_worker.py", r'"threshold":\s*([\d.]+)'),
        ("autodub/speech/transcriber.py", r'"threshold":\s*([\d.]+)'),
        ("autodub/speech/asr_paraformer_worker.py",
         r"silero_vad\.threshold\s*=\s*([\d.]+)"),
    ):
        src = _doc(*path.split("/"))
        m = re.search(needle, src)
        assert m, f"không tìm thấy threshold trong {path}"
        assert float(m.group(1)) == pytest.approx(0.3), (
            f"{path}: threshold đã đổi khỏi 0.3 (giá trị đã đo ở G3) mà "
            "không có test/tài liệu đo lại đi kèm")


# --------------------------------------------------------------------- #
# Đo thật bằng model Silero VAD thật (đã có sẵn trong .venv-whisper, không
# cần tải gì thêm) — xác nhận CƠ CHẾ, không chỉ tin vào con số trong comment.

def _co_faster_whisper() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _co_faster_whisper(), reason=(
    "Cần faster-whisper — chạy bằng .venv-whisper/bin/python hoặc "
    ".venv-test/bin/python (cả hai đều có) nếu muốn tự verify."))
def test_threshold_thap_hon_phat_hien_nhieu_audio_hon_tren_nhieu_tren():
    """Không dùng audio thật (bản quyền phim Sing 2) — tổng hợp tín hiệu mô
    phỏng ĐÚNG cơ chế đã đo: một đoạn giống-giọng-nói cường độ thấp bị chôn
    trong nhiễu, để xác nhận HƯỚNG tác động của threshold mà không cần audio
    thật. Không kỳ vọng khớp số liệu tuyệt đối của G3 (đó là môi trường thật,
    xem docs/TEST_LOG.md) — chỉ khoá đúng HƯỚNG: threshold thấp hơn không
    bao giờ phát hiện ÍT audio hơn threshold cao hơn."""
    import numpy as np
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    rng = np.random.default_rng(0)
    sr = 16000
    # Nhiễu nền liên tục (mô phỏng nhạc/hiệu ứng) trộn với vài đoạn biên độ
    # cao hơn xen kẽ (mô phỏng có lời nói nhưng bị nhiễu che bớt) — không
    # cần giống giọng người thật, chỉ cần tạo tín hiệu mà độ tin cậy VAD
    # dao động quanh ngưỡng 0.3-0.5 để thấy chênh lệch.
    duration_s = 20
    n = duration_s * sr
    noise = rng.normal(0, 0.02, n).astype("float32")
    for start_s in (3, 8, 13):
        seg = slice(start_s * sr, (start_s + 2) * sr)
        noise[seg] += (rng.normal(0, 0.06, 2 * sr)).astype("float32")

    ts_cao = get_speech_timestamps(
        noise, VadOptions(threshold=0.5, min_silence_duration_ms=500),
        sampling_rate=sr)
    ts_thap = get_speech_timestamps(
        noise, VadOptions(threshold=0.3, min_silence_duration_ms=500),
        sampling_rate=sr)
    tong_cao = sum(t["end"] - t["start"] for t in ts_cao)
    tong_thap = sum(t["end"] - t["start"] for t in ts_thap)
    assert tong_thap >= tong_cao, (
        "threshold thấp hơn phải phát hiện được audio NHIỀU HƠN HOẶC BẰNG, "
        "không bao giờ ít hơn — nếu test này đỏ, model VAD hoặc API đã đổi "
        "hành vi, cần điều tra lại trước khi tin số liệu G3")
