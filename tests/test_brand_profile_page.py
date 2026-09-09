"""Trang Hồ sơ Brand — mini-spec H1 (docs/PLAN.md, Phase H).

Trọng tâm: thao tác trên giao diện phải truyền ĐÚNG tham số xuống
`BrandProfileWorker` (đặc biệt `rangBuocKhongDuocNoi` luôn có mặt — Constraint
2 của H1), và nút Sửa/Xoá phải thao tác đúng hồ sơ đang chọn trên hàng đó
(không lẫn hồ sơ giữa các hàng).
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages import brand_profile_page as bpp  # noqa: E402

HO_SO = {
    "id": "abc123", "tenBrand": "Trà sữa Bình Minh",
    "moTaSanPham": "Trà sữa organic", "doiTuongKhach": "Sinh viên",
    "toneGiong": "vui vẻ", "usp": "Giao nhanh",
    "rangBuocKhongDuocNoi": ["không hứa giảm cân"],
}


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def page():
    return bpp.BrandProfilePage()


class _WorkerGia:
    finished_ok = type("S", (), {"connect": lambda *a: None})()
    failed = type("S", (), {"connect": lambda *a: None})()
    finished = type("S", (), {"connect": lambda *a: None})()
    last = None

    def __init__(self, action, *, profile_id="", fields=None, parent=None):
        type(self).last = {"action": action, "profile_id": profile_id, "fields": fields}

    def start(self):
        pass

    def isRunning(self):
        return False


@pytest.fixture(autouse=True)
def _reset_worker_gia():
    _WorkerGia.last = None
    yield


def test_render_danh_sach_va_cot_dung(page):
    page._on_worker_ok("list", [HO_SO])
    assert page._profiles == [HO_SO]


def test_tao_ho_so_truyen_dung_field_xuong_worker(page, monkeypatch):
    monkeypatch.setattr(bpp, "BrandProfileWorker", _WorkerGia)
    monkeypatch.setattr(
        bpp.BrandProfileFormDialog, "exec",
        lambda self: bpp.QDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        bpp.BrandProfileFormDialog, "fields",
        lambda self: {"ten_brand": "X", "rang_buoc_khong_duoc_noi": []})

    page._on_add()

    assert _WorkerGia.last["action"] == "create"
    assert _WorkerGia.last["fields"]["ten_brand"] == "X"
    assert _WorkerGia.last["fields"]["rang_buoc_khong_duoc_noi"] == []


def test_sua_ho_so_dung_id_cua_dong_dang_chon(page, monkeypatch):
    monkeypatch.setattr(bpp, "BrandProfileWorker", _WorkerGia)
    monkeypatch.setattr(
        bpp.BrandProfileFormDialog, "exec",
        lambda self: bpp.QDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        bpp.BrandProfileFormDialog, "fields",
        lambda self: {"ten_brand": "Tên mới", "rang_buoc_khong_duoc_noi": []})

    page._on_edit(HO_SO)

    assert _WorkerGia.last["action"] == "update"
    assert _WorkerGia.last["profile_id"] == "abc123"


def test_xoa_ho_so_phai_xac_nhan_truoc(page, monkeypatch):
    monkeypatch.setattr(bpp, "BrandProfileWorker", _WorkerGia)
    monkeypatch.setattr(bpp.ConfirmDialog, "ask",
                        staticmethod(lambda *a, **k: (False, False)))

    page._on_delete(HO_SO)

    assert _WorkerGia.last is None, "chưa xác nhận thì không được gọi worker xoá"


def test_xoa_ho_so_dung_id_sau_khi_xac_nhan(page, monkeypatch):
    monkeypatch.setattr(bpp, "BrandProfileWorker", _WorkerGia)
    monkeypatch.setattr(bpp.ConfirmDialog, "ask",
                        staticmethod(lambda *a, **k: (True, False)))

    page._on_delete(HO_SO)

    assert _WorkerGia.last["action"] == "delete"
    assert _WorkerGia.last["profile_id"] == "abc123"


def test_nut_thao_tac_dung_ho_so_cua_dong_do(page):
    actions = page._actions(HO_SO)
    assert actions[0].toolTip() == "Sửa hồ sơ"
    assert actions[1].toolTip() == "Xoá hồ sơ"


def test_form_rang_buoc_luon_co_mat_du_khong_go_gi():
    dialog = bpp.BrandProfileFormDialog()
    dialog.ten_brand.setText("Tên")
    assert dialog.fields()["rang_buoc_khong_duoc_noi"] == []
    assert "rang_buoc_khong_duoc_noi" in dialog.fields()


def test_form_tach_moi_dong_thanh_mot_rang_buoc():
    dialog = bpp.BrandProfileFormDialog()
    dialog.rang_buoc.setPlainText("không hứa y tế\n\nkhông dùng từ tuyệt đối\n")
    assert dialog.fields()["rang_buoc_khong_duoc_noi"] == [
        "không hứa y tế", "không dùng từ tuyệt đối"]


def test_trong_bang_ten_brand_thi_khong_luu_duoc(monkeypatch):
    warned = []
    monkeypatch.setattr(bpp.TOASTS, "warn", lambda msg, *a, **k: warned.append(msg))
    dialog = bpp.BrandProfileFormDialog()

    dialog._on_save()

    assert warned, "tên brand rỗng phải bị chặn, không lưu"


# -- Cửa vào trong sidebar ---------------------------------------------

def test_app_co_muc_ho_so_brand_va_noi_dung_trang():
    import inspect

    from autodub_gui import app as app_mod

    nguon = inspect.getsource(app_mod)
    assert "Hồ sơ Brand" in nguon
    assert "BrandProfilePage" in nguon
    assert app_mod.ROW_BRAND_PROFILE in app_mod._PAGE_BY_ROW, (
        "hàng mới phải có mặt trong PAGES thì mới hiện lên thanh bên")
