"""Tệp `.bat` của script CẦN TOKEN phải hỏi token, không thì đúp chuột vô nghĩa.

Chuyện thật 26/8/2026: người dùng bấm «Cai dat tach giong theo nguoi noi.bat»
ba lần, ba lần nhận cùng một câu *"Thiếu HuggingFace access token… xem hướng
dẫn ở đầu file này (docstring)"*, rồi «Cai dat that bai».

Hai chỗ hỏng chồng nhau:

1. `.bat` chạy script **không tham số** nên không có đường nào truyền token —
   bấm bao nhiêu lần cũng dừng đúng chỗ đó.
2. Câu báo lỗi bảo mở tệp `.py` ra đọc docstring. Với người bấm `.bat` thì đó
   không phải hướng dẫn, đó là ngõ cụt.
"""
from __future__ import annotations

import importlib.util
import os

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _build_exe():
    duong = os.path.join(GOC, "scripts", "build_exe.py")
    spec = importlib.util.spec_from_file_location("build_exe_thu", duong)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_bat_tach_giong_hoi_token_va_truyen_vao():
    bat = _build_exe()._bat_cho("setup_diarization.py")
    assert "set /p HFTOKEN" in bat, "không hỏi token thì đúp chuột luôn thất bại"
    assert "--hf-token %HFTOKEN%" in bat, "hỏi rồi mà không truyền vào script"


def test_bo_trong_token_thi_dung_lai_som():
    bat = _build_exe()._bat_cho("setup_diarization.py")
    assert 'if "%HFTOKEN%"==""' in bat, (
        "bỏ trống mà vẫn chạy tiếp thì lại rơi đúng vào câu lỗi cũ")


def test_bat_chi_dan_ba_trang_can_bam_dong_y():
    """Token hợp lệ vẫn 403 nếu chưa bấm đồng ý — phải nói ra TRƯỚC."""
    bat = _build_exe()._bat_cho("setup_diarization.py")
    for repo in ("speaker-diarization-3.1", "segmentation-3.0",
                 "speaker-diarization-community-1"):
        assert repo in bat, f"thiếu trang {repo}"


def test_script_khac_khong_bi_hoi_token():
    """Chỉ script nào cần mới hỏi — hỏi thừa là dạy người dùng bấm bừa."""
    for script in ("setup_ocr.py", "setup_voices.py", "setup_translate_local.py"):
        assert "HFTOKEN" not in _build_exe()._bat_cho(script), script


def test_cau_bao_thieu_token_noi_ro_cac_buoc():
    nguon = open(os.path.join(GOC, "scripts", "setup_diarization.py"),
                 encoding="utf-8").read()
    khoi = nguon.split("Thiếu HuggingFace access token", 1)[1][:1600]
    assert "huggingface.co/join" in khoi, "không chỉ chỗ tạo tài khoản"
    assert "settings/tokens" in khoi, "không chỉ chỗ tạo token"
    assert "docstring" not in khoi, (
        "vẫn bảo người dùng mở tệp .py ra đọc — đó là ngõ cụt")
