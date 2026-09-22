"""Bản chỉ đạo hình ảnh phía máy khách — MINI-SPEC I3.

Chỗ dễ nói sai nhất của I3 nằm ở đây, không phải ở máy chủ: máy chủ trả về
đúng cờ `laGoiY` cho từng mã, nhưng nếu giao diện trình bày hai loại giống
nhau thì người dùng vẫn hiểu rằng máy sắp tự dựng tất cả — và đó chính là
hứa thứ không làm được (lớp lỗi #5 của dự án).

Ba điều tệp này canh:

1. **Phân biệt được bằng CHỮ**, không chỉ bằng màu — màu không đọc được bằng
   test, không đọc được khi in ra, không đọc được với người mù màu.
2. **Nói thẳng tỉ lệ** ngay đầu bản, kèm câu "trang Dựng video chưa đọc tới".
3. **Không có nút «Áp dụng»/«Render»/«Sinh ảnh»** — luồng dựng chưa đọc bản
   chỉ đạo (việc của I5), nên một cái nút như vậy là lời hứa suông.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.chi_dao_text import (
    NHAN_GOI_Y, NHAN_MAY_DUNG, cau_trang_thai, cau_ty_le, dong_cho_doan,
    mo_ta_loai, nhan_muc,
)

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


BAN_MAU = {
    "catalogVersion": 2,
    "soGoiY": 4,
    "soMayDungDuoc": 2,
    "laCu": False,
    "doan": [
        {"thuTu": 1,
         "chon": [
             {"nhom": "shot", "ma": "can_canh", "nhan": "Cận cảnh", "laGoiY": True},
             {"nhom": "transition", "ma": "fade_nhe", "nhan": "Mờ chồng nhẹ",
              "laGoiY": False},
         ],
         "lyDo": "Cận cảnh cho thấy rõ sản phẩm ngay câu mở đầu."},
        {"thuTu": 2, "chon": [], "lyDo": ""},
    ],
}


# -- 1. Phân biệt hai loại ---------------------------------------------------

def test_hai_loai_phan_biet_duoc_bang_CHU():
    goi_y = nhan_muc(BAN_MAU["doan"][0]["chon"][0])
    may = nhan_muc(BAN_MAU["doan"][0]["chon"][1])
    assert goi_y != may
    assert NHAN_GOI_Y in goi_y and NHAN_MAY_DUNG in may
    # Và không được dùng CHUNG một câu giải thích.
    assert (mo_ta_loai(BAN_MAU["doan"][0]["chon"][0])
            != mo_ta_loai(BAN_MAU["doan"][0]["chon"][1]))


def test_muc_goi_y_noi_ro_may_KHONG_tu_lam_duoc():
    mo_ta = mo_ta_loai({"laGoiY": True})
    assert "không tự làm được" in mo_ta


def test_thieu_co_thi_coi_la_GOI_Y_chu_khong_phai_may_dung_duoc():
    """Mặc định phải nghiêng về phía nói ít hơn khả năng, không nhiều hơn."""
    assert NHAN_GOI_Y in nhan_muc({"ma": "x", "nhan": "X"})
    assert "không tự làm được" in mo_ta_loai({})


# -- 2. Nói thẳng tỉ lệ ------------------------------------------------------

def test_cau_dau_ban_noi_ro_TY_LE_va_gioi_han():
    cau = cau_ty_le(BAN_MAU)
    assert "4/6" in cau, "không nói ra có bao nhiêu mục chỉ là gợi ý"
    assert "2/6" in cau
    assert "CHƯA đọc tới" in cau, (
        "phải nói rõ luồng Dựng video chưa dùng bản chỉ đạo — nếu không, "
        "người dùng tưởng chọn xong là video tự đổi")
    assert "không tự áp" in cau


def test_ban_rong_khong_noi_lap_lung():
    cau = cau_ty_le({"soGoiY": 0, "soMayDungDuoc": 0})
    assert "chưa chọn mục nào" in cau


# -- 3. Bản cũ ---------------------------------------------------------------

def test_ban_con_moi_thi_KHONG_bia_ra_canh_bao():
    assert cau_trang_thai(BAN_MAU) == ""


@pytest.mark.parametrize("ban,phai_co", [
    ({"laCu": True, "kichBanDaDoi": True, "catalogDaDoi": False},
     "kịch bản đã đổi lời"),
    ({"laCu": True, "kichBanDaDoi": False, "catalogDaDoi": True,
      "catalogVersionHienTai": 2}, "từ điển chỉ đạo đã lên phiên bản 2"),
])
def test_ban_cu_noi_dung_ly_do_va_noi_ro_chay_lai_ton_tien(ban, phai_co):
    cau = cau_trang_thai(ban)
    assert phai_co in cau
    assert "tính thêm một lượt" in cau, (
        "máy chủ cố ý KHÔNG tự chạy lại; câu chữ phải nói rõ bấm lại là tốn "
        "tiền, không được úp mở")
    assert "vẫn đọc được" in cau, "không được doạ người dùng là mất dữ liệu"


# -- 4. Từng đoạn ------------------------------------------------------------

def test_doan_khong_chon_gi_van_noi_ra_chu_khong_de_trong():
    dong = dong_cho_doan(BAN_MAU["doan"][1])
    assert dong and "Không chọn mục nào" in dong[0]


def test_moi_doan_hien_ca_ly_do():
    dong = dong_cho_doan(BAN_MAU["doan"][0])
    assert any(d.startswith("Vì sao:") for d in dong)


# -- 5. Hộp thoại ------------------------------------------------------------

def test_hop_thoai_hien_du_chu_va_KHONG_co_nut_hua_render(qapp):
    from PySide6.QtWidgets import QAbstractButton

    from autodub_gui.ui.chi_dao_dialog import ChiDaoHinhAnhDialog

    hop = ChiDaoHinhAnhDialog(BAN_MAU)
    chu = hop.chu_hien_ra()
    assert "4/6" in chu
    assert NHAN_GOI_Y in chu and NHAN_MAY_DUNG in chu
    assert "Cận cảnh cho thấy rõ sản phẩm" in chu

    nhan_nut = [b.text() for b in hop.findChildren(QAbstractButton)]
    assert nhan_nut == ["Đóng"], (
        f"hộp thoại chỉ được có nút Đóng, đang có {nhan_nut}")
    for cam in ("áp dụng", "render", "sinh ảnh", "dựng video", "xuất video"):
        assert not any(cam in n.lower() for n in nhan_nut), (
            f"có nút «{cam}» — luồng dựng CHƯA đọc bản chỉ đạo (việc của I5), "
            "nút đó là lời hứa suông")


def test_hop_thoai_ban_cu_hien_canh_bao(qapp):
    from autodub_gui.ui.chi_dao_dialog import ChiDaoHinhAnhDialog

    ban = dict(BAN_MAU, laCu=True, kichBanDaDoi=True, catalogDaDoi=False)
    assert "đã cũ" in ChiDaoHinhAnhDialog(ban).chu_hien_ra()


# -- 6. Máy khách ------------------------------------------------------------

def test_client_goi_dung_cua_va_KHONG_tu_suy_co_goi_y(monkeypatch):
    """App không được tự tính `laGoiY` — cờ đó do máy chủ tính từ từ điển."""
    from autodub.saas_client import SaasClient

    da_goi = {}

    def gia(self, method, path, **kw):
        da_goi["method"] = method
        da_goi["path"] = path
        da_goi["body"] = kw.get("json_body")
        return {"id": "kb1", "doan": [], "soGoiY": 0, "soMayDungDuoc": 0}

    monkeypatch.setattr(SaasClient, "_request", gia)
    # `_note_usage` đụng khoá của instance thật; ở đây chỉ kiểm phần gửi đi.
    monkeypatch.setattr(SaasClient, "_note_usage", lambda self, data: None)
    c = SaasClient.__new__(SaasClient)
    c.tao_chi_dao_hinh_anh("kb1", job_id="job-12345678")

    assert da_goi["method"] == "POST"
    assert da_goi["path"] == "/v1/brand-scripts/kb1/visual-direction"
    assert da_goi["body"] == {"jobId": "job-12345678"}, (
        "app không được gửi thêm gì — vốn từ và cờ gợi ý là chuyện của máy chủ")


def test_client_chua_co_ban_thi_tra_None_chu_khong_nem(monkeypatch):
    from autodub.saas_client import SaasClient, SaasError

    def gia(self, method, path, **kw):
        raise SaasError("chưa có", code="CHUA_CO_CHI_DAO", status=404)

    monkeypatch.setattr(SaasClient, "_request", gia)
    c = SaasClient.__new__(SaasClient)
    assert c.doc_chi_dao_hinh_anh("kb1") is None


def test_client_loi_KHAC_thi_van_nem(monkeypatch):
    """Nuốt mọi lỗi thành None là hiện «chưa có bản nào» cho một máy chủ hỏng."""
    from autodub.saas_client import SaasClient, SaasError

    def gia(self, method, path, **kw):
        raise SaasError("mạng đứt", code="OFFLINE", status=0)

    monkeypatch.setattr(SaasClient, "_request", gia)
    c = SaasClient.__new__(SaasClient)
    with pytest.raises(SaasError):
        c.doc_chi_dao_hinh_anh("kb1")
