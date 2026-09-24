"""Worker Python — poll job cloud rendering qua HTTP nội bộ (mini-spec V12,
xem docs/PLAN.md). Chạy trong container RIÊNG (control_server/worker/
Dockerfile) — tách khỏi image control_server (Node) theo guardrail 1: đổi gì
bên Python (torch/demucs) không kéo theo build lại/redeploy control_server.

KHÔNG import autodub (venv khác, container khác) — độc lập hoàn toàn, đúng
quy ước của demucs_worker.py mà nó gọi qua subprocess. KHÔNG chạm Mongo trực
tiếp — mọi thao tác qua `/internal/jobs/*` (worker-auth.middleware.js phía
Node), Node vẫn là chủ sở hữu duy nhất của DB.

Vòng lặp: claim job queued cũ nhất -> spawn demucs_worker.py (subprocess,
CLI contract y hệt trước đây gọi từ Node ở mini-spec V9 — KHÔNG viết lại
logic tách nhạc, đúng guardrail gốc) -> báo done/failed. Heartbeat chạy ở
luồng riêng suốt lúc subprocess chạy, để job dài không bị sweeper coi là
worker chết (guardrail 5 của V12).

Biến môi trường:
    CONTROL_SERVER_URL     mặc định http://control_server:3001 (tên service
                            trong docker-compose.yml)
    WORKER_INTERNAL_TOKEN  bắt buộc — phải khớp .env của control_server
    WORKER_ID              mặc định hostname:pid
    DEMUCS_WORKER_SCRIPT   mặc định /app/autodub_media/demucs_worker.py
                            (đường copy trong Dockerfile)
    DEMUCS_PYTHON          mặc định chính interpreter đang chạy worker này
    POLL_INTERVAL_S        mặc định 3
    HEARTBEAT_INTERVAL_S   mặc định 30 (phải nhỏ hơn nhiều
                            cloud.render.heartbeat.stale.minutes ở server,
                            mặc định 5 phút — nhiều nhịp bỏ lỡ mới bị coi
                            là chết, không phải 1 nhịp chậm)
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time

import requests

CONTROL_SERVER_URL = os.environ.get("CONTROL_SERVER_URL", "http://control_server:3001").rstrip("/")
WORKER_TOKEN = os.environ.get("WORKER_INTERNAL_TOKEN", "")
WORKER_ID = os.environ.get("WORKER_ID") or f"{os.uname().nodename}:{os.getpid()}"
DEMUCS_WORKER_SCRIPT = os.environ.get(
    "DEMUCS_WORKER_SCRIPT", "/app/autodub_media/demucs_worker.py")
DEMUCS_PYTHON = os.environ.get("DEMUCS_PYTHON", sys.executable)
POLL_INTERVAL_S = float(os.environ.get("POLL_INTERVAL_S", "3"))
HEARTBEAT_INTERVAL_S = float(os.environ.get("HEARTBEAT_INTERVAL_S", "30"))
REQUEST_TIMEOUT_S = 15

_shutdown = threading.Event()


def _headers() -> dict:
    return {"X-Worker-Token": WORKER_TOKEN, "Content-Type": "application/json"}


def _post(path: str, payload: dict) -> dict | None:
    url = f"{CONTROL_SERVER_URL}{path}"
    try:
        resp = requests.post(url, json=payload, headers=_headers(),
                             timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException as e:
        print(f"[render_worker] Lỗi gọi {path}: {e}", flush=True)
        return None
    if resp.status_code >= 500:
        print(f"[render_worker] {path} trả {resp.status_code}: {resp.text[:300]}", flush=True)
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def claim_next_job() -> dict | None:
    result = _post("/internal/jobs/claim", {"workerId": WORKER_ID})
    if not result:
        return None
    return result.get("job")


def _heartbeat_loop(job_id: str, stop: threading.Event) -> None:
    while not stop.wait(HEARTBEAT_INTERVAL_S):
        result = _post(f"/internal/jobs/{job_id}/heartbeat", {"workerId": WORKER_ID})
        if result is not None and not result.get("ok"):
            print(f"[render_worker] Job {job_id} không còn do worker này giữ "
                 "(sweeper đã coi là chết) — dừng heartbeat.", flush=True)
            return


def run_demucs(input_path: str, vocals_path: str, no_vocals_path: str) -> dict:
    """Spawn demucs_worker.py — CLI/JSON-stdout contract y hệt V9, KHÔNG đổi."""
    proc = subprocess.run(
        [DEMUCS_PYTHON, DEMUCS_WORKER_SCRIPT,
         "--input", input_path, "--vocals", vocals_path, "--no-vocals", no_vocals_path],
        capture_output=True, text=True,
    )
    last_line = (proc.stdout or "").strip().split("\n")[-1] if proc.stdout else ""
    try:
        parsed = json.loads(last_line) if last_line else None
    except json.JSONDecodeError:
        parsed = None
    if parsed and parsed.get("ok"):
        return {"ok": True}
    error = (parsed and parsed.get("error")) or (proc.stderr or "")[-500:] \
        or f"exit code {proc.returncode}"
    return {"ok": False, "error": error}


def process_job(job: dict) -> None:
    job_id = job["jobId"]
    print(f"[render_worker] Nhận job {job_id} (stage={job['stage']})", flush=True)

    stop_heartbeat = threading.Event()
    hb_thread = threading.Thread(
        target=_heartbeat_loop, args=(job_id, stop_heartbeat), daemon=True)
    hb_thread.start()

    try:
        result = run_demucs(job["inputPath"], job["vocalsPath"], job["noVocalsPath"])
    except Exception as e:  # noqa: BLE001 — job lỗi nào cũng phải báo, không được rơi im lặng
        result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        stop_heartbeat.set()
        hb_thread.join(timeout=5)

    if result.get("ok"):
        _post(f"/internal/jobs/{job_id}/complete", {
            "workerId": WORKER_ID,
            "resultPaths": {"vocals": job["vocalsPath"], "no_vocals": job["noVocalsPath"]},
        })
        print(f"[render_worker] Job {job_id} xong.", flush=True)
    else:
        _post(f"/internal/jobs/{job_id}/fail", {
            "workerId": WORKER_ID, "error": result.get("error", "Lỗi không rõ"),
        })
        print(f"[render_worker] Job {job_id} lỗi: {result.get('error')}", flush=True)


def _handle_signal(signum, _frame) -> None:
    print(f"[render_worker] Nhận signal {signum} — dừng sau job hiện tại...", flush=True)
    _shutdown.set()


def main() -> None:
    if not WORKER_TOKEN:
        print("[render_worker] Thiếu WORKER_INTERNAL_TOKEN — dừng.", flush=True)
        sys.exit(1)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    print(f"[render_worker] worker_id={WORKER_ID} bắt đầu poll {CONTROL_SERVER_URL} "
         f"mỗi {POLL_INTERVAL_S}s", flush=True)
    while not _shutdown.is_set():
        job = claim_next_job()
        if job:
            process_job(job)
            continue
        _shutdown.wait(POLL_INTERVAL_S)


if __name__ == "__main__":
    main()
