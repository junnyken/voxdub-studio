"""Dịch local worker — chạy TRONG venv riêng .venv-mt (mini-spec V6, xem
docs/PLAN.md). Standalone script: KHÔNG được import gì từ ``autodub`` (venv
khác) — đúng quy ước của asr_whisper_worker.py/vieneu_worker.py.

Model: NLLB-200-distilled-600M, chuyển đổi ctranslate2 int8
(entai2965/JustFrederik ct2 conversion trên HuggingFace — xem
scripts/setup_translate_local.py cho nguồn tải). Giấy phép CC-BY-NC-4.0 kế
thừa từ facebook/nllb-200-distilled-600M — CHỈ dùng cho tính năng miễn phí,
không bán riêng bản dịch từ engine này (ghi rõ cho chủ dự án quyết định).

CLI:
    python translate_local_worker.py --model-dir models/translate-local
        --src-lang zho_Hans --tgt-lang vie_Latn

stdin: 1 dòng JSON {"segments": [{"id": 1, "text": "..."}, ...]}
stdout protocol (mỗi dòng 1 JSON, log khác đi ra stderr):
    {"ready": true}
    {"seg": true, "id": 1, "text": "bản dịch..."}
    {"done": true, "translated": N}
  | {"error": "..."}   rồi exit code 1
"""
import argparse
import json
import sys


def _die(msg: str) -> None:
    print(json.dumps({"error": msg}, ensure_ascii=False), flush=True)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--src-lang", required=True,
                        help="Mã FLORES-200 nguồn, vd zho_Hans")
    parser.add_argument("--tgt-lang", required=True,
                        help="Mã FLORES-200 đích, vd vie_Latn")
    parser.add_argument("--beam-size", type=int, default=4)
    args = parser.parse_args()

    try:
        import ctranslate2
        import sentencepiece as spm
    except ImportError as e:
        _die(f"Thiếu thư viện dịch local ({e}) — chạy lại "
             "scripts/setup_translate_local.py")
        return

    try:
        translator = ctranslate2.Translator(args.model_dir, device="cpu")
        sp = spm.SentencePieceProcessor(
            model_file=f"{args.model_dir}/sentencepiece.bpe.model")
    except Exception as e:  # noqa: BLE001 — model hỏng/thiếu file
        _die(f"Không nạp được model dịch local ({e})")
        return

    print(json.dumps({"ready": True}), flush=True)

    line = sys.stdin.readline()
    if not line:
        _die("Không nhận được yêu cầu dịch (stdin rỗng)")
        return
    try:
        request = json.loads(line)
        segments = request["segments"]
    except (json.JSONDecodeError, KeyError) as e:
        _die(f"Yêu cầu dịch sai định dạng ({e})")
        return

    translated = 0
    for seg in segments:
        text = str(seg.get("text") or "").strip()
        if not text:
            print(json.dumps({"seg": True, "id": seg.get("id"), "text": ""}),
                  flush=True)
            continue
        tokens = sp.encode(text, out_type=str)
        source = [args.src_lang] + tokens + ["</s>"]
        result = translator.translate_batch(
            [source], target_prefix=[[args.tgt_lang]],
            beam_size=args.beam_size)
        hyp = result[0].hypotheses[0]
        if hyp and hyp[0] == args.tgt_lang:
            hyp = hyp[1:]
        out_text = sp.decode(hyp)
        print(json.dumps({"seg": True, "id": seg.get("id"), "text": out_text},
                         ensure_ascii=False), flush=True)
        translated += 1

    print(json.dumps({"done": True, "translated": translated}), flush=True)


if __name__ == "__main__":
    main()
