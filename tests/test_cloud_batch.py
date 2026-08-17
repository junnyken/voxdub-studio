"""Mini-spec V51 — đẩy batch lên máy chủ lồng tiếng.

Chạy trên MỘT MÁY CHỦ HTTP THẬT dựng tại chỗ (``http.server`` trong thread),
không mock ``requests``: thứ đáng kiểm ở đây chính là hành vi qua dây — mã
lỗi, stream tải về, file dở dang. Mock đúng cái đang kiểm thì test chỉ chứng
minh mình hiểu đúng mock của mình.

Trọng tâm là các đường HỎNG, vì chúng đụng tiền thật:
  - hết quota giữa chừng phải DỪNG nộp, không bắn tiếp để ăn 402 hàng loạt
  - máy chủ mất kết quả (đã hoàn phí) KHÁC với video hỏng
  - tải dở dang KHÔNG được để lại file mang tên thật (máy chủ đã xoá bản gốc)
  - chạy lại phải bỏ qua video đã xong, nộp lại là trả tiền lần hai
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from autodub.cloud_batch import (
    STATUS_FAILED,
    STATUS_REFUNDED,
    STATUS_SUCCESS,
    run_cloud_batch,
)
from autodub.cloud_dub import CloudDubClient
import autodub.cloud_dub as cloud_dub

RESULT_BYTES = b"dubbed-video-bytes" * 100


class FakeServerState:
    """Kịch bản máy chủ do từng test tự dựng."""

    def __init__(self) -> None:
        self.minutes_remaining = 100
        self.submits: list[dict] = []
        self.jobs: dict[str, str] = {}          # jobId -> status
        self.job_error: dict[str, str] = {}
        self.quota_error_after = None           # nộp quá N lần thì trả 402
        self.result_mode = "ok"                 # ok | lost | truncated | empty
        self.downloads = 0


def _make_handler(state: FakeServerState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):        # im lặng, khỏi rác output test
            pass

        def _json(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):                      # noqa: N802
            path = self.path.split("?")[0]
            if path == "/api/v1/me":
                return self._json(200, {
                    "orgName": "Test", "dubMinutesQuota": 100,
                    "dubMinutesUsed": 0, "dubMinutesReserved": 0,
                    "dubMinutesRemaining": state.minutes_remaining,
                })
            if path.endswith("/result"):
                job_id = path.split("/")[-2]
                state.downloads += 1
                if state.result_mode == "lost":
                    return self._json(410, {
                        "code": "RESULT_LOST_REFUNDED",
                        "message": "Kết quả không còn trên máy chủ.",
                        "minutesRefunded": 2,
                    })
                if state.result_mode == "empty":
                    self.send_response(200)
                    self.send_header("content-length", "0")
                    self.end_headers()
                    return None
                if state.result_mode == "truncated":
                    # Khai dài hơn thực tế gửi — đúng ca đứt kết nối giữa chừng.
                    self.send_response(200)
                    self.send_header("content-length", str(len(RESULT_BYTES) * 2))
                    self.end_headers()
                    self.wfile.write(RESULT_BYTES)
                    return None
                self.send_response(200)
                self.send_header("content-type", "video/mp4")
                self.send_header("content-length", str(len(RESULT_BYTES)))
                self.end_headers()
                self.wfile.write(RESULT_BYTES)
                return None
            if "/api/v1/dub/" in path:
                job_id = path.rsplit("/", 1)[-1]
                payload = {"jobId": job_id, "status": state.jobs.get(job_id, "queued")}
                if state.job_error.get(job_id):
                    payload["error"] = state.job_error[job_id]
                return self._json(200, payload)
            return self._json(404, {"code": "NOT_FOUND"})

        def do_POST(self):                     # noqa: N802
            if not self.path.startswith("/api/v1/dub"):
                return self._json(404, {"code": "NOT_FOUND"})
            length = int(self.headers.get("content-length") or 0)
            self.rfile.read(length)
            if (state.quota_error_after is not None
                    and len(state.submits) >= state.quota_error_after):
                return self._json(402, {
                    "code": "DUB_QUOTA_EXCEEDED",
                    "message": "Không đủ quota phút lồng tiếng còn trống.",
                })
            job_id = f"job{len(state.submits) + 1}"
            state.submits.append({"path": self.path, "jobId": job_id})
            state.jobs[job_id] = "done"        # mặc định: xong ngay
            return self._json(200, {"jobId": job_id, "status": "queued"})

    return Handler


@pytest.fixture()
def server():
    state = FakeServerState()
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler(state))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    state.base_url = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield state
    httpd.shutdown()


@pytest.fixture(autouse=True)
def no_submit_pacing(monkeypatch):
    """Bỏ nhịp chờ 12s giữa 2 lượt nộp — hạn mức thật của máy chủ, không phải
    thứ cần chờ trong test (đã có test riêng cho chính cơ chế nhịp)."""
    monkeypatch.setattr(cloud_dub, "SUBMIT_MIN_INTERVAL_S", 0.0)


def _client(state) -> CloudDubClient:
    return CloudDubClient(base_url=state.base_url, api_key="vx_live_test")


def _videos(tmp_path: Path, n: int) -> Path:
    src = tmp_path / "in"
    src.mkdir()
    for i in range(n):
        (src / f"v{i}.mp4").write_bytes(b"fake video %d" % i)
    return src


def test_happy_path_downloads_every_video(server, tmp_path):
    src = _videos(tmp_path, 2)
    out = tmp_path / "out"

    report = run_cloud_batch(src, out, source_lang="en-US", target_lang="vi",
                             client=_client(server), poll_interval=0.01)

    assert len(report.succeeded) == 2
    assert not report.failed
    for i in range(2):
        dest = out / f"v{i}_dubbed.mp4"
        assert dest.read_bytes() == RESULT_BYTES
    assert len(server.submits) == 2


def test_rerun_skips_finished_videos(server, tmp_path):
    src = _videos(tmp_path, 2)
    out = tmp_path / "out"
    run_cloud_batch(src, out, source_lang="en-US", target_lang="vi",
                    client=_client(server), poll_interval=0.01)
    assert len(server.submits) == 2

    report = run_cloud_batch(src, out, source_lang="en-US", target_lang="vi",
                             client=_client(server), poll_interval=0.01)

    assert len(server.submits) == 2, "nộp lại video đã xong = trả tiền lần hai"
    assert len(report.succeeded) == 2


def test_retry_done_forces_resubmit(server, tmp_path):
    src = _videos(tmp_path, 1)
    out = tmp_path / "out"
    run_cloud_batch(src, out, source_lang="en-US", target_lang="vi",
                    client=_client(server), poll_interval=0.01)

    run_cloud_batch(src, out, source_lang="en-US", target_lang="vi",
                    client=_client(server), poll_interval=0.01, retry_done=True)

    assert len(server.submits) == 2


def test_quota_exhausted_midway_stops_submitting(server, tmp_path):
    src = _videos(tmp_path, 4)
    out = tmp_path / "out"
    server.quota_error_after = 2          # 2 job đầu qua, từ job 3 hết quota

    report = run_cloud_batch(src, out, source_lang="en-US", target_lang="vi",
                             client=_client(server), poll_interval=0.01)

    assert len(server.submits) == 2, "phải DỪNG nộp chứ không bắn tiếp để ăn 402"
    assert len(report.succeeded) == 2
    assert "quota" in report.stopped_early.lower()
    assert len(report.skipped) == 2, "2 video còn lại phải được báo là CHƯA chạy"


def test_no_quota_at_all_does_not_submit_anything(server, tmp_path):
    src = _videos(tmp_path, 2)
    server.minutes_remaining = 0

    report = run_cloud_batch(src, tmp_path / "out", source_lang="en-US",
                             target_lang="vi", client=_client(server),
                             poll_interval=0.01)

    assert server.submits == []
    assert report.stopped_early
    assert len(report.skipped) == 2


def test_server_lost_result_is_refunded_not_failed(server, tmp_path):
    src = _videos(tmp_path, 1)
    out = tmp_path / "out"
    server.result_mode = "lost"

    report = run_cloud_batch(src, out, source_lang="en-US", target_lang="vi",
                             client=_client(server), poll_interval=0.01)

    assert not report.failed, "mất kết quả KHÔNG phải video hỏng — gửi lại là xong"
    assert len(report.refunded) == 1
    assert report.refunded[0].status == STATUS_REFUNDED
    assert report.refunded[0].minutes_refunded == 2
    assert not (out / "v0_dubbed.mp4").exists()


def test_truncated_download_leaves_no_file_with_the_real_name(server, tmp_path):
    src = _videos(tmp_path, 1)
    out = tmp_path / "out"
    server.result_mode = "truncated"

    report = run_cloud_batch(src, out, source_lang="en-US", target_lang="vi",
                             client=_client(server), poll_interval=0.01)

    assert len(report.failed) == 1
    dest = out / "v0_dubbed.mp4"
    assert not dest.exists(), (
        "file dở mang tên thật là mất hàng: lượt sau tưởng đã xong, "
        "trong khi máy chủ đã xoá bản gốc"
    )
    assert not list(out.glob("*.part")), "cũng không được để lại rác .part"


def test_broken_download_does_not_kill_the_whole_batch(server, tmp_path):
    """CI bắt được ca này, sandbox thì không (2026-08-17).

    Máy chủ khai `content-length` dài hơn thứ nó gửi rồi đóng kết nối →
    `requests` ném `ChunkedEncodingError`. Lỗi transport đó KHÔNG phải
    `CloudDubError` nên nó xuyên qua vòng chạy và giết cả lượt batch: video
    số 2 trở đi không bao giờ được nộp, dù chẳng liên quan gì.
    """
    src = _videos(tmp_path, 3)
    out = tmp_path / "out"
    server.result_mode = "truncated"

    report = run_cloud_batch(src, out, source_lang="en-US", target_lang="vi",
                             client=_client(server), poll_interval=0.01)

    assert len(server.submits) == 3, (
        "1 video hỏng không được chặn 2 video còn lại — đó là lỗi CI bắt được"
    )
    assert len(report.failed) == 3
    assert not report.skipped, "không mục nào được phép bị bỏ lửng"
    assert not list(out.glob("*.part")), "không để lại rác .part sau khi đứt"


def test_empty_result_is_a_failure_not_a_success(server, tmp_path):
    src = _videos(tmp_path, 1)
    out = tmp_path / "out"
    server.result_mode = "empty"

    report = run_cloud_batch(src, out, source_lang="en-US", target_lang="vi",
                             client=_client(server), poll_interval=0.01)

    assert len(report.failed) == 1
    assert not (out / "v0_dubbed.mp4").exists()


def test_failed_job_reports_server_error_message(server, tmp_path):
    src = _videos(tmp_path, 1)
    out = tmp_path / "out"

    original = server.jobs
    # Job nhận xong nhưng máy chủ báo hỏng — phải giữ nguyên lý do của máy chủ.
    def fail_next():
        for job_id in list(server.jobs):
            server.jobs[job_id] = "failed"
            server.job_error[job_id] = "ASR không nhận ra tiếng nói nào"
    server.jobs = original

    import autodub.cloud_batch as cb
    real_wait = cb._wait_for_job

    def patched(client, job_id, *a, **kw):
        fail_next()
        return real_wait(client, job_id, *a, **kw)

    cb._wait_for_job = patched
    try:
        report = run_cloud_batch(src, out, source_lang="en-US", target_lang="vi",
                                 client=_client(server), poll_interval=0.01)
    finally:
        cb._wait_for_job = real_wait

    assert len(report.failed) == 1
    assert "ASR không nhận ra" in report.failed[0].error


def test_state_file_survives_and_records_each_item(server, tmp_path):
    src = _videos(tmp_path, 2)
    out = tmp_path / "out"

    run_cloud_batch(src, out, source_lang="en-US", target_lang="vi",
                    client=_client(server), poll_interval=0.01)

    state = json.loads((out / "cloud_batch_state.json").read_text(encoding="utf-8"))
    assert set(state["items"]) == {"v0.mp4", "v1.mp4"}
    assert all(v["status"] == STATUS_SUCCESS for v in state["items"].values())


def test_source_files_are_never_touched(server, tmp_path):
    src = _videos(tmp_path, 2)
    before = {p.name: p.read_bytes() for p in src.iterdir()}

    run_cloud_batch(src, tmp_path / "out", source_lang="en-US", target_lang="vi",
                    client=_client(server), poll_interval=0.01)

    after = {p.name: p.read_bytes() for p in src.iterdir()}
    assert after == before


def test_missing_api_key_refuses_instead_of_running_locally(monkeypatch):
    from autodub.cloud_dub import CloudDubError

    monkeypatch.delenv("VOXDUB_API_KEY", raising=False)
    monkeypatch.setenv("VOXDUB_API_URL", "http://example.invalid")

    with pytest.raises(CloudDubError) as err:
        CloudDubClient()
    assert err.value.code == "NO_API_KEY"
