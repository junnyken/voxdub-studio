"""Diarization worker — runs INSIDE the dedicated .venv-diar virtualenv.

Standalone script: must not import anything from ``autodub`` (different env)
— đúng quy ước của asr_paraformer_worker.py/vieneu_worker.py. Chạy
pyannote.audio (torch, CPU/GPU) để tách khoảng thời gian nói theo từng người
trong 1 file audio — mini-spec V26 (docs/PLAN.md, Phase G).

CLI:
    python diarize_worker.py --audio in.wav --model-dir models/diarization
        [--hf-token hf_xxx]

Model pretrained của pyannote (``pyannote/speaker-diarization-3.1``) nằm
trên HuggingFace Hub và THƯỜNG bị khoá (gated) — cần chấp nhận user
agreement + truyền access token thật (``--hf-token``, hoặc biến môi trường
``HF_TOKEN``/``HUGGINGFACE_TOKEN``) mới tải được lần đầu. Xem
docs/PLAN.md mục V26 "Audit Before Build" — đây là giới hạn xác nhận thật,
không phải giả định.

stdout protocol (mỗi dòng 1 JSON, log khác đi ra stderr — KHÔNG có bước
"ready" riêng: toàn bộ audio được xử lý 1 lượt trước khi có dòng đầu tiên,
khác các worker streaming-theo-khối như Whisper/Paraformer):
    {"segment": true, "start": 12.34, "end": 15.02, "speaker": "SPEAKER_00"}
    ...
    {"done": true, "num_speakers": 2}
  | {"error": "..."}   rồi exit code 1
"""
import argparse
import json
import os
import sys


def _die(msg: str) -> None:
    print(json.dumps({"error": msg}, ensure_ascii=False), flush=True)
    sys.exit(1)


def _speaker_hint(num: int, lo: int, hi: int) -> dict:
    """Gợi ý số người nói gửi cho pyannote — hàm thuần, test được.

    Quy ước ``0`` = không biết, KHÔNG phải "không có ai": người gọi để trống
    thì pyannote tự đoán y như trước V65b.

    ``num_speakers`` (biết chắc) ĐÈ lên cặp min/max: đưa cả ba mà lệch nhau
    thì pyannote không có cách nào chiều cả hai, và cái người dùng gõ tay
    đáng tin hơn con số suy ra từ hồ sơ.

    ``max < min`` là mâu thuẫn — bỏ ``max`` chứ không bỏ ``min``: thà tách
    hơi nhiều người còn hơn gộp nhầm hai người vào một giọng, vì gộp thì
    người xem nghe hai nhân vật cùng một giọng, còn tách dư thì hồ sơ nhân
    vật ở tập sau vẫn khớp lại được.
    """
    if num > 0:
        return {"num_speakers": int(num)}
    hint: dict = {}
    if lo > 0:
        hint["min_speakers"] = int(lo)
    if hi > 0 and not (lo > 0 and hi < lo):
        hint["max_speakers"] = int(hi)
    return hint


def _token_kwarg(load_fn) -> str:
    """Tên tham số truyền access token của ``Pipeline.from_pretrained``.

    pyannote đổi tên tham số này giữa hai dòng phiên bản, và KHÔNG bản nào có
    ``**kwargs`` để nuốt tên sai:

        3.1.x:  from_pretrained(checkpoint, hparams_file=None, use_auth_token=None, …)
        4.x:    from_pretrained(checkpoint, revision=None, …, token=None, …)

    Truyền nhầm tên là ``TypeError`` ngay lúc gọi — mà chỗ gọi lại nằm trong
    ``except Exception`` nên nó hiện ra thành "Không nạp được model
    diarization", đọc y như lỗi thiếu quyền truy cập model. Ai gặp sẽ đi kiểm
    token và user agreement, đúng hai thứ không hỏng.

    Cùng lớp lỗi với thứ V61 sửa ở ``apply()``, chỉ là ở một tầng cao hơn nên
    lượt đó bỏ sót: `setup_diarization.py` không ghim phiên bản, nên máy nào
    cài hôm nay cũng ra 4.x và diarization chết ngay từ bước nạp model.
    """
    import inspect

    try:
        params = inspect.signature(load_fn).parameters
    except (TypeError, ValueError):
        params = {}
    # Bản lạ không có tên nào quen thì đoán theo dòng mới — cài mới hôm nay ra 4.x.
    return "use_auth_token" if "use_auth_token" in params else "token"


def _nguon_am_thanh(duong: str):
    """Đọc WAV thành sóng âm để pyannote KHỎI phải tự giải mã.

    Lỗi thật, người dùng gặp 26/08/2026 — cài xong, smoke test báo PASS, mà
    mọi lượt chạy đều chết:

        Could not load libtorchcodec ...
        FileNotFoundError: Could not find module 'libtorchcodec_core9.dll'

    pyannote 4.x giải mã âm thanh bằng `torchcodec`, và torchcodec đòi bản
    FFmpeg "full-shared" có DLL trên Windows. App chỉ mang theo `ffmpeg.exe`
    (đủ cho mọi việc khác), nên diarization hỏng 100% dù đã cài đúng.

    Đưa thẳng sóng âm vào thì pyannote không cần giải mã gì cả — bỏ qua hẳn
    cả torchcodec lẫn chuyện phiên bản FFmpeg. Đầu vào luôn là WAV do chính
    app trích ra, nên đọc bằng `wave` của thư viện chuẩn là đủ.

    Đọc trượt (WAV lạ, 24-bit, float) thì trả lại ĐƯỜNG DẪN như cũ: có thể
    chạy được trên máy có torchcodec lành lặn, còn hơn dừng hẳn.
    """
    try:
        import wave

        import numpy as np
        import torch

        with wave.open(duong, "rb") as f:
            so_kenh = f.getnchannels()
            do_rong = f.getsampwidth()
            sr = f.getframerate()
            raw = f.readframes(f.getnframes())
        if do_rong != 2:
            raise ValueError(f"WAV {do_rong * 8}-bit, không phải 16-bit")

        x = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
        if so_kenh > 1:
            # pyannote làm việc trên một kênh — trộn xuống mono thay vì bỏ
            # bớt kênh, để không mất người nói chỉ có ở kênh kia.
            x = x.reshape(-1, so_kenh).mean(axis=1)
        song = torch.from_numpy(np.ascontiguousarray(x).reshape(1, -1))
        return {"waveform": song, "sample_rate": sr}
    except Exception as e:  # noqa: BLE001 — mọi lỗi đọc đều rơi về đường cũ
        print(json.dumps({"info": f"không nạp thẳng được sóng âm ({e}) — "
                                  "để pyannote tự giải mã"}), flush=True)
        return duong


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True, help="File audio (WAV khuyên dùng)")
    parser.add_argument("--model-dir", required=True,
                        help="Thư mục cache model pyannote (HF_HOME)")
    # V65b — gợi ý số người nói. pyannote nhận `num_speakers` (biết chắc),
    # hoặc cặp `min_speakers`/`max_speakers` (khoảng). Không truyền gì thì nó
    # tự đoán như trước.
    #
    # Vì sao cần: đo thật ngày 18-08 cho thấy 3 giọng nữ trong cùng một file
    # bị GỘP thành một người nói, và tầng hồ sơ nhân vật không sửa nổi — nó
    # chỉ thấy một người, không có cách nào biết đó là ba (xem TEST_LOG mục
    # V59 18-08).
    parser.add_argument("--num-speakers", type=int, default=0,
                        help="Biết CHẮC có bao nhiêu người nói (0 = không biết)")
    parser.add_argument("--min-speakers", type=int, default=0,
                        help="Ít nhất bao nhiêu người nói (0 = không đặt)")
    parser.add_argument("--max-speakers", type=int, default=0,
                        help="Nhiều nhất bao nhiêu người nói (0 = không đặt)")
    parser.add_argument("--hf-token", default="",
                        help="HuggingFace access token cho model gated "
                             "(mặc định đọc HF_TOKEN/HUGGINGFACE_TOKEN)")
    args = parser.parse_args()

    if not os.path.isfile(args.audio):
        _die(f"Không tìm thấy file audio: {args.audio}")
        return

    token = (args.hf_token or os.environ.get("HF_TOKEN")
            or os.environ.get("HUGGINGFACE_TOKEN") or "")
    if not token:
        _die("Thiếu HuggingFace access token — model diarization của "
             "pyannote yêu cầu đăng nhập (gated model). Xem hướng dẫn ở "
             "scripts/setup_diarization.py.")
        return

    os.environ.setdefault("HF_HOME", args.model_dir)

    try:
        from pyannote.audio import Pipeline
    except ImportError as e:
        _die(f"Thiếu thư viện diarization ({e}) — chạy lại "
             "scripts/setup_diarization.py")
        return

    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            **{_token_kwarg(Pipeline.from_pretrained): token})
    except Exception as e:  # noqa: BLE001 — model hỏng/thiếu quyền truy cập
        _die(f"Không nạp được model diarization ({e})")
        return

    # Mini-spec V59 (sửa lại ở V61 sau khi ĐỌC MÃ NGUỒN THẬT của pyannote):
    # hai phiên bản có hai API khác hẳn nhau, và `scripts/setup_diarization.py`
    # cài KHÔNG GHIM phiên bản nên máy nào cài hôm nay là ra bản 4.x.
    #
    #   pyannote 3.1.x:  apply(file, return_embeddings=True) -> (Annotation, ndarray)
    #   pyannote 4.x:    apply(file) -> DiarizeOutput(speaker_diarization,
    #                    exclusive_speaker_diarization, speaker_embeddings)
    #                    — KHÔNG có tham số `return_embeddings`; 4.x nuốt nó
    #                    vào **kwargs nên truyền vào cũng không báo lỗi.
    #
    # Bản V59 đầu tiên chỉ biết đường 3.1: trên 4.x nó unpack DiarizeOutput
    # thất bại, rơi vào nhánh dự phòng rồi gọi `.itertracks()` trên
    # DiarizeOutput (không có hàm đó) → chết cả lượt diarization. Đáng nói:
    # lỗi này CÓ SẴN TỪ V26 chứ không phải do V59 — mọi máy cài pyannote 4.x
    # đều không dùng được diarization, chỉ là chưa ai chạy thử để phát hiện.
    #
    # Dò API bằng chữ ký hàm TRƯỚC khi gọi: diarization chạy vài phút, không
    # thể gọi thử rồi gọi lại.
    embeddings = None
    speaker_order: list[str] = []
    try:
        import inspect

        try:
            supports_flag = "return_embeddings" in inspect.signature(
                pipeline.apply).parameters
        except (TypeError, ValueError):
            supports_flag = False

        # V65b — chỉ truyền tham số nào NGƯỜI GỌI thật sự đặt. Truyền
        # `num_speakers=None` cũng vô hại, nhưng dựng dict rỗng thì đọc log
        # ra biết ngay lượt chạy đó có gợi ý hay không.
        hint = _speaker_hint(args.num_speakers, args.min_speakers,
                             args.max_speakers)
        if hint:
            print(json.dumps({"info": f"gợi ý số người nói: {hint}"}),
                  flush=True)
        if supports_flag:
            hint["return_embeddings"] = True
        result = pipeline(_nguon_am_thanh(args.audio), **hint)

        if hasattr(result, "speaker_diarization"):          # pyannote 4.x
            diarization = result.speaker_diarization
            embeddings = getattr(result, "speaker_embeddings", None)
        elif isinstance(result, tuple):                      # pyannote 3.1.x
            diarization, embeddings = result
        else:                                                # bản cũ hơn nữa
            diarization = result

        if embeddings is not None:
            # Cả 2 phiên bản đều xếp embedding theo `labels()` — xác nhận
            # bằng chính mã nguồn của thư viện, không phải theo tài liệu.
            speaker_order = list(diarization.labels())
    except Exception as e:  # noqa: BLE001 — lỗi thật lúc xử lý audio
        _die(f"Diarization thất bại ({e})")
        return

    speakers: set[str] = set()
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        speakers.add(speaker)
        print(json.dumps({
            "segment": True,
            "start": round(float(turn.start), 3),
            "end": round(float(turn.end), 3),
            "speaker": str(speaker),
        }), flush=True)

    if embeddings is not None and speaker_order:
        # `embeddings` là mảng (num_speakers, dim) xếp theo `diarization.labels()`.
        # Gửi kèm nhãn để phía nhận không phải đoán thứ tự.
        try:
            for index, label in enumerate(speaker_order):
                vector = [round(float(x), 6) for x in embeddings[index]]
                # V70 — pyannote trả về NaN (hoặc toàn 0) cho người nói có quá
                # ít tiếng nói để tính đặc trưng giọng. Quan sát thật ngày
                # 18-08 trên clip của chủ dự án: người chỉ nói 3.1 giây trong
                # 53 giây rơi vào ca này.
                #
                # Gửi đi thì tầng trên vẫn AN TOÀN (`_normalise` biến nó thành
                # rỗng, `_cosine` trả 0.0, coi như không khớp) — nhưng người
                # dùng chỉ thấy "nhân vật mới" mọi tập mà không hiểu vì sao.
                # Nói thẳng ra thì họ biết cách xử lý: cắt clip có nhiều tiếng
                # của người đó hơn.
                tong = sum(x * x for x in vector)
                if not (tong > 0):   # bắt luôn NaN — mọi so sánh với NaN đều False
                    print(json.dumps({
                        "warn": f"Người nói {label} nói quá ít nên không tính "
                                "được đặc trưng giọng — tập sau sẽ không nhận "
                                "lại được người này.",
                    }), flush=True)
                    continue
                print(json.dumps({
                    "embedding": True, "speaker": str(label), "vector": vector,
                }), flush=True)
        except (IndexError, TypeError, ValueError) as e:
            print(json.dumps({
                "warn": f"Không đọc được embedding người nói ({e}) — bỏ qua.",
            }), flush=True)

    print(json.dumps({"done": True, "num_speakers": len(speakers)}), flush=True)


if __name__ == "__main__":
    main()
