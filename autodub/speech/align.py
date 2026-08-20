"""Forced alignment cho phụ đề karaoke — mốc THẬT của từng chữ tiếng Việt.

CapCut lấy mốc chữ bằng cách chạy ASR trên audio. Ở đây điều kiện còn tốt
hơn: audio là giọng TTS studio-sạch (không nhạc nền) và VĂN BẢN ĐÃ BIẾT
TRƯỚC (chính là bản dịch) — chỉ cần mốc thời gian, không cần đoán chữ.

Cách làm: Whisper ``base`` (~150 MB, tự tải lần đầu) nghe TỪNG clip WAV với
``word_timestamps=True``, rồi khớp chuỗi chữ Whisper nghe được với chuỗi chữ
của bản dịch:

- Số chữ hai bên bằng nhau (đa số — tiếng Việt đơn âm tiết) → map 1:1.
- Lệch nhau → nội suy vị trí (chữ thứ i của bản dịch lấy mốc của chữ
  ``i * n_asr / n_text`` phía Whisper). Nhịp vẫn đúng vì tổng thời lượng và
  các mốc neo là thật; chỉ ranh giới giữa các chữ bị nhòe nhẹ.

Mỗi clip độc lập — một clip khớp hỏng chỉ mất alignment của đúng clip đó
(caller tự rơi về ước lượng). Kết quả cache JSON trong work_dir nên resume
và rebuild không phải nghe lại.

Whisper chạy ở ĐÂU (mini-spec V75): ưu tiên ``.venv-whisper`` qua
``align_whisper_worker.py``; chỉ bản chạy từ mã nguồn mới được nạp model
ngay trong tiến trình này. ``autodub.spec`` cố ý không đóng gói
faster-whisper, nên trước V75 bản ``.exe`` KHÔNG canh được chữ lần nào —
và vì lỗi bị ``try/except`` nuốt, phụ đề âm thầm rơi về chia đều thời lượng
câu mà không ai biết.
"""
from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from autodub.progress import PipelineCancelled
from autodub.subprocess_watchdog import SubprocessTimeoutError, WatchedLineReader
from autodub.utils import (
    bundled_file,
    gpu_venv_dir,
    save_json_atomic,
    seg_wav_path,
    setup_logging,
)

logger = setup_logging("autodub.align")

# Model alignment: "base" đủ cho audio TTS sạch; đổi chỉ khi có lý do đo được.
ALIGN_MODEL = "base"

# Clip ngắn hơn mức này không đáng chạy model — ước lượng là đủ.
_MIN_CLIP_S = 0.4

_ALIGN_WORKER_SCRIPT = bundled_file("autodub", "speech",
                                    "align_whisper_worker.py")

# Cùng lý do như transcriber.py: `for line in proc.stdout` không có timeout,
# worker treo là treo luôn cả lượt xuất video. Model canh chữ là "base" (~150
# MB) — nhỏ hơn nhiều large-v3, nhưng LẦN ĐẦU phải tải về nên ngưỡng "sẵn
# sàng" vẫn để rộng.
_ALIGN_READY_TIMEOUT_S = 900     # nạp (và có thể tải) model base
_ALIGN_CLIP_TIMEOUT_S = 600      # giữa hai clip liên tiếp


def _align_workers() -> int:
    """Số clip nghe song song. Base model nhỏ nên nghẽn là CPU, không phải RAM."""
    return max(1, min(4, (os.cpu_count() or 4) // 2))


def _load_align_model():
    """Whisper base cho alignment. Trả ``(model, device, n_workers)``.

    ``num_workers`` cho phép gọi ``transcribe`` từ nhiều luồng Python cùng lúc
    (ctranslate2 giữ một bản trọng số, mỗi luồng một bộ đệm) — canh phụ đề là
    hàng trăm clip ngắn độc lập nên đây là chỗ song song hóa gần như tuyến tính.
    """
    from faster_whisper import WhisperModel

    from autodub.resources import GPU_LOCK, cpu_share
    from autodub.speech.transcriber import _enable_cuda_dlls
    if _enable_cuda_dlls():
        with GPU_LOCK:
            # float16 là đường nhanh nhất của ctranslate2 trên GPU; int8 trên
            # CUDA phải giải lượng tử liên tục nên chậm hơn.
            for compute in ("float16", "int8_float16", "int8"):
                try:
                    model = WhisperModel(ALIGN_MODEL, device="cuda",
                                         compute_type=compute)
                    # GPU đã bị một model chiếm hết — thêm luồng chỉ tranh nhau.
                    return model, "cuda", 1
                except Exception as e:
                    logger.debug(f"Alignment GPU {compute} không chạy ({e})")
        logger.info("Alignment dùng CPU")
    workers = _align_workers()
    model = WhisperModel(ALIGN_MODEL, device="cpu", compute_type="int8",
                         cpu_threads=cpu_share(workers), num_workers=workers)
    return model, "cpu", workers


def _asr_words(model, wav_path: str,
               language: str = "vi") -> list[tuple[str, float, float]]:
    """Chữ + mốc (tương đối trong clip) Whisper nghe được từ một clip.

    ``language`` PHẢI khớp ngôn ngữ ĐÍCH thật của clip TTS (mini-spec V11,
    xem docs/PLAN.md) — trước đây hardcode "vi", nên clip TTS tiếng Anh bị
    Whisper nghe nhầm sang tiếng Việt, alignment sai/rớt về ước lượng cho
    MỌI video không phải tiếng Việt. Không có fallback ngầm ở đây; caller
    (``align_segments``) chịu trách nhiệm truyền đúng mã Whisper.
    """
    segments, _info = model.transcribe(
        wav_path, language=language, word_timestamps=True,
        beam_size=1,              # audio sạch — greedy đủ, nhanh gấp đôi
        condition_on_previous_text=False,
        vad_filter=False,         # clip đã là lời nói thuần
    )
    out: list[tuple[str, float, float]] = []
    for seg in segments:
        for w in seg.words or []:
            token = w.word.strip()
            if token:
                out.append((token, float(w.start), float(w.end)))
    return out


def _map_words(
    text_words: list[str],
    asr_words: list[tuple[str, float, float]],
    clip_start: float,
    clip_dur: float,
) -> list[tuple[str, float, float]] | None:
    """Gán mốc cho từng chữ của bản dịch từ mốc Whisper nghe được.

    Trả về mốc TUYỆT ĐỐI (đã cộng ``clip_start``), hoặc None khi kết quả
    ASR quá lệch để tin (quá ít chữ so với văn bản).
    """
    nt, na = len(text_words), len(asr_words)
    if nt == 0 or na == 0:
        return None
    # ASR nghe ra quá ít chữ (nuốt nửa câu) → mốc nội suy sẽ sai nhịp nặng;
    # thà ước lượng đều còn hơn.
    if na < nt * 0.5:
        return None

    out: list[tuple[str, float, float]] = []
    if na == nt:
        pairs = zip(text_words, asr_words)
        for token, (_w, t0, t1) in pairs:
            out.append((token, clip_start + t0, clip_start + t1))
    else:
        # Nội suy vị trí: chữ i của văn bản ↔ vùng i*na/nt của ASR.
        for i, token in enumerate(text_words):
            j0 = min(na - 1, int(i * na / nt))
            j1 = min(na - 1, int((i + 1) * na / nt))
            t0 = asr_words[j0][1]
            t1 = asr_words[j1][2] if j1 > j0 else asr_words[j0][2]
            out.append((token, clip_start + t0, clip_start + max(t1, t0)))

    # Vá đơn điệu: mốc phải không lùi và nằm trong clip (ASR đôi khi trả
    # end < start quanh khoảng lặng).
    hi = clip_start + clip_dur
    prev = clip_start
    fixed: list[tuple[str, float, float]] = []
    for token, t0, t1 in out:
        t0 = min(max(t0, prev), hi)
        t1 = min(max(t1, t0 + 0.02), hi)
        fixed.append((token, round(t0, 3), round(t1, 3)))
        prev = t0
    return fixed


def _asr_words_subprocess(
    todo: list[tuple[dict, str, float, str]],
    language: str,
    settings,
    cancel_event=None,
) -> dict[int, list[tuple[str, float, float]]]:
    """Nghe từng clip bằng Whisper TRONG ``.venv-whisper`` (tiến trình con).

    Trả ``{seg_id: [(chữ, t0, t1), ...]}`` với mốc TƯƠNG ĐỐI trong clip —
    đúng thứ ``_asr_words`` trả về ở đường in-process, để ``_map_words`` phía
    sau không cần biết chữ tới từ đường nào.

    Vì sao (mini-spec V75): bản đóng gói KHÔNG có ``faster_whisper`` trong
    tiến trình chính, nên đường in-process ở đó chỉ ném ``ModuleNotFoundError``
    rồi rơi lặng lẽ về chia đều thời lượng. Clip nào worker nghe hỏng thì vắng
    mặt trong kết quả (câu đó ước lượng), nhưng hỏng CẢ MẺ thì raise để caller
    quyết định — im lặng là thứ đã làm lỗi này sống sót qua nhiều bản phát
    hành.
    """
    cuda_dll_dir = ""
    venv = gpu_venv_dir()
    if venv and os.name == "nt":
        _lib = os.path.join(venv, "Lib", "site-packages", "torch", "lib")
        if os.path.isdir(_lib):
            cuda_dll_dir = _lib

    cmd = [
        settings.whisper_venv_python_path(),
        _ALIGN_WORKER_SCRIPT,
        "--model",     ALIGN_MODEL,
        "--model-dir", settings.whisper_model_dir_path(),
        "--language",  language or "vi",
        "--workers",   str(_align_workers()),
    ]
    if cuda_dll_dir:
        cmd += ["--cuda-dll-dir", cuda_dll_dir]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    # Đóng app giữa chừng từng để lại tiến trình con mồ côi (mini-spec V40) —
    # `finally` chỉ chạy khi tiến trình cha còn sống.
    atexit.register(proc.kill)

    stderr_tail: deque[str] = deque(maxlen=30)

    def _drain() -> None:
        try:
            for line in proc.stderr:
                line = line.rstrip()
                if line:
                    stderr_tail.append(line)
                    logger.debug(f"[align-worker] {line}")
        except (ValueError, OSError):
            pass

    threading.Thread(target=_drain, daemon=True).start()
    reader = WatchedLineReader(proc)

    # V76 — luồng canh cờ Dừng, GIẾT tiến trình chứ không chỉ kiểm cờ ở đầu
    # vòng. Bài học V72: kiểm-rồi-chờ chỉ đúng khi cái chờ ngắn; ở đây câu
    # đầu tiên có thể mất hàng chục giây (nạp model) nên vòng đọc đang kẹt
    # trong `readline()` và không bao giờ chạy tới chỗ kiểm. Giết tiến trình
    # làm stdout đóng → `readline` trả "" ngay → thoát tức thì.
    _huy_xong = threading.Event()

    def _canh_huy() -> None:
        while not _huy_xong.is_set():
            if cancel_event.wait(0.3):
                proc.kill()
                return

    if cancel_event is not None:
        threading.Thread(target=_canh_huy, daemon=True).start()

    def _kiem_huy() -> None:
        """Đo thật (V76): bấm Dừng LÚC ĐANG NẠP MODEL thì tiến trình bị giết
        khi chưa có dòng nào ra, `readline` trả "" → trước khi thêm chỗ kiểm
        này nó báo "bộ canh chữ không phản hồi ready" và tầng trên hiểu là
        HỎNG: bản mã nguồn chạy lại toàn bộ ở in-process, bản .exe ghi phụ đề
        chia đều rồi đi tiếp. Cú bấm Dừng phải trông ra cú bấm Dừng."""
        if cancel_event is not None and cancel_event.is_set():
            raise PipelineCancelled("Đã dừng theo yêu cầu.")

    words_by_sid: dict[int, list[tuple[str, float, float]]] = {}
    n_loi_clip = 0
    try:
        try:
            ready_line = reader.readline(_ALIGN_READY_TIMEOUT_S).strip()
        except SubprocessTimeoutError as e:
            _kiem_huy()
            raise RuntimeError(
                f"bộ canh chữ không phản hồi trong {_ALIGN_READY_TIMEOUT_S}s "
                "khi nạp model\n" + "\n".join(stderr_tail)) from e
        _kiem_huy()
        try:
            ready = json.loads(ready_line)
        except (json.JSONDecodeError, ValueError):
            raise RuntimeError(
                f"bộ canh chữ không phản hồi ready: {ready_line!r}\n"
                + "\n".join(stderr_tail))
        if ready.get("error") or not ready.get("ready"):
            raise RuntimeError(
                f"bộ canh chữ báo lỗi: {ready.get('error') or ready}\n"
                + "\n".join(stderr_tail))

        req = {
            "language": language or "vi",
            "clips": [{"id": seg.get("id"), "wav": wav}
                      for seg, wav, _dur, _key in todo],
        }
        try:
            proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
            proc.stdin.flush()
            proc.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            # Tiến trình vừa bị giết vì Dừng — không phải lỗi gửi request.
            _kiem_huy()
            raise

        done = False
        while True:
            try:
                line = reader.readline(_ALIGN_CLIP_TIMEOUT_S)
            except SubprocessTimeoutError as e:
                _kiem_huy()
                raise RuntimeError(
                    f"bộ canh chữ không phản hồi trong "
                    f"{_ALIGN_CLIP_TIMEOUT_S}s giữa hai câu (đã canh được "
                    f"{len(words_by_sid)} câu)\n"
                    + "\n".join(stderr_tail)) from e
            if not line:
                # stdout đóng: hoặc worker xong, hoặc ta vừa giết nó vì Dừng.
                # Phân biệt hai ca — nếu không, lượt bị dừng trông y hệt một
                # lượt canh xong với 0 câu (rồi phụ đề lặng lẽ chia đều).
                if cancel_event is not None and cancel_event.is_set():
                    raise PipelineCancelled("Đã dừng theo yêu cầu.")
                break
            if cancel_event is not None and cancel_event.is_set():
                proc.kill()
                raise PipelineCancelled("Đã dừng theo yêu cầu.")
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("error") and not msg.get("clip"):
                raise RuntimeError(f"bộ canh chữ: {msg['error']}\n"
                                   + "\n".join(stderr_tail))
            if msg.get("clip"):
                sid = msg.get("id")
                if msg.get("error"):
                    n_loi_clip += 1
                    logger.debug(f"Canh chữ câu {sid} lỗi ({msg['error']}) "
                                 "— ước lượng")
                    continue
                words_by_sid[sid] = [
                    (str(w.get("word", "")).strip(),
                     float(w.get("start", 0.0)), float(w.get("end", 0.0)))
                    for w in (msg.get("words") or [])
                    if str(w.get("word", "")).strip()
                ]
            elif msg.get("done"):
                done = True
        proc.wait(timeout=600)
    finally:
        # Dừng luồng canh trước tiên — để nó sống tiếp là giữ một luồng chờ
        # vô ích cho mỗi mẻ đã xong.
        _huy_xong.set()
        if proc.poll() is None:
            proc.kill()
        atexit.unregister(proc.kill)
        for stream in (proc.stdout, proc.stderr):
            if stream:
                try:
                    stream.close()
                except Exception:
                    pass

    if not done:
        raise RuntimeError(
            f"bộ canh chữ thoát bất thường (mã {proc.returncode})"
            + ("\n" + "\n".join(stderr_tail) if stderr_tail else ""))
    if n_loi_clip:
        logger.debug(f"{n_loi_clip}/{len(todo)} câu bộ canh chữ nghe hỏng")
    return words_by_sid


def _asr_words_in_process(
    todo: list[tuple[dict, str, float, str]],
    language: str,
    cancel_event=None,
) -> dict[int, list[tuple[str, float, float]]]:
    """Đường cũ: nạp model NGAY TRONG tiến trình này.

    CHỈ hợp lệ khi chạy từ mã nguồn — bản ``.exe`` không đóng gói
    faster-whisper (xem ``autodub.spec``).

    Lưới an toàn cho lần sau: cùng một giả định sai ("cứ import là được") đã
    tái diễn ở ``_smoke_report`` (V38), ``preflight`` (V74) rồi chính tệp này
    (V75). Nên ở đây chặn thẳng thay vì để ``ModuleNotFoundError: av`` giả
    làm nguyên nhân.
    """
    if getattr(sys, "frozen", False):
        raise RuntimeError(
            "bản đóng gói không có faster-whisper trong tiến trình chính — "
            "phải nghe qua .venv-whisper")
    model, _device, n_workers = _load_align_model()

    def _one(item):
        seg, wav, _dur, _key = item
        sid = seg.get("id")
        # Mỗi clip chỉ 1–3 giây nên kiểm ở đầu mỗi clip là đủ nhanh; không
        # có cách nào cắt ngang một lượt `transcribe()` in-process.
        if cancel_event is not None and cancel_event.is_set():
            raise PipelineCancelled("Đã dừng theo yêu cầu.")
        try:
            return sid, _asr_words(model, wav, language)
        except Exception as e:
            logger.debug(f"ASR alignment câu {sid} lỗi ({e}) — ước lượng")
            return sid, None

    try:
        if n_workers > 1:
            with ThreadPoolExecutor(max_workers=n_workers) as pool:
                done = list(pool.map(_one, todo))
        else:
            done = [_one(item) for item in todo]
    finally:
        # Model base nhỏ; thả tham chiếu là đủ (ctranslate2 tự nhả khi GC).
        # Gán None thay vì `del`: `del` làm công cụ phân tích tĩnh báo closure
        # `_one` đang dùng tên đã bị xoá, che mất cảnh báo THẬT cùng loại.
        model = None  # noqa: F841 — thả tham chiếu cho GC

    return {sid: words for sid, words in done if words is not None}


def _asr_words_for_clips(
    todo: list[tuple[dict, str, float, str]],
    language: str,
    settings,
    cancel_event=None,
) -> dict[int, list[tuple[str, float, float]]] | None:
    """Chọn đường nghe rồi trả mốc chữ cho cả mẻ; ``None`` = không canh được.

    Thứ tự y hệt ``transcriber.transcribe`` để không đẻ ra một quy tắc thứ
    hai: có ``.venv-whisper`` thì đi subprocess; không có thì in-process,
    TRỪ bản đóng gói — ở đó in-process không tồn tại nên phải nói thẳng là
    chưa cài, thay vì âm thầm chia đều thời lượng.
    """
    dong_bang = getattr(sys, "frozen", False)
    if settings is not None and settings.whisper_venv_configured():
        try:
            return _asr_words_subprocess(todo, language, settings,
                                         cancel_event=cancel_event)
        except PipelineCancelled:
            # Dừng KHÔNG phải lỗi. Nuốt nó ở đây là chạy lại toàn bộ ở
            # in-process — đúng lỗi đã mắc ở V74 với TranscribeCancelled.
            raise
        except Exception as e:
            if dong_bang:
                logger.warning(
                    f"Không canh được phụ đề theo giọng đọc ({e}) — chữ sẽ "
                    "chia đều theo thời lượng câu")
                return None
            logger.warning(f"Bộ canh chữ trong .venv-whisper lỗi ({e}) — "
                           "thử lại ngay trong tiến trình này")
    elif dong_bang:
        # Thông báo này có bản dịch riêng trong log_text.NOTICES nên tới được
        # khung Nhật ký; đừng đổi 6 chữ đầu mà không sửa cả bảng đó.
        logger.warning(
            "Không canh được phụ đề: chưa cài bộ nghe Whisper trong thư mục "
            'ứng dụng này — đúp chuột "Cai dat Whisper ASR.bat" rồi chạy lại '
            "thì chữ mới nhảy đúng nhịp giọng đọc")
        return None

    try:
        return _asr_words_in_process(todo, language, cancel_event=cancel_event)
    except PipelineCancelled:
        raise
    except Exception as e:
        logger.warning(f"Không canh được phụ đề theo giọng đọc ({e}) — "
                       "chữ sẽ chia đều theo thời lượng câu")
        return None


def align_segments(
    segments: list[dict],
    merge_dir: str,
    text_field: str,
    cache_path: str | None = None,
    language: str = "vi",
    settings=None,
    cancel_event=None,
) -> dict[int, list[tuple[str, float, float]]]:
    """Alignment thật cho mọi segment. Trả ``{id: [(chữ, t0, t1), ...]}``.

    Mốc trả về TUYỆT ĐỐI theo timeline video (clip đặt tại ``seg["start"]``).
    Segment thiếu file/khớp hỏng thì vắng mặt trong kết quả — caller bù bằng
    ước lượng. Cache theo (mtime clip, text) nên chỉ câu bị re-TTS/sửa chữ
    mới phải nghe lại.

    ``language`` là mã Whisper của NGÔN NGỮ ĐÍCH (giọng TTS đọc thứ tiếng
    gì) — mặc định "vi" để mọi lời gọi cũ (chỉ có target tiếng Việt trước
    V11) chạy y hệt trước, KHÔNG suy ra tự động ở đây (mini-spec V11, xem
    docs/PLAN.md — caller là nơi biết target thật).
    """
    from autodub.media.audio import wav_duration_s

    cache: dict = {}
    if cache_path and os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            cache = {}

    out: dict[int, list[tuple[str, float, float]]] = {}
    todo: list[tuple[dict, str, float, str]] = []  # (seg, wav, dur, key)
    for seg in segments:
        sid = seg.get("id")
        text = str(seg.get(text_field, "")).strip()
        if not text:
            continue
        wav = seg_wav_path(merge_dir, sid)
        if not os.path.exists(wav):
            continue
        dur = wav_duration_s(wav)
        if not dur or dur < _MIN_CLIP_S:
            continue
        key = f"{sid}:{int(os.path.getmtime(wav))}:{hash(text) & 0xFFFFFFFF}"
        hit = cache.get(key)
        if hit:
            # Cache giữ mốc TƯƠNG ĐỐI trong clip — cộng start hiện tại để
            # timeline mềm dịch clip đi đâu mốc vẫn theo đó.
            base = float(seg["start"])
            out[sid] = [(w, round(base + t0, 3), round(base + t1, 3))
                        for w, t0, t1 in hit]
            continue
        todo.append((seg, wav, dur, key))

    if not todo:
        return out

    n_cached = len(out)
    logger.info(f"Đang canh phụ đề nhảy đúng nhịp giọng đọc "
                f"({len(todo)} câu"
                + (f", {n_cached} câu dùng lại của lần trước" if n_cached else "")
                + ") — chờ chút...")
    if settings is None:
        # Caller cũ không truyền settings — vẫn phải biết .venv-whisper nằm
        # đâu, nếu không bản đóng gói lại rơi về đường in-process không tồn
        # tại. Đọc cấu hình ở đây là rẻ (chỉ .env + biến môi trường).
        try:
            from autodub.config import Settings
            settings = Settings.load()
        except Exception as e:
            logger.debug(f"Không đọc được cấu hình cho bộ canh chữ ({e})")

    asr_by_sid = _asr_words_for_clips(todo, language, settings,
                                      cancel_event=cancel_event)
    if asr_by_sid is None:
        return out

    def _one(item):
        seg, wav, dur, key = item
        sid = seg.get("id")
        asr = asr_by_sid.get(sid)
        if not asr:
            return None
        text_words = str(seg.get(text_field, "")).split()
        mapped = _map_words(text_words, asr, float(seg["start"]), dur)
        if mapped is None:
            return None
        return sid, key, float(seg["start"]), mapped

    done = [_one(item) for item in todo]

    new_cache_entries: dict = {}
    n_ok = 0
    for res in done:
        if res is None:
            continue
        sid, key, base, mapped = res
        out[sid] = mapped
        n_ok += 1
        new_cache_entries[key] = [
            [w, round(t0 - base, 3), round(t1 - base, 3)]
            for w, t0, t1 in mapped
        ]

    n_est = len(todo) - n_ok
    logger.info(f"Canh phụ đề xong: {n_ok}/{len(todo)} câu khớp chính xác "
                "theo giọng đọc"
                + (f", {n_est} câu chia đều theo thời lượng" if n_est else ""))
    if cache_path and new_cache_entries:
        try:
            save_json_atomic({**cache, **new_cache_entries}, cache_path)
        except OSError:
            pass
    return out
