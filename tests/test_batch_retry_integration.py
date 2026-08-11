"""Mini-spec V24 (docs/PLAN.md, Phase F) — tự thử lại video lỗi tạm thời
trong batch + log lỗi tập trung, tích hợp qua `run_batch()`.

Tái dùng đúng `FakePipeline` style của tests/test_batch.py (pipeline giả,
không tải/ASR/TTS thật) nhưng hỗ trợ SCRIPT NHIỀU LƯỢT cho cùng 1 URL (lỗi
lần đầu, thành công lần sau) — cái test_batch.py cũ chưa cần.
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from autodub.batch import STATE_FILENAME, run_batch
from autodub.config import Settings
from autodub.pipeline import DubRequest
from autodub.subprocess_watchdog import SubprocessTimeoutError


class ScriptedPipeline:
    """``outcomes[url]`` là 1 DANH SÁCH kết quả tiêu thụ theo thứ tự mỗi lần
    ``run()`` được gọi cho URL đó — mô phỏng "lỗi lần 1, thành công lần 2".

    Tạo THẬT thư mục ``last_work_dir`` trên đĩa (như pipeline thật tạo
    ``work_dir`` sớm trong ``run()``, trước các bước có thể lỗi) — logic
    resume trong ``batch.py::_run_items`` đòi ``os.path.isdir(prev_dir)``
    thật, không chỉ 1 chuỗi giả.
    """

    def __init__(self, outcomes: dict[str, list], root=None):
        self.outcomes = {k: list(v) for k, v in outcomes.items()}
        self.seen: list[DubRequest] = []
        self.last_work_dir = ""
        self._call_count: dict[str, int] = {}
        self._root = root or tempfile.mkdtemp(prefix="voxdub-batch-retry-test-")
        #: work_dir dùng ở MỖI lượt gọi run(), theo thứ tự — để test đối
        #: chiếu "lượt gọi thứ 2 resume đúng work_dir của lượt gọi thứ 1".
        self.work_dirs_used: list[str] = []

    def run(self, req):
        self.seen.append(req)
        self._call_count[req.url] = self._call_count.get(req.url, 0) + 1
        work_dir = req.resume_dir or os.path.join(
            str(self._root), f"wd_{req.url.replace('://', '_').replace('/', '_')}")
        os.makedirs(work_dir, exist_ok=True)
        self.last_work_dir = work_dir
        self.work_dirs_used.append(work_dir)
        queue = self.outcomes.get(req.url, [])
        outcome = queue.pop(0) if queue else "ok"
        if isinstance(outcome, Exception):
            raise outcome
        return type("R", (), {
            "status": "completed", "work_dir": self.last_work_dir,
            "report": {
                "session_id": f"sess_{req.url}_{self._call_count[req.url]}",
                "total_segments": 1, "total_original_duration": 1.0,
                "total_tts_duration": 1.0, "processing_time_seconds": 0.1,
            },
        })()


@pytest.fixture
def env(tmp_path, monkeypatch):
    # Backoff giữa các lần thử lại KHÔNG được làm test chậm thật.
    monkeypatch.setattr("autodub.batch.time.sleep", lambda s: None)
    settings = Settings(output_dir=str(tmp_path))
    template = DubRequest(url="", voice="Phạm Tuyên", output_dir=str(tmp_path))
    return settings, template, str(tmp_path / STATE_FILENAME), tmp_path


def read_state(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_failures(tmp_path):
    path = tmp_path / "failures.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# --------------------------------------------------------------------- #
# retry_transient=False (mặc định) — 0 regression

def test_retry_off_by_default_transient_error_still_fails_immediately(env):
    settings, template, state_path, tmp_path = env
    pipe = ScriptedPipeline({"https://a.com/1": [SubprocessTimeoutError("treo"), "ok"]})

    summary = run_batch("https://a.com/1", settings, template, pipeline=pipe)

    assert (summary.success, summary.failed) == (0, 1)
    assert len(pipe.seen) == 1  # KHÔNG tự thử lại


# --------------------------------------------------------------------- #
# retry_transient=True

def test_transient_error_recovers_on_retry_within_limit(env):
    settings, template, state_path, tmp_path = env
    pipe = ScriptedPipeline({"https://a.com/1": [SubprocessTimeoutError("treo")]})

    summary = run_batch("https://a.com/1", settings, template, pipeline=pipe,
                        retry_transient=True)

    assert (summary.success, summary.failed) == (1, 0)
    assert len(pipe.seen) == 2  # 1 lần đầu lỗi + 1 lần thử lại thành công


def test_retry_resumes_from_the_failed_attempts_work_dir(env):
    settings, template, state_path, tmp_path = env
    pipe = ScriptedPipeline({"https://a.com/1": [SubprocessTimeoutError("treo")]})

    run_batch("https://a.com/1", settings, template, pipeline=pipe,
              retry_transient=True)

    assert len(pipe.work_dirs_used) == 2
    # Lượt thử lại PHẢI resume đúng work_dir của lượt lỗi đầu — không tạo
    # thư mục mới (không tải/nghe-chép lại từ đầu).
    assert pipe.seen[1].resume_dir == pipe.work_dirs_used[0]
    assert pipe.work_dirs_used[0] == pipe.work_dirs_used[1]


def test_permanent_error_never_retried_even_when_flag_on(env):
    settings, template, state_path, tmp_path = env
    pipe = ScriptedPipeline({"https://a.com/1": [RuntimeError("hết Vox")]})

    summary = run_batch("https://a.com/1", settings, template, pipeline=pipe,
                        retry_transient=True)

    assert (summary.success, summary.failed) == (0, 1)
    assert len(pipe.seen) == 1  # lỗi vĩnh viễn -> không thử lại dù cờ bật


def test_transient_error_beyond_max_retries_eventually_fails(env):
    settings, template, state_path, tmp_path = env
    pipe = ScriptedPipeline({"https://a.com/1": [
        SubprocessTimeoutError("treo 1"),
        SubprocessTimeoutError("treo 2"),
        SubprocessTimeoutError("treo 3"),
    ]})  # nhiều hơn max_retries=2 mặc định

    summary = run_batch("https://a.com/1", settings, template, pipeline=pipe,
                        retry_transient=True, max_retries=2)

    assert (summary.success, summary.failed) == (0, 1)
    assert len(pipe.seen) == 3  # 1 lần đầu + đúng 2 lần thử lại, rồi dừng


def test_other_videos_in_batch_unaffected_by_one_videos_retries(env):
    settings, template, state_path, tmp_path = env
    pipe = ScriptedPipeline({"https://a.com/1": [SubprocessTimeoutError("treo")]})

    summary = run_batch("https://a.com/1\nhttps://a.com/2", settings, template,
                        pipeline=pipe, retry_transient=True)

    assert (summary.success, summary.failed) == (2, 0)


def test_retrying_status_reported_to_observer(env):
    settings, template, state_path, tmp_path = env
    pipe = ScriptedPipeline({"https://a.com/1": [SubprocessTimeoutError("treo")]})
    events = []

    run_batch("https://a.com/1", settings, template, pipeline=pipe,
              retry_transient=True, observer=lambda i, t, item, status, detail:
                  events.append(status))

    assert "retrying" in events
    assert events[-1] == "success"


# --------------------------------------------------------------------- #
# failures.jsonl — LUÔN ghi, không phụ thuộc retry_transient (Constraint 3)

def test_failures_log_written_even_without_retry_enabled(env):
    settings, template, state_path, tmp_path = env
    pipe = ScriptedPipeline({"https://a.com/1": [RuntimeError("lỗi vĩnh viễn")]})

    run_batch("https://a.com/1", settings, template, pipeline=pipe)

    entries = read_failures(tmp_path)
    assert len(entries) == 1
    assert entries[0]["transient"] is False
    assert entries[0]["retried"] is False
    assert "lỗi vĩnh viễn" in entries[0]["error"]


def test_failures_log_records_each_retry_attempt_separately(env):
    settings, template, state_path, tmp_path = env
    pipe = ScriptedPipeline({"https://a.com/1": [
        SubprocessTimeoutError("treo 1"), SubprocessTimeoutError("treo 2"),
    ]})

    run_batch("https://a.com/1", settings, template, pipeline=pipe,
              retry_transient=True, max_retries=2)

    entries = read_failures(tmp_path)
    assert len(entries) == 2  # 2 lượt thất bại trước khi thành công lần 3
    assert [e["attempt"] for e in entries] == [1, 2]
    assert all(e["transient"] is True for e in entries)
    assert [e["retried"] for e in entries] == [True, True]


def test_failures_log_does_not_touch_batch_state_status_field(env):
    """Constraint 3: 2 file độc lập — batch_state.json không đổi format."""
    settings, template, state_path, tmp_path = env
    pipe = ScriptedPipeline({"https://a.com/1": [RuntimeError("lỗi")]})

    run_batch("https://a.com/1", settings, template, pipeline=pipe)

    videos = read_state(state_path)["videos"]
    assert videos[0]["status"] == "failed"
    assert "quality" not in videos[0]  # không lẫn field của V23


def test_failures_log_uses_injected_now_fn_for_deterministic_timestamp(env):
    settings, template, state_path, tmp_path = env
    pipe = ScriptedPipeline({"https://a.com/1": [RuntimeError("lỗi")]})

    from autodub import batch as batch_module

    # run_batch() không expose now_fn trực tiếp (nội bộ _run_items) — gọi
    # thẳng _run_items ở đây để khoá đúng hợp đồng "timestamp từ ngoài vào".
    from autodub.pipeline import DubPipeline

    videos = []
    state = {"videos": videos}

    class Item:
        def __init__(self, url):
            self.url, self.file_path, self.voice = url, None, None
            self.subtitle_mode = self.subtitle_style = self.blur_regions = None
            self.ref = {"status": "waiting"}

        @property
        def label(self):
            return self.url

    item = Item("https://a.com/1")
    batch_module._run_items(
        [item], pipe, template, on_result=lambda *a: None,
        failures_log_path=str(tmp_path / "failures.jsonl"),
        now_fn=lambda: "2026-08-12T00:00:00")

    entries = read_failures(tmp_path)
    assert entries[0]["timestamp"] == "2026-08-12T00:00:00"
