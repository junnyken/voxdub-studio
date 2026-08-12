"""Mini-spec V24 (docs/PLAN.md, Phase F) — watchdog cho subprocess treo.

Test bằng subprocess PYTHON THẬT (không mock) — hành vi cần khoá lại là
thời gian chờ thật sự bị chặn hay không, mock không đo được đúng cái đó.
"""
from __future__ import annotations

import subprocess
import sys
import time

import pytest

from autodub.subprocess_watchdog import (
    SubprocessTimeoutError, WatchedLineReader, read_all_with_timeout,
    read_lines_with_timeout,
)


def _spawn(script: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", script],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True)


def test_reads_lines_normally_when_worker_responds_promptly():
    proc = _spawn("print('a'); print('b'); print('c')")
    lines = list(read_lines_with_timeout(proc, timeout=5.0))
    assert lines == ["a\n", "b\n", "c\n"]
    proc.wait(timeout=5)


def test_stops_cleanly_when_stdout_closes_no_timeout_raised():
    proc = _spawn("pass")  # không in gì, thoát ngay
    lines = list(read_lines_with_timeout(proc, timeout=5.0))
    assert lines == []
    proc.wait(timeout=5)


def test_raises_timeout_error_when_worker_hangs():
    """Bug thật đã audit: `for line in proc.stdout:` chặn vô thời hạn nếu
    worker treo — đây là hành vi PHẢI khác: raise trong thời gian hữu hạn."""
    proc = _spawn("import time; time.sleep(60)")  # treo lâu hơn hẳn timeout test
    start = time.monotonic()
    with pytest.raises(SubprocessTimeoutError):
        list(read_lines_with_timeout(proc, timeout=0.3))
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, "phải phát hiện treo NHANH, không chờ hết 60s của worker"
    proc.kill()
    proc.wait(timeout=5)


def test_partial_output_then_hang_still_raises_after_first_lines():
    proc = _spawn(
        "print('before'); import sys; sys.stdout.flush(); "
        "import time; time.sleep(60)")
    reader = WatchedLineReader(proc)
    first = reader.readline(timeout=5.0)
    assert first == "before\n"
    with pytest.raises(SubprocessTimeoutError):
        reader.readline(timeout=0.3)
    proc.kill()
    proc.wait(timeout=5)


def test_blank_lines_pass_through_not_mistaken_for_stream_closed():
    proc = _spawn("print(); print('x')")
    lines = list(read_lines_with_timeout(proc, timeout=5.0))
    assert lines == ["\n", "x\n"]
    proc.wait(timeout=5)


# --------------------------------------------------------------------- #
# read_all_with_timeout — cho worker phát 1 khối kết quả rồi thoát (không
# streaming theo dòng), vd autodub/speech/tts/voice_downloader.py.

def test_read_all_returns_full_output_when_worker_responds_promptly():
    proc = _spawn("print('dong 1'); print('dong 2')")
    output = read_all_with_timeout(proc, timeout=5.0)
    assert output == "dong 1\ndong 2\n"
    proc.wait(timeout=5)


def test_read_all_raises_timeout_error_when_worker_hangs():
    proc = _spawn("import time; time.sleep(60)")
    start = time.monotonic()
    with pytest.raises(SubprocessTimeoutError):
        read_all_with_timeout(proc, timeout=0.3)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0
    proc.kill()
    proc.wait(timeout=5)


def test_read_all_returns_empty_string_when_no_output():
    proc = _spawn("pass")
    assert read_all_with_timeout(proc, timeout=5.0) == ""
    proc.wait(timeout=5)
