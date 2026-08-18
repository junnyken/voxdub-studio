"""Driver diarization — gọi ``diarize_worker.py`` qua subprocess, map kết
quả vào ASR segments theo % overlap thời gian lớn nhất. Mini-spec V26
(docs/PLAN.md, Phase G).

Dùng ``autodub.subprocess_watchdog`` NGAY TỪ ĐẦU (không lặp lại bug đã sửa ở
V24 cho translate_local/Whisper/Paraformer/voice_downloader) — diarization
xử lý CẢ FILE audio 1 lượt trước khi có dòng đầu tiên (không phải giao thức
streaming-theo-khối), nên timeout ở đây là timeout TỔNG cho toàn bộ lượt xử
lý, không phải giữa các dòng.
"""
from __future__ import annotations

import json
import subprocess
import threading
from collections import deque

from autodub.config import Settings
from autodub.subprocess_watchdog import SubprocessTimeoutError, WatchedLineReader
from autodub.utils import bundled_file, setup_logging

logger = setup_logging("autodub.diarization")

_WORKER_SCRIPT = bundled_file("autodub", "speech", "diarize_worker.py")

#: Bảo thủ có chủ đích — CHƯA benchmark thật (không có GPU/HF token trong
#: sandbox phát triển, xem docs/TEST_LOG.md mục V26). Toàn bộ audio xử lý 1
#: lượt trước dòng đầu tiên, nên đây là trần cho CẢ VIDEO, không phải/đoạn.
_DIARIZE_TIMEOUT_S = 1800


class DiarizationError(Exception):
    """Lỗi thật khi chạy diarization — caller (pipeline) quyết định fallback
    về single-voice (Constraint 2 của V26: không giả vờ có mà gán bừa)."""


def diarize(audio_path: str, settings: Settings,
            with_embeddings: bool = False,
            num_speakers: int = 0, min_speakers: int = 0,
            max_speakers: int = 0):
    """Chạy diarization worker trên ``audio_path``.

    Trả về danh sách các khoảng nói theo thời gian, sắp theo thứ tự worker
    phát ra: ``[{"start": float, "end": float, "speaker": "SPEAKER_00"}, ...]``.
    Raise :class:`DiarizationError` nếu thất bại.

    ``with_embeddings=True`` (mini-spec V59) trả thêm bản đồ
    ``{speaker: [float, ...]}`` — vector đặc trưng giọng do chính pyannote
    tính sẵn khi gom nhóm người nói. Mặc định ``False`` để mọi caller cũ (và
    test V26) giữ nguyên chữ ký trả về là 1 danh sách.

    Bản pyannote cũ không hỗ trợ thì bản đồ này RỖNG — caller phải tự lo
    đường lui (hồ sơ nhân vật rơi về khớp bằng cao độ giọng), không được coi
    embedding là chắc chắn có.
    """
    cmd = [
        settings.diarization_venv_python_path(),
        _WORKER_SCRIPT,
        "--audio", audio_path,
        "--model-dir", settings.diarization_model_dir_path(),
    ]
    # V65b — gợi ý số người nói. `0` = không biết, worker bỏ qua. Chỉ thêm
    # tham số nào khác 0 để dòng lệnh trong log đọc ra đúng ý định lượt chạy.
    for co, gia_tri in (("--num-speakers", num_speakers),
                        ("--min-speakers", min_speakers),
                        ("--max-speakers", max_speakers)):
        if gia_tri and gia_tri > 0:
            cmd += [co, str(int(gia_tri))]
    logger.info("Đang tách giọng theo người nói (diarization)...")
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding="utf-8", errors="replace",
    )

    stderr_tail: deque[str] = deque(maxlen=30)

    def _drain() -> None:
        try:
            for line in proc.stderr:
                line = line.rstrip()
                if line:
                    stderr_tail.append(line)
        except (ValueError, OSError):
            pass

    threading.Thread(target=_drain, daemon=True).start()
    reader = WatchedLineReader(proc)

    segments: list[dict] = []
    embeddings: dict[str, list[float]] = {}
    done = False
    try:
        while True:
            line = reader.readline(_DIARIZE_TIMEOUT_S)
            if not line:
                break
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("error"):
                raise DiarizationError(f"Worker diarization: {msg['error']}")
            if msg.get("segment"):
                segments.append({
                    "start": float(msg["start"]),
                    "end": float(msg["end"]),
                    "speaker": str(msg["speaker"]),
                })
            elif msg.get("embedding"):
                vector = msg.get("vector") or []
                if vector:
                    embeddings[str(msg["speaker"])] = [float(x) for x in vector]
            elif msg.get("warn"):
                logger.info("Diarization: %s", msg["warn"])
            elif msg.get("done"):
                done = True
    except SubprocessTimeoutError as e:
        proc.kill()
        raise DiarizationError(
            f"Worker diarization không phản hồi trong {_DIARIZE_TIMEOUT_S}s "
            "— coi như treo.\n" + "\n".join(stderr_tail)) from e

    proc.wait(timeout=30)
    if not done:
        raise DiarizationError(
            "Worker diarization kết thúc bất thường\n" + "\n".join(stderr_tail))

    num_speakers = len({s["speaker"] for s in segments})
    logger.info(f"Diarization xong: {len(segments)} khoảng nói, "
               f"{num_speakers} người nói"
               + (f", {len(embeddings)} embedding" if embeddings else ""))
    if with_embeddings:
        return segments, embeddings
    return segments


def assign_speakers(asr_segments: list[dict], diar_segments: list[dict]) -> None:
    """Gán ``speaker_label`` cho từng ASR segment theo % overlap thời gian
    LỚN NHẤT với các khoảng diarization (Design Choice V26 — đơn giản, đủ
    dùng cho video 2-4 người nói không chồng tiếng nhiều).

    Sửa TRỰC TIẾP ``asr_segments`` (thêm key mới, không đổi field cũ nào).
    ASR segment không overlap khoảng diarization nào (hiếm — khoảng lặng
    ASR tạo ra mà diarization không phủ tới) giữ nguyên, không có
    ``speaker_label``.
    """
    for seg in asr_segments:
        seg_start, seg_end = seg["start"], seg["end"]
        best_speaker = None
        best_overlap = 0.0
        for d in diar_segments:
            overlap = min(seg_end, d["end"]) - max(seg_start, d["start"])
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = d["speaker"]
        if best_speaker is not None:
            seg["speaker_label"] = best_speaker
