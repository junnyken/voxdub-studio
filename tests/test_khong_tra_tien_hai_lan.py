"""Giá đã chốt theo đường ngoại tuyến thì không được gọi máy chủ dịch.

Lỗi thật, đọc ra từ nhật ký của người dùng 26/08/2026:

    14:17  Bạn chọn dịch ngoại tuyến — không tính phí dịch cho lượt này
    14:17  Video này tốn 250 Vox (23 câu thoại) — ví còn 2,670 Vox
    14:21  Dùng lại lượt đã trả phí của lần chạy trước (250 Vox)
    14:21  Đang dịch 23 câu qua VoxDub Cloud
    14:21  Lượt dịch này tốn 276 Vox (còn lại 2,394)

Giá của video chốt MỘT LẦN sau bước nghe-chép và không đổi nữa. Lượt đó chốt
250 Vox theo đường ngoại tuyến — tức KHÔNG kê phần phí dịch. Nhưng lượt chạy
sau lại dịch qua máy chủ, và phần đó bị trừ NGOÀI khoản đã chốt: 276 Vox nữa
cho cùng một video.

Người dùng được báo giá 250 rồi mất 526. Đúng lớp lỗi #5 (câu chữ về tiền
lệch khỏi việc mã thật sự làm), lần này là chính bản D1 của tôi tạo ra.
"""
from __future__ import annotations

import ast
import json
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _than(ten_ham: str) -> str:
    nguon = open(os.path.join(REPO, "autodub", "pipeline.py"),
                 encoding="utf-8").read()
    for nut in ast.walk(ast.parse(nguon)):
        if isinstance(nut, ast.FunctionDef) and nut.name == ten_ham:
            return ast.get_source_segment(nguon, nut) or ""
    raise AssertionError(f"pipeline.py không còn {ten_ham}")


def test_ghi_lai_duong_dich_luc_chot_gia():
    than = _than("_run_impl")
    assert "duong_dich_da_chot.json" in than, (
        "không ghi lại đường dịch đã dùng để chốt giá — lượt sau không có gì "
        "để đối chiếu")
    assert than.index("duong_dich_da_chot") < than.index("_setup_hold("), \
        "ghi dấu sau khi giữ chỗ thì lượt chạy đầu đã kịp lệch"


def test_chan_goi_may_chu_khi_gia_chot_theo_ngoai_tuyen():
    than = _than("_auto_translate")
    assert "duong_dich_da_chot.json" in than, (
        "đường dịch qua máy chủ không hề kiểm giá đã chốt theo cách nào")
    i = than.index("duong_dich_da_chot")
    j = than.index("translate_segments(")
    assert i < j, "kiểm SAU khi đã gọi máy chủ thì tiền đã mất rồi"
    khoi = than[i:j]
    assert "return None" in khoi, "phát hiện lệch mà vẫn chạy tiếp"
    assert "logger.error" in khoi, "dừng mà không nói vì sao"


def test_loi_noi_ro_hai_cach_chua():
    than = _than("_auto_translate")
    i = than.index("duong_dich_da_chot")
    khoi = than[i:i + 1600]
    assert "Luôn ngoại tuyến" in khoi, "không chỉ cách quay lại đường miễn phí"
    assert "dự án mới" in khoi, "không chỉ cách chốt lại giá theo máy chủ"


def test_dau_khong_doc_duoc_thi_khong_chan_oan(tmp_path):
    """Thư mục cũ (trước bản này) không có dấu — không được chặn oan."""
    than = _than("_auto_translate")
    i = than.index("duong_dich_da_chot")
    khoi = than[i:i + 900]
    assert "except (OSError, ValueError)" in khoi, (
        "thiếu dấu hoặc dấu hỏng phải coi như không có, không phải chặn")
    assert 'da_chot.get("khong_tinh_phi_dich")' in khoi, (
        "phải chặn theo đúng cờ, không phải chỉ cần tệp tồn tại")
