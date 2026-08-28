"""Whisper ASR worker — runs INSIDE the dedicated .venv-whisper virtualenv.

Standalone script: must NOT import anything from ``autodub`` (different env).
Wraps faster-whisper with the same JSON-line protocol used by the Paraformer
worker so ``transcriber.py`` can drive both the same way.

CLI:
    python asr_whisper_worker.py --audio in.wav --model <name|auto>
        [--language zh-CN] [--beam-size 5] [--model-dir models/whisper]
        [--cuda-dll-dir path/to/torch/lib]

stdout protocol (one JSON per line, everything else goes to stderr):
    {"ready": true}
    {"seg": true, "id": 1, "text": "...", "start": 1.02, "end": 4.31,
     "words": [{"word": "...", "start": 1.02, "end": 1.30}]}
    {"done": true, "num_segments": 42, "language": "zh", "language_prob": 0.99}
  | {"error": "..."}   then exit code 1

Design note: The worker loads the model once, prints {"ready": true}, then
reads ONE JSON request from stdin and transcribes. Single-shot like Paraformer
(ASR is one call per pipeline run — persistent pool would be overkill).
"""
import argparse
import json
import os
import sys


def _die(proto_out, msg: str) -> None:
    print(json.dumps({"error": msg}, ensure_ascii=False),
          file=proto_out, flush=True)
    sys.exit(1)


def _resolve_model(model_arg: str, cuda_ok: bool) -> str:
    if model_arg.strip().lower() != "auto":
        return model_arg.strip()
    return "large-v3" if cuda_ok else "medium"


#: Bậc lùi khi máy không đủ bộ nhớ. Xếp từ nặng xuống nhẹ; lùi MỘT bậc mỗi
#: lần và nói ra, chứ không nhảy thẳng xuống đáy — mini-spec C46.
_BAC_MODEL = ["large-v3", "large-v2", "medium", "small", "base", "tiny"]

#: RAM (GB) cần để nạp mỗi model ở dạng int8 trên CPU, đã cộng phần dư cho
#: chính tiến trình. Dùng để chọn ĐÚNG BẬC NGAY TỪ ĐẦU: lùi bậc sau khi nạp
#: hỏng thì mỗi bậc phải TẢI VỀ vài GB rồi mới biết là không nạp nổi — người
#: dùng ngồi chờ hàng chục phút cho một việc đằng nào cũng hỏng (C46).
_RAM_CAN_GB = {"large-v3": 3.6, "large-v2": 3.6, "medium": 2.0,
               "small": 1.0, "base": 0.6, "tiny": 0.4}


def _model_vua_ram(model_name: str, ram_trong_gb: float) -> str:
    """Model to nhất KHÔNG vượt quá lựa chọn của người dùng mà máy còn tải nổi.

    `ram_trong_gb <= 0` nghĩa là không đọc được RAM — trả nguyên lựa chọn,
    thà thử rồi lùi còn hơn tự ý hạ mức dựa trên một con số không có.
    """
    ten = model_name.strip().lower()
    if ram_trong_gb <= 0 or ten not in _BAC_MODEL:
        return model_name
    for ung_vien in _BAC_MODEL[_BAC_MODEL.index(ten):]:
        if _RAM_CAN_GB.get(ung_vien, 0) <= ram_trong_gb:
            return ung_vien
    return _BAC_MODEL[-1]


#: Câu lỗi của ctranslate2/MKL khi hết bộ nhớ. Chỉ những câu này mới đáng lùi
#: bậc: lỗi khác (thiếu tệp model, mạng hỏng) mà lùi bậc thì chỉ hỏng chậm hơn
#: và giấu mất nguyên nhân thật.
_DAU_HIEU_HET_BO_NHO = ("mkl_malloc", "failed to allocate", "out of memory",
                        "bad_alloc", "cannot allocate")


def _la_loi_het_bo_nho(e: Exception) -> bool:
    return any(d in str(e).lower() for d in _DAU_HIEU_HET_BO_NHO)


def _bac_nhe_hon(model_name: str) -> str:
    """Model nhẹ hơn kế tiếp, hoặc "" nếu đã ở đáy."""
    ten = model_name.strip().lower()
    if ten not in _BAC_MODEL:
        # Người dùng gõ tên lạ (bản fine-tune riêng) — không đoán bậc hộ họ,
        # nhưng vẫn cho một lối thoát nhẹ nhất thay vì chết hẳn.
        return "small"
    i = _BAC_MODEL.index(ten)
    return _BAC_MODEL[i + 1] if i + 1 < len(_BAC_MODEL) else ""


def _nap_cpu_co_bac_lui(WhisperModel, model_name: str, download_root,
                        ram_trong_gb: float = 0.0):
    """Nạp model trên CPU, lùi dần bậc khi máy không đủ bộ nhớ.

    Vì sao (mini-spec C46 — lỗi thật chủ dự án gặp ở v3.14.0): máy dùng card
    Intel nên CUDA hỏng, rơi xuống CPU, rồi `medium` không nạp nổi vì thiếu
    RAM — cả lượt chạy chết với đúng một câu `mkl_malloc: failed to allocate
    memory`. Người dùng không có cách nào đoán ra việc cần làm là hạ mức
    "Độ chính xác" ở bước 2.
    """
    vua_ram = _model_vua_ram(model_name, ram_trong_gb)
    if vua_ram != model_name:
        print(f"Máy còn {ram_trong_gb:.1f} GB trống — nghe bằng model "
              f"'{vua_ram}' thay cho '{model_name}' (bản lớn hơn không nạp "
              f"nổi). Chọn sẵn mức thấp hơn ở bước Nhận dạng thì khỏi phải "
              f"chờ.", flush=True)
    thu = vua_ram
    da_thu = []
    while thu:
        try:
            model = WhisperModel(thu, device="cpu", compute_type="int8",
                                 download_root=download_root)
            if thu != vua_ram:
                print(f"Đã nghe bằng model '{thu}' thay cho '{model_name}' — "
                      f"máy không đủ bộ nhớ cho bản lớn hơn. Muốn chắc chắn "
                      f"thì chọn sẵn mức thấp hơn ở bước Nhận dạng.", flush=True)
            return model, thu
        except Exception as e:
            if not _la_loi_het_bo_nho(e):
                raise
            da_thu.append(thu)
            nhe_hon = _bac_nhe_hon(thu)
            if not nhe_hon:
                raise RuntimeError(
                    "Máy không đủ bộ nhớ cho bất kỳ model nào (đã thử: "
                    + ", ".join(da_thu) + "). Đóng bớt ứng dụng đang mở rồi "
                    "chạy lại; nhớ là tiến độ đã lưu nên không bị trừ Vox lần "
                    "nữa.") from e
            print(f"Máy không đủ bộ nhớ cho model '{thu}' — thử '{nhe_hon}'",
                  flush=True)
            thu = nhe_hon
    raise RuntimeError("Không còn model nào để thử")


def _try_load_cuda_dlls(dll_dir: str) -> bool:
    """Nạp cuBLAS/cuDNN từ torch lib dir — giống cách transcriber.py làm."""
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


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    proto_out = sys.stdout
    sys.stdout = sys.stderr   # thư viện in ra stderr, không lẫn vào JSON

    parser = argparse.ArgumentParser()
    parser.add_argument("--audio",      required=True)
    parser.add_argument("--model",      default="auto")
    parser.add_argument("--language",   default="")
    parser.add_argument("--beam-size",  type=int, default=5)
    parser.add_argument("--model-dir",  default="",
                        help="Thư mục cache model; rỗng = HuggingFace default")
    parser.add_argument("--cuda-dll-dir", default="",
                        help="Thư mục torch/lib chứa cublas64_*.dll (Windows)")
    parser.add_argument("--ram-trong-gb", type=float, default=0.0,
                        help="RAM còn trống do tiến trình cha đo (0 = không biết)")
    args = parser.parse_args()

    # --- Thử GPU ---
    #
    # mini-spec C46: nạp được cuBLAS KHÔNG có nghĩa là máy có card NVIDIA —
    # DLL đó nằm sẵn trong thư mục torch. Máy chủ dự án dùng card Intel vẫn
    # lọt vào nhánh CUDA, thất bại ba lượt (float16 / int8_float16 / int8) rồi
    # mới chịu rơi xuống CPU, và nhật ký thì đầy chữ "CUDA out of memory" gây
    # hiểu nhầm là card yếu. Hỏi thẳng ctranslate2 xem có card nào không.
    cuda_ok = False
    if os.name == "nt" and args.cuda_dll_dir:
        cuda_ok = _try_load_cuda_dlls(args.cuda_dll_dir)
    if cuda_ok:
        try:
            import ctranslate2
            so_card = ctranslate2.get_cuda_device_count()
            if so_card < 1:
                print("Không thấy card NVIDIA nào — nghe bằng CPU", flush=True)
                cuda_ok = False
        except Exception as e:  # thư viện cũ không có hàm này
            print(f"Không kiểm được số card CUDA ({e}) — cứ thử GPU", flush=True)

    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        _die(proto_out, f"faster-whisper chưa cài trong .venv-whisper: {e}")

    model_name = _resolve_model(args.model, cuda_ok)
    download_root = args.model_dir if args.model_dir else None

    try:
        if cuda_ok:
            model = None
            # float16 trước: nhanh nhất trên CUDA. int8 chỉ là lưới an toàn
            # cho card thiếu VRAM.
            for compute in ("float16", "int8_float16", "int8"):
                try:
                    model = WhisperModel(model_name, device="cuda",
                                         compute_type=compute,
                                         download_root=download_root)
                    print(f"Whisper '{model_name}' trên GPU "
                          f"(CUDA, {compute})", flush=True)
                    break
                except Exception as e:
                    print(f"GPU {compute} thất bại ({e})", flush=True)
            if model is None:
                print("GPU không dùng được, chuyển sang CPU", flush=True)
                cuda_ok = False
                # C46: GIỮ lựa chọn của người dùng. Trước đây chỗ này gọi
                # `_resolve_model("auto", False)` nên ai chọn large-v3 cũng bị
                # đổi ngầm thành medium — vừa nuốt lựa chọn, vừa khiến câu lỗi
                # nói tên một model mà người dùng chưa từng chọn.
                if args.model.strip().lower() == "auto":
                    model_name = _resolve_model("auto", False)
                model, model_name = _nap_cpu_co_bac_lui(
                    WhisperModel, model_name, download_root, args.ram_trong_gb)
        else:
            model, model_name = _nap_cpu_co_bac_lui(
                WhisperModel, model_name, download_root, args.ram_trong_gb)
            print(f"Whisper '{model_name}' trên CPU", flush=True)
    except Exception as e:
        _die(proto_out, f"Không nạp được model Whisper '{model_name}': {e}")

    # Model sẵn sàng
    print(json.dumps({"ready": True}), file=proto_out, flush=True)

    # Đọc request từ stdin
    try:
        raw = sys.stdin.readline()
    except (EOFError, OSError):
        _die(proto_out, "stdin đóng trước khi nhận request")

    try:
        req = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as e:
        _die(proto_out, f"Request JSON không hợp lệ: {e}")

    audio_path = req.get("audio") or args.audio
    language   = req.get("language") or args.language or None
    beam_size  = req.get("beam_size", args.beam_size)

    # Normalize language: "zh-CN" → "zh"
    if language:
        language = language.split("-")[0].lower()
        if language == "auto":
            language = None

    try:
        raw_segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=beam_size,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            word_timestamps=True,
            # Mini-spec C28 — CHẶN VÒNG LẶP BỊA.
            #
            # Mặc định của faster-whisper là bơm bản chép của đoạn trước vào
            # lời nhắc của đoạn sau. Gặp quãng im hoặc tiếng nhỏ, mô hình
            # không có gì để nghe nên nó lặp lại chính câu vừa in ra — rồi
            # câu đó lại thành lời nhắc cho đoạn kế. Kết quả trên bài giảng
            # thật: từ phút 33 tới 37 in ra một dòng "Các bạn hãy đăng ký
            # kênh…" mỗi 40 giây, không ai nói câu nào cả.
            #
            # Tắt đi thì mất một chút mạch văn giữa các đoạn, nhưng đổi lại
            # không có chữ nào bị BỊA RA. Với bản chép lời, bịa nguy hiểm hơn
            # lạc mạch nhiều.
            condition_on_previous_text=False,
        )
    except Exception as e:
        _die(proto_out, f"Lỗi khi nhận dạng: {e}")

    detected_lang = getattr(info, "language", "") or ""
    detected_prob = getattr(info, "language_probability", 0.0)
    if not language and detected_lang:
        print(f"Ngôn ngữ tự nhận: {detected_lang} ({detected_prob:.0%})",
              flush=True)

    seg_id = 0
    for seg in raw_segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        seg_id += 1
        words = []
        for w in (getattr(seg, "words", None) or []):
            words.append({"word": w.word,
                          "start": round(w.start, 3),
                          "end":   round(w.end, 3)})
        out = {
            "seg":   True,
            "id":    seg_id,
            "text":  text,
            "start": round(seg.start, 3),
            "end":   round(seg.end, 3),
            "words": words,
        }
        print(json.dumps(out, ensure_ascii=False), file=proto_out, flush=True)

    print(json.dumps({
        "done":         True,
        "num_segments": seg_id,
        "language":     detected_lang,
        "language_prob": round(detected_prob, 3),
    }), file=proto_out, flush=True)


if __name__ == "__main__":
    main()
