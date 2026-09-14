"""RS-4 và RS-5 — hai lỗ hổng phía giao diện của trang «Viết kịch bản».

Cùng một hình dạng với nhóm RS-1…RS-6 phía máy chủ: **giao diện giữ lại một
trạng thái sau khi cơ sở của nó đã mất**.

- **RS-4** — nút Viết được mở lại bởi một lượt KHÁC. `list` chạy nền (mở
  trang, sau mỗi thao tác) có thể về đích giữa lúc lượt viết đang chạy; mở nút
  theo "vừa có lượt nào xong" là mở nhầm lượt, và cái bấm thêm đó tốn thật
  12 Vox.
- **RS-5** — sau `409 NGUON_DA_MAT`, máy chủ VỪA hạ trạng thái bản ghi xuống,
  nhưng giao diện vẫn giữ bản sao `ready` cũ trong bộ nhớ và trong bảng lịch
  sử. Bấm lại vào đó là mở cổng sang H4 bằng đúng kịch bản mà máy chủ vừa nói
  là không kiểm được.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages import brand_script_page as bsp  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def page(monkeypatch):
    # Không cho trang tự gọi máy chủ trong test — chỉ đếm số lượt nó XIN gọi.
    p = bsp.BrandScriptPage(lambda: object())
    p._so_lan_tai_lai = 0

    def _gia_list():
        p._so_lan_tai_lai += 1
    monkeypatch.setattr(p, "_list_scripts", _gia_list)
    return p


# ------------------------------------------------------------------ RS-4 ---

def test_luot_list_ve_dich_khong_duoc_mo_lai_nut_viet(page):
    """Đây đúng là đường dẫn tới việc trừ tiền HAI LẦN."""
    page.btn_run.setEnabled(False)
    page._dang_ton_tien = "create"          # lượt viết đang chạy

    page._on_action_ok("list", [])          # lượt nền về đích trước

    assert not page.btn_run.isEnabled(), (
        "nút Viết mở lại giữa lúc đang viết ⇒ bấm thêm một cái là 12 Vox nữa")
    assert page._dang_ton_tien == "create", "lượt tốn tiền vẫn đang chạy"


def test_luot_delete_ve_dich_cung_khong_mo_lai_nut(page):
    page.btn_run.setEnabled(False)
    page._dang_ton_tien = "regenerate"
    page._on_action_ok("delete", None)
    assert not page.btn_run.isEnabled()


def test_chinh_luot_viet_xong_thi_mo_lai_nut(page):
    """Mặt ngược lại — thiếu test này thì một bản vá khoá cứng nút vẫn qua."""
    page.btn_run.setEnabled(False)
    page._dang_ton_tien = "create"
    page._on_action_ok("create", {"id": "x", "status": "ready", "beats": []})
    assert page.btn_run.isEnabled()
    assert page._dang_ton_tien is None


def test_luot_viet_that_bai_cung_mo_lai_nut(page):
    """Hỏng thì phải cho thử lại — khoá cứng là bắt người dùng khởi động lại."""
    page.btn_run.setEnabled(False)
    page._dang_ton_tien = "create"
    page._on_action_failed("create", "Máy chủ bận")
    assert page.btn_run.isEnabled()
    assert page._dang_ton_tien is None


def test_list_that_bai_khong_mo_nut_cua_luot_viet_dang_chay(page):
    page.btn_run.setEnabled(False)
    page._dang_ton_tien = "create"
    page._on_action_failed("list", "mất mạng")
    assert not page.btn_run.isEnabled()


# ------------------------------------------------------------------ RS-5 ---

def test_nguon_da_mat_thi_bo_phan_quyet_cu_va_hoi_lai_may_chu(page):
    page._hien_tai = {"id": "kb1", "status": "ready", "beats": []}
    page.btn_use.setEnabled(True)           # cổng H4 đang mở theo phán quyết cũ
    page._dang_ton_tien = "regenerate"

    page._on_action_failed(
        "regenerate",
        "NGUON_DA_MAT: Flow Blueprint hoặc hồ sơ brand gốc đã bị xoá — "
        "không kiểm lại được kịch bản này.")

    assert not page.btn_use.isEnabled(), "cổng sang H4 phải đóng ngay"
    assert page._hien_tai is None, (
        "giữ bản sao `ready` cũ là để người dùng bấm lại rồi đi tiếp bằng một "
        "phán quyết máy chủ vừa huỷ")
    assert page._so_lan_tai_lai == 1, (
        "phải hỏi lại máy chủ, không được tự đoán trạng thái mới")


def test_that_bai_khac_cung_khong_de_ngo_cua_H4(page):
    """Phán quyết cũ chưa chắc còn đúng sau một lượt viết lại hỏng."""
    page._hien_tai = {"id": "kb1", "status": "ready", "beats": []}
    page.btn_use.setEnabled(True)
    page._dang_ton_tien = "regenerate"

    page._on_action_failed("regenerate", "Máy chủ đang bận")

    assert not page.btn_use.isEnabled()
    # Khác ca NGUON_DA_MAT: máy chủ KHÔNG đổi gì, nên không xoá bản sao và
    # không bắt tải lại — chỉ đóng cổng cho tới khi có phán quyết mới.
    assert page._hien_tai is not None
    assert page._so_lan_tai_lai == 0


def test_luot_list_hong_khong_dong_cua_H4(page):
    """`list` hỏng là việc của bảng lịch sử, không phải phán quyết kịch bản."""
    page._hien_tai = {"id": "kb1", "status": "ready", "beats": []}
    page.btn_use.setEnabled(True)
    page._on_action_failed("list", "mất mạng")
    assert page.btn_use.isEnabled()


def test_chan_truoc_khi_tru_vox_thi_noi_dung_cau_cua_may_chu(page):
    """RS-3 phía giao diện: người dùng phải đọc được là CHƯA mất tiền."""
    page._dang_ton_tien = "create"
    cau = ("BLUEPRINT_KHONG_KIEM_DUOC: Không đối chiếu được kịch bản với video "
           "nguồn vì lượt phân tích này chạy trước khi máy chủ biết lưu dấu "
           "vân tay bằng chứng. Kịch bản viết ra sẽ không bao giờ được duyệt, "
           "nên chưa trừ Vox. Hãy phân tích lại video tham khảo rồi dùng lượt "
           "phân tích mới.")
    page._on_action_failed("create", cau)

    hien = page.status.text()
    assert "chưa trừ Vox" in hien and "phân tích lại" in hien, (
        "câu của máy chủ phải tới được người dùng nguyên vẹn")
    # ĐÂY mới là thứ test này phân biệt được. Nhánh cũ dán thêm tiền tố
    # "Không viết được kịch bản: " lên trước — nhưng đây KHÔNG phải một lượt
    # hỏng, đây là máy chủ CHẶN ĐÚNG trước khi trừ tiền. Gọi một hành động
    # bảo vệ là "không viết được" thì người dùng đọc câu sau đó bằng con mắt
    # của người vừa gặp sự cố, và "chưa trừ Vox" nghe như một lời an ủi.
    #
    # (Bản đầu của test này chỉ chốt hai cụm trên — mà cả hai vẫn còn nguyên
    # ở nhánh cũ vì nó nối cả `message` vào. Test xanh cả khi gỡ bản vá, tức
    # nó chưa chốt gì. Ghi lại đây để lần sau khỏi viết lại đúng cái bẫy đó.)
    assert "Không viết được kịch bản" not in hien
