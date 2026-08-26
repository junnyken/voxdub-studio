"""Tìm ffprobe bằng cách đổi chữ trong đường dẫn là hỏng ở thư mục tên "ffmpeg".

Bug thật, 26/8/2026. Cách cũ:

    ffprobe = duong_dan_ffmpeg().replace("ffmpeg", "ffprobe")

`str.replace` đổi **mọi** chỗ khớp, mà `C:\\ffmpeg\\bin\\ffmpeg.exe` là đường
dẫn rất thường gặp — nó thành `C:\\ffprobe\\bin\\ffprobe.exe`, một thư mục
không tồn tại.

Hậu quả nhìn từ người dùng KHÔNG phải một câu lỗi mà là **máy đứng**: không đo
được độ dài thì tệp dài không được cắt nhỏ, bộ nghe chạy thẳng vào tệp ba
tiếng, thanh tiến trình nằm im hàng chục phút.
"""
from __future__ import annotations

import os

import pytest

from autodub import ffmpeg_deps
from autodub.media import cat_tep


@pytest.fixture()
def khong_co_trong_path(monkeypatch):
    """Giả lập máy KHÔNG có ffmpeg/ffprobe trong PATH — đúng ca bản đóng gói."""
    monkeypatch.setattr(ffmpeg_deps.shutil, "which", lambda _ten: None)


def test_giu_nguyen_thu_muc_chi_doi_ten_tep(tmp_path, monkeypatch,
                                            khong_co_trong_path):
    """Ca đã hỏng: thư mục cũng tên «ffmpeg»."""
    thu_muc = tmp_path / "ffmpeg" / "bin"
    thu_muc.mkdir(parents=True)
    (thu_muc / "ffmpeg.exe").write_text("x")
    (thu_muc / "ffprobe.exe").write_text("x")
    monkeypatch.setattr(ffmpeg_deps, "duong_dan_ffmpeg",
                        lambda: str(thu_muc / "ffmpeg.exe"))

    ra = ffmpeg_deps.duong_dan_ffprobe()
    assert ra == str(thu_muc / "ffprobe.exe")
    assert os.path.isfile(ra), "trỏ vào tệp không tồn tại — đúng lỗi cũ"


def test_khong_co_ffprobe_canh_ffmpeg_thi_tra_rong(tmp_path, monkeypatch,
                                                   khong_co_trong_path):
    """Đoán bừa một đường dẫn không tồn tại còn tệ hơn nói thẳng là không có."""
    thu_muc = tmp_path / "bin"
    thu_muc.mkdir(parents=True)
    (thu_muc / "ffmpeg.exe").write_text("x")
    monkeypatch.setattr(ffmpeg_deps, "duong_dan_ffmpeg",
                        lambda: str(thu_muc / "ffmpeg.exe"))
    monkeypatch.setattr(ffmpeg_deps, "app_root", lambda: str(tmp_path / "khong-co"))

    assert ffmpeg_deps.duong_dan_ffprobe() == ""


def test_uu_tien_PATH_he_thong(monkeypatch):
    monkeypatch.setattr(ffmpeg_deps.shutil, "which",
                        lambda ten: "/usr/bin/ffprobe" if ten == "ffprobe" else None)
    assert ffmpeg_deps.duong_dan_ffprobe() == "/usr/bin/ffprobe"


def test_do_dai_khong_co_ffprobe_thi_noi_ro_HAU_QUA(monkeypatch, caplog):
    """"Không đọc được độ dài" không cho người dùng biết vì sao máy đứng."""
    monkeypatch.setattr(cat_tep, "duong_dan_ffprobe", lambda: "")

    with caplog.at_level("WARNING"):
        assert cat_tep.do_dai_giay("/khong-co/video.mp4") == 0.0

    chu = " ".join(r.message for r in caplog.records)
    assert "ffprobe" in chu
    assert "cắt nhỏ" in chu, "phải nói hậu quả: tệp dài không được cắt"
    assert "FFmpeg" in chu, "phải chỉ ra tệp cài đặt cần chạy"
