"""PoC benchmark Lip-sync (MuseTalk) — mini-spec V32a, docs/PLAN.md Phase G.

Chạy SAU KHI đã cài xong qua `py scripts/setup_lipsync_poc.py`, BÊN TRONG
`.venv-lipsync` (script setup không tự kích hoạt venv cho bạn — tự chạy
bằng đúng python của venv đó, xem ví dụ bên dưới).

Đo 3 nhóm số liệu THẬT cho 1 video mẫu (Scope B/C/D của mini-spec V32a):
  B. Benchmark: chạy MuseTalk inference thật (subprocess `scripts/inference.py`
     của chính MuseTalk, KHÔNG viết lại) — đo thời gian xử lý + VRAM peak
     (poll `nvidia-smi` mỗi 0.5s trong lúc chạy).
  C. Consent-check: tách frame bằng đúng lệnh ffmpeg MuseTalk dùng nội bộ,
     gọi THẲNG `musetalk.utils.preprocessing.get_landmark_and_bbox()` (hàm
     THẬT của MuseTalk, không tự viết detector riêng) — đếm % frame KHÔNG
     phát hiện được khuôn mặt nào (`coord_placeholder`).
  D. Watermark: thử 2 phương án ffmpeg trên video kết quả — overlay chữ góc
     dưới (nhìn thấy được) và metadata ẩn — đo thời gian xử lý thêm mỗi
     phương án.

Ví dụ chạy (Windows):
  .venv-lipsync\\Scripts\\python.exe scripts\\research\\lipsync_poc.py ^
    --video "output\\VN\\20260101000000_vi\\data\\..." --audio "...audio_vi_full.wav" ^
    --label mat_thang

Ví dụ chạy (Linux):
  .venv-lipsync/bin/python scripts/research/lipsync_poc.py \\
    --video /path/video_goc.mp4 --audio /path/audio_vi_full.wav --label goc_nghieng

Kết quả: JSON report ghi vào scripts/research/lipsync_poc_output/<label>/report.json
— gộp báo cáo của ≥3 lượt chạy (mặt thẳng/góc nghiêng/nhiều người, Constraint 6
của mini-spec) thành bảng cuối cùng trong docs/TEST_LOG.md, KHÔNG tự động hoá
bước tổng hợp/viết tài liệu đó (cần đọc số liệu thật rồi viết tay).
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

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO_DIR = os.path.join(PROJECT_ROOT, "scripts", "research", "musetalk_repo")
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "scripts", "research", "lipsync_poc_output")


def log(msg: str) -> None:
    print(f"[lipsync-poc] {msg}", flush=True)


def _require_repo() -> None:
    if not os.path.isdir(os.path.join(REPO_DIR, "musetalk")):
        raise SystemExit(
            f"!! không thấy {REPO_DIR}/musetalk — chạy "
            "`py scripts/setup_lipsync_poc.py` trước.")
    if not sys.executable.replace("\\", "/").endswith(
            (".venv-lipsync/bin/python", ".venv-lipsync/Scripts/python.exe")):
        log("CẢNH BÁO: có vẻ đang chạy KHÔNG PHẢI bằng python của "
            ".venv-lipsync — script này cần torch/mmpose/... đã cài ở đó. "
            f"Đang chạy bằng: {sys.executable}")


def _resolve_ffmpeg() -> str:
    # KHÔNG import autodub ở đây — "import autodub.<bất kỳ gì>" luôn chạy
    # autodub/__init__.py trước, kéo theo toàn bộ dependency nặng của
    # VoxDub (dotenv/pydub/faster-whisper/...) không có sẵn trong
    # .venv-lipsync (bug thật đã gặp ở setup_lipsync_poc.py, xem
    # docs/TEST_LOG.md mục V32a). PROJECT_ROOT ở đây đã tương đương
    # app_root() khi không đóng gói PyInstaller (luôn đúng cho script
    # nghiên cứu này).
    local_ffmpeg = os.path.join(PROJECT_ROOT, "bin", "ffmpeg.exe")
    return shutil.which("ffmpeg") or (
        local_ffmpeg if os.path.isfile(local_ffmpeg) else "ffmpeg")


class _VramPoller:
    """Poll `nvidia-smi` mỗi 0.5s trong lúc 1 tiến trình chạy — MuseTalk
    không tự báo VRAM peak, phải đo từ bên ngoài."""

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


def step_benchmark_inference(video: str, audio: str, result_dir: str,
                             ffmpeg_bin: str) -> dict:
    """Scope B — chạy `scripts/inference.py` THẬT của MuseTalk, đo thời gian
    + VRAM peak. KHÔNG viết lại logic inference — chỉ gọi qua subprocess
    đúng như README chỉ dẫn."""
    # Bug thật gặp khi live-verify: tự ghép chuỗi YAML bằng f-string, đường
    # dẫn tuyệt đối Windows có "\" bị hiểu nhầm thành ký tự escape trong
    # chuỗi có ngoặc kép ("\s" không phải escape hợp lệ) — YAML parser của
    # MuseTalk (OmegaConf) báo lỗi ScannerError, benchmark chết ngay từ đầu.
    # Dùng thư viện yaml chuẩn (đã có sẵn trong .venv-lipsync, kéo theo bởi
    # omegaconf — dependency của chính MuseTalk) để escape ĐÚNG mọi trường
    # hợp, không tự ghép chuỗi nữa.
    import yaml  # noqa: PLC0415

    config_path = os.path.join(result_dir, "task.yaml")
    task_name = os.path.splitext(os.path.basename(video))[0]
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"task_0": {"video_path": video, "audio_path": audio}},
                       f, allow_unicode=True)

    unet_path = os.path.join(REPO_DIR, "models", "musetalkV15", "unet.pth")
    unet_cfg = os.path.join(REPO_DIR, "models", "musetalkV15", "musetalk.json")
    cmd = [
        sys.executable, "-m", "scripts.inference",
        "--inference_config", config_path,
        "--result_dir", result_dir,
        "--unet_model_path", unet_path,
        "--unet_config", unet_cfg,
        "--version", "v15",
        "--ffmpeg_path", os.path.dirname(ffmpeg_bin) or ".",
    ]
    log(f"chạy MuseTalk inference thật: {' '.join(cmd)}")
    log("(tiến trình MuseTalk in trực tiếp bên dưới — tải model + xử lý "
        "268 frame có thể mất vài phút, không phải bị treo)")

    started = time.monotonic()
    output_lines: list[str] = []
    with _VramPoller() as vram:
        # stream trực tiếp ra console (không capture_output im lặng như
        # trước — người dùng không biết đang chạy hay bị treo) VÀ vẫn gom
        # lại để ghi report.json.
        proc = subprocess.Popen(cmd, cwd=REPO_DIR, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            print(line, end="", flush=True)
            output_lines.append(line)
        proc.wait()
    elapsed_s = time.monotonic() - started
    full_output = "".join(output_lines)

    ok = proc.returncode == 0
    if not ok:
        log(f"!! inference LỖI (mã {proc.returncode})")

    output_video = None
    if ok:
        candidates = glob.glob(os.path.join(result_dir, "v15", "*.mp4"))
        candidates = [c for c in candidates if not c.endswith("_concat.mp4")]
        output_video = candidates[0] if candidates else None

    return {
        "ok": ok, "task_name": task_name, "elapsed_seconds": round(elapsed_s, 1),
        "vram_peak_mb": vram.peak_mb, "output_video": output_video,
        "returncode": proc.returncode,
        "stderr_tail": full_output[-2000:] if not ok else "",
    }


def step_consent_check(video: str, result_dir: str, ffmpeg_bin: str) -> dict:
    """Scope C — tách frame bằng đúng lệnh MuseTalk dùng nội bộ, gọi THẲNG
    `get_landmark_and_bbox()` thật của MuseTalk để đếm % frame không phát
    hiện được khuôn mặt nào.

    Bug thật gặp khi live-verify: `musetalk/utils/preprocessing.py` mở
    config DWPose bằng đường dẫn TƯƠNG ĐỐI (`./musetalk/utils/dwpose/...`)
    ngay ở CẤP MODULE (chạy lúc import, không phải lúc gọi hàm) — đường dẫn
    đó chỉ đúng khi thư mục làm việc hiện tại LÀ `REPO_DIR`. Tiến trình chạy
    `lipsync_poc.py` có cwd là chỗ người dùng gõ lệnh (vd D:\\voidmix), không
    phải REPO_DIR — phải đổi cwd tạm thời trước khi import, trả lại ngay sau
    (không ảnh hưởng các bước khác vì mọi tham số đường dẫn khác trong file
    này đều đã là ĐƯỜNG DẪN TUYỆT ĐỐI, xem `main()`).
    """
    sys.path.insert(0, REPO_DIR)
    original_cwd = os.getcwd()
    try:
        os.chdir(REPO_DIR)
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

    log(f"chạy face-detection thật của MuseTalk trên {len(img_list)} frame ...")
    coords_list, _frames = get_landmark_and_bbox(img_list)
    no_face = sum(1 for c in coords_list if tuple(c) == coord_placeholder)
    return {
        "ok": True, "total_frames": len(img_list), "no_face_frames": no_face,
        "no_face_ratio": round(no_face / len(img_list), 4) if img_list else None,
    }


def step_watermark(input_video: str, result_dir: str, ffmpeg_bin: str) -> dict:
    """Scope D — 2 phương án watermark, đo chi phí thời gian xử lý thêm mỗi
    phương án. Chỉ 1 trong 2 sẽ được chọn thật khi build V32b — PoC này chỉ
    chứng minh khả thi kỹ thuật, không chốt phương án cuối."""
    out = {}
    if not input_video or not os.path.isfile(input_video):
        return {"ok": False, "reason": "không có video output từ Scope B để thử watermark"}

    visible_out = os.path.join(result_dir, "watermarked_visible.mp4")
    started = time.monotonic()
    proc = subprocess.run([
        ffmpeg_bin, "-v", "error", "-y", "-i", input_video,
        "-vf", "drawtext=text='VoxDub AI':fontcolor=white@0.7:fontsize=18:"
               "x=w-tw-10:y=h-th-10:box=1:boxcolor=black@0.4",
        "-codec:a", "copy", visible_out,
    ], capture_output=True, text=True)
    out["visible_overlay"] = {
        "ok": proc.returncode == 0, "elapsed_seconds": round(time.monotonic() - started, 2),
        "output": visible_out if proc.returncode == 0 else None,
        "stderr_tail": proc.stderr[-500:] if proc.returncode != 0 else "",
    }

    metadata_out = os.path.join(result_dir, "watermarked_metadata.mp4")
    started = time.monotonic()
    proc = subprocess.run([
        ffmpeg_bin, "-v", "error", "-y", "-i", input_video,
        "-metadata", "comment=Đã xử lý bằng AI lip-sync — VoxDub Studio",
        "-codec", "copy", metadata_out,
    ], capture_output=True, text=True)
    out["metadata_only"] = {
        "ok": proc.returncode == 0, "elapsed_seconds": round(time.monotonic() - started, 2),
        "output": metadata_out if proc.returncode == 0 else None,
        "stderr_tail": proc.stderr[-500:] if proc.returncode != 0 else "",
    }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, help="Video gốc (mp4)")
    parser.add_argument("--audio", required=True,
                        help="Audio ĐÃ DỊCH (wav) — lấy từ 1 lượt pipeline "
                             "VoxDub thật, vd data/audio_vi_full.wav")
    parser.add_argument("--label", required=True,
                        help="Nhãn video mẫu, vd mat_thang/goc_nghieng/nhieu_nguoi")
    args = parser.parse_args()

    _require_repo()
    # Bug thật gặp khi live-verify: người dùng gõ đường dẫn TƯƠNG ĐỐI (vd
    # "scripts\\research\\...\\yongen.mp4", tính từ chỗ gõ lệnh) — nhưng
    # Scope B ghi đường dẫn này vào 1 file YAML rồi MuseTalk đọc lại với cwd
    # KHÁC (REPO_DIR), nên đường dẫn tương đối bị hiểu sai, MuseTalk báo lỗi
    # không thấy file (exit code 1). Ép về TUYỆT ĐỐI ngay từ đầu, dùng xuyên
    # suốt mọi bước — không còn phụ thuộc cwd của bất kỳ tiến trình con nào.
    args.video = os.path.abspath(args.video)
    args.audio = os.path.abspath(args.audio)
    if not os.path.isfile(args.video):
        raise SystemExit(f"!! không thấy video: {args.video}")
    if not os.path.isfile(args.audio):
        raise SystemExit(f"!! không thấy audio: {args.audio}")

    ffmpeg_bin = _resolve_ffmpeg()
    result_dir = os.path.join(OUTPUT_ROOT, args.label)
    os.makedirs(result_dir, exist_ok=True)

    log(f"=== PoC lip-sync — mẫu «{args.label}» ===")
    report = {"label": args.label, "video": args.video, "audio": args.audio}

    # Mỗi bước tách try/except riêng — 1 bước lỗi KHÔNG được làm mất kết quả
    # (hoặc chẩn đoán lỗi) của 2 bước còn lại. Bug thật đã gặp: Scope C lỗi
    # làm cả script dừng NGANG, mất luôn report.json (kể cả log lỗi thật của
    # Scope B) — người dùng phải chạy lại từ đầu chỉ để xem lại lỗi cũ.
    try:
        report["benchmark"] = step_benchmark_inference(
            args.video, args.audio, result_dir, ffmpeg_bin)
        if not report["benchmark"]["ok"]:
            log("!! benchmark lỗi — output đầy đủ đã in ở trên (live), cũng "
                "lưu lại trong report.json để gửi lại khi cần chẩn đoán.")
    except Exception as e:  # noqa: BLE001 — PoC: ghi lại lỗi, không để chết cả script
        log(f"!! Scope B (benchmark) lỗi ngoài dự kiến: {e}")
        report["benchmark"] = {"ok": False, "error": str(e)}

    try:
        report["consent_check"] = step_consent_check(args.video, result_dir, ffmpeg_bin)
    except Exception as e:  # noqa: BLE001
        log(f"!! Scope C (consent-check) lỗi ngoài dự kiến: {e}")
        report["consent_check"] = {"ok": False, "error": str(e)}

    try:
        report["watermark"] = step_watermark(
            report["benchmark"].get("output_video"), result_dir, ffmpeg_bin)
    except Exception as e:  # noqa: BLE001
        log(f"!! Scope D (watermark) lỗi ngoài dự kiến: {e}")
        report["watermark"] = {"ok": False, "error": str(e)}

    report_path = os.path.join(result_dir, "report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(f"XONG — report thật: {report_path}")
    log(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
