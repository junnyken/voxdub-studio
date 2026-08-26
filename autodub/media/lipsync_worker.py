"""Worker lip-sync (MuseTalk) — chạy BÊN TRONG .venv-lipsync (mini-spec V32b,
docs/PLAN.md Phase G). KHÔNG chạy trực tiếp bằng Python của app chính —
MuseTalk pin numpy==1.23.5, xung đột numpy>=1.24 của pyproject.toml gốc, đây
CHÍNH LÀ lý do venv phải tách hẳn (xem docs/TEST_LOG.md mục V32a).

Đây là bản PRODUCTION, chuyển thể TRỰC TIẾP từ harness nghiên cứu đã
live-verify thật trên GPU thật (scripts/research/lipsync_poc.py, 8 bug môi
trường đã tìm+sửa — xem docs/TEST_LOG.md mục "V32a — Re-audit") — chỉ đổi
đường dẫn (vendor/musetalk thay scripts/research/musetalk_repo) và bọc lại
thành 1 worker JSON qua stdout (đúng giao thức demucs_worker.py/
asr_paraformer_worker.py: mỗi dòng in ra là 1 JSON, cha đọc lại bằng
`json.loads`), KHÔNG viết lại logic MuseTalk.

Giao thức stdout (mỗi dòng flush ngay):
  {"stage": "consent_check", ...}   — kết quả bước 1, LUÔN in trước khi chạy
                                       inference (dù pass hay fail)
  {"stage": "done", "ok": true, "output_video": "...", ...}
  {"stage": "done", "ok": false, "reason": "consent_blocked"|"error", ...}

Gọi (ví dụ):
  .venv-lipsync/bin/python -m autodub.media.lipsync_worker \\
    --video <video gốc> --audio <audio đã lồng tiếng> --output-dir <thư mục> \\
    --max-no-face-ratio 0.0
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import threading
import time

# Windows mặc định cho tiến trình con dùng bảng mã cp1252 khi ghi ra ống —
# in một chữ Việt có dấu là chết ngay giữa chừng với UnicodeEncodeError, và
# tiến trình cha chỉ thấy "worker kết thúc bất thường". Lỗi thật, xảy ra với
# người dùng 26/8/2026: chữ "Đ" làm hỏng cả lượt dịch ngoại tuyến.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO_DIR = os.path.join(PROJECT_ROOT, "vendor", "musetalk")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models", "lipsync")


def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def _resolve_ffmpeg() -> str:
    # KHÔNG import autodub ở đây — "import autodub.<bất kỳ gì>" luôn chạy
    # autodub/__init__.py trước, kéo theo dependency nặng không có trong
    # .venv-lipsync (bug thật đã gặp ở setup_lipsync_poc.py, xem V32a).
    local_ffmpeg = os.path.join(PROJECT_ROOT, "bin", "ffmpeg.exe")
    return shutil.which("ffmpeg") or (
        local_ffmpeg if os.path.isfile(local_ffmpeg) else "ffmpeg")


class _VramPoller:
    """Poll `nvidia-smi` mỗi 0.5s trong lúc inference chạy — MuseTalk không
    tự báo VRAM peak, phải đo từ bên ngoài (nguyên văn V32a)."""

    def __init__(self):
        self.peak_mb = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5).stdout.strip()
                used = int(out.splitlines()[0])
                self.peak_mb = max(self.peak_mb, used)
            except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
                pass
            self._stop.wait(0.5)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=2)


def consent_check(video: str, result_dir: str, ffmpeg_bin: str) -> dict:
    """Đúng logic Scope C của V32a (`get_landmark_and_bbox()` THẬT của
    MuseTalk, không tự viết detector riêng) — % frame KHÔNG phát hiện được
    khuôn mặt nào. CHẠY TRƯỚC inference (Constraint 3 của V32b: consent-check
    PHẢI chạy trước khi xử lý, không phải hậu kiểm)."""
    sys.path.insert(0, REPO_DIR)
    original_cwd = os.getcwd()
    try:
        os.chdir(REPO_DIR)   # preprocessing.py mở config DWPose bằng đường
                              # dẫn tương đối ngay lúc import (bug #5, V32a)
        from musetalk.utils.preprocessing import (  # noqa: PLC0415
            coord_placeholder, get_landmark_and_bbox,
        )
    finally:
        os.chdir(original_cwd)

    frame_dir = os.path.join(result_dir, "frames_for_face_audit")
    os.makedirs(frame_dir, exist_ok=True)
    subprocess.run([ffmpeg_bin, "-v", "fatal", "-y", "-i", video,
                    "-start_number", "0",
                    os.path.join(frame_dir, "%08d.png")], check=True)
    img_list = sorted(glob.glob(os.path.join(frame_dir, "*.png")))
    if not img_list:
        return {"ok": False, "reason": "không tách được frame nào từ video"}

    coords_list, _frames = get_landmark_and_bbox(img_list)
    no_face = sum(1 for c in coords_list if tuple(c) == coord_placeholder)
    total = len(img_list)
    return {
        "ok": True, "total_frames": total, "no_face_frames": no_face,
        "no_face_ratio": round(no_face / total, 4) if total else None,
    }


def run_inference(video: str, audio: str, result_dir: str, ffmpeg_bin: str,
                  parsing_mode: str) -> dict:
    """Đúng logic Scope B của V32a — gọi `scripts.inference` THẬT của
    MuseTalk qua subprocess, KHÔNG viết lại. Cờ `--use_float16
    --batch_size 4` là kết quả live-verify thật (bug #7, V32a) — không đổi
    nếu chưa có số liệu mới trên phần cứng khác."""
    import yaml  # noqa: PLC0415 — chỉ cần trong nhánh này (bug #6, V32a)

    config_path = os.path.join(result_dir, "task.yaml")
    task_name = os.path.splitext(os.path.basename(video))[0]
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"task_0": {"video_path": video, "audio_path": audio}},
                       f, allow_unicode=True)

    unet_path = os.path.join(MODELS_DIR, "musetalkV15", "unet.pth")
    unet_cfg = os.path.join(MODELS_DIR, "musetalkV15", "musetalk.json")
    cmd = [
        sys.executable, "-m", "scripts.inference",
        "--inference_config", config_path,
        "--result_dir", result_dir,
        "--unet_model_path", unet_path,
        "--unet_config", unet_cfg,
        "--version", "v15",
        "--ffmpeg_path", os.path.dirname(ffmpeg_bin) or ".",
        "--use_float16",
        "--batch_size", "4",
        "--parsing_mode", parsing_mode,
    ]

    # Ép UTF-8 cả 2 đầu — MuseTalk in ký tự CJK trang trí, Windows rơi về
    # codepage ANSI hẹp khi stdout bị pipe-redirect (bug #8, V32a).
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    started = time.monotonic()
    output_lines: list[str] = []
    with _VramPoller() as vram:
        proc = subprocess.Popen(cmd, cwd=REPO_DIR, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1,
                                encoding="utf-8", errors="replace", env=env)
        for line in proc.stdout:
            output_lines.append(line)
        proc.wait()
    elapsed_s = time.monotonic() - started
    full_output = "".join(output_lines)

    # Mã thoát của MuseTalk KHÔNG đáng tin (bug #8, V32a) — nó tự bắt MỌI
    # exception trong lúc xử lý rồi chỉ IN RA, không sys.exit()/raise lại.
    # Chỉ coi "ok" khi ĐỦ 3 điều: mã thoát 0, KHÔNG có chuỗi lỗi đặc trưng
    # trong output, VÀ file video kết quả thật sự tồn tại.
    exit_ok = proc.returncode == 0
    error_in_output = "Error occurred during processing:" in full_output

    candidates = glob.glob(os.path.join(result_dir, "v15", "*.mp4"))
    candidates = [c for c in candidates if not c.endswith("_concat.mp4")]
    output_video = candidates[0] if candidates else None
    ok = exit_ok and not error_in_output and output_video is not None

    return {
        "ok": ok, "task_name": task_name, "elapsed_seconds": round(elapsed_s, 1),
        "vram_peak_mb": vram.peak_mb, "output_video": output_video,
        "returncode": proc.returncode, "error_in_output": error_in_output,
        "output_tail": full_output[-3000:] if not ok else "",
    }


def apply_watermark(input_video: str, output_video: str, ffmpeg_bin: str) -> dict:
    """Watermark chữ đè, LUÔN áp dụng — Constraint 4 của V32b: không phải
    tính năng thẩm mỹ, không có code path nào bỏ qua được. Kèm THÊM metadata
    ẩn (bonus — dấu vết pháp lý khi video bị re-encode/mất phần overlay
    hình ảnh), 2 lớp cùng lúc thay vì chọn 1 trong 2 như PoC đã thử nghiệm."""
    font_path = os.path.join(PROJECT_ROOT, "fonts", "BarlowCondensed-Regular.ttf")
    font_arg = font_path.replace("\\", "/").replace(":", "\\:")

    proc = subprocess.run([
        ffmpeg_bin, "-v", "error", "-y", "-i", input_video,
        "-vf", f"drawtext=fontfile='{font_arg}':text='VoxDub AI — Đồng "
               "bộ khẩu h\xecnh AI':fontcolor=white@0.7:fontsize=18:"
               "x=w-tw-10:y=h-th-10:box=1:boxcolor=black@0.4",
        "-metadata", "comment=Video xử lý bằng AI đồng bộ khẩu hình — VoxDub Studio",
        "-codec:a", "copy", output_video,
    ], capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0,
        "output": output_video if proc.returncode == 0 else None,
        "stderr_tail": proc.stderr[-800:] if proc.returncode != 0 else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--parsing-mode", default="jaw", choices=["jaw", "raw", "neck"])
    parser.add_argument("--max-no-face-ratio", type=float, default=0.0,
                        help="Constraint 3 của V32b — chặn NGAY nếu tỷ lệ "
                             "frame thiếu mặt vượt trần (mặc định 0.0, đúng "
                             "mẫu benchmark thành công duy nhất của V32a).")
    args = parser.parse_args()

    video = os.path.abspath(args.video)
    audio = os.path.abspath(args.audio)
    if not os.path.isfile(video):
        _emit({"stage": "done", "ok": False, "reason": "video_not_found", "path": video})
        return 1
    if not os.path.isfile(audio):
        _emit({"stage": "done", "ok": False, "reason": "audio_not_found", "path": audio})
        return 1
    if not os.path.isdir(os.path.join(REPO_DIR, "musetalk")):
        _emit({"stage": "done", "ok": False, "reason": "not_installed",
              "message": "vendor/musetalk chưa cài — chạy scripts/setup_lipsync.py"})
        return 1

    ffmpeg_bin = _resolve_ffmpeg()
    os.makedirs(args.output_dir, exist_ok=True)

    try:
        consent = consent_check(video, args.output_dir, ffmpeg_bin)
    except Exception as e:  # noqa: BLE001 — worker: báo lỗi rõ, không chết mù mờ
        _emit({"stage": "done", "ok": False, "reason": "consent_check_error", "error": str(e)})
        return 1
    _emit({"stage": "consent_check", **consent})

    if not consent.get("ok") or (consent.get("no_face_ratio") or 0) > args.max_no_face_ratio:
        _emit({"stage": "done", "ok": False, "reason": "consent_blocked",
              "consent_check": consent})
        return 0   # KHÔNG phải lỗi — đúng chính sách chặn, thoát sạch.

    try:
        inference = run_inference(video, audio, args.output_dir, ffmpeg_bin, args.parsing_mode)
    except Exception as e:  # noqa: BLE001
        _emit({"stage": "done", "ok": False, "reason": "inference_error", "error": str(e)})
        return 1
    if not inference["ok"]:
        _emit({"stage": "done", "ok": False, "reason": "inference_failed", **inference})
        return 1

    final_output = os.path.join(args.output_dir, "lipsync_watermarked.mp4")
    try:
        wm = apply_watermark(inference["output_video"], final_output, ffmpeg_bin)
    except Exception as e:  # noqa: BLE001
        _emit({"stage": "done", "ok": False, "reason": "watermark_error", "error": str(e)})
        return 1
    if not wm["ok"]:
        _emit({"stage": "done", "ok": False, "reason": "watermark_failed", **wm})
        return 1

    _emit({
        "stage": "done", "ok": True, "output_video": final_output,
        "elapsed_seconds": inference["elapsed_seconds"],
        "vram_peak_mb": inference["vram_peak_mb"],
        "consent_check": consent,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
