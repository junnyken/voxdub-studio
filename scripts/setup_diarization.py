"""Cài đặt Diarization — tự tách giọng theo từng người nói trong video nhiều
người, gán mỗi người 1 giọng TTS riêng (mini-spec V26, docs/PLAN.md Phase G).

Chạy 1 lần:  py scripts/setup_diarization.py [--hf-token hf_xxx]

Các bước resume-safe — chạy lại script sẽ bỏ qua phần đã xong:
  1. Tạo virtualenv .venv-diar
  2. pip install pyannote.audio (kéo theo torch — nặng, ~1-2 GB tải về)
  3. Kiểm tra HuggingFace access token (BẮT BUỘC — model pretrained của
     pyannote bị khoá, cần đăng nhập + chấp nhận user agreement)
  4. Smoke test: nạp thử pipeline model thật (cần mạng + token hợp lệ)
  5. Bật DIARIZATION_ENABLED=true trong .env

pyannote/speaker-diarization-3.1 là "gated model" trên HuggingFace Hub —
KHÔNG có cách nào tải được nếu chưa:
  (a) Tạo tài khoản tại https://huggingface.co (miễn phí)
  (b) Bấm "Agree and access repository" ở các trang model — DANH SÁCH KHÁC
      NHAU THEO PHIÊN BẢN pyannote mà pip cài về (script này không ghim
      phiên bản):
        - pyannote 3.1.x:
            https://huggingface.co/pyannote/speaker-diarization-3.1
            https://huggingface.co/pyannote/segmentation-3.0
        - pyannote 4.x (bản pip cài về hôm nay): tên 'speaker-diarization-3.1'
          được CHUYỂN HƯỚNG sang một repo gated KHÁC, phải xin quyền riêng:
            https://huggingface.co/pyannote/speaker-diarization-community-1
      Bấm đủ ở nhóm 3.1.x rồi vẫn 403 trên máy cài 4.x là chuyện bình thường,
      không phải token hỏng — xem thông báo lỗi của smoke test, nó in ra ĐÚNG
      repo đang khoá.
  (c) Tạo access token (read-only đủ dùng) tại
      https://huggingface.co/settings/tokens
  (d) Chạy lại script này với --hf-token <token>, hoặc đặt biến môi trường
      HF_TOKEN trước khi chạy
Đây là yêu cầu CỦA PYANNOTE (không phải VoxDub) — script không thể tự động
hoá bước này.
"""
import argparse
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_DIR = os.path.join(PROJECT_ROOT, ".venv-diar")
VENV_PY = os.path.join(VENV_DIR, "Scripts" if os.name == "nt" else "bin",
                       "python.exe" if os.name == "nt" else "python")
MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "diarization")
MARKER = os.path.join(MODEL_DIR, "installed_ok.json")

WORKER = os.path.join(PROJECT_ROOT, "autodub", "speech", "diarize_worker.py")
if not os.path.isfile(WORKER):
    for _d in ("data", "_internal"):
        _candidate = os.path.join(PROJECT_ROOT, _d, "autodub", "speech",
                                  "diarize_worker.py")
        if os.path.isfile(_candidate):
            WORKER = _candidate
            break


def log(msg: str) -> None:
    print(f"[setup-diarization] {msg}", flush=True)


def step_venv() -> None:
    if os.path.isfile(VENV_PY):
        log("venv .venv-diar đã có — bỏ qua")
        return
    log("tạo virtualenv .venv-diar ...")
    subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)


def step_install() -> None:
    probe = subprocess.run([VENV_PY, "-c", "import pyannote.audio"],
                           capture_output=True)
    if probe.returncode == 0:
        log("package pyannote.audio đã cài — bỏ qua")
        return
    log("cài pyannote.audio (kéo theo torch — nặng, có thể mất vài phút) ...")
    subprocess.run([VENV_PY, "-m", "pip", "install", "--quiet",
                    "pyannote.audio"], check=True)


def step_smoke(hf_token: str) -> None:
    if os.path.isfile(MARKER):
        log("smoke test đã đạt — bỏ qua")
        return
    if not hf_token:
        raise SystemExit(
            "!! Thiếu HuggingFace access token — bắt buộc để dùng model "
            "diarization. Xem hướng dẫn ở đầu file này (docstring), rồi "
            "chạy lại: py scripts/setup_diarization.py --hf-token hf_xxx")

    log("nạp thử model diarization thật (cần mạng, có thể mất vài phút "
        "lần đầu) ...")
    os.makedirs(MODEL_DIR, exist_ok=True)
    # Tên tham số truyền token đổi giữa hai dòng pyannote (3.1.x
    # `use_auth_token`, 4.x `token`) và không bản nào có `**kwargs` — xem
    # `autodub/speech/diarize_worker.py::_token_kwarg`. Script này KHÔNG import
    # được hàm đó (chạy ở env khác, đúng quy ước worker) nên dò lại tại chỗ.
    #
    # Không dò thì thông báo lỗi bên dưới đổ tội cho token và user agreement —
    # đã xảy ra thật ngày 18-08: token hợp lệ, agreement đã bấm, lỗi thật là
    # sai tên tham số.
    gen = (
        "import inspect, os, sys\n"
        f"os.environ['HF_HOME'] = {MODEL_DIR!r}\n"
        "from pyannote.audio import Pipeline\n"
        "params = inspect.signature(Pipeline.from_pretrained).parameters\n"
        "kw = 'use_auth_token' if 'use_auth_token' in params else 'token'\n"
        "Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', "
        f"**{{kw: {hf_token!r}}})\n"
        "print('OK')\n"
    )
    result = subprocess.run([VENV_PY, "-c", gen], capture_output=True,
                            encoding="utf-8", errors="replace", timeout=600)
    if "OK" not in (result.stdout or ""):
        err = (result.stderr or "")
        # `GatedRepoError` nói THẲNG repo nào đang khoá — dựng lại lời khuyên
        # theo đúng repo đó thay vì đọc thuộc lòng danh sách 2 model, vì
        # pyannote 4.x chuyển hướng sang `speaker-diarization-community-1`
        # (một repo gated KHÁC, phải xin quyền riêng). Bảo người dùng đi bấm
        # Agree ở model họ đã bấm rồi là cách chắc chắn nhất làm họ bỏ cuộc.
        goi_y = ("pyannote/speaker-diarization-3.1 và pyannote/segmentation-3.0")
        for dong in err.splitlines():
            if "Cannot access gated repo" in dong or "is restricted" in dong:
                goi_y = dong.strip()
                break
        raise SystemExit(
            "!! smoke test thất bại. Nếu là lỗi quyền truy cập thì vào đúng "
            f"trang model bên dưới bấm 'Agree and access repository':\n  {goi_y}"
            f"\n{result.stdout}\n{err[-800:]}")
    with open(MARKER, "w", encoding="utf-8") as f:
        json.dump({"ok": True, "model": "pyannote/speaker-diarization-3.1"},
                  f, ensure_ascii=False, indent=2)
    log("smoke test PASS")


def step_enable_env(hf_token: str) -> None:
    env_path = os.path.join(PROJECT_ROOT, ".env")
    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            lines = f.read().splitlines()

    def _set(key: str, value: str) -> None:
        nonlocal lines
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                return
        lines.append(f"{key}={value}")

    _set("DIARIZATION_ENABLED", "true")
    if hf_token:
        _set("HF_TOKEN", hf_token)
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    log("đã bật DIARIZATION_ENABLED=true trong .env")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""))
    args = parser.parse_args()

    log("Cài đặt Diarization — tự tách giọng theo người nói (tuỳ chọn)")
    if not os.path.isfile(WORKER):
        raise SystemExit(f"!! không thấy worker script: {WORKER}")
    step_venv()
    step_install()
    step_smoke(args.hf_token)
    step_enable_env(args.hf_token)
    log("XONG — video nhiều người nói giờ tự tách giọng, mỗi người 1 giọng "
        "TTS riêng (bật/tắt ở trang Cài đặt, mục 'Tự tách giọng theo người "
        "nói').")


if __name__ == "__main__":
    main()
