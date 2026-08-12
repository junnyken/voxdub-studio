"""Cài đặt PoC Lip-sync (MuseTalk) — mini-spec V32a, docs/PLAN.md Phase G.

Chạy 1 lần:  py scripts/setup_lipsync_poc.py

Đây KHÔNG PHẢI cài đặt tính năng sản phẩm — chỉ dựng môi trường THỬ NGHIỆM
cô lập để đo benchmark thật (VRAM/thời gian xử lý/tỷ lệ nhận diện khuôn mặt)
trên GPU thật, phục vụ quyết định V32b có đáng build không. KHÔNG đụng
`pipeline.py`/`requirements.txt` chính của VoxDub.

BẮT BUỘC PHẢI CÓ GPU NVIDIA THẬT (CUDA) — đây là giới hạn kỹ thuật thật của
MuseTalk (xem docs/TEST_LOG.md mục V30), không phải của script này. Tối
thiểu đã có số liệu cộng đồng chạy được: ~4GB VRAM (vd RTX 3050 Ti laptop),
chậm nhưng chạy được. Không có GPU NVIDIA → script dừng ngay ở bước đầu,
không phí thời gian cài ~10-15GB dependency + model weights.

MuseTalk (README chính chủ) khuyến nghị CHÍNH XÁC Python 3.10 — bản mới hơn
(3.12/3.13/3.14) KHÔNG cài được torch==2.0.1 (bị pin cứng, không có wheel).
Script tự tìm Python 3.10 riêng trên máy qua launcher `py -3.10` (Windows)
nếu Python mặc định không phải 3.10 — không cần tự lo trước, nhưng máy PHẢI
có sẵn 1 bản Python 3.10 đã cài (xem bước 2 bên dưới nếu chưa có).

Các bước resume-safe — chạy lại script sẽ bỏ qua phần đã xong:
  1. Kiểm tra GPU NVIDIA thật (nvidia-smi) — DỪNG NGAY nếu không có.
  2. Kiểm tra/tìm Python 3.10 (torch==2.0.1 không cài được ở Python mới hơn)
     — DỪNG kèm hướng dẫn cài nếu máy chưa có Python 3.10 nào.
  3. Tạo virtualenv .venv-lipsync (bằng đúng Python 3.10 tìm được ở bước 2)
  4. Cài PyTorch 2.0.1 (bản CUDA 11.8, đúng pin của MuseTalk) + requirements.txt
  5. Cài bộ MMLab (mmengine/mmcv/mmdet/mmpose — dùng cho DWPose face-keypoint,
     đây CŨNG là bước dùng lại được cho consent-check face-detection ở Scope C)
  6. Clone mã nguồn MuseTalk (ghim đúng 1 commit cụ thể để tái lập được, xem
     MUSETALK_COMMIT bên dưới) vào scripts/research/musetalk_repo/ — KHÔNG
     commit vào git (xem .gitignore)
  7. Tải model weights thật (~5-6GB, nhiều nguồn: HuggingFace + Google Drive +
     pytorch.org) vào scripts/research/musetalk_repo/models/

Sau khi xong, chạy: py scripts/research/lipsync_poc.py --video <đường dẫn>
để đo benchmark thật (Scope B/C/D của mini-spec V32a).

Ghi chú THẬT về độ rủi ro (không giấu):
- Gói `mmcv==2.0.1` là extension biên dịch sẵn (OpenMMLab) — cài qua `mim
  install` sẽ tự tìm wheel dựng sẵn khớp đúng bản Python/CUDA/PyTorch đang
  dùng. Nếu KHÔNG có wheel dựng sẵn khớp máy bạn (thường xảy ra với bản
  Python/CUDA lạ), bước này có thể lỗi và cần build từ mã nguồn (cần
  Visual Studio Build Tools trên Windows) — đây là rủi ro THẬT của chính
  MuseTalk, không phải lỗi script.
- requirements.txt của MuseTalk ghim `numpy==1.23.5` — CŨ hơn nhiều so với
  `numpy>=1.24` mà `pyproject.toml` chính của VoxDub yêu cầu. Đây là đúng lý
  do venv `.venv-lipsync` phải TÁCH HẲN, không bao giờ được cài vào venv
  chính hay dùng chung site-packages.
"""
import json
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_DIR = os.path.join(PROJECT_ROOT, ".venv-lipsync")
VENV_PY = os.path.join(VENV_DIR, "Scripts" if os.name == "nt" else "bin",
                       "python.exe" if os.name == "nt" else "python")

RESEARCH_DIR = os.path.join(PROJECT_ROOT, "scripts", "research")
REPO_DIR = os.path.join(RESEARCH_DIR, "musetalk_repo")
MODELS_DIR = os.path.join(REPO_DIR, "models")
MARKER = os.path.join(RESEARCH_DIR, "lipsync_poc_setup_ok.json")

MUSETALK_REPO_URL = "https://github.com/TMElyralab/MuseTalk.git"
# Ghim đúng 1 commit (main, 2025-09-26) để PoC tái lập được — kiểm tra thật
# qua GitHub API trước khi ghim, không suy đoán. Đổi giá trị này (kèm ghi
# chú lý do) nếu chủ động muốn dùng bản mới hơn.
MUSETALK_COMMIT = "0a89dec45a0192b824e3cf4daf96c239440c5ed8"

# Đúng pin của chính MuseTalk (README "Install PyTorch 2.0.1", Option 1 pip)
# — KHÔNG tự đổi version, mmcv/mmdet/mmpose bên dưới build sẵn khớp đúng tổ
# hợp này.
TORCH_INDEX_URL = "https://download.pytorch.org/whl/cu118"
TORCH_PACKAGES = ["torch==2.0.1", "torchvision==0.15.2", "torchaudio==2.0.2"]


def log(msg: str) -> None:
    print(f"[setup-lipsync-poc] {msg}", flush=True)


def _find_py310() -> str | None:
    """Tìm 1 bản Python 3.10 CỤ THỂ trên máy — torch==2.0.1 (MuseTalk pin
    cứng) không có wheel cho Python quá mới (xác nhận thật: lỗi "No matching
    distribution found for torch==2.0.1" khi tạo venv bằng Python 3.14).
    Ưu tiên `py -3.10` (launcher chuẩn của Windows, tìm được cả khi 3.10
    không phải bản mặc định), sau đó `python3.10` (Linux/Mac)."""
    candidates = ([["py", "-3.10"]] if os.name == "nt" else []) + [["python3.10"]]
    for cmd in candidates:
        if not shutil.which(cmd[0]):
            continue
        probe = subprocess.run([*cmd, "-c", "import sys; print(sys.executable)"],
                               capture_output=True, text=True)
        if probe.returncode == 0 and probe.stdout.strip():
            return probe.stdout.strip()
    return None


def step_check_python() -> str:
    """MuseTalk (README) khuyến nghị CHÍNH XÁC Python 3.10 — GATE trước khi
    tạo venv, tránh lặp lại lỗi thật đã gặp (venv tạo bằng Python 3.14 khiến
    bước cài torch==2.0.1 chết ngay với "No matching distribution"). Trả về
    đường dẫn Python 3.10 sẽ dùng để tạo `.venv-lipsync`."""
    if sys.version_info[:2] == (3, 10):
        return sys.executable
    log(f"Python đang chạy script này ({sys.version.split()[0]}) không phải "
        "3.10 — torch==2.0.1 (MuseTalk pin cứng) không có bản cài cho "
        "version này. Tìm Python 3.10 riêng trên máy ...")
    found = _find_py310()
    if not found:
        raise SystemExit(
            "!! Không tìm thấy Python 3.10 trên máy. MuseTalk BẮT BUỘC "
            "đúng Python 3.10 (KHÔNG chạy được bản mới hơn như 3.12/3.13/"
            "3.14).\nCài Python 3.10 tại: "
            "https://www.python.org/downloads/release/python-31011/ "
            "(mục 'Windows installer (64-bit)', nhớ tick 'Add python.exe "
            "to PATH' lúc cài) rồi chạy lại:\n"
            "  py -3.10 scripts\\setup_lipsync_poc.py")
    log(f"tìm thấy Python 3.10: {found}")
    return found


def step_check_gpu() -> None:
    """Constraint 2 của mini-spec V32a — GATE CHẶN CỨNG, kiểm TRƯỚC khi cài
    bất cứ gì (đỡ phí ~15GB tải về + thời gian nếu máy không có GPU)."""
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        raise SystemExit(
            "!! Không tìm thấy nvidia-smi — máy này không có GPU NVIDIA "
            "(hoặc driver chưa cài). MuseTalk BẮT BUỘC cần GPU NVIDIA thật "
            "(xem docs/TEST_LOG.md mục V30) — dừng lại ở đây, không cài "
            "tiếp. Cài driver NVIDIA mới nhất (nvidia.com/drivers) rồi chạy "
            "lại script này.")
    try:
        out = subprocess.run(
            [nvidia_smi, "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=15, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        raise SystemExit(f"!! nvidia-smi có mặt nhưng chạy lỗi: {e}") from e
    if not out:
        raise SystemExit("!! nvidia-smi không báo GPU nào — kiểm tra driver.")
    log(f"GPU thật phát hiện được: {out}")
    try:
        vram_mb = int(out.split(",")[-1].strip().split()[0])
    except (ValueError, IndexError):
        vram_mb = 0
    if vram_mb and vram_mb < 3500:
        log(f"CẢNH BÁO: VRAM {vram_mb}MB thấp hơn mức tối thiểu cộng đồng đã "
            "chạy được (~4GB) — vẫn tiếp tục cài theo yêu cầu, nhưng benchmark "
            "có thể fail vì hết bộ nhớ (OOM), không phải lỗi cài đặt.")


def step_venv(py310: str) -> None:
    if os.path.isfile(VENV_PY):
        probe = subprocess.run(
            [VENV_PY, "-c", "import sys; print(sys.version_info[:2])"],
            capture_output=True, text=True)
        if probe.returncode == 0 and probe.stdout.strip() == "(3, 10)":
            log("venv .venv-lipsync đã có, đúng Python 3.10 — bỏ qua")
            return
        log("venv .venv-lipsync đã có nhưng SAI bản Python (không phải "
            "3.10, chắc chắn sẽ lỗi cài torch) — xoá và tạo lại đúng bằng "
            "Python 3.10 ...")
        shutil.rmtree(VENV_DIR, ignore_errors=True)
    log(f"tạo virtualenv .venv-lipsync bằng {py310} (Python 3.10) ...")
    subprocess.run([py310, "-m", "venv", VENV_DIR], check=True)


def _pip_install(*args: str) -> None:
    subprocess.run([VENV_PY, "-m", "pip", "install", "--quiet", *args], check=True)


def step_torch() -> None:
    probe = subprocess.run(
        [VENV_PY, "-c", "import torch; print(torch.__version__)"],
        capture_output=True, text=True)
    if probe.returncode == 0 and probe.stdout.strip().startswith("2.0.1"):
        log("PyTorch 2.0.1 đã cài — bỏ qua")
        return
    log("cài PyTorch 2.0.1 (bản CUDA 11.8, ~2.5GB) — có thể mất nhiều phút ...")
    _pip_install(*TORCH_PACKAGES, "--index-url", TORCH_INDEX_URL)


def step_clone_repo() -> None:
    if os.path.isdir(os.path.join(REPO_DIR, ".git")):
        log("mã nguồn MuseTalk đã clone — kiểm tra đúng commit ghim ...")
        current = subprocess.run(
            ["git", "-C", REPO_DIR, "rev-parse", "HEAD"],
            capture_output=True, text=True).stdout.strip()
        if current == MUSETALK_COMMIT:
            log("đúng commit đã ghim — bỏ qua")
            return
        log(f"commit hiện tại ({current[:10]}) khác commit ghim "
            f"({MUSETALK_COMMIT[:10]}) — checkout lại")
        subprocess.run(["git", "-C", REPO_DIR, "fetch", "--depth", "1",
                        "origin", MUSETALK_COMMIT], check=True)
        subprocess.run(["git", "-C", REPO_DIR, "checkout", MUSETALK_COMMIT],
                       check=True)
        return
    os.makedirs(RESEARCH_DIR, exist_ok=True)
    log(f"clone MuseTalk (ghim commit {MUSETALK_COMMIT[:10]}) ...")
    subprocess.run(["git", "clone", MUSETALK_REPO_URL, REPO_DIR], check=True)
    subprocess.run(["git", "-C", REPO_DIR, "checkout", MUSETALK_COMMIT],
                   check=True)


def step_install_requirements() -> None:
    req_path = os.path.join(REPO_DIR, "requirements.txt")
    if not os.path.isfile(req_path):
        raise SystemExit(f"!! không thấy {req_path} — clone repo lỗi?")
    log("cài requirements.txt của MuseTalk (numpy/opencv/diffusers/... — "
        "cô lập trong .venv-lipsync, KHÔNG đụng venv chính VoxDub) ...")
    _pip_install("-r", req_path)


def step_install_mmlab() -> None:
    probe = subprocess.run([VENV_PY, "-c", "import mmpose"], capture_output=True)
    if probe.returncode == 0:
        log("bộ MMLab (mmcv/mmdet/mmpose) đã cài — bỏ qua")
        return
    log("cài bộ MMLab (mmengine/mmcv/mmdet/mmpose — dùng cho DWPose, cũng là "
        "nền cho thử nghiệm face-detection/consent-check Scope C) — đây là "
        "bước DỄ LỖI NHẤT nếu máy dùng bản Python/CUDA không có wheel dựng "
        "sẵn, xem ghi chú rủi ro ở đầu file ...")
    _pip_install("--no-cache-dir", "-U", "openmim")
    for pkg in ("mmengine", "mmcv==2.0.1", "mmdet==3.1.0", "mmpose==1.1.0"):
        subprocess.run([VENV_PY, "-m", "mim", "install", pkg], check=True)


def step_download_weights() -> None:
    if os.path.isfile(MARKER):
        log("model weights đã tải đủ — bỏ qua")
        return
    log("tải model weights thật (~5-6GB tổng — HuggingFace + Google Drive + "
        "pytorch.org, có thể mất nhiều phút tuỳ mạng) ...")
    _pip_install("-U", "huggingface_hub[cli]", "gdown")

    for d in ("musetalk", "musetalkV15", "syncnet", "dwpose",
             "face-parse-bisent", "sd-vae", "whisper"):
        os.makedirs(os.path.join(MODELS_DIR, d), exist_ok=True)

    downloads = [
        ("TMElyralab/MuseTalk", MODELS_DIR,
         ["musetalk/musetalk.json", "musetalk/pytorch_model.bin",
          "musetalkV15/musetalk.json", "musetalkV15/unet.pth"]),
        ("stabilityai/sd-vae-ft-mse", os.path.join(MODELS_DIR, "sd-vae"),
         ["config.json", "diffusion_pytorch_model.bin"]),
        ("openai/whisper-tiny", os.path.join(MODELS_DIR, "whisper"),
         ["config.json", "pytorch_model.bin", "preprocessor_config.json"]),
        ("yzd-v/DWPose", os.path.join(MODELS_DIR, "dwpose"),
         ["dw-ll_ucoco_384.pth"]),
        ("ByteDance/LatentSync", os.path.join(MODELS_DIR, "syncnet"),
         ["latentsync_syncnet.pt"]),
    ]
    for repo_id, local_dir, patterns in downloads:
        gen = (
            "from huggingface_hub import snapshot_download\n"
            f"snapshot_download(repo_id={repo_id!r}, local_dir={local_dir!r}, "
            f"allow_patterns={patterns!r})\n"
        )
        subprocess.run([VENV_PY, "-c", gen], check=True)

    face_parse_pth = os.path.join(MODELS_DIR, "face-parse-bisent",
                                  "79999_iter.pth")
    if not os.path.isfile(face_parse_pth):
        log("tải face-parse-bisent qua Google Drive (gdown) ...")
        subprocess.run([VENV_PY, "-m", "gdown",
                        "--id", "154JgKpzCPW82qINcVieuPH3fZ2e0P812",
                        "-O", face_parse_pth], check=True)

    resnet_pth = os.path.join(MODELS_DIR, "face-parse-bisent",
                              "resnet18-5c106cde.pth")
    if not os.path.isfile(resnet_pth):
        gen = (
            "import urllib.request\n"
            "urllib.request.urlretrieve("
            "'https://download.pytorch.org/models/resnet18-5c106cde.pth', "
            f"{resnet_pth!r})\n"
        )
        subprocess.run([VENV_PY, "-c", gen], check=True)

    missing = [p for p in (
        os.path.join(MODELS_DIR, "musetalkV15", "unet.pth"),
        os.path.join(MODELS_DIR, "sd-vae", "diffusion_pytorch_model.bin"),
        os.path.join(MODELS_DIR, "whisper", "pytorch_model.bin"),
        os.path.join(MODELS_DIR, "dwpose", "dw-ll_ucoco_384.pth"),
        face_parse_pth, resnet_pth,
    ) if not os.path.isfile(p)]
    if missing:
        raise SystemExit(
            "!! Tải weights KHÔNG đủ, thiếu:\n  " + "\n  ".join(missing) +
            "\nChạy lại script — các phần đã tải sẽ được bỏ qua (resume-safe).")

    with open(MARKER, "w", encoding="utf-8") as f:
        json.dump({"ok": True, "musetalk_commit": MUSETALK_COMMIT},
                  f, ensure_ascii=False, indent=2)
    log("tải weights XONG, đủ file.")


def step_check_ffmpeg() -> None:
    """MuseTalk cần ffmpeg — VoxDub đã có sẵn (bin/ffmpeg.exe hoặc PATH),
    dùng lại chứ không cài riêng (đỡ 1 bộ cài trùng)."""
    from autodub.resources import app_root  # noqa: PLC0415

    local_ffmpeg = os.path.join(app_root(), "bin", "ffmpeg.exe")
    ffmpeg_cmd = shutil.which("ffmpeg") or (
        local_ffmpeg if os.path.isfile(local_ffmpeg) else None)
    if not ffmpeg_cmd:
        log("CẢNH BÁO: không tìm thấy ffmpeg trên máy — MuseTalk (mux audio "
            "vào video output) và bước thử nghiệm watermark (Scope D) cần "
            "ffmpeg. Cài theo đúng hướng dẫn preflight của VoxDub trước khi "
            "chạy scripts/research/lipsync_poc.py.")
    else:
        log(f"ffmpeg sẵn có: {ffmpeg_cmd}")


def main() -> None:
    log("Cài đặt PoC Lip-sync (MuseTalk) — mini-spec V32a, docs/PLAN.md Phase G")
    log("Đây là môi trường THỬ NGHIỆM cô lập, KHÔNG phải tính năng sản phẩm.")
    step_check_gpu()
    py310 = step_check_python()
    step_venv(py310)
    step_torch()
    step_clone_repo()
    step_install_requirements()
    step_install_mmlab()
    step_download_weights()
    step_check_ffmpeg()
    log("XONG — chạy tiếp: py scripts/research/lipsync_poc.py --video "
        "<đường dẫn video mẫu> để đo benchmark thật (Scope B/C/D của V32a).")


if __name__ == "__main__":
    main()
