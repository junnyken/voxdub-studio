"""Worker Python — poll job lồng tiếng đầy đủ qua HTTP nội bộ (mini-spec
V34a, xem docs/PLAN.md). Chạy trong container RIÊNG (control_server/
worker-dub/Dockerfile) — TÁCH HẲN khỏi `control_server/worker/`
(render_worker.py, chỉ Demucs) theo Constraint 2 của V34a.

KHÔNG chạm Mongo trực tiếp — mọi thao tác qua `/internal/dub-jobs/*`
(worker-auth.middleware.js phía Node, cùng token WORKER_INTERNAL_TOKEN của
V12 — tái dùng nguyên, không cần token riêng). Cấu trúc vòng lặp/heartbeat
COPY Y HỆT `render_worker.py` (đã chứng minh đúng từ V12) — chỉ đổi việc
"chạy gì" (spawn `voxdub dub` thay vì `demucs_worker.py`) và cách đọc kết
quả (tìm `dubbed_video.mp4` trong `work_dir` thay vì 2 stem cố định).

Biến môi trường:
    CONTROL_SERVER_URL     mặc định http://control_server:3001
    WORKER_INTERNAL_TOKEN  bắt buộc — phải khớp .env của control_server
    WORKER_ID              mặc định hostname:pid
    VOXDUB_PYTHON          mặc định chính interpreter đang chạy worker này
                            (main venv — .venv-whisper/.venv-vieneu/.venv-mt
                            là venv CON mà autodub.cli tự gọi qua subprocess,
                            xem autodub/config.py)
    POLL_INTERVAL_S        mặc định 3
    HEARTBEAT_INTERVAL_S   mặc định 30 (job dub CHẠY LÂU hơn Demucs nhiều —
                            server cho ngưỡng "worker chết" rộng hơn hẳn,
                            xem cloud.dub.heartbeat.stale.minutes)
    DUB_WORK_DIR            mặc định /app/work — nơi autodub.cli ghi
                            work_dir trung gian (khác input/output path
                            server quản lý)
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

CONTROL_SERVER_URL = os.environ.get("CONTROL_SERVER_URL", "http://control_server:3001").rstrip("/")
WORKER_TOKEN = os.environ.get("WORKER_INTERNAL_TOKEN", "")
WORKER_ID = os.environ.get("WORKER_ID") or f"{os.uname().nodename}:{os.getpid()}"
VOXDUB_PYTHON = os.environ.get("VOXDUB_PYTHON", sys.executable)
POLL_INTERVAL_S = float(os.environ.get("POLL_INTERVAL_S", "3"))
HEARTBEAT_INTERVAL_S = float(os.environ.get("HEARTBEAT_INTERVAL_S", "30"))
DUB_WORK_DIR = os.environ.get("DUB_WORK_DIR", "/app/work")
REQUEST_TIMEOUT_S = 15
# Truyền file cỡ trăm MB — hạn mức của các lệnh gọi JSON ngắn (15s) sẽ cắt
# ngang giữa chừng. Đây là timeout cho tới lúc BẮT ĐẦU có dữ liệu/kết thúc
# request, không phải giới hạn tổng thời gian tải theo chunk.
DOWNLOAD_TIMEOUT_S = 300
UPLOAD_TIMEOUT_S = 600
# Worker này không tự phục vụ HTTP nào cho nghiệp vụ (chỉ poll ra ngoài) —
# port này CHỈ để nền tảng hosting (Vibe Host) health-check thấy container
# có lắng nghe, không phản ánh trạng thái job/queue thật.
HEALTH_PORT = int(os.environ.get("PORT", "3000"))

_shutdown = threading.Event()


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 — tên bắt buộc bởi BaseHTTPRequestHandler
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args) -> None:  # im lặng — không spam log poll loop
        pass


def _start_health_server() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", HEALTH_PORT), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[dub_worker] health server lắng nghe 0.0.0.0:{HEALTH_PORT}", flush=True)


def _headers() -> dict:
    return {"X-Worker-Token": WORKER_TOKEN, "Content-Type": "application/json"}


def _post(path: str, payload: dict) -> dict | None:
    url = f"{CONTROL_SERVER_URL}{path}"
    try:
        resp = requests.post(url, json=payload, headers=_headers(),
                             timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException as e:
        print(f"[dub_worker] Lỗi gọi {path}: {e}", flush=True)
        return None
    if resp.status_code >= 500:
        print(f"[dub_worker] {path} trả {resp.status_code}: {resp.text[:300]}", flush=True)
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def claim_next_job() -> dict | None:
    result = _post("/internal/dub-jobs/claim", {"workerId": WORKER_ID})
    if not result:
        return None
    return result.get("job")


def _heartbeat_loop(job_id: str, stop: threading.Event) -> None:
    while not stop.wait(HEARTBEAT_INTERVAL_S):
        result = _post(f"/internal/dub-jobs/{job_id}/heartbeat", {"workerId": WORKER_ID})
        if result is not None and not result.get("ok"):
            print(f"[dub_worker] Job {job_id} không còn do worker này giữ "
                 "(sweeper đã coi là chết) — dừng heartbeat.", flush=True)
            return


def download_input(job_id: str, dest_path: str) -> bool:
    """Kéo file input về đĩa CỦA WORKER qua HTTP.

    Bản V34a đọc thẳng `job["inputPath"]` vì worker và control_server dùng
    chung volume trong docker-compose. Khi 2 container chạy tách nhau (mỗi
    service 1 project trên nền tảng hosting) thì đường dẫn đó không tồn tại
    ở đây, nên luôn tải qua HTTP — chạy đúng ở CẢ hai kiểu triển khai.

    Ghi theo chunk, KHÔNG nạp cả file vào RAM (video tới 300 MB).
    """
    url = f"{CONTROL_SERVER_URL}/internal/dub-jobs/{job_id}/input"
    try:
        with requests.get(url, headers={"X-Worker-Token": WORKER_TOKEN},
                          params={"workerId": WORKER_ID},
                          stream=True, timeout=DOWNLOAD_TIMEOUT_S) as resp:
            if resp.status_code != 200:
                print(f"[dub_worker] Tải input job {job_id} lỗi {resp.status_code}: "
                      f"{resp.text[:200]}", flush=True)
                return False
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
    except requests.RequestException as e:
        print(f"[dub_worker] Tải input job {job_id} lỗi: {e}", flush=True)
        return False
    return True


def upload_output(job_id: str, video_path: str) -> str | None:
    """Đẩy video kết quả lên control_server, trả `outputPath` phía server
    (để gọi /complete) hoặc None nếu hỏng. Truyền file handle cho requests
    để nó stream, không đọc hết vào RAM.
    """
    url = f"{CONTROL_SERVER_URL}/internal/dub-jobs/{job_id}/output"
    try:
        with open(video_path, "rb") as f:
            resp = requests.post(
                url, headers={"X-Worker-Token": WORKER_TOKEN},
                params={"workerId": WORKER_ID},
                files={"file": ("dubbed_video.mp4", f, "video/mp4")},
                timeout=UPLOAD_TIMEOUT_S)
    except (requests.RequestException, OSError) as e:
        print(f"[dub_worker] Đẩy kết quả job {job_id} lỗi: {e}", flush=True)
        return None
    if resp.status_code != 200:
        print(f"[dub_worker] Đẩy kết quả job {job_id} lỗi {resp.status_code}: "
              f"{resp.text[:200]}", flush=True)
        return None
    try:
        return resp.json().get("outputPath")
    except ValueError:
        return None


def run_dub(job: dict) -> dict:
    """Spawn `python3 -m autodub.cli dub` — engine headless V22, KHÔNG viết
    lại pipeline riêng (Design Choice của V34a). Trả về
    {"ok": True, "video_path": ..., "metrics": {...}} hoặc {"ok": False, "error": ...}.

    `bg-mode` (mini-spec V34b) là tham số THẬT từ job (`job["bgMode"]`,
    mặc định "none" nếu job cũ/thiếu field — giữ đúng hành vi V34a) — đã
    live-verify thật cả 2 giá trị (xem docs/TEST_LOG.md mục V34b: video có
    nhạc nền qua `--bg-mode demucs`, CPU-only, không cần GPU).
    """
    job_dir = os.path.join(DUB_WORK_DIR, str(job["jobId"]))
    os.makedirs(job_dir, exist_ok=True)

    local_input = os.path.join(job_dir, "input.mp4")
    if not download_input(str(job["jobId"]), local_input):
        return {"ok": False, "error": "Không tải được file input từ control_server."}

    input_size = os.path.getsize(local_input) if os.path.exists(local_input) else 0
    if not input_size:
        return {"ok": False, "error": "File input tải về rỗng."}
    bg_mode = job.get("bgMode") or "none"

    cmd = [
        VOXDUB_PYTHON, "-m", "autodub.cli", "dub",
        "--file", local_input,
        "--source-lang", job["sourceLang"],
        "--target", job["targetLang"],
        "--bg-mode", bg_mode,
        "--output-dir", job_dir,
        "--json",
    ]
    if job.get("voice"):
        cmd += ["--voice", job["voice"]]

    t0 = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd="/app")
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    last_line = (proc.stdout or "").strip().split("\n")[-1] if proc.stdout else ""
    try:
        parsed = json.loads(last_line) if last_line else None
    except json.JSONDecodeError:
        parsed = None

    if not parsed or parsed.get("status") != "completed":
        error = (parsed and json.dumps(parsed, ensure_ascii=False)) \
            or (proc.stderr or "")[-800:] or f"exit code {proc.returncode}"
        return {"ok": False, "error": error}

    video_path = os.path.join(parsed["work_dir"], "dubbed_video.mp4")
    if not os.path.isfile(video_path):
        return {"ok": False, "error": f"pipeline báo completed nhưng không thấy {video_path}"}

    output_size = os.path.getsize(video_path)
    # Thời lượng video gốc ĐO THẬT bởi pipeline (report.total_original_duration,
    # từ ASR) — dùng để tính phí (mini-spec V34b Scope A), KHÔNG suy từ kích
    # thước file hay giá trị client tự khai lúc submit.
    duration_s = float(parsed.get("report", {}).get("total_original_duration") or 0.0)
    return {
        "ok": True,
        "video_path": video_path,
        "metrics": {
            "inputBytes": input_size, "outputBytes": output_size,
            "processingMs": elapsed_ms, "durationS": duration_s,
        },
    }


def process_job(job: dict) -> None:
    job_id = job["jobId"]
    print(f"[dub_worker] Nhận job {job_id} ({job['sourceLang']}->{job['targetLang']})", flush=True)

    stop_heartbeat = threading.Event()
    hb_thread = threading.Thread(
        target=_heartbeat_loop, args=(job_id, stop_heartbeat), daemon=True)
    hb_thread.start()

    try:
        result = run_dub(job)
        if result.get("ok"):
            # Đẩy kết quả TRONG KHI heartbeat còn chạy: file cỡ trăm MB nên
            # upload mất vài phút, tắt heartbeat trước sẽ để sweeper
            # (sweepStaleRunning) coi worker đã chết và fail job ngay giữa
            # lúc đang đẩy. `video_path` nằm trong work_dir trung gian của
            # autodub.cli, còn nơi lưu chính thức do server tự quyết và trả
            # về (jobPaths() của dub-job.service.js) — worker không tự đoán.
            server_output = upload_output(str(job_id), result["video_path"])
            if server_output:
                result["server_output_path"] = server_output
            else:
                result = {"ok": False,
                          "error": "Không đẩy được video kết quả lên control_server."}
    except Exception as e:  # noqa: BLE001 — job lỗi nào cũng phải báo, không được rơi im lặng
        result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        stop_heartbeat.set()
        hb_thread.join(timeout=5)

    if result.get("ok"):
        _post(f"/internal/dub-jobs/{job_id}/complete", {
            "workerId": WORKER_ID,
            "outputPath": result["server_output_path"],
            "metrics": result["metrics"],
        })
        print(f"[dub_worker] Job {job_id} xong ({result['metrics']['processingMs']} ms).", flush=True)
    else:
        _post(f"/internal/dub-jobs/{job_id}/fail", {
            "workerId": WORKER_ID, "error": result.get("error", "Lỗi không rõ"),
        })
        print(f"[dub_worker] Job {job_id} lỗi: {result.get('error')}", flush=True)


def _handle_signal(signum, _frame) -> None:
    print(f"[dub_worker] Nhận signal {signum} — dừng sau job hiện tại...", flush=True)
    _shutdown.set()


def main() -> None:
    if not WORKER_TOKEN:
        print("[dub_worker] Thiếu WORKER_INTERNAL_TOKEN — dừng.", flush=True)
        sys.exit(1)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    os.makedirs(DUB_WORK_DIR, exist_ok=True)
    _start_health_server()

    print(f"[dub_worker] worker_id={WORKER_ID} bắt đầu poll {CONTROL_SERVER_URL} "
         f"mỗi {POLL_INTERVAL_S}s", flush=True)
    while not _shutdown.is_set():
        job = claim_next_job()
        if job:
            process_job(job)
            continue
        _shutdown.wait(POLL_INTERVAL_S)


if __name__ == "__main__":
    main()
