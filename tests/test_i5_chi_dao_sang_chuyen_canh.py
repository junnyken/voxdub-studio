"""Bản chỉ đạo hình ảnh → kiểu chuyển cảnh từng mối nối — mini-spec I5 §7.

Vì sao tách khỏi `test_h4c1_thoi_luong.py`: tệp kia đo THỜI LƯỢNG bằng ffmpeg
thật (chậm, cần ffmpeg). Tệp này chỉ kiểm phép ánh xạ đoạn→mối nối, chạy được
ở mọi máy và chạy trong mili giây — hai thứ hỏng theo hai cách khác nhau thì
đo bằng hai bộ khác nhau.
"""
from __future__ import annotations

import pytest

from autodub.chi_dao_hinh_anh import (
    ChiDaoDaCu, KIEU_MAC_DINH, kieu_chuyen_theo_moi_noi,
)
from autodub.product_video import KIEU_CHUYEN, _lenh_ghep


def _chon(ma: str, kieu: str | None):
    """Một lựa chọn như máy chủ trả về. `kieu=None` = mã gợi ý, máy không dựng."""
    c = {"nhom": "transition", "ma": ma, "nhan": ma, "laGoiY": kieu is None}
    if kieu is not None:
        c["dung"] = {"implementation": "product_video.ghep_anh_nguoi_dung",
                     "parameters": {"kieu_chuyen": kieu}}
    return c


def _ban(kieu_tung_doan: list[str | None], **them):
    """Bản chỉ đạo giả lập — mỗi phần tử là kiểu của MỘT đoạn (None = bỏ trống)."""
    return {
        "catalogVersion": 2, "laCu": False,
        "doan": [
            {"thuTu": i + 1, "lyDo": f"lý do {i + 1}",
             "chon": [] if k is None else [_chon(f"ma{i}", k)]}
            for i, k in enumerate(kieu_tung_doan)
        ],
        **them,
    }


# ------------------------------------------------ không có bản chỉ đạo ----

def test_khong_co_ban_thi_giu_nguyen_hanh_vi_cu():
    assert kieu_chuyen_theo_moi_noi(None, 3) == (None, [])
    assert kieu_chuyen_theo_moi_noi({}, 3) == (None, [])


def test_ban_khong_co_doan_nao_cung_la_giu_nguyen():
    assert kieu_chuyen_theo_moi_noi({"laCu": False, "doan": []}, 3) == (None, [])


# ------------------------------------------------------- bản đã cũ -------

def test_kich_ban_da_doi_thi_NEM_LOI_khong_dung_bua():
    ban = _ban(["mo_chong", "tan"], laCu=True, kichBanDaDoi=True)
    with pytest.raises(ChiDaoDaCu, match="kịch bản đã sửa"):
        kieu_chuyen_theo_moi_noi(ban, 3)


def test_catalog_da_doi_cung_NEM_LOI():
    ban = _ban(["mo_chong", "tan"], laCu=True, catalogDaDoi=True)
    with pytest.raises(ChiDaoDaCu, match="từ điển chỉ đạo"):
        kieu_chuyen_theo_moi_noi(ban, 3)


# ---------------------------------------------- ánh xạ đoạn → mối nối ----

def test_kieu_cua_doan_la_kieu_DI_VAO_doan_do():
    """3 ảnh = 2 mối. Mối 1 (ảnh1→ảnh2) lấy kiểu đoạn 2; mối 2 lấy đoạn 3.
    Kiểu của đoạn ĐẦU không dùng — không có gì đứng trước nó."""
    ban = _ban(["khong", "tan", "truot_len"])
    kieus, ghi_chu = kieu_chuyen_theo_moi_noi(ban, 3)
    assert kieus == ["tan", "truot_len"]
    assert ghi_chu == []


def test_mot_anh_thi_khong_co_moi_noi_nao():
    assert kieu_chuyen_theo_moi_noi(_ban(["tan"]), 1) == ([], [])


# --------------------------------------------------- số lượng lệch -------

def test_anh_NHIEU_hon_doan_thi_phan_du_dung_kieu_doan_cuoi_VA_noi_ra():
    ban = _ban(["khong", "tan", "mo_vong"])          # 3 đoạn
    kieus, ghi_chu = kieu_chuyen_theo_moi_noi(ban, 5)  # 5 ảnh = 4 mối
    assert kieus == ["tan", "mo_vong", "mo_vong", "mo_vong"]
    assert any("5 ảnh" in c and "3 đoạn" in c for c in ghi_chu), ghi_chu


def test_anh_IT_hon_doan_thi_chi_dung_phan_dau_VA_noi_ra():
    ban = _ban(["khong", "tan", "mo_vong", "truot_trai", "truot_len"])
    kieus, ghi_chu = kieu_chuyen_theo_moi_noi(ban, 2)   # 2 ảnh = 1 mối
    assert kieus == ["tan"]
    assert any("2 ảnh" in c and "5 đoạn" in c for c in ghi_chu), ghi_chu


# ------------------------------------------------- đoạn bỏ trống ---------

def test_doan_bo_trong_dung_mac_dinh_VA_noi_ra_dung_so_doan():
    ban = _ban(["khong", None, "tan"])
    kieus, ghi_chu = kieu_chuyen_theo_moi_noi(ban, 3)
    assert kieus == [KIEU_MAC_DINH, "tan"]
    assert any("Đoạn 2" in c for c in ghi_chu), ghi_chu


def test_ma_GOI_Y_cho_nguoi_cung_tinh_la_bo_trong():
    """Mã `advisory_only` không kèm `dung` — máy không dựng được, nên phải rơi
    về mặc định và NÓI RA, chứ không im lặng bỏ qua cả mối nối."""
    ban = _ban(["khong", "tan"])
    ban["doan"][1]["chon"] = [_chon("rack_focus", None)]
    kieus, ghi_chu = kieu_chuyen_theo_moi_noi(ban, 2)
    assert kieus == [KIEU_MAC_DINH]
    assert any("Đoạn 2" in c for c in ghi_chu), ghi_chu


def test_moi_lan_may_tu_quyet_deu_phai_co_mot_cau_giai_thich():
    """Gộp hai ca tự quyết cùng lúc: ảnh nhiều hơn đoạn VÀ có đoạn bỏ trống."""
    ban = _ban(["khong", None])
    kieus, ghi_chu = kieu_chuyen_theo_moi_noi(ban, 4)
    assert kieus == [KIEU_MAC_DINH] * 3
    assert len(ghi_chu) == 2, ghi_chu


# ----------------------------------------- nối thẳng được vào khâu dựng --

def test_ket_qua_dung_THANG_duoc_cho_khau_ghep_hinh():
    """Chốt đường nối: mọi mã trả ra phải là khoá thật của `KIEU_CHUYEN`, và
    `_lenh_ghep` phải nhận được danh sách đó mà không ném."""
    ban = _ban(["khong", "tan", "mo_vong", "truot_trai"])
    kieus, _ = kieu_chuyen_theo_moi_noi(ban, 4)
    assert all(k in KIEU_CHUYEN for k in kieus), kieus
    lenh = _lenh_ghep(["a.png", "b.png", "c.png", "d.png"], "ra.mp4",
                      [2.0, 1.0, 3.0, 1.5], 0.3, kieus)
    loc = lenh[lenh.index("-filter_complex") + 1]
    assert "xfade=transition=dissolve" in loc      # tan
    assert "xfade=transition=circleopen" in loc    # mo_vong
    assert "xfade=transition=slideleft" in loc     # truot_trai


# -- I6: nếp của thương hiệu là chỗ rơi cho đoạn bỏ trống -------------------

def test_I6_doan_bo_trong_roi_ve_NEP_thuong_hieu(_=None):
    ban = _ban(["khong", None, "tan"])
    ban["nepMacDinh"] = "truot_len"
    kieus, ghi_chu = kieu_chuyen_theo_moi_noi(ban, 3)
    assert kieus == ["truot_len", "tan"]
    assert any("nếp của thương hiệu" in c for c in ghi_chu), ghi_chu


def test_I6_khong_co_nep_thi_van_roi_ve_mo_chong_nhu_truoc():
    ban = _ban(["khong", None, "tan"])
    kieus, ghi_chu = kieu_chuyen_theo_moi_noi(ban, 3)
    assert kieus == [KIEU_MAC_DINH, "tan"]
    assert any("Mờ chồng" in c for c in ghi_chu), ghi_chu


def test_I6_nep_KHONG_de_len_doan_da_co_chi_dao():
    """Nếp là chỗ rơi, không phải lệnh. Đè lên lựa chọn đã có là quyết thay
    người dùng — và xoá luôn thứ họ vừa trả Vox để có."""
    ban = _ban(["khong", "tan", "mo_vong"])
    ban["nepMacDinh"] = "truot_trai"
    kieus, ghi_chu = kieu_chuyen_theo_moi_noi(ban, 3)
    assert kieus == ["tan", "mo_vong"]
    assert ghi_chu == []


def test_I6_nep_rong_hoac_thieu_deu_khong_lam_vo():
    for gia_tri in ("", "   ", None):
        ban = _ban(["khong", None])
        if gia_tri is not None:
            ban["nepMacDinh"] = gia_tri
        kieus, _ = kieu_chuyen_theo_moi_noi(ban, 2)
        assert kieus == [KIEU_MAC_DINH], gia_tri
