"""Lỗi máy chủ phải nói ĐÚNG chuyện gì xảy ra.

Lỗi thật chủ dự án gặp ngày 10/09/2026 khi lưu hồ sơ brand đầu tiên: hộp thoại
báo "Kiểm tra kết nối mạng rồi thử lại" trong khi mạng đang tốt. Câu đó được
gắn CỨNG cho mọi loại hỏng — hết hạn đăng nhập, dữ liệu sai, thiết bị bị khoá
đều ra cùng một câu — còn nguyên nhân thật thì nằm sau nút «Chi tiết».

Hỏng kiểu này tệ hơn một câu kỹ thuật khó đọc: nó **dẫn người dùng đi sửa
nhầm chỗ**. Họ kiểm mạng, đổi wifi, thử lại, và không lần nào tới gần nguyên
nhân.
"""
from __future__ import annotations

import pytest

from autodub_gui.dub_constants import friendly_server_error


# ------------------------------------------------- nói đúng nguyên nhân ----

@pytest.mark.parametrize("thong_bao, phai_co", [
    ('{"code":"BAD_TOKEN","message":"Token không hợp lệ."}', "Cài đặt"),
    ("HTTP 401: Unauthorized", "Cài đặt"),
    ("Tính năng này cần tài khoản VoxDub", "Cài đặt"),
    ("FST_ERR_VALIDATION: body/tenBrand", "Chi tiết"),
    ("body must have required property 'rangBuocKhongDuocNoi'", "Chi tiết"),
    ("body/usp must NOT have more than 1000 characters", "Chi tiết"),
    ("Thiết bị này đã bị khóa", "hỗ trợ"),
    ("Máy chủ đang bảo trì", "bảo trì"),
    ("Không đủ Vox. Cần 12, bạn có 3.", "Vox"),
    ("DAILY_LIMIT: hết lượt", "ngày mai"),
])
def test_noi_dung_nguyen_nhan(thong_bao, phai_co):
    ra = friendly_server_error(thong_bao)
    assert phai_co in ra, f"«{thong_bao[:40]}» ra câu không dẫn tới việc cần làm"


@pytest.mark.parametrize("thong_bao", [
    '{"code":"BAD_TOKEN","message":"Token không hợp lệ."}',
    "HTTP 401: Unauthorized",
    "FST_ERR_VALIDATION: body/tenBrand",
    "Thiết bị này đã bị khóa",
    "Máy chủ đang bảo trì",
    "Không đủ Vox. Cần 12, bạn có 3.",
])
def test_KHONG_do_cho_mang_khi_khong_phai_loi_mang(thong_bao):
    """Chốt chính của tệp này.

    Sáu nguyên nhân trên không có cái nào liên quan tới đường truyền. Nói
    "kiểm tra kết nối mạng" ở đây là chỉ sai đường — và đó đúng là lỗi đã xảy
    ra thật.
    """
    ra = friendly_server_error(thong_bao).lower()
    assert "kết nối mạng" not in ra, f"vẫn đổ cho mạng: {ra}"
    assert "kiểm tra mạng" not in ra


# --------------------------------------------- ca THẬT SỰ là lỗi mạng ------

@pytest.mark.parametrize("thong_bao", [
    "Không kết nối được máy chủ",
    "Read timed out",
    "connection timeout after 30s",
])
def test_dung_la_loi_mang_thi_van_duoc_noi_the(thong_bao):
    ra = friendly_server_error(thong_bao).lower()
    assert "mạng" in ra or "chậm" in ra


# ------------------------------------------------ không nhận ra thì sao ----

def test_khong_nhan_ra_thi_TRA_LAI_NGUYEN_VAN_khong_doan_bua():
    la = "ECONNRESET while reading upstream from pool 7"
    assert friendly_server_error(la) == la, (
        "đoán bừa nguyên nhân còn tệ hơn hiện nguyên văn khó đọc")


def test_thong_bao_rong_van_ra_mot_cau_dung():
    for rong in ("", "   ", None):
        ra = friendly_server_error(rong)
        assert ra and "không rõ nguyên nhân" in ra


# ------------------------------------------------------- chốt hồi quy ------

def test_trang_Ho_so_Brand_hien_dung_nguyen_nhan_len_hop_thoai(monkeypatch):
    """Hồi quy cho đúng lỗi chủ dự án gặp ngày 10/09.

    Kiểm HÀNH VI, không quét mã: bản đầu của test này chỉ tìm chữ
    `friendly_server_error` trong thân hàm, nên khi tôi cố tình phá phần thân
    mà dòng `import` còn sót lại thì test vẫn xanh — một test không đỏ được
    khi mã hỏng thì không bảo vệ gì cả.
    """
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from autodub_gui.pages import brand_profile_page as bpp

    QApplication.instance() or QApplication([])
    thay = {}
    monkeypatch.setattr(
        bpp.ConfirmDialog, "show_error",
        staticmethod(lambda _p, tieu_de, loi, detail="": thay.update(
            tieu_de=tieu_de, loi=loi, detail=detail)))

    trang = bpp.BrandProfilePage.__new__(bpp.BrandProfilePage)

    class _NhatKyGia:
        def append_log(self, *a, **k):
            pass

    trang.log = _NhatKyGia()
    bpp.BrandProfilePage._on_worker_failed(
        trang, "create", '{"code":"BAD_TOKEN","message":"Token không hợp lệ."}')

    assert "kết nối mạng" not in thay["loi"].lower(), (
        "hết hạn đăng nhập mà vẫn bảo người dùng đi kiểm mạng")
    assert "Cài đặt" in thay["loi"], "phải chỉ đúng chỗ cần mở"
    # Nguyên văn vẫn phải giữ ở «Chi tiết» — câu dễ đọc KHÔNG được thay thế
    # bằng chứng kỹ thuật, vì lúc đi báo lỗi thì cần đúng chuỗi gốc.
    assert "BAD_TOKEN" in thay["detail"]
