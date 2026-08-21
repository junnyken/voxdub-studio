"""C1 — trang Ảnh sản phẩm.

Trọng tâm không phải bố cục mà là những chỗ giao diện có thể LÀM MỜ phán
quyết tuân thủ: nhãn hiển thị sai, câu tổng kết nói "xong hết" khi có ảnh
lệch, hoặc danh sách bối cảnh trôi khỏi danh sách máy chủ chấp nhận.
"""
from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub.config import Settings  # noqa: E402
from autodub.product_scene import KetQua, Phien  # noqa: E402
from autodub_gui.pages import product_scene_page as psp  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def page(tmp_path):
    settings = Settings()
    settings.output_dir = str(tmp_path)
    return psp.ProductScenePage(lambda: settings)


def _ket(boi_canh="ban_go", that="SAFE", da_kiem=True, ly_do="chỉ đổi nền"):
    return KetQua(duong_dan="/khong-co.jpg", boi_canh=boi_canh,
                  che_do_xin="SAFE", che_do_that=that, ly_do=ly_do,
                  da_kiem=da_kiem)


# -- Danh sách bối cảnh phải khớp máy chủ -----------------------------------

def test_boi_canh_khop_voi_may_chu():
    """Chọn một bối cảnh máy chủ không biết = mất tiền gọi rồi nhận lỗi."""
    js = open(os.path.join("control_server", "src", "prompts",
                           "product_scene.js"), encoding="utf-8").read()
    than = js.split("const BOI_CANH = {", 1)[1].split("\n}", 1)[0]
    tren_may_chu = {d.strip()[:-3] for d in than.splitlines()
                    if d.strip().endswith(": {")}
    trong_app = {k for k, _ in psp.BOI_CANH}
    assert trong_app == tren_may_chu, (
        "danh sách bối cảnh trong app lệch khỏi máy chủ")


def test_che_do_mac_dinh_la_giu_nguyen_san_pham(page):
    """Chế độ rủi ro phải là thứ người dùng CHỌN, không phải mặc định."""
    assert page.che_do.current_key() == "SAFE"


def test_nhan_che_do_noi_ro_hau_qua(page):
    """"CONCEPT" không nói cho người bán biết điều gì; câu cảnh báo thì có."""
    nhan = [n for n, k in psp._CHE_DO if k == "CONCEPT"][0]
    assert "KHÔNG đăng kèm" in nhan


# -- Chặn trước khi tốn tiền -------------------------------------------------

def test_khong_co_anh_thi_khong_khoi_dong_worker(page, monkeypatch):
    goi = {}
    monkeypatch.setattr(psp, "ProductSceneWorker",
                        lambda *a, **k: goi.setdefault("dung", True))
    page._chay()
    assert not goi


def test_anh_khong_ton_tai_thi_bao_ngay(page, monkeypatch):
    goi = {}
    monkeypatch.setattr(psp, "ProductSceneWorker",
                        lambda *a, **k: goi.setdefault("dung", True))
    page.anh_goc.set_text("/khong/co/thuc/anh.jpg")
    page._chay()
    assert not goi


def test_khong_chon_boi_canh_thi_khong_chay(page, monkeypatch, tmp_path):
    goi = {}
    monkeypatch.setattr(psp, "ProductSceneWorker",
                        lambda *a, **k: goi.setdefault("dung", True))
    anh = tmp_path / "a.jpg"
    anh.write_bytes(b"x")
    page.anh_goc.set_text(str(anh))
    for o in page._o_boi_canh.values():
        o.setChecked(False)
    page._chay()
    assert not goi


def test_chon_qua_nhieu_boi_canh_bi_chan(page, monkeypatch, tmp_path):
    """Mỗi ảnh là một lượt sinh + một lượt kiểm; chọn cả sáu là hoá đơn bất ngờ."""
    goi = {}
    monkeypatch.setattr(psp, "ProductSceneWorker",
                        lambda *a, **k: goi.setdefault("dung", True))
    anh = tmp_path / "a.jpg"
    anh.write_bytes(b"x")
    page.anh_goc.set_text(str(anh))
    for o in page._o_boi_canh.values():
        o.setChecked(True)
    page._chay()
    assert not goi, "vượt hạn mức mỗi lượt mà vẫn chạy"


# -- Hiển thị phán quyết -----------------------------------------------------

def test_anh_dat_hien_huy_hieu_dang_ban_duoc(page):
    the = page._the_anh(_ket())
    nhan = _cac_huy_hieu(the)
    assert nhan == ["Đăng bán được"]


def test_anh_lech_khong_bao_gio_hien_la_dang_ban_duoc(page):
    the = page._the_anh(_ket(that="CONCEPT", ly_do="nhãn khác chữ"))
    assert _cac_huy_hieu(the) == ["Chỉ để tham khảo"]


def test_anh_chua_kiem_duoc_hien_rieng_mot_nhan(page):
    """Gộp chung với "chỉ để tham khảo" thì người dùng tưởng ảnh có lỗi;
    sự thật là chưa ai kiểm — hai chuyện khác nhau, cách xử khác nhau."""
    the = page._the_anh(_ket(da_kiem=False, ly_do="không kiểm được"))
    assert _cac_huy_hieu(the) == ["Chưa kiểm được"]


def test_ly_do_hien_ra_cho_nguoi_dung(page):
    the = page._the_anh(_ket(that="CONCEPT", ly_do="nhãn khác chữ so với gốc"))
    chu = " ".join(w.text() for w in the.findChildren(type(page.status)))
    assert "nhãn khác chữ so với gốc" in chu


def _cac_huy_hieu(the):
    from autodub_gui.ui.badges import StatusBadge
    return [b.text() for b in the.findChildren(StatusBadge)]


# -- Câu tổng kết ------------------------------------------------------------

def test_tong_ket_khong_noi_xong_het_khi_co_anh_lech(page):
    phien = Phien(anh_goc="a.jpg", thu_muc="ra")
    phien.ket_qua = [_ket(), _ket("gio_qua", that="CONCEPT", ly_do="đổi nhãn")]
    page._xong(phien)
    chu = page.status.text()
    assert "1 ảnh đăng bán được" in chu
    assert "1 ảnh CHỈ để tham khảo" in chu


def test_tong_ket_khi_tat_ca_deu_dat(page):
    phien = Phien(anh_goc="a.jpg", thu_muc="ra")
    phien.ket_qua = [_ket(), _ket("gio_qua")]
    page._xong(phien)
    assert "đăng bán được" in page.status.text()
    assert "tham khảo" not in page.status.text()


def test_khong_dung_duoc_anh_nao_thi_noi_that(page):
    page._xong(Phien(anh_goc="a.jpg", thu_muc="ra"))
    assert "Không dựng được ảnh nào" in page.status.text()


def test_chay_lai_thi_xoa_ket_qua_cu(page):
    phien = Phien(anh_goc="a.jpg", thu_muc="ra")
    phien.ket_qua = [_ket(), _ket("gio_qua")]
    page._xong(phien)
    assert page.ket_qua.count() == 2
    page._xoa_ket_qua()
    assert page.ket_qua.count() == 0, (
        "ảnh lượt trước còn lại trên màn hình lượt sau = người dùng đọc "
        "phán quyết của ảnh khác")
