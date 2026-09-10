"""Trang Viết kịch bản cho thương hiệu — mini-spec H3.

Trọng tâm là **cửa sang H4**: nút "Dùng kịch bản này" chỉ được sáng khi máy
chủ trả `ready`. Đây là chốt cuối phía giao diện — máy chủ đã chặn rồi, nhưng
một nút sáng lên khi kịch bản chưa sạch là dạy người dùng rằng cảnh báo có
thể bỏ qua, và lần sau họ sẽ bỏ qua thật.

Cùng canh: mỗi lý do "chưa kiểm được" phải ra một câu RIÊNG (gộp thành một
câu chung thì người dùng không biết mình có làm gì được không).
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages import brand_script_page as bsp  # noqa: E402


def _beat(**kw):
    goc = {
        "beatType": "hook", "voiceoverTextVi": "Lời đọc mới",
        "captionSuggestionVi": "Chữ trên hình", "visualBriefVi": "Cận cảnh",
        "originalityFlag": "clear", "flaggedExcerpt": "", "lyDoChuaKiem": "",
        "complianceFlag": "clear", "complianceExcerpt": "", "complianceRule": "",
    }
    goc.update(kw)
    return goc


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def page():
    return bsp.BrandScriptPage(lambda: object())


# ----------------------------------------------------- cửa sang H4 ---------

@pytest.mark.parametrize("trang_thai,mo_cua", [
    ("ready", True),
    ("blocked", False),
    ("unconfirmed", False),
    ("draft", False),
    ("checking", False),
    ("failed", False),
])
def test_nut_dung_kich_ban_chi_sang_khi_ready(page, trang_thai, mo_cua):
    page._hien_tai = {"status": trang_thai, "beats": [_beat()]}
    page._render_script()
    assert page.btn_use.isEnabled() is mo_cua, \
        f"trạng thái {trang_thai!r} mà nút sang H4 {'sáng' if not mo_cua else 'tắt'}"


def test_khong_co_nut_nao_bo_qua_canh_bao(page):
    # Guardrail H3: không có "bỏ qua cảnh báo, dùng luôn". Quét nhãn mọi nút
    # trên trang — thêm một nút như vậy sau này sẽ làm test này đỏ.
    from PySide6.QtWidgets import QPushButton
    nhan = " ".join((b.text() or "").lower() for b in page.findChildren(QPushButton))
    for cam in ("bỏ qua", "dùng luôn", "vẫn dùng", "xác nhận vẫn"):
        assert cam not in nhan, f"trang có nút bỏ qua cảnh báo: {cam!r}"


def test_render_lai_ban_bi_chan_thi_tat_nut_dang_sang(page):
    # Ca thật: xem một kịch bản sạch (nút sáng), rồi mở một kịch bản bị chặn.
    # Quên tắt nút ở lần render sau là lọt thẳng sang H4.
    page._hien_tai = {"status": "ready", "beats": [_beat()]}
    page._render_script()
    assert page.btn_use.isEnabled()

    page._hien_tai = {"status": "blocked",
                      "beats": [_beat(originalityFlag="flagged", flaggedExcerpt="abc")]}
    page._render_script()
    assert not page.btn_use.isEnabled()


# ------------------------------------------------- câu chữ giải thích ------

def test_beat_trung_cau_chu_hien_dung_cum_bi_chan(page):
    dong = bsp._tom_tat_co(_beat(originalityFlag="flagged",
                                 flaggedExcerpt="mất quá nhiều thời gian mỗi sáng"))
    assert "mất quá nhiều thời gian mỗi sáng" in dong
    assert bsp.STATUS_ERROR in dong


def test_beat_vi_pham_hien_CA_cum_lan_rang_buoc_da_kich_hoat(page):
    dong = bsp._tom_tat_co(_beat(complianceFlag="violated",
                                 complianceExcerpt="tốt nhất",
                                 complianceRule="tốt nhất"))
    assert "tốt nhất" in dong
    # Không chỉ báo "có vấn đề" — phải nói rõ ràng buộc nào kích hoạt.
    assert "ràng buộc" in dong.lower()


@pytest.mark.parametrize("ly_do", [
    "khong_co_dau_van_tay", "khac_phien_ban", "day_tran", "bang_chung_khong_du",
])
def test_bon_ly_do_chua_kiem_ra_bon_cau_KHAC_nhau(page, ly_do):
    dong = bsp._tom_tat_co(_beat(originalityFlag="unconfirmed", lyDoChuaKiem=ly_do))
    assert bsp.STATUS_WARN in dong
    assert bsp._LY_DO_CHUA_KIEM[ly_do] in dong


def test_bon_cau_ly_do_khong_trung_nhau():
    cau = list(bsp._LY_DO_CHUA_KIEM.values())
    assert len(set(cau)) == len(cau), "hai lý do dùng chung một câu là mất thông tin"


def test_beat_sach_noi_ro_da_kiem_gi(page):
    dong = bsp._tom_tat_co(_beat())
    assert bsp.STATUS_OK in dong
    assert "trùng" in dong.lower() and "cấm" in dong.lower()


# --------------------------------------------------------- wording --------

def test_khong_dung_tu_sao_chep_video_trong_chu_nguoi_dung_thay(page):
    # Guardrail wording kế thừa từ H2: công cụ HỌC NHỊP, không "copy video".
    # Quét CHỮ HIỂN THỊ chứ không quét mã nguồn — chính câu dặn trong docstring
    # có chứa cụm cấm, quét mã là tự bắt nhầm mình.
    from PySide6.QtWidgets import QLabel, QPushButton

    hien_thi = " ".join(
        (w.text() or "")
        for lop in (QLabel, QPushButton)
        for w in page.findChildren(lop)).lower()
    for cam in ("sao chép video", "copy video", "clone video", "sao chép lại video"):
        assert cam not in hien_thi, f"chữ hiển thị có wording cấm: {cam!r}"
    # ...và phải nói đúng thứ nó thật sự làm
    assert "nhịp kể chuyện" in hien_thi


def test_hien_thi_beat_type_bang_tieng_Viet(page):
    assert bsp._nhan_beat({"beatType": "cta"}) == "Kêu gọi hành động"
    assert bsp._nhan_beat({"beatType": "khong_co_that"}) == "Chưa xác định"


# ------------------------------------------------------ danh sách nguồn ----

def test_chi_nhan_blueprint_da_phan_tich_xong(page):
    # Chọn một lượt hỏng thì tới lúc gọi máy chủ mới báo lỗi, mà khi đó người
    # dùng đã chờ mất công.
    page._on_bp_listed("list", [
        {"id": "1", "status": "ready", "sourceReference": "a", "beats": [{}]},
        {"id": "2", "status": "failed", "sourceReference": "b", "beats": []},
        {"id": "3", "status": "blocked", "sourceReference": "c", "beats": []},
    ])
    assert [b["id"] for b in page._blueprints] == ["1"]
    assert page.cbo_blueprint.count() == 1


def test_chua_co_blueprint_thi_chi_duong_di_tiep(page):
    page._on_bp_listed("list", [])
    assert "Phân tích cấu trúc" in page.status.text()


def test_chua_co_ho_so_brand_thi_chi_duong_di_tiep(page):
    page._on_brand_listed("list", [])
    assert "Hồ sơ" in page.status.text() or "hồ sơ" in page.status.text()
