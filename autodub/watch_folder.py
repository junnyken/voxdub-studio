"""Chế độ theo dõi thư mục (watch-folder) — mini-spec V25 (docs/PLAN.md,
Phase F). Phụ thuộc V22 (CLI — điểm vào ``voxdub watch``) và V24 (retry/
watchdog/failures.jsonl — 1 tiến trình chạy dài hạn CÀNG cần watchdog cho
từng lượt dub bên trong, không thì 1 video kẹt treo cả hàng đợi phía sau).

Thiết kế polling đơn giản (KHÔNG thêm dependency ``watchdog``/`inotify`) —
đúng nguyên tắc dự án ưu tiên ít phụ thuộc, xem Design Choice trong mini-
spec. Mọi phần XỬ LÝ (phát hiện file ổn định, dedup, chạy 1 lượt) tách
thành hàm THUẦN để test được mà không cần chạy vòng lặp polling thật —
``watch_forever()`` là lớp vỏ mỏng DUY NHẤT có ``while True``/``sleep``.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from typing import Callable

from autodub.batch_retry import is_transient_error
from autodub.failures_log import append_failure
from autodub.pipeline import DubPipeline, DubRequest
from autodub.utils import save_json_atomic, setup_logging

logger = setup_logging("autodub.watch_folder")

#: File có đuôi này CHẮC CHẮN chưa ghi xong (quy ước trình duyệt/trình tải
#: phổ biến) — bỏ qua ngay, không cần chờ ổn định mới loại (Constraint 1).
_PROVISIONAL_SUFFIXES = (".part", ".crdownload", ".tmp", ".download")

STATE_FILENAME = "_watch_state.json"

#: Mini-spec khuyến nghị đặt STATE_FILENAME ở output_dir (khác input_dir) —
#: nhưng nếu người dùng lỡ trỏ 2 thư mục trùng nhau, các tên file bookkeeping
#: này KHÔNG BAO GIỜ được coi là input hợp lệ (tránh tự "dub" chính file
#: trạng thái của mình). Liệt kê thêm `batch_state.json` phòng trường hợp
#: cùng thư mục cũng được dùng cho batch (V2/V24).
_RESERVED_FILENAMES = frozenset({STATE_FILENAME, "failures.jsonl", "batch_state.json"})


def file_key(path: str) -> str:
    """Định danh 1 file theo NỘI DUNG tại thời điểm phát hiện (path + mtime
    + size) — file trùng TÊN nhưng khác nội dung (ghi đè) vẫn được coi là
    file MỚI, không bị dedup nhầm theo Constraint 2 của mini-spec."""
    st = os.stat(path)
    return f"{path}|{int(st.st_mtime)}|{st.st_size}"


class StabilityTracker:
    """Theo dõi kích thước file qua nhiều lượt poll — "ổn định" khi kích
    thước không đổi liên tục trong ``stable_seconds`` giây (Constraint 1:
    không đụng file đang được ghi/tải dở).

    ``now_fn`` bơm được từ ngoài (mặc định ``time.monotonic``) — test
    không cần `sleep()` thật để mô phỏng thời gian trôi qua.
    """

    def __init__(self, stable_seconds: float, now_fn: Callable[[], float] = time.monotonic):
        self._stable_seconds = stable_seconds
        self._now_fn = now_fn
        self._seen: dict[str, tuple[int, float]] = {}

    def check(self, path: str) -> bool:
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        now = self._now_fn()
        prev = self._seen.get(path)
        if prev is None or prev[0] != size:
            self._seen[path] = (size, now)
            return False
        return (now - prev[1]) >= self._stable_seconds

    def forget(self, path: str) -> None:
        self._seen.pop(path, None)


class WatchState:
    """Trạng thái BỀN (đĩa) của thư mục theo dõi — sống sót qua tắt/bật lại
    tiến trình watch (Constraint 2), tách hẳn khỏi ``batch_state.json``
    (khoá theo URL, dùng cho danh sách CỐ ĐỊNH — đây khoá theo path+mtime+
    size, dùng cho luồng LIÊN TỤC, xem Design Choice của mini-spec).
    """

    def __init__(self, path: str):
        self.path = path
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def get(self, key: str) -> dict | None:
        return self._data.get(key)

    def is_done(self, key: str) -> bool:
        entry = self._data.get(key)
        return entry is not None and entry.get("status") in ("success", "failed")

    def record(self, key: str, entry: dict) -> None:
        self._data[key] = entry
        save_json_atomic(self._data, self.path)


def _is_provisional(filename: str) -> bool:
    if filename.startswith("."):
        return True
    if filename in _RESERVED_FILENAMES:
        return True
    return filename.lower().endswith(_PROVISIONAL_SUFFIXES)


def discover_ready_files(input_dir: str, tracker: StabilityTracker,
                         state: WatchState) -> list[str]:
    """File trong ``input_dir`` ĐÃ ổn định VÀ chưa xử lý xong lần nào —
    thứ tự theo tên (ổn định giữa các lượt poll, dễ theo dõi log)."""
    ready: list[str] = []
    try:
        names = sorted(os.listdir(input_dir))
    except OSError:
        return ready
    for name in names:
        if _is_provisional(name):
            continue
        path = os.path.join(input_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            key = file_key(path)
        except OSError:
            continue  # file biến mất giữa listdir() và stat() — bỏ qua lượt này
        if state.is_done(key):
            continue
        if tracker.check(path):
            ready.append(path)
    return ready


def process_file(
    path: str, pipeline: DubPipeline, req_template: DubRequest, state: WatchState,
    failures_log_path: str | None = None,
    now_fn: Callable[[], str] = lambda: "",
) -> dict:
    """Dub 1 file, ghi kết quả vào ``state``. Trả về entry vừa ghi.

    Đánh dấu "processing" TRƯỚC khi chạy — nếu lượt sau phát hiện lại đúng
    file này (còn "processing", tiến trình cũ có thể đã bị dừng đột ngột)
    thì resume đúng ``work_dir`` đã ghi thay vì dub lại từ đầu (Constraint 4
    — chỉ đúng với lỗi PIPELINE THẬT bắt được ở đây; ngắt bằng tín hiệu hệ
    thống giữa lúc pipeline đang chạy là giới hạn còn lại, xem TEST_LOG).
    """
    key = file_key(path)
    prior = state.get(key) or {}
    resume_dir = prior.get("work_dir") or None
    if resume_dir and not os.path.isdir(resume_dir):
        resume_dir = None
    state.record(key, {"status": "processing", "work_dir": resume_dir or ""})

    req = DubRequest(
        file_path=path,
        source_lang=req_template.source_lang,
        voice=req_template.voice,
        bg_mode=req_template.bg_mode,
        bg_duck_db=req_template.bg_duck_db,
        skip_video=req_template.skip_video,
        subtitle_mode=req_template.subtitle_mode,
        subtitle_style=req_template.subtitle_style,
        blur_regions=req_template.blur_regions,
        output_dir=req_template.output_dir,
        resume_dir=resume_dir,
        target=req_template.target,
    )
    try:
        result = pipeline.run(req)
        ok = result.status == "completed"
        entry = {
            "status": "success" if ok else "failed",
            "work_dir": result.work_dir,
            "error": None if ok else f"Pipeline dừng ở trạng thái {result.status}",
        }
    except Exception as e:  # noqa: BLE001 — lỗi thật của 1 file, không được giết cả vòng theo dõi
        work_dir = getattr(pipeline, "last_work_dir", "") or resume_dir or ""
        error_msg = str(e)[:200]
        entry = {"status": "failed", "work_dir": work_dir, "error": error_msg}
        if failures_log_path:
            append_failure({
                "timestamp": now_fn(), "video": path,
                "transient": is_transient_error(e), "error": error_msg,
            }, failures_log_path)

    state.record(key, entry)
    return entry


def run_watch_once(
    input_dir: str, pipeline: DubPipeline, req_template: DubRequest, state: WatchState,
    tracker: StabilityTracker, failures_log_path: str | None = None,
    now_fn: Callable[[], str] = lambda: "",
) -> list[dict]:
    """1 lượt quét: xử lý MỌI file mới+ổn định hiện có, tuần tự. Trả về
    danh sách ``{"path", **entry}`` — dùng trực tiếp trong test (không cần
    chạy ``watch_forever()``, đúng Test Plan của mini-spec)."""
    results = []
    for path in discover_ready_files(input_dir, tracker, state):
        entry = process_file(path, pipeline, req_template, state,
                             failures_log_path=failures_log_path, now_fn=now_fn)
        tracker.forget(path)
        results.append({"path": path, **entry})
        logger.info(f"[watch] {os.path.basename(path)}: {entry['status']}")
    return results


def watch_forever(
    input_dir: str, pipeline: DubPipeline, req_template: DubRequest, state_path: str,
    poll_interval_s: float = 10.0, stable_seconds: float = 5.0,
    failures_log_path: str | None = None, stop_event: threading.Event | None = None,
) -> None:
    """Vòng lặp polling thật — lớp vỏ MỎNG DUY NHẤT có ``while``/`sleep`.

    Dừng khi ``stop_event`` được set (CLI gắn nó với SIGINT/Ctrl+C) —
    KHÔNG bắt ``KeyboardInterrupt`` bên trong 1 lượt ``pipeline.run()``
    đang chạy dở (xem giới hạn ở docstring :func:`process_file`).
    """
    state = WatchState(state_path)
    tracker = StabilityTracker(stable_seconds)
    logger.info(f"[watch] Theo dõi {input_dir} (mỗi {poll_interval_s:.0f}s)...")
    stop_event = stop_event or threading.Event()
    while not stop_event.is_set():
        run_watch_once(input_dir, pipeline, req_template, state, tracker,
                       failures_log_path=failures_log_path,
                       now_fn=lambda: datetime.now().isoformat(timespec="seconds"))
        stop_event.wait(poll_interval_s)
