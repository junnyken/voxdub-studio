"""Cài bộ tách nhạc nền (Demucs) — để bản lồng tiếng còn nhạc/tiếng động nền.

Chạy 1 lần:  py scripts/setup_demucs.py   (hoặc đúp chuột tệp .bat cùng tên)

Vì sao có tệp này (mini-spec V86): `autodub.spec` CỐ Ý loại torch/demucs/
soundfile khỏi bản đóng gói (chúng nặng hàng GB), Demucs chạy trong venv
riêng `.venv-gpu` qua `demucs_worker.py`. Nhưng **chưa từng có script nào tạo
venv đó** — chỉ có tài liệu nhắc tên. Nên trên MỌI bản đóng gói, bước "Tách
nhạc nền" luôn hỏng và video ra chỉ còn giọng đọc, không có nhạc/tiếng động.

Người dùng báo đúng lỗi này (2026-08-19, v3.4.8):
    Không tách được nhạc nền — video sẽ chỉ còn giọng đọc

Máy có card NVIDIA thì cài torch bản CUDA (nhanh hơn nhiều, ~2,5 GB); không
có thì cài bản CPU (~200 MB, chậm hơn nhưng vẫn chạy).
"""
import os
import shutil
import subprocess
import sys
import wave

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _python_ho_tro import (  # noqa: E402
    bao_dam_python_ho_tro,
    venv_dung_python_ho_tro,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_DIR = os.path.join(PROJECT_ROOT, ".venv-gpu")
VENV_PY = os.path.join(VENV_DIR, "Scripts" if os.name == "nt" else "bin",
                       "python.exe" if os.name == "nt" else "python")

#: Chốt trần major: demucs 5.x có thể đổi API `apply_model` mà worker gọi thẳng.
_DEMUCS_SPEC = "demucs>=4.0.0,<5.0"
_SOUNDFILE_SPEC = "soundfile>=0.13.0,<0.14"
#: Bản CUDA của torch — chỉ dùng khi máy có card NVIDIA thật.
_TORCH_CUDA_INDEX = "https://download.pytorch.org/whl/cu124"
_TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"


def log(msg: str) -> None:
    print(f"[setup-demucs] {msg}", flush=True)


def co_card_nvidia() -> bool:
    if not shutil.which("nvidia-smi"):
        return False
    try:
        return subprocess.run(["nvidia-smi"], capture_output=True,
                              timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def step_venv() -> None:
    if os.path.isfile(VENV_PY):
        if venv_dung_python_ho_tro(VENV_PY):
            log("venv .venv-gpu đã có — bỏ qua")
            return
        log("venv .venv-gpu được tạo bằng Python không hỗ trợ — dựng lại")
        shutil.rmtree(VENV_DIR, ignore_errors=True)
    log("tạo virtualenv .venv-gpu ...")
    subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)


def step_install() -> None:
    probe = subprocess.run([VENV_PY, "-c", "import demucs, torch, soundfile"],
                           capture_output=True)
    if probe.returncode == 0:
        log("demucs + torch đã cài — bỏ qua")
        return
    if co_card_nvidia():
        log("phát hiện card NVIDIA — cài torch bản CUDA (~2,5 GB, tải lâu)")
        index = _TORCH_CUDA_INDEX
    else:
        log("không thấy card NVIDIA — cài torch bản CPU (~200 MB, chậm hơn "
            "nhưng vẫn tách được)")
        index = _TORCH_CPU_INDEX
    subprocess.run([VENV_PY, "-m", "pip", "install", "--quiet", "--upgrade",
                    "pip"], check=False)
    subprocess.run([VENV_PY, "-m", "pip", "install", "--quiet",
                    "--index-url", index, "torch", "torchaudio"], check=True)
    log("cài demucs + soundfile ...")
    subprocess.run([VENV_PY, "-m", "pip", "install", "--quiet",
                    _DEMUCS_SPEC, _SOUNDFILE_SPEC], check=True)


def _worker_script() -> str:
    """`demucs_worker.py` trong gói — bản onedir để nó ở `_internal/`."""
    ung_vien = [os.path.join(PROJECT_ROOT, "autodub", "media",
                             "demucs_worker.py")]
    for d in ("_internal", "data"):
        ung_vien.append(os.path.join(PROJECT_ROOT, d, "autodub", "media",
                                     "demucs_worker.py"))
    for duong in ung_vien:
        if os.path.isfile(duong):
            return duong
    raise SystemExit("!! không thấy demucs_worker.py — bản cài bị thiếu tệp")


def step_smoke() -> None:
    """Tách thử 2 giây im lặng: kéo luôn model htdemucs (~80 MB) về máy để
    lần lồng tiếng đầu tiên không phải chờ tải giữa chừng."""
    import tempfile

    tam = tempfile.mkdtemp(prefix="demucs-smoke-")
    wav = os.path.join(tam, "test.wav")
    with wave.open(wav, "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b"\0\0\0\0" * 44100 * 2)

    log("chạy thử (lần đầu tải model ~80 MB, có thể mất vài phút) ...")
    ket = subprocess.run(
        [VENV_PY, _worker_script(),
         "--input", wav,
         "--vocals", os.path.join(tam, "vocals.wav"),
         "--no-vocals", os.path.join(tam, "no_vocals.wav"),
         "--model", "htdemucs"],
        capture_output=True, text=True, timeout=3600)
    shutil.rmtree(tam, ignore_errors=True)
    if ket.returncode != 0:
        duoi = (ket.stderr or ket.stdout or "")[-500:]
        raise SystemExit(f"!! chạy thử thất bại:\n{duoi}")
    log("chạy thử đạt")


def main() -> None:
    bao_dam_python_ho_tro()
    log("Cài bộ tách nhạc nền (Demucs) — giữ lại nhạc/tiếng động của video gốc")
    step_venv()
    step_install()
    step_smoke()
    log("XONG — mở lại ứng dụng, bước Tách nhạc nền sẽ chạy được.")


if __name__ == "__main__":
    main()
