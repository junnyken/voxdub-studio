"""Mini-spec V56 — nghe thử N giây đầu trước khi chạy cả video.

Thứ đáng test không phải "có cắt được không" mà là 3 chỗ nếu sai sẽ gây thiệt
hại thật:

* bản nghe thử KHÔNG được nhầm thành bản cuối (đăng nhầm 30 giây lên kênh),
* cắt hỏng KHÔNG được âm thầm rơi về chạy cả video — người dùng bấm nghe thử
  chính là để tránh chuyện đó,
* `preview_seconds=0` phải giữ NGUYÊN hành vi cũ.

Có 1 test cắt bằng ffmpeg THẬT (tự dựng video bằng ffmpeg rồi đo lại bằng
ffprobe) — tự skip nếu máy không có ffmpeg.
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from autodub.preview import (
    apply_folder_suffix,
    folder_suffix,
    is_preview_dir,
    make_preview_clip,
)


def test_folder_suffix_is_visible_in_the_name():
    assert folder_suffix(30) == "-preview30s"
    assert is_preview_dir("/out/VN/20260818120000_vi-preview30s") is True
    assert is_preview_dir("/out/VN/20260818120000_vi") is False, (
        "dự án thật KHÔNG được bị nhận nhầm là bản thử"
    )


def test_folder_name_gets_the_suffix_only_for_preview_runs():
    """Đây là chỗ quyết định bản thử có bị nhầm thành bản cuối hay không."""
    assert apply_folder_suffix("20260818120000_vi", 30) == "20260818120000_vi-preview30s"
    assert apply_folder_suffix("20260818120000_vi", 0) == "20260818120000_vi", (
        "chạy bình thường phải giữ NGUYÊN tên cũ — 0 regression"
    )
    assert apply_folder_suffix("20260818120000_vi", None) == "20260818120000_vi"


def test_zero_seconds_is_rejected_loudly():
    with pytest.raises(ValueError):
        make_preview_clip("bất kỳ.mp4", "/tmp", 0)


def test_ffmpeg_failure_raises_instead_of_falling_back(tmp_path, monkeypatch):
    """Cắt hỏng phải BÁO LỖI, không được trả về video gốc.

    Nếu âm thầm rơi về video gốc thì pipeline sẽ chạy CẢ video — tốn đúng thời
    gian và Vox mà người dùng đang cố tiết kiệm khi bấm "nghe thử".
    """
    def fake_run(cmd, **_kw):
        class R:
            returncode = 1
            stdout = ""
            stderr = "moov atom not found"
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as err:
        make_preview_clip(str(tmp_path / "hong.mp4"), str(tmp_path), 30)
    assert "nghe thử" in str(err.value)
    assert "moov atom" in str(err.value), "phải giữ lý do thật của ffmpeg"


def test_empty_output_is_treated_as_failure(tmp_path, monkeypatch):
    """ffmpeg trả về 0 nhưng file rỗng — vẫn là hỏng, không phải thành công."""
    dest = tmp_path / "preview_30s.mp4"

    def fake_run(cmd, **_kw):
        dest.write_bytes(b"")
        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        make_preview_clip(str(tmp_path / "src.mp4"), str(tmp_path), 30)


def test_command_asks_for_stream_copy_not_reencode(tmp_path, monkeypatch):
    """`-c copy` là lý do preview gần như tức thì kể cả video vài GB."""
    seen = {}

    def fake_run(cmd, **_kw):
        seen["cmd"] = cmd
        dest = cmd[-1]
        with open(dest, "wb") as fh:
            fh.write(b"x" * 100)
        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    make_preview_clip(str(tmp_path / "src.mp4"), str(tmp_path), 45)

    cmd = seen["cmd"]
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "copy"
    assert "-t" in cmd and cmd[cmd.index("-t") + 1] == "45"


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="cần ffmpeg + ffprobe thật")
def test_real_ffmpeg_cuts_a_real_video(tmp_path):
    """Cắt THẬT rồi đo lại bằng ffprobe — không mock thứ đang kiểm."""
    src = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=12:size=320x240:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", str(src)],
        capture_output=True, check=True)

    out = make_preview_clip(str(src), str(tmp_path), 5)

    assert os.path.isfile(out)
    duration = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", out],
        capture_output=True, text=True, check=True).stdout.strip())
    # `-c copy` cắt theo keyframe nên lệch chút là bình thường; điều phải đúng
    # là NGẮN HƠN HẲN bản gốc 12s.
    assert 3.0 <= duration <= 7.5, f"đoạn thử dài {duration}s, không hợp lý"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="cần ffmpeg thật")
def test_video_shorter_than_requested_is_not_an_error(tmp_path):
    """Video 3 giây mà xin 30 giây: trả về cả video, KHÔNG phải lỗi."""
    src = tmp_path / "ngan.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10",
         "-c:v", "libx264", str(src)],
        capture_output=True, check=True)

    out = make_preview_clip(str(src), str(tmp_path), 30)
    assert os.path.getsize(out) > 0
