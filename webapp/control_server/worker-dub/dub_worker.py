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
    POLL_BACKOFF_MAX_S      mặc định 60 — trần nhịp chờ khi MẤT kết nối tới
                            control_server (xem C54)
    BAO_KET_THUC_SO_LAN     mặc định 6 — số lần thử báo kết quả cuối job
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
# C54 — worker và control_server chạy trên HAI project hosting tách nhau, nên
# mọi lệnh gọi đi vòng ra tên miền công cộng: mất DNS hoặc timeout là chuyện
# BÌNH THƯỜNG, không phải sự cố hiếm (31-08: mất phân giải tên ~1 tiếng, worker
# vẫn nện 3 giây/lần và xả log lặp kín cả cửa sổ). Ba con số dưới đây là cách
# chịu đựng chuyện đó mà không mất việc đã làm.
POLL_BACKOFF_MAX_S = float(os.environ.get("POLL_BACKOFF_MAX_S", "60"))
BAO_KET_THUC_SO_LAN = int(os.environ.get("BAO_KET_THUC_SO_LAN", "6"))
TRUYEN_FILE_SO_LAN = int(os.environ.get("TRUYEN_FILE_SO_LAN", "3"))

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


def _mot_dong(text: str, toi_da: int = 200) -> str:
    """Ép thân phản hồi về MỘT dòng ngắn.

    C57b, thấy trên prod: lúc control_server khởi động lại, worker nhận trang
    HTML 502 của proxy và in nguyên xi — một lần hỏng nở thành năm dòng log
    lẫn thẻ `<head>`, đẩy trôi những dòng đáng đọc. Log mà khó đọc thì cũng
    không ai đọc.
    """
    gon = " ".join((text or "").split())
    return gon[:toi_da] + ("…" if len(gon) > toi_da else "")


def _post_chi_tiet(path: str, payload: dict) -> tuple[dict | None, str | None]:
    """Gọi POST, trả `(kết quả, lời lỗi)`.

    Tách khỏi `_post` để phía gọi TỰ quyết định in lỗi thế nào: vòng poll gặp
    cùng một lỗi hàng nghìn lần thì phải gộp lại, còn lệnh gọi lẻ vẫn in ngay.
    """
    url = f"{CONTROL_SERVER_URL}{path}"
    try:
        resp = requests.post(url, json=payload, headers=_headers(),
                             timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException as e:
        return None, f"Lỗi gọi {path}: {e}"
    if resp.status_code >= 500:
        return None, f"{path} trả {resp.status_code}: {_mot_dong(resp.text)}"
    try:
        return resp.json(), None
    except ValueError:
        return None, (f"{path} trả nội dung không phải JSON: "
                      f"{_mot_dong(resp.text)}")


def _post(path: str, payload: dict) -> dict | None:
    ket_qua, loi = _post_chi_tiet(path, payload)
    if loi:
        print(f"[dub_worker] {loi}", flush=True)
    return ket_qua


def _nhip_cho(loi_lien_tiep: int) -> float:
    """Nhịp chờ trước lượt poll kế tiếp, theo số lần lỗi LIÊN TIẾP.

    0 lỗi → nhịp thường (3s). Mất kết nối thì giãn gấp đôi dần tới trần
    `POLL_BACKOFF_MAX_S`: một tiếng mất DNS nện 1200 lượt (mỗi lượt còn ôm
    timeout 15s) không giúp kết nối trở lại sớm hơn một giây nào.
    """
    if loi_lien_tiep <= 0:
        return POLL_INTERVAL_S
    return min(POLL_INTERVAL_S * (2 ** loi_lien_tiep), POLL_BACKOFF_MAX_S)


class _SoMatKetNoi:
    """Gộp log của chuỗi lỗi lặp — nhưng KHÔNG im lặng.

    In lần đầu ngay, rồi thưa dần (lần 2, 4, 8, 16… — cùng nhịp với backoff),
    kèm tổng số lần và mất bao lâu. Khi nối lại được thì NÓI RA, vì "im lặng
    trở lại bình thường" đọc log không phân biệt được với "vẫn đang chết".
    """

    def __init__(self, now=time.monotonic):
        self._now = now
        self.lien_tiep = 0
        self._moc = 0.0
        self._nguong = 1

    def ghi_loi(self, loi: str) -> str | None:
        self.lien_tiep += 1
        if self.lien_tiep == 1:
            self._moc = self._now()
            self._nguong = 1
        if self.lien_tiep < self._nguong:
            return None
        self._nguong = max(2, self.lien_tiep * 2)
        if self.lien_tiep == 1:
            return f"[dub_worker] {loi}"
        giay = round(self._now() - self._moc)
        return (f"[dub_worker] Vẫn mất kết nối tới control_server: "
                f"{self.lien_tiep} lần trong {giay}s. Lỗi mới nhất: {loi}")

    def ghi_thanh_cong(self) -> str | None:
        if self.lien_tiep == 0:
            return None
        giay = round(self._now() - self._moc)
        lan = self.lien_tiep
        self.lien_tiep = 0
        self._nguong = 1
        return (f"[dub_worker] Đã nối lại được control_server sau {lan} lần "
                f"hỏng / {giay}s.")


def claim_next_job() -> tuple[dict | None, str | None]:
    """Trả `(job hoặc None, lời lỗi hoặc None)`.

    Trước C54 hàm này trả None cho CẢ hai ca "không có việc" và "không gọi
    được máy chủ" — vòng lặp không phân biệt được nên không thể giãn nhịp khi
    mất kết nối. Nay "không có việc" là `(None, None)`, còn hỏng là
    `(None, "…")`.
    """
    result, loi = _post_chi_tiet("/internal/dub-jobs/claim", {"workerId": WORKER_ID})
    if loi is not None:
        return None, loi
    if not result:
        return None, None
    return result.get("job"), None


# Nhịp kiểm "job còn của mình không" trong lúc chờ tiến trình dub (V55).
CANCEL_POLL_S = 5.0


class _FinishedProc:
    """Gói kết quả Popen cho giống `subprocess.run` — phần code đọc
    stdout/stderr bên dưới giữ nguyên, không phải viết lại."""

    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _heartbeat_loop(job_id: str, stop: threading.Event,
                    lost: threading.Event | None = None) -> None:
    while not stop.wait(HEARTBEAT_INTERVAL_S):
        result = _post(f"/internal/dub-jobs/{job_id}/heartbeat", {"workerId": WORKER_ID})
        if result is not None and not result.get("ok"):
            print(f"[dub_worker] Job {job_id} không còn do worker này giữ "
                 "(khách đã huỷ, hoặc sweeper coi là chết) — dừng heartbeat.", flush=True)
            # V55: báo ra ngoài để bên xử lý GIẾT tiến trình dub luôn. Trước
            # đây chỉ dừng heartbeat rồi vẫn chạy tới hết: khách bấm Huỷ mà
            # máy chủ vẫn cày hết video, tốn CPU cho một kết quả chắc chắn bị
            # vứt đi.
            if lost is not None:
                lost.set()
            return


def _thu_lai(mo_ta: str, ham, so_lan: int, cho_dau_s: float = 5.0,
             dung_khi_tat_may: bool = True):
    """Chạy `ham()` tới `so_lan` lần, nghỉ giãn dần, trả kết quả đầu tiên dùng
    được (`None`/`False` là hỏng).

    `ham` trả `(giá_trị, thử_lại_được)`: máy chủ trả 4xx nghĩa là *nó* từ chối
    (job không còn của worker này chẳng hạn) — thử lại chỉ tốn thời gian, nên
    dừng ngay. Còn mất mạng/5xx thì đáng thử lại.
    """
    cho = cho_dau_s
    for lan in range(1, so_lan + 1):
        gia_tri, thu_lai_duoc = ham()
        if gia_tri:
            if lan > 1:
                print(f"[dub_worker] {mo_ta}: xong ở lần thử {lan}/{so_lan}.", flush=True)
            return gia_tri
        if not thu_lai_duoc or lan == so_lan:
            break
        if dung_khi_tat_may and _shutdown.is_set():
            print(f"[dub_worker] {mo_ta}: đang tắt máy — không thử lại nữa.", flush=True)
            break
        print(f"[dub_worker] {mo_ta}: hỏng lần {lan}/{so_lan}, thử lại sau {cho:.0f}s.",
              flush=True)
        if dung_khi_tat_may:
            _shutdown.wait(cho)
        else:
            time.sleep(cho)
        cho = min(cho * 2, 30.0)
    return None


def _tai_input_mot_lan(job_id: str, dest_path: str) -> tuple[bool, bool]:
    url = f"{CONTROL_SERVER_URL}/internal/dub-jobs/{job_id}/input"
    try:
        with requests.get(url, headers={"X-Worker-Token": WORKER_TOKEN},
                          params={"workerId": WORKER_ID},
                          stream=True, timeout=DOWNLOAD_TIMEOUT_S) as resp:
            if resp.status_code != 200:
                print(f"[dub_worker] Tải input job {job_id} lỗi {resp.status_code}: "
                      f"{resp.text[:200]}", flush=True)
                return False, resp.status_code >= 500
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
    except requests.RequestException as e:
        print(f"[dub_worker] Tải input job {job_id} lỗi: {e}", flush=True)
        return False, True
    return True, False


def download_input(job_id: str, dest_path: str) -> bool:
    """Kéo file input về đĩa CỦA WORKER qua HTTP.

    Bản V34a đọc thẳng `job["inputPath"]` vì worker và control_server dùng
    chung volume trong docker-compose. Khi 2 container chạy tách nhau (mỗi
    service 1 project trên nền tảng hosting) thì đường dẫn đó không tồn tại
    ở đây, nên luôn tải qua HTTP — chạy đúng ở CẢ hai kiểu triển khai.

    Ghi theo chunk, KHÔNG nạp cả file vào RAM (video tới 300 MB).

    C54: một cú chập mạng ở đây từng đủ để đánh hỏng cả job (khách mất tiền
    giữ chỗ cho một lượt chưa hề chạy) — nay thử lại có giới hạn.
    """
    return bool(_thu_lai(f"Tải input job {job_id}",
                         lambda: _tai_input_mot_lan(job_id, dest_path),
                         TRUYEN_FILE_SO_LAN))


def _day_ket_qua_mot_lan(job_id: str, video_path: str) -> tuple[str | None, bool]:
    url = f"{CONTROL_SERVER_URL}/internal/dub-jobs/{job_id}/output"
    try:
        with open(video_path, "rb") as f:
            resp = requests.post(
                url, headers={"X-Worker-Token": WORKER_TOKEN},
                params={"workerId": WORKER_ID},
                files={"file": ("dubbed_video.mp4", f, "video/mp4")},
                timeout=UPLOAD_TIMEOUT_S)
    except requests.RequestException as e:
        print(f"[dub_worker] Đẩy kết quả job {job_id} lỗi: {e}", flush=True)
        return None, True
    except OSError as e:
        # Không đọc được file trên đĩa của chính mình — thử lại cũng thế.
        print(f"[dub_worker] Đẩy kết quả job {job_id} lỗi: {e}", flush=True)
        return None, False
    if resp.status_code != 200:
        print(f"[dub_worker] Đẩy kết quả job {job_id} lỗi {resp.status_code}: "
              f"{resp.text[:200]}", flush=True)
        return None, resp.status_code >= 500
    try:
        return resp.json().get("outputPath"), False
    except ValueError:
        return None, False


def upload_output(job_id: str, video_path: str) -> str | None:
    """Đẩy video kết quả lên control_server, trả `outputPath` phía server
    (để gọi /complete) hoặc None nếu hỏng. Truyền file handle cho requests
    để nó stream, không đọc hết vào RAM.

    C54: đây là chỗ ĐẮT NHẤT để hỏng — video đã dub xong (có khi 20 phút CPU),
    hỏng ở bước đẩy là vứt sạch. Thử lại có giới hạn, mở lại file mỗi lần.
    """
    return _thu_lai(f"Đẩy kết quả job {job_id}",
                    lambda: _day_ket_qua_mot_lan(job_id, video_path),
                    TRUYEN_FILE_SO_LAN, cho_dau_s=10.0)


def run_dub(job: dict, lost: threading.Event | None = None) -> dict:
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
    # Popen chứ không subprocess.run: chỉ có cầm process mới giết được nó khi
    # khách huỷ giữa chừng (V55).
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, cwd="/app")
    while True:
        try:
            stdout, stderr = proc.communicate(timeout=CANCEL_POLL_S)
            break
        except subprocess.TimeoutExpired:
            if lost is not None and lost.is_set():
                print(f"[dub_worker] Job {job['jobId']} đã bị huỷ — giết tiến trình dub.",
                      flush=True)
                proc.kill()
                proc.communicate()
                return {"ok": False, "cancelled": True,
                        "error": "Job bị huỷ trong lúc đang xử lý."}
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    proc = _FinishedProc(proc.returncode, stdout, stderr)

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


def _bao_ket_thuc_mot_lan(path: str, payload: dict) -> tuple[bool, bool]:
    ket_qua, loi = _post_chi_tiet(path, payload)
    if loi is not None:
        print(f"[dub_worker] {loi}", flush=True)
        return False, True
    # Máy chủ trả lời rành mạch (kể cả "job không còn của bạn") — đó là câu
    # trả lời, không phải sự cố đường truyền: không thử lại.
    return ket_qua is not None, False


def _bao_ket_thuc(path: str, payload: dict, mo_ta: str) -> bool:
    """Báo trạng thái CUỐI của job (xong/hỏng) — thử lại có giới hạn.

    C54: trước đây đây là lệnh gọi bắn-rồi-quên. Mạng chập đúng lúc này thì
    một job đã dub xong (hàng chục phút CPU, khách đã bị giữ tiền) rơi vào
    im lặng, và log vẫn in "Job … xong" như thường — dòng log nói dối.

    Không dừng sớm khi worker đang tắt: đây là thứ đáng cố nhất trong cả
    vòng đời job.
    """
    return bool(_thu_lai(mo_ta, lambda: _bao_ket_thuc_mot_lan(path, payload),
                         BAO_KET_THUC_SO_LAN, cho_dau_s=3.0,
                         dung_khi_tat_may=False))


def process_job(job: dict) -> None:
    job_id = job["jobId"]
    print(f"[dub_worker] Nhận job {job_id} ({job['sourceLang']}->{job['targetLang']})", flush=True)

    stop_heartbeat = threading.Event()
    lost = threading.Event()
    hb_thread = threading.Thread(
        target=_heartbeat_loop, args=(job_id, stop_heartbeat, lost), daemon=True)
    hb_thread.start()

    try:
        result = run_dub(job, lost)
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

    if result.get("cancelled"):
        # Không gọi /fail: job đã ở trạng thái `cancelled` phía máy chủ, báo
        # fail chỉ tạo tiếng ồn và có thể ghi đè một trạng thái ĐÚNG bằng một
        # trạng thái SAI ("hỏng" khác hẳn "khách đổi ý").
        print(f"[dub_worker] Job {job_id} dừng theo yêu cầu huỷ.", flush=True)
        return

    if result.get("ok"):
        da_bao = _bao_ket_thuc(f"/internal/dub-jobs/{job_id}/complete", {
            "workerId": WORKER_ID,
            "outputPath": result["server_output_path"],
            "metrics": result["metrics"],
        }, f"Báo XONG job {job_id}")
        if da_bao:
            print(f"[dub_worker] Job {job_id} xong "
                  f"({result['metrics']['processingMs']} ms).", flush=True)
        else:
            print(f"[dub_worker] MẤT BÁO CÁO: job {job_id} đã dub XONG và đã đẩy "
                  f"video lên, nhưng không báo được cho control_server. Máy chủ "
                  f"sẽ coi worker này chết và cho job hỏng — khách phải chạy lại "
                  f"dù việc đã làm xong.", flush=True)
    else:
        _bao_ket_thuc(f"/internal/dub-jobs/{job_id}/fail", {
            "workerId": WORKER_ID, "error": result.get("error", "Lỗi không rõ"),
        }, f"Báo HỎNG job {job_id}")
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
    dem = _SoMatKetNoi()
    while not _shutdown.is_set():
        job, loi = claim_next_job()
        if loi is not None:
            dong = dem.ghi_loi(loi)
            if dong:
                print(dong, flush=True)
            _shutdown.wait(_nhip_cho(dem.lien_tiep))
            continue
        dong = dem.ghi_thanh_cong()
        if dong:
            print(dong, flush=True)
        if job:
            process_job(job)
            continue
        _shutdown.wait(POLL_INTERVAL_S)


if __name__ == "__main__":
    main()
