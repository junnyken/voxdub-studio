"""Cột nút phải đủ rộng cho CHÍNH nhãn của nó — đo, không áng chừng.

Người dùng báo hai lần trong một ngày (14/09): nút «Viết lại đoạn» ở H3 hiện
ra `: lại đi`, rồi hai nút ở cột «Ảnh» của H4 hiện ra **trắng trơn**.

Đây không phải chuyện thẩm mỹ. Ở H3, «Viết lại đoạn» là đường thoát DUY NHẤT
khi kịch bản bị chặn. Ở H4, một trong hai nút **tốn 33 Vox**, nút kia miễn phí
— hai ô trắng cạnh nhau thì không đoán nổi cái nào.

Đo bằng `sizeHint()` thật của widget, vì độ rộng chữ phụ thuộc phông của máy.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui import tokens  # noqa: E402
from autodub_gui.ui.buttons import GhostButton, SecondaryButton  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def _rong_cot(trang_lop, chi_so_cot: int) -> int:
    trang = trang_lop(lambda: object())
    bang = getattr(trang, "bang", None) or trang.beats_table
    return bang._columns[chi_so_cot].width


def test_H4_cot_nut_du_cho_CA_HAI_nut():
    from autodub_gui.pages.storyboard_page import GIA_MOI_ANH, StoryboardPage

    chon = SecondaryButton("Chọn ảnh…")
    ve = GhostButton(f"Vẽ ({GIA_MOI_ANH} Vox)")
    # `set_widget` thêm lề hai bên + khoảng cách giữa hai nút.
    can = (chon.sizeHint().width() + ve.sizeHint().width()
           + tokens.SP_2 * 2 + tokens.SP_2)

    co = _rong_cot(StoryboardPage, 4)
    assert co >= can, (
        f"cột nút rộng {co}px nhưng «Chọn ảnh…» + «Vẽ ({GIA_MOI_ANH} Vox)» "
        f"cần {can}px — chữ sẽ bị cắt, và một trong hai nút TỐN TIỀN")


def test_H3_cot_nut_du_cho_Viet_lai_doan():
    from autodub_gui.pages.brand_script_page import BrandScriptPage

    nut = SecondaryButton("Viết lại đoạn")
    can = nut.sizeHint().width() + tokens.SP_2 * 2
    co = _rong_cot(BrandScriptPage, 5)
    assert co >= can, (
        f"cột {co}px < {can}px cần — «Viết lại đoạn» là đường thoát DUY NHẤT "
        "khi kịch bản bị chặn")


def test_H3_cot_thao_tac_du_cho_hai_nut_lich_su():
    from autodub_gui.pages.brand_script_page import BrandScriptPage
    from autodub_gui.ui.buttons import GhostButton as _Ghost
    from autodub_gui.ui.buttons import SecondaryButton as _Sec

    mo, xoa = _Sec("Mở"), _Ghost("Xoá")
    can = mo.sizeHint().width() + xoa.sizeHint().width() + tokens.SP_2 * 3
    trang = BrandScriptPage(lambda: object())
    co = trang.history_table._columns[3].width
    assert co >= can, f"cột Thao tác {co}px < {can}px cần"
