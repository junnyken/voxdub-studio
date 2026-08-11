"""Cài đặt quét chữ tự động (OCR, mini-spec V5, xem docs/PLAN.md) — đề xuất
sẵn vùng che chữ overlay thay vì bắt người dùng tự vẽ tay từ đầu.

Chạy 1 lần:  py scripts/setup_ocr.py

Các bước đều resume-safe:
  1. Tạo virtualenv .venv-ocr
  2. pip install rapidocr-onnxruntime (ONNX Runtime — KHÔNG cần GPU/torch;
     model phát hiện+nhận dạng chữ ~16 MB đã nằm sẵn trong gói pip, không
     cần tải thêm — nhẹ hơn hẳn Whisper/VieNeu/Paraformer/dịch local)
  3. Quét thử 1 ảnh tự vẽ (smoke test, không cần video thật)
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_DIR = os.path.join(PROJECT_ROOT, ".venv-ocr")
VENV_PY = os.path.join(VENV_DIR, "Scripts" if os.name == "nt" else "bin",
                       "python.exe" if os.name == "nt" else "python")


def log(msg: str) -> None:
    print(f"[setup-ocr] {msg}", flush=True)


def step_venv() -> None:
    if os.path.isfile(VENV_PY):
        log("venv .venv-ocr đã có — bỏ qua")
        return
    log("tạo virtualenv .venv-ocr ...")
    subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)


def step_install() -> None:
    probe = subprocess.run([VENV_PY, "-c", "import rapidocr_onnxruntime"],
                           capture_output=True)
    if probe.returncode == 0:
        log("rapidocr-onnxruntime đã cài — bỏ qua")
        return
    log("cài rapidocr-onnxruntime (nhẹ, model đã kèm sẵn trong gói) ...")
    subprocess.run([VENV_PY, "-m", "pip", "install", "--quiet",
                    "rapidocr-onnxruntime"], check=True)


def step_smoke_test() -> None:
    log("quét thử 1 ảnh tự vẽ (smoke test) ...")
    code = """
import tempfile, os
from PIL import Image, ImageDraw
from rapidocr_onnxruntime import RapidOCR

img = Image.new("RGB", (640, 200), (20, 20, 20))
draw = ImageDraw.Draw(img)
draw.text((40, 80), "TEST 12345", fill=(255, 255, 255))
tmp = os.path.join(tempfile.gettempdir(), "voxdub_ocr_smoke.png")
img.save(tmp)

engine = RapidOCR()
result, _ = engine(tmp)
os.remove(tmp)
assert result, "OCR khong doc duoc chu thu"
print("OCR OK, doc duoc:", result[0][1])
"""
    subprocess.run([VENV_PY, "-c", code], check=True)


def main() -> None:
    log("Cài đặt quét chữ tự động (RapidOCR, ONNX, chạy CPU)")
    step_venv()
    step_install()
    step_smoke_test()
    log("XONG — mở dự án, trang Phụ đề/che chữ có nút \"Quét chữ tự động\".")


if __name__ == "__main__":
    main()
