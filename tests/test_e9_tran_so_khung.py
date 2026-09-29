"""E9 — trần số khung cho phân tích cấu trúc.

Không có trần thì số khung tỉ lệ thẳng với độ dài video (10 phút = 1.231
khung), mà trích khung + lấy vân tay chạy ĐÚNG số mốc. Chủ dự án gặp thật
28/09/2026: một lượt chạy 562 giây vẫn chưa xong.

Trần chốt bằng đo, không gõ đại — xem `docs/TEST_LOG.md` mục E9 §5.
"""
from __future__ import annotations

import pytest

from autodub.flow_blueprint import (
    GIAY_KHUYEN_NGHI_TOI_DA, GIAY_MOI_KHUNG_DAU_CUOI, GIAY_MOI_KHUNG_GIUA,
    KHOANG_CACH_TOI_DA_DE_GOP_GIAY, KHOANG_DAU_CUOI_GIAY, SO_KHUNG_TOI_DA,
    buoc_giua_thuc_te, gop_quan_sat_lien_tiep, khoang_gop_theo_buoc,
    moc_lay_mau_thich_ung,
)


def _moc_cu(dai: float) -> list[float]:
    """Thuật toán TRƯỚC E9, chép nguyên văn — bản tham chiếu cho rào chắn 1."""
    if dai <= 0:
        return []

    def rai(a, z, b):
        if z <= a or b <= 0:
            return []
        n = int(round((z - a) / b)) + 1
        return [round(a + i * b, 2) for i in range(n) if a + i * b <= z + 1e-9]

    if dai - 2 * KHOANG_DAU_CUOI_GIAY <= 0:
        return sorted(set(rai(0.0, dai, GIAY_MOI_KHUNG_DAU_CUOI)))
    return sorted(set(
        rai(0.0, KHOANG_DAU_CUOI_GIAY, GIAY_MOI_KHUNG_DAU_CUOI)
        + rai(KHOANG_DAU_CUOI_GIAY, dai - KHOANG_DAU_CUOI_GIAY, GIAY_MOI_KHUNG_GIUA)
        + rai(dai - KHOANG_DAU_CUOI_GIAY, dai, GIAY_MOI_KHUNG_DAU_CUOI)))


# ------------------------------------------------ rào chắn 1: vùng cam kết --

@pytest.mark.parametrize("dai", [0.5, 3, 8, 10, 15, 30, 47, 60, 75, 89, 90])
def test_video_trong_vung_CAM_KET_khong_doi_MOT_MOC_nao(dai):
    """H2-MVP cam kết độ phủ đầy đủ tới 90 giây. Trần không được cắn vào đó.

    So TỪNG MỐC chứ không so số lượng: cùng số mốc mà lệch vị trí thì bằng
    chứng vẫn đổi, và phép so theo số lượng sẽ không thấy.
    """
    assert moc_lay_mau_thich_ung(dai) == _moc_cu(dai)


def test_MEP_cam_ket_90s_dung_bang_211_khung():
    """Con số chốt cận dưới của trần — đổi nó là đổi cả lý do chọn 250."""
    assert len(moc_lay_mau_thich_ung(GIAY_KHUYEN_NGHI_TOI_DA)) == 211
    assert SO_KHUNG_TOI_DA >= 211, (
        "trần thấp hơn 211 là cắt vào vùng H2-MVP đã cam kết độ phủ đầy đủ")


# ------------------------------------------------------------ trần có cắn --

@pytest.mark.parametrize("dai", [120, 180, 240, 300, 600, 900, 3600])
def test_khong_bao_gio_vuot_tran(dai):
    assert len(moc_lay_mau_thich_ung(dai)) <= SO_KHUNG_TOI_DA


def test_BANG_CHUNG_PHU_DINH_khong_co_tran_thi_PHINH():
    """Chứng minh trần thật sự là thứ chặn, không phải trùng hợp."""
    assert len(_moc_cu(600)) == 1231
    assert len(moc_lay_mau_thich_ung(600)) <= SO_KHUNG_TOI_DA
    assert len(_moc_cu(600)) > 4 * SO_KHUNG_TOI_DA


# --------------------------------------------- rào chắn 2: hai đầu vẫn dày --

@pytest.mark.parametrize("dai", [300, 600, 900])
def test_hai_dau_van_day_khi_tran_can(dai):
    """Hook ở đầu, kêu gọi hành động ở cuối — thưa hai chỗ đó là hỏng đúng
    thứ tính năng này sinh ra để đọc."""
    moc = moc_lay_mau_thich_ung(dai)
    dau = [t for t in moc if t <= KHOANG_DAU_CUOI_GIAY]
    cuoi = [t for t in moc if t >= dai - KHOANG_DAU_CUOI_GIAY]
    for ten, phan in (("đầu", dau), ("cuối", cuoi)):
        assert len(phan) >= 26, f"{ten} bị thưa còn {len(phan)} mốc"
        assert round(phan[1] - phan[0], 2) == GIAY_MOI_KHUNG_DAU_CUOI


# ------------------------------------- rào chắn 3: rải đều, không cắt đuôi --

@pytest.mark.parametrize("dai", [180, 300, 600])
def test_van_lay_mau_toi_CUOI_video(dai):
    """Cắt đuôi là mất sạch phần cuối — nơi có cao trào và lời kêu gọi."""
    assert moc_lay_mau_thich_ung(dai)[-1] == pytest.approx(dai)


def test_doan_giua_rai_DEU_chu_khong_don_cuc():
    moc = moc_lay_mau_thich_ung(600)
    giua = [t for t in moc
            if KHOANG_DAU_CUOI_GIAY < t < 600 - KHOANG_DAU_CUOI_GIAY]
    buoc = [round(b - a, 2) for a, b in zip(giua, giua[1:])]
    assert max(buoc) - min(buoc) < 0.05, f"bước giữa không đều: {set(buoc)}"


# --------------------------------------------- §4B: khoảng gộp theo bước ---

def test_video_ngan_giu_NGUYEN_khoang_gop_cu():
    for dai in (30, 60, 90):
        assert khoang_gop_theo_buoc(dai) == KHOANG_CACH_TOI_DA_DE_GOP_GIAY


def test_video_dai_thi_khoang_gop_GAP_DOI_buoc_that():
    """Giữ đúng quan hệ đã ghi ở hằng số: gấp đôi bước thưa nhất."""
    for dai in (300, 600):
        assert khoang_gop_theo_buoc(dai) == pytest.approx(
            2 * buoc_giua_thuc_te(dai))


def test_gop_mac_dinh_KHONG_doi_hanh_vi_cu():
    """Mọi lời gọi sẵn có không truyền khoảng gộp phải chạy y như trước."""
    tho = [{"text": "A", "status": "ok", "timestamp_s": t}
           for t in (0.0, 0.5, 1.0)]
    assert len(gop_quan_sat_lien_tiep(tho)) == 1
    xa = [{"text": "A", "status": "ok", "timestamp_s": t} for t in (0.0, 3.0)]
    assert len(gop_quan_sat_lien_tiep(xa)) == 2


def test_khoang_gop_rong_hon_thi_gop_duoc_quan_sat_xa_hon():
    xa = [{"text": "A", "status": "ok", "timestamp_s": t} for t in (0.0, 3.0)]
    assert len(gop_quan_sat_lien_tiep(xa, khoang_gop=6.0)) == 1


def test_khoang_gop_KHONG_bao_gio_hep_hon_hang_cu():
    """Truyền số nhỏ hơn cũng không được làm video ngắn gộp kém đi."""
    tho = [{"text": "A", "status": "ok", "timestamp_s": t} for t in (0.0, 0.9)]
    assert len(gop_quan_sat_lien_tiep(tho, khoang_gop=0.1)) == 1


# ----------------------------------------- §4C: khai đúng mật độ đã dùng ---

def test_chinh_sach_NOI_RA_khi_da_thua():
    from autodub.flow_blueprint import ta_chinh_sach_lay_mau
    noi = ta_chinh_sach_lay_mau(600)
    assert "ĐÃ THƯA" in noi and str(SO_KHUNG_TOI_DA) in noi, (
        "thưa mà vẫn khai mật độ cũ là để mô hình tin quá mức vào bằng chứng "
        "mỏng — tệ hơn cả việc thưa")
    assert f"{buoc_giua_thuc_te(600):.2f}s" in noi


def test_chinh_sach_video_ngan_KHONG_noi_thua():
    from autodub.flow_blueprint import ta_chinh_sach_lay_mau
    assert "ĐÃ THƯA" not in ta_chinh_sach_lay_mau(60)
