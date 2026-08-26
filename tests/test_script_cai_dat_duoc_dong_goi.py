"""Script cài đặt nào app bảo người dùng chạy thì phải có trong bản phát hành.

Lỗi thật, chủ dự án phát hiện bằng ảnh chụp thư mục (26/08/2026): mở
`VoxDub-Studio-v3.10.0-win64/scripts/` ra chỉ thấy 6 tệp `setup_*`, không có
`setup_translate_local.py` — đúng tệp vừa được bảo phải chạy để bật dịch ngoại
tuyến. Danh sách đóng gói trong `build_exe.py` là một danh sách GÕ TAY, và nó
đã lệch khỏi mã từ lâu.

Hậu quả: dịch ngoại tuyến, phân biệt người nói, lipsync, OCR và ghi danh giọng
**chưa bao giờ cài được từ một bản tải nào**. Không có dòng lỗi nào — app chỉ
bảo "chạy scripts/setup_X.py" còn tệp thì không tồn tại.

Đây là lớp lỗi #3 của dự án (FEATURES.md §6) tái diễn: cùng cơ chế đã khiến
`asr_whisper_worker.py` không được đóng gói và chép lời trong bản .exe chưa
từng chạy được lần nào (V80). Bài học đã ghi ở đó: **suy ra, đừng gõ tay** —
và phải có test canh, vì tài liệu không chặn được lỗi kiểu này.
"""
from __future__ import annotations

import importlib.util
import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def se_dong_goi() -> set[str]:
    spec = importlib.util.spec_from_file_location(
        "_be", os.path.join(REPO, "scripts", "build_exe.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return set(mod.scripts_can_dong_goi())


def _script_app_bao_chay() -> dict[str, str]:
    """{tên script: nơi nhắc} — quét mọi chuỗi `scripts/setup_*.py` trong mã.

    Quét cả chú thích lẫn chuỗi: một câu log bảo người dùng chạy tệp cũng là
    một lời hứa tệp đó có mặt.
    """
    ra: dict[str, str] = {}
    for goc in ("autodub", "autodub_gui"):
        for thu, _d, tep in os.walk(os.path.join(REPO, goc)):
            if any(x in thu for x in (".venv", "__pycache__")):
                continue
            for f in tep:
                if not f.endswith(".py"):
                    continue
                duong = os.path.join(thu, f)
                src = open(duong, encoding="utf-8").read()
                for ten in re.findall(r"scripts[/\\](setup_[a-z_]+\.py)", src):
                    ra.setdefault(ten, os.path.relpath(duong, REPO))
    return ra


def test_moi_script_app_nhac_deu_co_that(se_dong_goi):
    """Nhắc một tệp không tồn tại là gửi người dùng đi tìm hư không."""
    thieu = {t: o for t, o in _script_app_bao_chay().items()
             if not os.path.isfile(os.path.join(REPO, "scripts", t))}
    assert not thieu, f"app nhắc script không có trong kho: {thieu}"


def test_moi_script_app_nhac_deu_duoc_dong_goi(se_dong_goi):
    """Chốt chính: có trong kho là chưa đủ — phải có trong bản người dùng tải."""
    thieu = {t: o for t, o in _script_app_bao_chay().items()
             if t not in se_dong_goi}
    assert not thieu, (
        "app bảo người dùng chạy các script này nhưng bản phát hành không "
        f"chứa chúng — tính năng chết âm thầm: {thieu}")


def test_module_dung_chung_di_kem(se_dong_goi):
    """Thiếu nó thì mọi script trên chết ngay dòng import (bài học V80)."""
    assert "_python_ho_tro.py" in se_dong_goi


def test_danh_sach_duoc_suy_ra_chu_khong_go_tay():
    """Danh sách gõ tay là thứ đã gây ra chính lỗi này. Nếu ai đó quay lại
    gõ tay, test này đỏ trước khi bản phát hành kịp thiếu tệp."""
    src = open(os.path.join(REPO, "scripts", "build_exe.py"),
               encoding="utf-8").read()
    i = src.index("def scripts_can_dong_goi")
    than = src[i:src.index("\ndef ", i + 10)]
    assert "os.listdir" in than, "danh sách đóng gói lại được gõ tay"
    # Đếm số tên tệp gõ thẳng trong hàm: chỉ được phép đúng một
    # (`_python_ho_tro.py`, không khớp mẫu setup_*).
    go_tay = re.findall(r'"(setup_[a-z_]+\.py)"', than)
    assert not go_tay, f"vẫn còn tên gõ thẳng trong danh sách: {go_tay}"
