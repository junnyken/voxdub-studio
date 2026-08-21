"""C8 — bộ canh cho chính bộ canh đọc mã.

Bốn phép kiểm dưới đây tương ứng ĐÚNG bốn kiểu hỏng đã mắc trong một ngày khi
viết test đọc mã nguồn bằng cách tìm chuỗi. Nếu `doc_ma` hỏng thì mọi test
đứng trên nó đều xanh giả, nên nó phải có test riêng.
"""
from __future__ import annotations

from tests.doc_ma import cac_luot_goi, co_goi, goi_truoc


def _mau_co_chu_thich():
    # gọi kiem_tra() trong chú thích — KHÔNG được tính
    thong_bao = "nhớ gọi kiem_tra() nhé"   # trong chuỗi — cũng không tính
    return thong_bao


def _mau_goi_that():
    a = len("x")
    b = str(a)
    return b


def _mau_thu_tu():
    _mau_goi_that()
    _mau_co_chu_thich()


def kiem_tra():
    """Hàm cùng tên với thứ đang tìm — dòng `def` không được tính là lượt gọi."""
    return True


def _mau_goi_chinh_no():
    return kiem_tra()


def test_kieu_hong_1_thieu_mot_ve_thi_KHONG_coi_la_dung():
    """`indexOf(a) < indexOf(b)` vẫn đúng khi `a` vắng mặt — đây là chỗ đó."""
    assert goi_truoc(_mau_thu_tu, "_mau_goi_that", "_mau_co_chu_thich")
    assert not goi_truoc(_mau_thu_tu, "khong_he_co", "_mau_co_chu_thich")
    assert not goi_truoc(_mau_thu_tu, "_mau_goi_that", "khong_he_co")


def test_kieu_hong_2_chu_trong_chu_thich_va_chuoi_khong_tinh():
    assert not co_goi(_mau_co_chu_thich, "kiem_tra")


def test_kieu_hong_3_khong_doc_lay_sang_ham_sau():
    """Cắt bằng `inspect.getsource` nên chỉ có đúng một hàm."""
    assert cac_luot_goi(_mau_goi_that) == ["len", "str"]


def test_kieu_hong_4_dong_def_cung_ten_khong_tinh_la_luot_goi():
    assert co_goi(_mau_goi_chinh_no, "kiem_tra")
    # Bản thân `kiem_tra` không gọi `kiem_tra`.
    assert not co_goi(kiem_tra, "kiem_tra")


def test_nhan_ra_luot_goi_co_ten_mo_dun():
    def _mau():
        import os
        return os.path.join("a", "b")

    assert co_goi(_mau, "join")
    assert "os.path.join" in cac_luot_goi(_mau)
