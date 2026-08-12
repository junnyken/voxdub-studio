"""Mini-spec V25 (docs/PLAN.md, Phase F) — chế độ theo dõi thư mục.

KHÔNG chạy `watch_forever()` (vòng lặp polling thật) trong test suite —
đúng Test Plan của mini-spec: gọi trực tiếp các hàm thuần
(`discover_ready_files`/`process_file`/`run_watch_once`) với dữ liệu giả
lập, không cần vòng lặp polling/sleep thật.
"""
from __future__ import annotations

import json
import os
import threading
import time

import pytest

from autodub.pipeline import DubRequest
from autodub.watch_folder import (
    StabilityTracker, WatchState, discover_ready_files, file_key,
    process_file, run_watch_once, watch_forever,
)


# --------------------------------------------------------------------- #
# StabilityTracker — phát hiện file ổn định KHÔNG cần sleep() thật

def test_growing_file_never_reported_stable(tmp_path):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"a")
    clock = [0.0]
    tracker = StabilityTracker(stable_seconds=5.0, now_fn=lambda: clock[0])

    assert tracker.check(str(path)) is False  # lần đầu thấy -> chưa đủ dữ liệu
    clock[0] = 2.0
    path.write_bytes(b"ab")  # file LỚN THÊM (đang được ghi tiếp)
    assert tracker.check(str(path)) is False  # đổi kích thước -> reset mốc thời gian
    clock[0] = 3.0
    assert tracker.check(str(path)) is False  # mới 1s kể từ lần đổi cuối, < 5s


def test_unchanged_size_for_long_enough_is_stable(tmp_path):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"finished content")
    clock = [0.0]
    tracker = StabilityTracker(stable_seconds=5.0, now_fn=lambda: clock[0])

    assert tracker.check(str(path)) is False  # lần đầu
    clock[0] = 5.0
    assert tracker.check(str(path)) is True  # 5s trôi qua, kích thước không đổi


def test_missing_file_is_not_stable(tmp_path):
    tracker = StabilityTracker(stable_seconds=1.0)
    assert tracker.check(str(tmp_path / "khong_ton_tai.mp4")) is False


def test_forget_resets_tracking(tmp_path):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"x")
    clock = [0.0]
    tracker = StabilityTracker(stable_seconds=1.0, now_fn=lambda: clock[0])
    tracker.check(str(path))
    clock[0] = 1.0
    assert tracker.check(str(path)) is True
    tracker.forget(str(path))
    assert tracker.check(str(path)) is False  # phải "thấy lần đầu" lại từ đầu


# --------------------------------------------------------------------- #
# file_key — dedup theo path+mtime+size (Constraint 2)

def test_file_key_changes_when_content_overwritten(tmp_path):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"v1")
    key1 = file_key(str(path))
    time.sleep(0.01)
    os.utime(path, None)  # đổi mtime mà không đổi nội dung/size vẫn đủ đổi key
    path.write_bytes(b"v2!")  # đổi cả size cho chắc
    key2 = file_key(str(path))
    assert key1 != key2


def test_file_key_stable_for_unchanged_file(tmp_path):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"v1")
    assert file_key(str(path)) == file_key(str(path))


# --------------------------------------------------------------------- #
# WatchState — bền qua tắt/bật lại (Constraint 2)

def test_state_persists_across_restart(tmp_path):
    state_path = str(tmp_path / "_watch_state.json")
    state1 = WatchState(state_path)
    state1.record("key1", {"status": "success", "work_dir": "/tmp/wd"})

    state2 = WatchState(state_path)  # "khởi động lại"
    assert state2.is_done("key1") is True
    assert state2.get("key1")["work_dir"] == "/tmp/wd"


def test_missing_state_file_starts_empty(tmp_path):
    state = WatchState(str(tmp_path / "khong_co.json"))
    assert state.is_done("bat_ky") is False


def test_processing_status_not_counted_as_done():
    """"processing" (đang dở, chưa xong) khác "success"/"failed" — chưa
    được coi là ĐÃ xử lý, để process_file() còn resume được."""
    state = WatchState("/tmp/khong-dung-toi.json")
    state._data["k"] = {"status": "processing", "work_dir": ""}
    assert state.is_done("k") is False


# --------------------------------------------------------------------- #
# discover_ready_files

def test_discovers_new_stable_files_only(tmp_path):
    ready_file = tmp_path / "ready.mp4"
    ready_file.write_bytes(b"data")
    clock = [0.0]
    tracker = StabilityTracker(stable_seconds=1.0, now_fn=lambda: clock[0])
    state = WatchState(str(tmp_path / "_watch_state.json"))

    assert discover_ready_files(str(tmp_path), tracker, state) == []  # lần đầu -> chưa ổn định
    clock[0] = 1.0
    assert discover_ready_files(str(tmp_path), tracker, state) == [str(ready_file)]


def test_provisional_suffixes_never_discovered(tmp_path):
    (tmp_path / "downloading.mp4.part").write_bytes(b"x")
    (tmp_path / ".hidden.mp4").write_bytes(b"x")
    tracker = StabilityTracker(stable_seconds=0.0)
    state = WatchState(str(tmp_path / "_watch_state.json"))

    assert discover_ready_files(str(tmp_path), tracker, state) == []


def test_already_done_files_not_rediscovered(tmp_path):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"data")
    tracker = StabilityTracker(stable_seconds=0.0)
    state = WatchState(str(tmp_path / "_watch_state.json"))
    state.record(file_key(str(path)), {"status": "success", "work_dir": "/tmp/wd"})

    assert discover_ready_files(str(tmp_path), tracker, state) == []


def test_state_file_itself_never_discovered_even_when_colocated(tmp_path):
    """Nếu input_dir và output_dir trùng nhau (cấu hình lỡ tay), file
    bookkeeping (_watch_state.json/failures.jsonl/batch_state.json) KHÔNG
    BAO GIỜ được coi là input hợp lệ — tránh tool tự "dub" trạng thái của
    chính nó."""
    state_path = str(tmp_path / "_watch_state.json")
    state = WatchState(state_path)
    state.record("k", {"status": "success"})  # tạo file _watch_state.json thật
    (tmp_path / "failures.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "batch_state.json").write_text("{}", encoding="utf-8")
    tracker = StabilityTracker(stable_seconds=0.0)

    assert discover_ready_files(str(tmp_path), tracker, state) == []
    # cả sau lượt poll thứ 2 (đủ để "ổn định" nếu không bị loại tường minh)
    assert discover_ready_files(str(tmp_path), tracker, state) == []


def test_subdirectories_are_ignored(tmp_path):
    (tmp_path / "subdir").mkdir()
    tracker = StabilityTracker(stable_seconds=0.0)
    state = WatchState(str(tmp_path / "_watch_state.json"))
    assert discover_ready_files(str(tmp_path), tracker, state) == []


# --------------------------------------------------------------------- #
# process_file / run_watch_once — pipeline giả, không tải/ASR/TTS thật

class FakePipeline:
    def __init__(self, outcome="ok"):
        self.outcome = outcome
        self.seen: list[DubRequest] = []
        self.last_work_dir = ""

    def run(self, req):
        self.seen.append(req)
        self.last_work_dir = req.resume_dir or f"wd_{os.path.basename(req.file_path)}"
        # BaseException (không chỉ Exception) — cho phép test KeyboardInterrupt,
        # vốn KHÔNG kế thừa từ Exception.
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return type("R", (), {
            "status": "completed", "work_dir": self.last_work_dir,
            "report": {"session_id": "s1"},
        })()


def _req_template(output_dir):
    return DubRequest(voice="Phạm Tuyên", output_dir=str(output_dir))


def test_process_file_records_success(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"data")
    pipe = FakePipeline("ok")
    state = WatchState(str(tmp_path / "_watch_state.json"))

    entry = process_file(str(video), pipe, _req_template(tmp_path), state)

    assert entry["status"] == "success"
    assert state.is_done(file_key(str(video))) is True


def test_process_file_records_failure_without_crashing(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"data")
    pipe = FakePipeline(RuntimeError("lỗi thật"))
    state = WatchState(str(tmp_path / "_watch_state.json"))

    entry = process_file(str(video), pipe, _req_template(tmp_path), state)

    assert entry["status"] == "failed"
    assert "lỗi thật" in entry["error"]


def test_process_file_saves_work_dir_on_keyboard_interrupt_and_reraises(tmp_path):
    """Lớp phòng thủ THÊM cho trường hợp gọi process_file() trực tiếp
    (không qua CLI — không có SIGINT handler tuỳ biến, Ctrl+C khi đó raise
    KeyboardInterrupt THẬT theo mặc định của Python): work_dir đã tạo được
    phải được ghi lại TRƯỚC KHI lỗi lan ra ngoài, và KeyboardInterrupt vẫn
    phải lan tiếp (không được nuốt — người dùng bấm Ctrl+C phải thấy tác
    dụng ngay, không phải bị "nuốt" im lặng)."""
    video = tmp_path / "video.mp4"
    video.write_bytes(b"data")
    pipe = FakePipeline(KeyboardInterrupt())
    state = WatchState(str(tmp_path / "_watch_state.json"))

    with pytest.raises(KeyboardInterrupt):
        process_file(str(video), pipe, _req_template(tmp_path), state)

    entry = state.get(file_key(str(video)))
    assert entry["status"] == "processing"  # chưa xong — resume được ở lượt sau
    assert entry["work_dir"] == pipe.last_work_dir


def test_process_file_writes_failures_log(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"data")
    pipe = FakePipeline(RuntimeError("lỗi thật"))
    state = WatchState(str(tmp_path / "_watch_state.json"))
    failures_path = str(tmp_path / "failures.jsonl")

    process_file(str(video), pipe, _req_template(tmp_path), state,
                failures_log_path=failures_path, now_fn=lambda: "2026-08-12T00:00:00")

    lines = open(failures_path, encoding="utf-8").read().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["timestamp"] == "2026-08-12T00:00:00"
    assert entry["video"] == str(video)


def test_run_watch_once_processes_all_ready_files_and_skips_after(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"1")
    (tmp_path / "b.mp4").write_bytes(b"2")
    pipe = FakePipeline("ok")
    tracker = StabilityTracker(stable_seconds=0.0)
    state = WatchState(str(tmp_path / "_watch_state.json"))

    # Lượt quét ĐẦU TIÊN thấy file lần đầu -> chưa có gì để so sánh, chưa xử
    # lý (đúng thiết kế: 1 lần thấy không đủ để coi là "ổn định", dù
    # stable_seconds=0 — cần ÍT NHẤT 2 lượt poll để so sánh kích thước).
    results0 = run_watch_once(str(tmp_path), pipe, _req_template(tmp_path), state, tracker)
    assert results0 == []

    # Lượt quét THỨ 2: kích thước không đổi từ lượt trước -> ổn định, xử lý.
    results = run_watch_once(str(tmp_path), pipe, _req_template(tmp_path), state, tracker)
    assert len(results) == 2
    assert all(r["status"] == "success" for r in results)

    # Lượt quét THỨ 3 (không có file mới) -> không xử lý lại.
    results2 = run_watch_once(str(tmp_path), pipe, _req_template(tmp_path), state, tracker)
    assert results2 == []
    assert len(pipe.seen) == 2  # không tăng thêm


def test_restart_resumes_from_recorded_work_dir_for_interrupted_file(tmp_path):
    """Constraint 4: file bị dừng dở ("processing") ở lượt trước -> lượt
    sau resume đúng work_dir đã ghi thay vì dub lại từ đầu."""
    video = tmp_path / "video.mp4"
    video.write_bytes(b"data")
    work_dir = tmp_path / "wd_da_co"
    work_dir.mkdir()
    state = WatchState(str(tmp_path / "_watch_state.json"))
    state.record(file_key(str(video)), {"status": "processing", "work_dir": str(work_dir)})

    pipe = FakePipeline("ok")
    process_file(str(video), pipe, _req_template(tmp_path), state)

    assert pipe.seen[0].resume_dir == str(work_dir)


def test_new_video_dropped_after_a_failed_one_still_gets_processed(tmp_path):
    (tmp_path / "bad.mp4").write_bytes(b"1")
    pipe = FakePipeline(RuntimeError("lỗi"))
    tracker = StabilityTracker(stable_seconds=0.0)
    state = WatchState(str(tmp_path / "_watch_state.json"))
    run_watch_once(str(tmp_path), pipe, _req_template(tmp_path), state, tracker)  # lần thấy đầu
    run_watch_once(str(tmp_path), pipe, _req_template(tmp_path), state, tracker)  # xử lý, fail

    (tmp_path / "good.mp4").write_bytes(b"2")
    pipe.outcome = "ok"
    run_watch_once(str(tmp_path), pipe, _req_template(tmp_path), state, tracker)  # lần thấy đầu
    results = run_watch_once(str(tmp_path), pipe, _req_template(tmp_path), state, tracker)
    assert len(results) == 1
    assert results[0]["status"] == "success"


# --------------------------------------------------------------------- #
# watch_forever — chỉ test 1 vòng lặp CÓ KIỂM SOÁT (dừng ngay sau lượt đầu
# qua stop_event), không chạy polling dài hạn thật trong test suite.

def test_watch_forever_passes_a_real_non_empty_timestamp_to_failures_log(tmp_path):
    """Bug thật bắt được lúc live-verify V25: `run_watch_once()`/
    `process_file()` mặc định `now_fn=lambda: ""` (đúng cho unit test thuần,
    xem test_process_file_writes_failures_log) nhưng `watch_forever()` ban
    đầu QUÊN truyền `now_fn` thật — mọi dòng failures.jsonl khi chạy `voxdub
    watch` thật đều có timestamp RỖNG, mất hết giá trị theo dõi theo thời
    gian. Test này khoá lại: `watch_forever()` PHẢI tự cấp timestamp thật."""
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "bad.mp4").write_bytes(b"khong phai video that")
    state_path = str(tmp_path / "_watch_state.json")
    failures_log = str(tmp_path / "failures.jsonl")
    stop_event = threading.Event()

    pipe = FakePipeline(RuntimeError("lỗi thật"))
    original_run = pipe.run

    def _run_then_stop(req):
        try:
            return original_run(req)
        finally:
            stop_event.set()  # dừng NGAY sau lượt xử lý đầu tiên

    pipe.run = _run_then_stop

    watch_forever(str(tmp_path / "in"), pipe, _req_template(tmp_path), state_path,
                  poll_interval_s=0.01, stable_seconds=0.0, stop_event=stop_event,
                  failures_log_path=failures_log)

    lines = open(failures_log, encoding="utf-8").read().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["timestamp"] != ""
