"""Ước lượng giới tính từng người nói từ cao độ giọng nói (F0/pitch) — mini-
spec V36, docs/PLAN.md Phase G. Hàm thuần, KHÔNG phụ thuộc model AI phân
loại giọng nói riêng (Constraint 1) — ước lượng F0 bằng autocorrelation
thuần numpy trên các khung "có tiếng nói" (voiced), cùng tinh thần "tín
hiệu số học đơn giản, đủ dùng" đã dùng cho `autodub/speech/tts/
audio_quality.py` (V35).

Đây là HEURISTIC THÔ (Constraint 2 của V36) — không phải phân loại khoa
học chính xác. Khi không đủ dữ liệu voiced hoặc F0 trung vị nằm trong vùng
mù mờ giữa 2 ngưỡng, trả `""` (không đoán) thay vì chọn liều — caller
(`voice_assign.assign_voices_by_gender()`) tự rơi về round-robin cho
speaker đó.

Chạy trong venv CHÍNH (không phải venv con cô lập như `.venv-vieneu`/
`.venv-whisper`) — module này được gọi từ `pipeline.py`, có toàn bộ
`autodub` package + numpy sẵn có, không cần nạp qua file path như
`vieneu_worker.py` phải làm.
"""
from __future__ import annotations

import numpy as np

#: Miền tần số cơ bản giọng nói người lớn thực tế (loại bỏ hài âm cao/thấp
#: giả — không phải trần sinh lý học chính xác, chỉ đủ lọc nhiễu autocorrelation).
_F0_MIN_HZ = 60.0
_F0_MAX_HZ = 400.0

#: Ngưỡng phân loại — CÓ KHOẢNG TRỐNG cố ý giữa 2 ngưỡng (145-175Hz) cho
#: vùng "không chắc" (Constraint 2) — giọng nam trầm/nữ cao thật có thể lệch
#: khỏi khoảng trung bình thống kê, thà bỏ qua còn hơn gán sai.
_MALE_MAX_HZ = 145.0
_FEMALE_MIN_HZ = 175.0

#: Khung phân tích 40ms/bước nhảy 20ms — đủ chu kỳ cho F0 thấp nhất quan tâm
#: (60Hz ~ 16.7ms/chu kỳ) mà vẫn đủ độ phân giải thời gian.
_FRAME_MS = 40.0
_HOP_MS = 20.0

#: Ngưỡng độ nổi bật đỉnh tự tương quan — khung nhiễu/câm có tỷ lệ này thấp,
#: loại khỏi tập ước lượng thay vì tính ra F0 giả.
_CONFIDENCE_MIN = 0.3

#: Cần tối thiểu chừng này giây khung F0 hợp lệ mới đủ tin để phân loại —
#: vài khung lẻ tẻ dễ bị nhiễu chi phối.
_MIN_VOICED_SECONDS = 0.5


def _frame_f0(frame: np.ndarray, sr: int) -> float:
    """F0 (Hz) của 1 khung bằng autocorrelation, hoặc 0.0 nếu không đủ tin
    (khung câm/nhiễu, không tìm được chu kỳ rõ ràng)."""
    frame = frame.astype(np.float64) - frame.mean()
    energy = float(np.dot(frame, frame))
    if energy <= 0:
        return 0.0

    corr = np.correlate(frame, frame, mode="full")
    corr = corr[len(corr) // 2:]   # chỉ giữ lag >= 0
    if corr[0] <= 0:
        return 0.0

    min_lag = max(1, int(sr / _F0_MAX_HZ))
    max_lag = min(len(corr) - 1, int(sr / _F0_MIN_HZ))
    if min_lag >= max_lag:
        return 0.0

    segment = corr[min_lag:max_lag + 1]
    peak_idx = int(np.argmax(segment))
    peak_val = segment[peak_idx]
    confidence = peak_val / corr[0]
    if confidence < _CONFIDENCE_MIN:
        return 0.0

    lag = min_lag + peak_idx
    return sr / lag if lag > 0 else 0.0


def _speaker_f0_samples(wav: np.ndarray, sr: int) -> list[float]:
    """F0 hợp lệ (>0) của mọi khung trong đoạn audio 1 người nói."""
    frame_len = max(1, int(sr * _FRAME_MS / 1000))
    hop_len = max(1, int(sr * _HOP_MS / 1000))
    f0s = []
    for start in range(0, max(0, len(wav) - frame_len + 1), hop_len):
        f0 = _frame_f0(wav[start:start + frame_len], sr)
        if f0 > 0:
            f0s.append(f0)
    return f0s


def _classify(median_f0: float) -> str:
    if median_f0 <= 0:
        return ""
    if median_f0 <= _MALE_MAX_HZ:
        return "male"
    if median_f0 >= _FEMALE_MIN_HZ:
        return "female"
    return ""   # vùng mù mờ — không đoán (Constraint 2)


def load_wav_mono(path: str) -> tuple[np.ndarray, int]:
    """Đọc 1 file WAV PCM 16-bit thành mảng float32 mono chuẩn hoá ±1.0.

    Audio gốc trong pipeline (``audio_path`` truyền vào
    ``_apply_diarization()``) LUÔN là WAV PCM 16-bit (đầu ra của bước tách
    audio, cùng định dạng ASR/diarization worker đọc) — dùng thẳng `wave`
    stdlib, KHÔNG cần ffmpeg/pydub cho việc đọc đơn giản này (cùng cách
    đọc header nhẹ đã dùng ở `autodub/media/audio.py`/`pipeline.py`).
    """
    import wave as _wave

    with _wave.open(path, "rb") as w:
        sr = w.getframerate()
        sampwidth = w.getsampwidth()
        nchannels = w.getnchannels()
        raw = w.readframes(w.getnframes())

    if sampwidth != 2:
        raise OSError(f"Chỉ hỗ trợ WAV PCM 16-bit, file này sampwidth={sampwidth}")
    wav = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if nchannels > 1:
        wav = wav.reshape(-1, nchannels).mean(axis=1)
    return wav, sr


def estimate_speaker_genders(
    wav: np.ndarray, sr: int, diar_segments: list[dict],
) -> dict[str, str]:
    """Ước lượng giới tính TỪNG người nói phát hiện bởi diarization.

    ``wav``: toàn bộ audio (mono, đã có sẵn trong pipeline, KHÔNG đọc lại
    file — tránh I/O thừa). ``diar_segments``: kết quả
    ``autodub.speech.diarization.diarize()``
    (``[{"start", "end", "speaker"}, ...]``, giây).

    Trả về ``{speaker: "male"|"female"|""}`` cho MỌI speaker xuất hiện
    trong ``diar_segments`` — `""` khi không đủ audio voiced hoặc F0 nằm
    trong vùng không chắc (Constraint 2 của V36 — không đoán liều).
    """
    wav = np.asarray(wav, dtype=np.float64).reshape(-1)
    by_speaker: dict[str, list[float]] = {}
    for d in diar_segments:
        speaker = d.get("speaker")
        if not speaker:
            continue
        start_sample = max(0, int(d["start"] * sr))
        end_sample = min(len(wav), int(d["end"] * sr))
        if end_sample <= start_sample:
            continue
        by_speaker.setdefault(speaker, []).extend(
            _speaker_f0_samples(wav[start_sample:end_sample], sr))

    result: dict[str, str] = {}
    min_voiced_frames = int(_MIN_VOICED_SECONDS * 1000 / _HOP_MS)
    for speaker, f0s in by_speaker.items():
        if len(f0s) < min_voiced_frames:
            result[speaker] = ""
            continue
        result[speaker] = _classify(float(np.median(f0s)))
    return result
