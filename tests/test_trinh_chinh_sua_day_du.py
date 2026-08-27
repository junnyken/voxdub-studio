"""Trình chỉnh sửa: có đường quay lại, và dự án nhập vào không rỗng thông tin.

Hai lỗi thật, chủ dự án báo 26-27/08/2026 ngay lượt dùng đầu tiên của tính
năng nhập (C37):

1. *"hình như nó không thể nhấn quay lại về trước được"* — `close_requested`
   đã khai và `app.py` đã nối về trang Dự án, nhưng KHÔNG nút nào phát nó ra.
   Dây đã nối, thiếu đúng cái công tắc. Người dùng mở Trình chỉnh sửa xong là
   kẹt, nhất là khi thanh bên của app bị ẩn.

2. Dự án nhập vào hiện «Thời lượng 00:00», «Ngôn ngữ gốc: không rõ» và
   «Không đọc được dạng sóng của tệp âm thanh này» — vì bộ nhập chỉ ghi phụ
   đề và đường dẫn video, không đo độ dài cũng không trích âm thanh.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import struct
import subprocess
import wave

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(ten: str) -> str:
    return open(os.path.join(REPO, ten), encoding="utf-8").read()


# --- 1. Nút quay lại ----------------------------------------------------

def test_co_nut_phat_tin_hieu_quay_lai():
    src = _doc("autodub_gui/pages/editor_page.py")
    assert "close_requested = Signal()" in src, "mất luôn tín hiệu quay lại"
    assert "self.close_requested.emit" in src, (
        "tín hiệu quay lại khai ra nhưng KHÔNG nút nào phát — người dùng vào "
        "Trình chỉnh sửa rồi không có đường ra")


def test_nut_quay_lai_nam_tren_thanh_dau():
    """Nằm cuối trang thì cũng như không có."""
    src = _doc("autodub_gui/pages/editor_page.py")
    assert "row.addWidget(self.btn_back)" in src
    assert src.index("row.addWidget(self.btn_back)") < src.index("row.addWidget(logo)")


def test_app_van_noi_tin_hieu_do_ve_trang_du_an():
    """Nút có mà đầu kia không nối thì bấm cũng không đi đâu."""
    src = _doc("autodub_gui/app.py")
    assert "close_requested.connect" in src


# --- 2. Dự án nhập vào phải đủ thông tin --------------------------------

@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="cần ffmpeg")
def test_nhap_du_an_do_do_dai_va_trich_am_thanh(tmp_path):
    """Chạy THẬT trên một video dựng tại chỗ — đây là loại lỗi mà đọc mã
    không đủ, phải chạy mới biết tệp có ra hay không."""
    from autodub.nhap_phu_de import nhap_du_an

    video = tmp_path / "thu.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
         "sine=frequency=440:duration=6", "-f", "lavfi", "-i",
         "color=c=black:s=160x120:d=6", "-shortest", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", "-c:a", "aac", str(video), "-y"], check=True)
    (tmp_path / "thu.srt").write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nXin chào.\n\n"
        "2\n00:00:03,500 --> 00:00:05,000\nCâu hai.\n",
        encoding="utf-8")

    ra = nhap_du_an(str(video), str(tmp_path / "thu.srt"), str(tmp_path / "out"))
    data = os.path.join(ra.thu_muc, "data")

    bao_cao = json.load(open(os.path.join(data, "report.json"), encoding="utf-8"))
    assert bao_cao["total_original_duration"] > 5, (
        "không đo được độ dài — Trình chỉnh sửa sẽ hiện 00:00")
    assert bao_cao["source_language"] == "vi", "không ghi ngôn ngữ gốc"
    assert bao_cao["total_segments"] == 2

    wav = os.path.join(data, "original_audio.wav")
    assert os.path.isfile(wav), (
        "không trích âm thanh — thanh thời gian sẽ báo 'Không đọc được dạng sóng'")
    with wave.open(wav, "rb") as f:
        assert f.getnframes() > 0, "tệp âm thanh rỗng"


def test_bao_cao_khong_bia_so_da_xu_ly():
    """Dự án nhập vào chưa từng chạy — bịa số Vox hay thời gian xử lý là nói
    dối người dùng về việc chưa xảy ra."""
    src = _doc("autodub/nhap_phu_de.py")
    i = src.index('"report.json"')
    khoi = src[i:i + 700]
    for cam in ("processing_time_seconds", "total_vox", "vox"):
        assert cam not in khoi, f"báo cáo dựng sẵn có bịa trường {cam!r}"


def test_thieu_am_thanh_khong_chan_viec_sua():
    """Trích trượt thì vẫn nhập được — chỉ mất dạng sóng, không mất dự án."""
    src = _doc("autodub/nhap_phu_de.py")
    for nut in ast.walk(ast.parse(src)):
        if isinstance(nut, ast.FunctionDef) and nut.name == "nhap_du_an":
            than = ast.get_source_segment(src, nut) or ""
            break
    else:
        raise AssertionError("không còn hàm nhap_du_an")
    i = than.index("extract_audio")
    sau = than[i:]
    assert "except Exception" in sau and "logger.warning" in sau, (
        "trích âm thanh trượt là hỏng cả lượt nhập, hoặc hỏng mà không nói")
    assert "canh_bao.append" in sau, "không báo cho người dùng biết thiếu gì"
