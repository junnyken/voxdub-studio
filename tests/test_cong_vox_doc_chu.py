"""Hỏi trước khi đọc chữ vượt 50 Vox — H2b.

Lượt chạy thật 11/09/2026 (`youtube.com/shorts/9iB1Io8InXg`, ~34 giây): 65
khung cần đọc = 11 lô = **88 Vox**, tiêu hết rồi mới hỏng ở bước cuối. Màn
hình lúc đó hứa "khoảng 32 Vox" và không có chỗ nào hỏi.

Số khung biết được TRƯỚC lượt gọi đầu tiên (`chia_doan` chạy xong là biết),
nên chỗ này hỏi được mà không cần đoán.

Cổng nằm ở TẦNG HÀM, không ở giao diện: đường CLI và script cũng tiêu đúng
số tiền đó. Hàm nhận `xin_phep` — không truyền thì chạy như cũ, để 2.700 test
sẵn có và mọi đường gọi nội bộ không đổi hành vi.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from autodub.media import doc_chu_may_chu as m


class _Khach:
    """Máy chủ giả — đếm số lô đã gửi đi."""

    def __init__(self):
        self.so_lo = 0

    def assist(self, *a, **kw):
        self.so_lo += 1
        return []


@pytest.fixture
def quan_sat_65(monkeypatch):
    monkeypatch.setattr(m, "chia_doan", lambda _q: [[i] for i in range(65)])
    return [{"frame": i} for i in range(65)]


@pytest.fixture
def quan_sat_12(monkeypatch):
    monkeypatch.setattr(m, "chia_doan", lambda _q: [[i] for i in range(12)])
    return [{"frame": i} for i in range(12)]


def _duong_dan(n, tmp_path):
    return [str(tmp_path / f"{i}.jpg") for i in range(n)]


def test_nguong_la_50_vox():
    assert m.NGUONG_XIN_PHEP_VOX == 50


def test_vuot_nguong_thi_hoi_truoc_khi_gui_lo_nao(quan_sat_65, tmp_path):
    """Hỏi phải xảy ra TRƯỚC lô đầu tiên, không phải sau.

    Hỏi sau khi đã gửi vài lô là hỏi về số tiền đã tiêu — không còn là xin
    phép nữa.
    """
    khach = _Khach()
    da_hoi = []

    def xin_phep(so_vox, so_khung):
        da_hoi.append((so_vox, so_khung, khach.so_lo))
        return False

    with patch.object(m, "_anh_gui_di", return_value={"data": "x"}):
        m.doc_lai_bang_may_chu(quan_sat_65, _duong_dan(65, tmp_path),
                               client=khach, xin_phep=xin_phep)

    assert da_hoi == [(88, 65, 0)], (
        f"phải hỏi đúng một lần, với số Vox và số khung THẬT, trước lô nào "
        f"cả. Thực tế: {da_hoi}")


def test_tu_choi_thi_khong_gui_lo_nao(quan_sat_65, tmp_path):
    khach = _Khach()
    with patch.object(m, "_anh_gui_di", return_value={"data": "x"}):
        ra = m.doc_lai_bang_may_chu(quan_sat_65, _duong_dan(65, tmp_path),
                                    client=khach, xin_phep=lambda v, k: False)
    assert khach.so_lo == 0, "từ chối rồi vẫn tiêu tiền"
    assert ra == quan_sat_65, (
        "từ chối phải trả về bản đọc CỤC BỘ, không phải rỗng — chữ mất dấu "
        "vẫn phân tích cấu trúc được, y như ca chưa cấu hình máy chủ")


def test_dong_y_thi_chay_het(quan_sat_65, tmp_path):
    khach = _Khach()
    with patch.object(m, "_anh_gui_di", return_value={"data": "x"}):
        m.doc_lai_bang_may_chu(quan_sat_65, _duong_dan(65, tmp_path),
                               client=khach, xin_phep=lambda v, k: True)
    assert khach.so_lo == 11


def test_duoi_nguong_thi_khong_hoi(quan_sat_12, tmp_path):
    """12 khung = 2 lô = 16 Vox — dưới 50, chạy thẳng.

    Hỏi mọi lượt là dạy người dùng bấm Đồng ý theo phản xạ, rồi lượt 88 Vox
    cũng trôi qua y như vậy.
    """
    khach = _Khach()
    da_hoi = []
    with patch.object(m, "_anh_gui_di", return_value={"data": "x"}):
        m.doc_lai_bang_may_chu(quan_sat_12, _duong_dan(12, tmp_path),
                               client=khach,
                               xin_phep=lambda v, k: da_hoi.append(v) or True)
    assert da_hoi == []
    assert khach.so_lo == 2


def test_khong_truyen_xin_phep_thi_chay_nhu_cu(quan_sat_65, tmp_path):
    """Đường gọi cũ không đổi hành vi — 2.700 test sẵn có phụ thuộc điều này."""
    khach = _Khach()
    with patch.object(m, "_anh_gui_di", return_value={"data": "x"}):
        m.doc_lai_bang_may_chu(quan_sat_65, _duong_dan(65, tmp_path),
                               client=khach)
    assert khach.so_lo == 11


def test_xin_phep_nem_loi_thi_coi_nhu_tu_choi(quan_sat_65, tmp_path):
    """Hộp thoại hỏng không được biến thành 88 Vox tiêu âm thầm."""
    khach = _Khach()

    def no(so_vox, so_khung):
        raise RuntimeError("không dựng được hộp thoại")

    with patch.object(m, "_anh_gui_di", return_value={"data": "x"}):
        ra = m.doc_lai_bang_may_chu(quan_sat_65, _duong_dan(65, tmp_path),
                                    client=khach, xin_phep=no)
    assert khach.so_lo == 0
    assert ra == quan_sat_65
