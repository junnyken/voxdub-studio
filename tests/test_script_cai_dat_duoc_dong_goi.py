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


# --- Tầng thứ hai: có tệp .py thôi chưa đủ ------------------------------
#
# 26/8/2026, ngay sau khi vá phần trên: chủ dự án mở thư mục bản v3.10.2 ra,
# thấy 6 tệp cài đặt đúp-chuột mà không tệp nào nói về tách giọng người nói
# hay dịch ngoại tuyến, rồi hỏi "hình như nó chưa có hả ta". Tệp `.py` đã
# nằm trong `scripts/` — nhưng người dùng không đọc thư mục `scripts/`, họ
# đọc mấy tệp đúp-chuột-là-chạy ở thư mục gốc.
#
# Danh sách `.bat` cũng là một danh sách gõ tay, và cũng đã bỏ quên hai lần
# trước: FFmpeg (V82) và Demucs (V86). Ba lần cùng một cơ chế.


@pytest.fixture(scope="module")
def bat_se_sinh():
    spec = importlib.util.spec_from_file_location(
        "_be2", os.path.join(REPO, "scripts", "build_exe.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_moi_script_cai_dat_deu_co_tep_bat(bat_se_sinh, se_dong_goi):
    """Người dùng không mở thư mục scripts/ ra đọc — họ nhìn mấy tệp .bat ở
    thư mục gốc. Thiếu .bat = tính năng coi như không tồn tại."""
    noi_dung = "\n".join(c for _t, c in bat_se_sinh.cac_bat_can_sinh())
    thieu = []
    for script in se_dong_goi:
        if not script.startswith("setup_"):
            continue
        if script in bat_se_sinh.KHONG_SINH_BAT:
            continue
        if script not in noi_dung:
            thieu.append(script)
    assert not thieu, (
        f"script cài đặt không có tệp .bat để đúp chuột: {thieu}")


def test_bo_qua_bat_phai_kem_ly_do(bat_se_sinh):
    """Danh sách bỏ qua không lý do là cách làm bộ canh im lặng."""
    for ten, ly_do in bat_se_sinh.KHONG_SINH_BAT.items():
        assert os.path.isfile(os.path.join(REPO, "scripts", ten)), ten
        assert len(ly_do) > 30, f"lý do bỏ qua quá sơ sài: {ten}"


def test_ten_tep_bat_khong_dau_va_khong_trung(bat_se_sinh):
    """Tên tệp có dấu tiếng Việt hay trùng nhau đều là rắc rối trên Windows."""
    ten = [t for t, _c in bat_se_sinh.cac_bat_can_sinh()]
    assert len(ten) == len(set(ten)), f"tên .bat bị trùng: {ten}"
    for t in ten:
        assert t.isascii(), f"tên .bat có ký tự ngoài ASCII: {t!r}"
        assert t.endswith(".bat")


def test_bat_chay_tu_thu_muc_goc_app(bat_se_sinh):
    """Thiếu `cd /d "%~dp0"` thì đúp chuột từ nơi khác là sai đường dẫn —
    đúng lỗi chủ dự án gặp khi tự gõ tay (scripts\scripts\...)."""
    for ten, noi in bat_se_sinh.cac_bat_can_sinh():
        assert 'cd /d "%~dp0"' in noi, f"{ten} không tự về thư mục gốc app"
        assert "scripts\\setup_" in noi or "scripts\\" in noi, ten
