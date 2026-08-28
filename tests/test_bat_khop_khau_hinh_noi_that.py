"""Tệp .bat cài khớp khẩu hình phải nói THẬT giới hạn (mini-spec C48).

Bản phát hành v3.14.1 ghi đúng một câu: «Nang, can GPU de chay cho ra hon».
Người đọc câu đó sẽ tải ~4 GB về, rồi mới vỡ lẽ tính năng chỉ chạy được video
12 giây, chậm 74 lần thời gian thật, và chưa ai chấm chất lượng lần nào — số
liệu đều đã có sẵn trong docs/TEST_LOG.md từ mini-spec V32a/V32b.

Đây là lớp lỗi #5 của dự án (câu chữ đi lệch khỏi mã) ở dạng nhẹ hơn: câu chữ
không SAI, chỉ là nói thiếu đúng những thứ quyết định việc có nên cài hay không.
"""
from __future__ import annotations

import importlib.util
import os
import re

import pytest

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def build_exe():
    spec = importlib.util.spec_from_file_location(
        "build_exe", os.path.join(GOC, "scripts", "build_exe.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bat_lipsync(build_exe) -> str:
    return build_exe._bat_cho("setup_lipsync.py")


@pytest.mark.parametrize("phai_co", [
    "THU NGHIEM",        # nhãn ngay ở tiêu đề cửa sổ
    "CHUA ON DINH",
    "12 giay",           # trần độ dài thật
    "794 giay",          # tốc độ đo thật
    "NVIDIA",            # máy card Intel/AMD cài cũng vô ích
    "4 GB",              # dung lượng
    "CHUA duoc danh gia",  # chất lượng chưa ai chấm
])
def test_bat_noi_du_gioi_han_that(bat_lipsync, phai_co):
    assert phai_co in bat_lipsync, (
        f"tệp .bat không nói {phai_co!r} — người dùng chỉ biết sau khi tải 4 GB")


def test_hoi_xac_nhan_truoc_khi_tai_4GB(bat_lipsync):
    """Đúp chuột nhầm vào một tệp .bat không được kéo về 4 GB."""
    assert "Go CO roi bam Enter" in bat_lipsync
    assert 'if /I not "%DONGY%"=="CO"' in bat_lipsync
    assert "Khong tai gi ve may" in bat_lipsync


def test_tran_do_dai_trong_cau_chu_DOC_TU_MA(build_exe):
    """Ai đó nới trần trong config.py thì câu chữ phải đi theo, không thì lời
    hứa thành sai. Nên số này đọc thẳng từ nguồn sự thật, không gõ tay."""
    cfg = open(os.path.join(GOC, "autodub", "config.py"), encoding="utf-8").read()
    that = float(re.search(r"lipsync_max_duration_s: float = ([\d.]+)",
                           cfg).group(1))
    assert build_exe._gioi_han_lipsync() == str(int(that))
    assert f"{int(that)} giay" in build_exe._bat_cho("setup_lipsync.py")


def test_cac_bat_khac_khong_bi_hoi_xac_nhan(build_exe):
    """Hỏi xác nhận ở MỌI tệp .bat thì thành phiền, rồi ai cũng gõ CO theo
    quán tính — chỉ dành cho thứ vừa nặng vừa có giới hạn thật."""
    for script in ("setup_ocr.py", "setup_voices.py", "setup_whisper.py"):
        assert "Go CO roi bam Enter" not in build_exe._bat_cho(script)


def test_bat_nhieu_dong_canh_bao_van_dung_khuon_cu(build_exe):
    """Bảng mô tả nay nhận cả chuỗi lẫn nhiều dòng — dạng cũ phải chạy y như trước."""
    bat = build_exe._bat_cho("setup_diarization.py")
    assert "NANG (~1-2 GB)" in bat
    assert bat.startswith("@echo off")
    assert "chcp 65001" in bat
