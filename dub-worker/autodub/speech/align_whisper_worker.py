"""Forced-alignment worker — chạy TRONG ``.venv-whisper``.

Standalone: KHÔNG được import bất cứ thứ gì từ ``autodub`` (khác môi trường).
Đây là bản song sinh của ``asr_whisper_worker.py`` nhưng cho việc canh chữ
karaoke: thay vì nghe MỘT file dài một lần, nó nạp model ``base`` một lần rồi
nghe HÀNG TRĂM clip ngắn — nên model phải nạp một lần cho cả mẻ, không phải
một lần cho mỗi clip (nạp lại mỗi clip thì canh một video hết cả buổi).

Vì sao phải có tệp này (mini-spec V75): ``autodub.spec`` CỐ Ý không đóng gói
``faster_whisper``/``ctranslate2``/``av``. Trước đây ``align.py`` import chúng
NGAY TRONG tiến trình chính, có bọc ``try/except`` — nên ở bản ``.exe`` việc
canh chữ HỎNG ÂM THẦM: phụ đề rơi về chia đều theo thời lượng câu mà không ai
biết. Xem [[project-voidmix-v74-whisper-venv-gate]] và docs/PLAN.md.

CLI:
    python align_whisper_worker.py --model base --model-dir models/whisper
        [--language vi] [--workers 4] [--cuda-dll-dir path/to/torch/lib]

Giao thức stdout (mỗi dòng một JSON, mọi thứ khác đi ra stderr):
    {"ready": true, "device": "cpu", "workers": 4}
  ← stdin (MỘT dòng): {"clips": [{"id": 3, "wav": "..."}], "language": "vi"}
    {"clip": true, "id": 3, "words": [{"word": "xin", "start": 0.0, "end": 0.2}]}
    {"clip": true, "id": 4, "error": "..."}      ← một clip hỏng, mẻ vẫn chạy
    {"done": true, "n": 2}
  | {"error": "..."} rồi thoát mã 1                ← hỏng cả mẻ
"""
import argparse
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor


def _die(proto_out, msg: str) -> None:
    print(json.dumps({"error": msg}, ensure_ascii=False),
          file=proto_out, flush=True)
    sys.exit(1)


def _try_load_cuda_dlls(dll_dir: str) -> bool:
    """Nạp cuBLAS/cuDNN từ torch lib dir — giống asr_whisper_worker.py."""
    if not dll_dir or not os.path.isdir(dll_dir):
        return False
    import ctypes
    import glob

    try:
        os.add_dll_directory(dll_dir)
        matches = glob.glob(os.path.join(dll_dir, "cublas64_*.dll"))
        if matches:
            ctypes.CDLL(matches[0])
            return True
    except OSError:
        pass
    return False


def _cpu_workers(requested: int) -> int:
    """Số clip nghe song song. Giữ đúng công thức của đường in-process cũ."""
    if requested > 0:
        return min(4, requested)
    return max(1, min(4, (os.cpu_count() or 4) // 2))


def _cpu_threads(n_workers: int) -> int:
    """Thread cho MỖI worker; chừa 2 lõi cho giao diện — như resources.cpu_share."""
    return max(1, ((os.cpu_count() or 4) - 2) // max(1, n_workers))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    proto_out = sys.stdout
    sys.stdout = sys.stderr   # thư viện in ra stderr, không lẫn vào JSON

    parser = argparse.ArgumentParser()
    parser.add_argument("--model",        default="base")
    parser.add_argument("--model-dir",    default="",
                        help="Thư mục cache model; rỗng = HuggingFace default")
    parser.add_argument("--language",     default="vi")
    parser.add_argument("--workers",      type=int, default=0,
                        help="0 = tự tính theo số lõi")
    parser.add_argument("--cuda-dll-dir", default="",
                        help="Thư mục torch/lib chứa cublas64_*.dll (Windows)")
    args, _thua = parser.parse_known_args()
    if _thua:
        # C53 — tiến trình cha đời MỚI gửi tham số worker này chưa biết thì bỏ
        # qua và nói ra, KHÔNG chết. Lỗi thật 28/08: cha mới gửi `--ram-trong-gb`
        # xuống worker cũ, argparse sys.exit(2) và giết cả lượt lồng tiếng.
        print(f"Bỏ qua tham số không nhận ra: {' '.join(_thua)}",
              file=sys.stderr, flush=True)

    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        _die(proto_out, f"faster-whisper chưa cài trong .venv-whisper: {e}")

    download_root = args.model_dir or None

    cuda_ok = False
    if os.name == "nt" and args.cuda_dll_dir:
        cuda_ok = _try_load_cuda_dlls(args.cuda_dll_dir)

    model = None
    device = "cpu"
    n_workers = 1
    if cuda_ok:
        # float16 là đường nhanh nhất của ctranslate2 trên GPU; int8 trên CUDA
        # phải giải lượng tử liên tục nên chậm hơn. GPU đã bị một model chiếm
        # hết nên thêm luồng chỉ tranh nhau → giữ 1 worker.
        for compute in ("float16", "int8_float16", "int8"):
            try:
                model = WhisperModel(args.model, device="cuda",
                                     compute_type=compute,
                                     download_root=download_root)
                device, n_workers = "cuda", 1
                print(f"Canh chữ bằng '{args.model}' trên GPU "
                      f"(CUDA, {compute})", flush=True)
                break
            except Exception as e:
                print(f"GPU {compute} không chạy ({e})", flush=True)
    if model is None:
        n_workers = _cpu_workers(args.workers)
        try:
            model = WhisperModel(args.model, device="cpu", compute_type="int8",
                                 cpu_threads=_cpu_threads(n_workers),
                                 num_workers=n_workers,
                                 download_root=download_root)
        except Exception as e:
            _die(proto_out, f"Không nạp được model canh chữ "
                            f"'{args.model}': {e}")
        print(f"Canh chữ bằng '{args.model}' trên CPU "
              f"({n_workers} luồng)", flush=True)

    print(json.dumps({"ready": True, "device": device, "workers": n_workers}),
          file=proto_out, flush=True)

    try:
        raw = sys.stdin.readline()
    except (EOFError, OSError):
        _die(proto_out, "stdin đóng trước khi nhận request")
    if not raw.strip():
        _die(proto_out, "stdin đóng trước khi nhận request")

    try:
        req = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as e:
        _die(proto_out, f"Request JSON không hợp lệ: {e}")

    clips = req.get("clips") or []
    language = (req.get("language") or args.language or "vi").strip()
    if not clips:
        _die(proto_out, "Request không có clip nào")

    lock = threading.Lock()

    def _emit(payload: dict) -> None:
        # Nhiều luồng cùng ghi một pipe: khoá để hai dòng JSON không xen nhau.
        with lock:
            print(json.dumps(payload, ensure_ascii=False),
                  file=proto_out, flush=True)

    def _one(clip: dict) -> None:
        cid = clip.get("id")
        try:
            segments, _info = model.transcribe(
                clip["wav"], language=language, word_timestamps=True,
                beam_size=1,              # audio TTS sạch — greedy đủ, nhanh gấp đôi
                condition_on_previous_text=False,
                vad_filter=False,         # clip đã là lời nói thuần
            )
            words = []
            for seg in segments:
                for w in (getattr(seg, "words", None) or []):
                    token = (w.word or "").strip()
                    if token:
                        words.append({"word": token,
                                      "start": round(float(w.start), 3),
                                      "end":   round(float(w.end), 3)})
        except Exception as e:
            # Một clip hỏng chỉ mất alignment của đúng clip đó — caller tự
            # rơi về ước lượng cho câu ấy. Đừng để nó giết cả mẻ.
            _emit({"clip": True, "id": cid, "error": str(e)})
            return
        _emit({"clip": True, "id": cid, "words": words})

    if n_workers > 1:
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            list(pool.map(_one, clips))
    else:
        for clip in clips:
            _one(clip)

    print(json.dumps({"done": True, "n": len(clips)}),
          file=proto_out, flush=True)


if __name__ == "__main__":
    main()
