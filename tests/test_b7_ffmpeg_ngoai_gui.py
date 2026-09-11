"""B7 — FFmpeg trong `bin/` chỉ tìm thấy được khi chạy GUI.

Ba mươi chỗ trong `autodub/` gọi `"ffmpeg"`/`"ffprobe"` trần. Chúng chạy được
**chỉ vì** `autodub_gui/app.py` nối `bin/` vào `PATH` lúc khởi động. Console
script `voxdub` (`[project.scripts]` trong `pyproject.toml`) không đi qua chỗ
đó, nên trên máy chỉ có ffmpeg trong `bin/` — đúng cấu hình của người dùng
đang chạy thử, preflight in ra `...\\bin\\ffmpeg.EXE` — mọi lệnh CLI chết với
`[WinError 2] The system cannot find the file specified`.

Chữa ở MỘT chỗ (vá `PATH`) chứ không sửa 30 chỗ gọi: sửa 30 chỗ là 30 cơ hội
bỏ sót, và chỗ thứ 31 thêm vào tháng sau lại hỏng y như cũ.
"""
from __future__ import annotations

import os
import shutil
from unittest.mock import patch

import pytest

from autodub import ffmpeg_deps


@pytest.fixture
def path_sach(monkeypatch):
    """PATH không có ffmpeg — mô phỏng máy Windows của người dùng."""
    monkeypatch.setenv("PATH", os.pathsep.join(["/khong-co-gi-o-day"]))
    return None


def test_vao_duong_bin_them_bin_vao_path(tmp_path, path_sach, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "ffmpeg").write_text("#!/bin/sh\n")
    monkeypatch.setattr(ffmpeg_deps, "app_root", lambda: str(tmp_path))

    ffmpeg_deps.vao_duong_ffmpeg()

    assert str(bin_dir) in os.environ["PATH"].split(os.pathsep)


def test_vao_duong_lam_shutil_which_tim_thay(tmp_path, path_sach, monkeypatch):
    """Đây mới là điều thật sự cần: `["ffmpeg", …]` phải chạy được.

    Thêm chữ vào biến môi trường mà `which` vẫn không thấy thì chưa chữa gì.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "ffmpeg"
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(0o755)
    monkeypatch.setattr(ffmpeg_deps, "app_root", lambda: str(tmp_path))

    assert shutil.which("ffmpeg") is None
    ffmpeg_deps.vao_duong_ffmpeg()
    assert shutil.which("ffmpeg") == str(exe)


def test_vao_duong_khong_lam_gi_khi_khong_co_bin(tmp_path, path_sach,
                                                 monkeypatch):
    monkeypatch.setattr(ffmpeg_deps, "app_root", lambda: str(tmp_path))
    truoc = os.environ["PATH"]
    ffmpeg_deps.vao_duong_ffmpeg()
    assert os.environ["PATH"] == truoc


def test_vao_duong_khong_them_hai_lan(tmp_path, path_sach, monkeypatch):
    """Gọi lại nhiều lượt không được phình PATH.

    `main()` của CLI có thể gọi nhiều lần trong một tiến trình (test, watch
    folder); mỗi lượt thêm một bản sao là PATH dài dần tới giới hạn 32767 ký
    tự của Windows rồi cả tiến trình hỏng theo cách không liên quan gì.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "ffmpeg").write_text("")
    monkeypatch.setattr(ffmpeg_deps, "app_root", lambda: str(tmp_path))

    ffmpeg_deps.vao_duong_ffmpeg()
    sau_lan_dau = os.environ["PATH"]
    ffmpeg_deps.vao_duong_ffmpeg()
    assert os.environ["PATH"] == sau_lan_dau


def test_vao_duong_giu_nguyen_path_cu(tmp_path, path_sach, monkeypatch):
    """Không được ĐÈ PATH — chỉ thêm vào đầu."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "ffmpeg").write_text("")
    monkeypatch.setattr(ffmpeg_deps, "app_root", lambda: str(tmp_path))

    ffmpeg_deps.vao_duong_ffmpeg()
    assert "/khong-co-gi-o-day" in os.environ["PATH"].split(os.pathsep)


def test_cli_main_goi_vao_duong_ffmpeg():
    """CHỐT CHỖ GỌI, không chỉ chốt thân hàm.

    Viết xong `vao_duong_ffmpeg()` mà `cli.main()` không gọi thì hàm mới chỉ
    là trang trí — đúng lớp lỗi đã lặp bốn lần trong dự án này.
    """
    from autodub import cli

    with patch.object(cli, "vao_duong_ffmpeg") as gia:
        with pytest.raises(SystemExit):
            cli.main([])          # không có lệnh con -> thoát ngay
    assert gia.called, "`cli.main()` không vá PATH trước khi làm gì cả"


def test_cli_vao_duong_truoc_khi_chay_lenh(tmp_path, path_sach, monkeypatch):
    """Vá PATH phải xảy ra TRƯỚC lệnh con, không phải sau.

    Vá sau thì lệnh đầu tiên vẫn chết — và lệnh đầu tiên thường là lệnh duy
    nhất người dùng chạy.
    """
    from autodub import cli

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "ffmpeg").write_text("")
    monkeypatch.setattr(ffmpeg_deps, "app_root", lambda: str(tmp_path))

    thay: list[bool] = []

    def _ghi_lai(args):
        thay.append(str(bin_dir) in os.environ["PATH"].split(os.pathsep))
        return 0

    monkeypatch.setattr(cli, "_cmd_transcribe", _ghi_lai)
    try:
        cli.main(["transcribe", "--input", "https://vi.du/x",
                  "--output-dir", str(tmp_path / "ra")])
    except SystemExit:
        pass

    assert thay == [True], (
        "lệnh con chạy khi PATH chưa có bin/ — vá quá muộn" if thay
        else "không vào được lệnh con để đo (đổi tên lệnh?)")
