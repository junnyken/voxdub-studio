"""Xoá chữ gốc thay vì làm mờ (mini-spec C51).

Chủ dự án yêu cầu sau khi tôi ghi rằng «vẫn là làm mờ, không xoá thật».

ĐO THẬT trước khi xây, trên một khung hình của video mẫu (vùng chữ 246x51, so
với NỀN GỐC — thứ đáng lẽ hiện ra nếu xoá được thật):

    còn nguyên chữ   lệch 58,98/255
    làm mờ           lệch 52,66      ← gần như không khá hơn để nguyên chữ
    xoá (delogo)     lệch  3,58      ← sát nền thật gấp ~16 lần

Làm mờ chỉ TRỘN chữ với nền thành một vũng mờ; `delogo` nội suy từ viền nên
dựng lại nền. Cả hai đều là bộ lọc có sẵn của ffmpeg — không thêm model, không
thêm dung lượng cài đặt.
"""
from __future__ import annotations

import pytest

from autodub.media.subtitle import (
    CHE_LAM_MO, CHE_XOA, build_filter_complex, che_kieu_cua, delogo_filter,
)

VUNG = {"x": 0.07, "y": 0.91, "w": 0.86, "h": 0.05}
W, H = 576, 1024


def test_mac_dinh_van_la_lam_mo():
    """Đổi mặc định là đổi hình ảnh của mọi dự án đã có — phải do người dùng chọn."""
    chuoi = build_filter_complex([VUNG], W, H)
    assert "boxblur" in chuoi and "delogo" not in chuoi
    assert che_kieu_cua({}, None) == CHE_LAM_MO
    assert che_kieu_cua({}, {"che_kieu": "lam_mo"}) == CHE_LAM_MO


def test_bat_xoa_thi_dung_delogo():
    chuoi = build_filter_complex([VUNG], W, H, style={"che_kieu": "xoa"})
    assert "delogo=" in chuoi and "boxblur" not in chuoi
    assert "[vout]" in chuoi


def test_tung_vung_dat_rieng_duoc_kieu_che():
    """Dải phụ đề mỏng hợp với xoá, mảng lớn nền động thì làm mờ đỡ lộ hơn —
    nên khoá riêng của vùng phải thắng kiểu chung."""
    assert che_kieu_cua({"kieu": "xoa"}, {"che_kieu": "lam_mo"}) == CHE_XOA
    assert che_kieu_cua({"kieu": "lam_mo"}, {"che_kieu": "xoa"}) == CHE_LAM_MO


def test_xoa_van_giu_khoang_thoi_gian_cua_C50():
    vung = dict(VUNG, t_start=870, t_end=1998)
    chuoi = build_filter_complex([vung], W, H, style={"che_kieu": "xoa"})
    assert "enable='between(t,870.0,1998.0)'" in chuoi


def test_vung_sat_mep_khung_duoc_kep_lai():
    """delogo nội suy từ ĐƯỜNG VIỀN quanh vùng — sát mép thì không còn viền."""
    f = delogo_filter(0, 0, W, 40, W, H)
    assert f is not None
    assert "x=1" in f and "y=1" in f
    assert f"w={W - 2}" in f


def test_vung_khong_con_cho_noi_suy_thi_ROI_VE_lam_mo():
    """Che kiểu gì cũng hơn đổ cả lượt xuất video."""
    assert delogo_filter(0, 0, 1, 1, 1, 1) is None
    chuoi = build_filter_complex([{"x": 0, "y": 0, "w": 1.0, "h": 1.0}],
                                 2, 2, style={"che_kieu": "xoa"})
    assert "boxblur" in chuoi


def test_nhieu_vung_moi_vung_mot_nut_loc():
    vungs = [dict(VUNG), dict(VUNG, y=0.05)]
    chuoi = build_filter_complex(vungs, W, H, style={"che_kieu": "xoa"})
    assert chuoi.count("delogo=") == 2


@pytest.mark.parametrize("kieu,mong_doi", [("xoa", "delogo"), ("lam_mo", "boxblur"),
                                           ("gi_do_la", "boxblur")])
def test_kieu_la_thi_ve_lam_mo(kieu, mong_doi):
    chuoi = build_filter_complex([VUNG], W, H, style={"che_kieu": kieu})
    assert mong_doi in chuoi


def test_giao_dien_co_o_chon_va_ghi_vao_kieu():
    pytest.importorskip("PySide6")
    src = open("autodub_gui/style_dialog.py", encoding="utf-8").read()
    assert "chk_xoa_chu" in src
    assert 'self._style["che_kieu"] = "xoa" if bat else "lam_mo"' in src
    assert "thử nghiệm" in src, "phải nói rõ đây là bản thử nghiệm"
    assert "nhiều chi tiết" in src, (
        "tooltip phải nói giới hạn thật: vùng rộng trên nền động sẽ bị kéo nhoè")


def test_kieu_che_nam_trong_style_mac_dinh():
    from autodub.media.subtitle import DEFAULT_STYLE, normalize_style
    assert DEFAULT_STYLE["che_kieu"] == "lam_mo"
    assert normalize_style({})["che_kieu"] == "lam_mo"
    assert normalize_style({"che_kieu": "xoa"})["che_kieu"] == "xoa"
