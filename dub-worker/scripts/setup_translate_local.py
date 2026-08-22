"""Cài đặt dịch local/offline (mini-spec V6, xem docs/PLAN.md) — path C bên
cạnh dịch tay và dịch qua máy chủ. Chỉ có tác dụng khi bật
TRANSLATE_LOCAL_ENABLED=true trong .env VÀ không có máy chủ nào cấu hình.

Chạy 1 lần:  py scripts/setup_translate_local.py

Các bước đều resume-safe:
  1. Tạo virtualenv .venv-mt
  2. pip install ctranslate2 + sentencepiece (KHÔNG cài torch/GPU — nhẹ,
     khác hẳn argostranslate mặc định kéo theo stanza+torch+CUDA toolkit,
     xem docs/TEST_LOG.md mục V6 cho lý do không dùng argostranslate)
  3. Tải model NLLB-200-distilled-600M bản ctranslate2 int8 (~620 MB) về
     models/translate-local
  4. Dịch thử 1 câu (smoke test) → installed_ok.json

Giấy phép model: CC-BY-NC-4.0 (kế thừa từ facebook/nllb-200-distilled-600M
của Meta) — CHỈ dùng cho tính năng miễn phí, không bán riêng bản dịch từ
engine này. Kiểm tra lại license trên HuggingFace trước khi dùng thương mại.
"""
import json
import os
import subprocess
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_DIR = os.path.join(PROJECT_ROOT, ".venv-mt")
VENV_PY = os.path.join(VENV_DIR, "Scripts" if os.name == "nt" else "bin",
                       "python.exe" if os.name == "nt" else "python")
MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "translate-local")
MARKER = os.path.join(MODEL_DIR, "installed_ok.json")

# Bản chuyển đổi ctranslate2 int8 cộng đồng, đã kiểm tra thật (2026-08-10,
# xem docs/TEST_LOG.md mục V6): ~620 MB, dịch zh/en/ko/ja/th/id -> vi đúng,
# fluent. Đổi nguồn ở đây nếu HuggingFace đổi repo/bị gỡ.
_MODEL_REPO = "JustFrederik/nllb-200-distilled-600M-ct2-int8"
_MODEL_FILES = (
    "config.json", "model.bin", "sentencepiece.bpe.model",
    "shared_vocabulary.txt", "special_tokens_map.json",
    "tokenizer.json", "tokenizer_config.json",
)


def log(msg: str) -> None:
    print(f"[setup-translate-local] {msg}", flush=True)


def step_venv() -> None:
    if os.path.isfile(VENV_PY):
        log("venv .venv-mt đã có — bỏ qua")
        return
    log("tạo virtualenv .venv-mt ...")
    subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)


def step_install() -> None:
    probe = subprocess.run([VENV_PY, "-c", "import ctranslate2, sentencepiece"],
                           capture_output=True)
    if probe.returncode == 0:
        log("ctranslate2 + sentencepiece đã cài — bỏ qua")
        return
    log("cài ctranslate2 + sentencepiece (nhẹ, không cần GPU) ...")
    subprocess.run([VENV_PY, "-m", "pip", "install", "--quiet",
                    "ctranslate2", "sentencepiece"], check=True)


def step_model() -> None:
    if os.path.isfile(MARKER):
        log("model đã có — bỏ qua")
        return
    log("tải model NLLB-200-distilled-600M (~620 MB, lần đầu hơi lâu) ...")
    os.makedirs(MODEL_DIR, exist_ok=True)
    base = f"https://huggingface.co/{_MODEL_REPO}/resolve/main/"
    for name in _MODEL_FILES:
        dest = os.path.join(MODEL_DIR, name)
        if os.path.isfile(dest):
            continue
        log(f"  tải {name} ...")
        urllib.request.urlretrieve(base + name, dest)

    log("dịch thử 1 câu (smoke test) ...")
    code = f"""
import ctranslate2, sentencepiece as spm, json
translator = ctranslate2.Translator({MODEL_DIR!r}, device="cpu")
sp = spm.SentencePieceProcessor(model_file={os.path.join(MODEL_DIR, "sentencepiece.bpe.model")!r})
tokens = sp.encode("你好，欢迎观看。", out_type=str)
source = ["zho_Hans"] + tokens + ["</s>"]
result = translator.translate_batch([source], target_prefix=[["vie_Latn"]])
hyp = result[0].hypotheses[0]
if hyp and hyp[0] == "vie_Latn":
    hyp = hyp[1:]
text = sp.decode(hyp)
assert text.strip(), "model trả về rỗng"
json.dump({{"ok": True, "model": "nllb-200-distilled-600M-ct2-int8",
           "smoke_test_output": text}},
          open({MARKER!r}, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("model OK, ví dụ dịch:", text)
"""
    subprocess.run([VENV_PY, "-c", code], check=True)


def main() -> None:
    log("Cài đặt dịch local/offline — không cần máy chủ, chạy trên CPU")
    log(f"Model: {_MODEL_REPO} (CC-BY-NC-4.0, kiểm tra license trên "
        "HuggingFace trước khi dùng thương mại)")
    step_venv()
    step_install()
    step_model()
    log("XONG — bật TRANSLATE_LOCAL_ENABLED=true trong .env để dùng "
        "(chỉ có tác dụng khi KHÔNG cấu hình máy chủ dịch).")


if __name__ == "__main__":
    main()
