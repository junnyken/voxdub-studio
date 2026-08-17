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


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True, help="File audio (WAV khuyên dùng)")
    parser.add_argument("--model-dir", required=True,
                        help="Thư mục cache model pyannote (HF_HOME)")
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
            "pyannote/speaker-diarization-3.1", use_auth_token=token)
    except Exception as e:  # noqa: BLE001 — model hỏng/thiếu quyền truy cập
        _die(f"Không nạp được model diarization ({e})")
        return

    # Mini-spec V59: xin luôn EMBEDDING của từng người nói.
    #
    # `speaker-diarization-3.1` vốn ĐÃ tính embedding bên trong để gom nhóm —
    # trước V59 nó bị vứt đi, và hồ sơ nhân vật (V57) phải khớp người bằng F0
    # trung vị, một heuristic thô dễ lẫn hai người cùng giới. `return_embeddings`
    # lấy đúng vector đó ra: KHÔNG thêm model, không thêm thời gian xử lý.
    #
    # pyannote cũ hơn 3.1 không có tham số này → chạy lại bản không embedding
    # thay vì chết (người dùng cài từ trước vẫn dub được, chỉ mất phần khớp
    # chính xác).
    embeddings = None
    speaker_order: list[str] = []
    try:
        try:
            diarization, embeddings = pipeline(args.audio, return_embeddings=True)
            speaker_order = list(diarization.labels())
        except TypeError:
            print(json.dumps({
                "warn": "pyannote bản này không hỗ trợ return_embeddings — "
                        "hồ sơ nhân vật sẽ khớp bằng cao độ giọng như trước.",
            }), flush=True)
            diarization = pipeline(args.audio)
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
