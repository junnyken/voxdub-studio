"""Paraformer ASR driver — runs the worker in .venv-asr as a one-shot subprocess.

Unlike the TTS engines (hundreds of small requests → persistent worker pool),
ASR is one request per pipeline run, so the worker starts, streams one JSON
line per recognized segment (progress shows up in the GUI log live) and exits.

The worker script (:mod:`autodub.speech.asr_paraformer_worker`) is standalone
and executes with the .venv-asr interpreter — sherpa-onnx never has to be
installed in (or bundled with) the main app.
"""
from __future__ import annotations

import json
import subprocess
import threading
from collections import deque

from autodub.config import Settings
from autodub.subprocess_watchdog import SubprocessTimeoutError, WatchedLineReader
from autodub.utils import bundled_file, setup_logging

logger = setup_logging("autodub.paraformer")

_WORKER_SCRIPT = bundled_file("autodub", "speech", "asr_paraformer_worker.py")

# mini-spec V24 (docs/PLAN.md, Phase F, đợt 2) — cùng bug đã sửa ở
# translate_local.py/transcriber.py: đọc stdout không timeout, worker treo
# làm pipeline treo vô thời hạn. Không có bước "ready" riêng (worker phát
# thẳng segment) nên chỉ 1 hằng số; tham chiếu `proc.wait(timeout=600)`
# sẵn có (10 phút) — chưa benchmark phần cứng thật.
_PARAFORMER_SEGMENT_TIMEOUT_S = 300


def transcribe_paraformer(audio_path: str, settings: Settings) -> list[dict]:
    """Run the Paraformer worker on ``audio_path`` (16 kHz mono WAV).

    Returns Whisper-shaped segments ``[{id, text, start, end, duration}]``.
    Raises :class:`RuntimeError` on any failure — the caller falls back to
    Whisper.
    """
    cmd = [
        settings.asr_venv_python_path(),
        _WORKER_SCRIPT,
        "--audio", audio_path,
        "--model-dir", settings.paraformer_model_dir_path(),
        "--num-threads", str(settings.asr_num_threads),
    ]
    logger.info("Nhận dạng tiếng Trung bằng Paraformer (sherpa-onnx, CPU)...")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )

    stderr_tail: deque[str] = deque(maxlen=20)

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
    done = False
    # mini-spec V41: mặc định True (khớp hành vi cũ nếu worker cũ không gửi
    # field này) — chỉ hạ xuống False khi worker THẬT SỰ báo thiếu model
    # chấm câu, tránh cảnh báo giả cho lượt chạy bình thường.
    punctuation_available = True
    try:
        while True:
            line = reader.readline(_PARAFORMER_SEGMENT_TIMEOUT_S)
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
                raise RuntimeError(f"Paraformer worker: {msg['error']}")
            if msg.get("seg"):
                start = float(msg["start"])
                end = float(msg["end"])
                segments.append({
                    "id": len(segments) + 1,
                    "text": str(msg["text"]).strip(),
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "duration": round(end - start, 3),
                })
                logger.info(f"Segment {len(segments)}: "
                            f"[{start:.1f}s-{end:.1f}s] {msg['text'][:50]}...")
            elif msg.get("done"):
                done = True
                punctuation_available = bool(msg.get("punctuation_available", True))
        # Thời lượng phụ thuộc độ dài video — chờ tiến trình kết thúc hẳn
        # (stdout đã EOF nên wait không thể treo vô hạn vì pipe đầy).
        proc.wait(timeout=600)
    except SubprocessTimeoutError as e:
        proc.kill()
        raise RuntimeError(
            f"Paraformer worker không phản hồi trong "
            f"{_PARAFORMER_SEGMENT_TIMEOUT_S}s giữa lúc nhận dạng — coi như "
            f"treo (đã nhận dạng được {len(segments)} đoạn trước đó).\n"
            + "\n".join(stderr_tail)) from e
    finally:
        if proc.poll() is None:
            proc.kill()
        for s in (proc.stdout, proc.stderr):
            if s is not None:
                try:
                    s.close()
                except Exception:  # đóng phiên lúc dọn dẹp, hỏng cũng không còn gì để cứu
                    pass

    tail = "\n".join(stderr_tail)
    if not done:
        raise RuntimeError(
            f"Paraformer worker thoát bất thường (exit {proc.returncode})"
            + (f"\n{tail}" if tail else ""))
    if not segments:
        raise RuntimeError("Paraformer không nhận dạng được câu nào"
                           + (f"\n{tail}" if tail else ""))
    if not punctuation_available:
        # mini-spec V41: trước đây chỉ log ở stderr của worker con (GUI
        # không đọc) — giờ cảnh báo NGAY tại logger chính, người dùng thấy
        # được lý do bản dịch/TTS sau này có thể gộp nhiều câu làm một
        # (transcript thiếu dấu câu → mất ranh giới câu). Chạy lại
        # `scripts/setup_paraformer.py` để tải lại model chấm câu.
        logger.warning(
            "Model chấm câu tiếng Trung (CT-Transformer) không có — "
            "transcript sẽ KHÔNG có dấu câu, có thể ảnh hưởng chất lượng "
            "dịch (nhiều câu gộp làm một). Chạy lại "
            "scripts/setup_paraformer.py để tải lại model chấm câu.")
    return segments
