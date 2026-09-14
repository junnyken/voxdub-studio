"""Cột nút phải đủ rộng cho CHÍNH nhãn của nó — và KHÔNG do tôi đo.

Người dùng báo hai lần trong một ngày (14/09): nút «Viết lại đoạn» ở H3 hiện
ra `: lại đi`, rồi hai nút ở cột «Ảnh» của H4 hiện ra **trắng trơn**.

Đây không phải chuyện thẩm mỹ. Ở H3, «Viết lại đoạn» là đường thoát DUY NHẤT
khi kịch bản bị chặn. Ở H4, một trong hai nút **tốn 33 Vox**, nút kia miễn phí
— hai ô trắng cạnh nhau thì không đoán nổi cái nào.

Bản vá đầu chốt số cứng (110→160, rồi 120→240) và tôi đo `sizeHint()` trên
Linux để chứng minh nó đủ. Test xanh, nút VẪN cắt trên Windows của chủ dự
án. Bề rộng chữ phụ thuộc phông CỦA MÁY CHẠY, nên mọi con số đo ở đây đều
là số của máy tôi. Nay cột để Qt tự co (`ResizeToContents`) và test khẳng
định đúng CƠ CHẾ đó — không còn con số nào để sai.
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


#: Giữ tham chiếu tới trang: thả ra thì Qt thu hồi luôn widget C++ bên dưới
#: và mọi truy vấn sau đó ném "Internal C++ object already deleted".
_GIU = []


def _cot(trang_lop, chi_so: int):
    trang = trang_lop(lambda: object())
    _GIU.append(trang)
    bang = getattr(trang, "bang", None) or trang.beats_table
    return bang, bang._columns[chi_so]


def _che_do(bang, chi_so: int):
    return bang.table.horizontalHeader().sectionResizeMode(chi_so)


def test_BANG_CHUNG_PHU_DINH_cot_nut_KHONG_duoc_chot_so_cung():
    """Bản vá đầu (120→240) ĐÃ HỎNG trên máy thật, và đây là lý do.

    Bề rộng chữ phụ thuộc PHÔNG CỦA MÁY. Tôi đo `sizeHint()` trên Linux, test
    xanh, rồi nút vẫn bị cắt trên Windows của chủ dự án: `:họn ảnh..` và
    `/ẽ (33 Vox`. Chốt một con số là chốt bề rộng phông của máy mình.

    Cách duy nhất không sai được: để Qt tự đo widget thật
    (`ResizeToContents`) — lúc đó không còn con số nào để sai.
    """
    from PySide6.QtWidgets import QHeaderView

    from autodub_gui.pages.brand_script_page import BrandScriptPage
    from autodub_gui.pages.storyboard_page import StoryboardPage

    for lop, chi_so, ten in ((StoryboardPage, 4, "H4 cột nút ảnh"),
                             (BrandScriptPage, 5, "H3 cột nút viết lại")):
        bang, cot = _cot(lop, chi_so)
        assert not cot.width, (
            f"{ten}: còn chốt width={cot.width} — con số đó chỉ đúng với phông "
            "của máy viết ra nó")
        assert _che_do(bang, chi_so) == QHeaderView.ResizeMode.ResizeToContents, (
            f"{ten}: cột không tự co theo nội dung")


def test_cot_thao_tac_lich_su_cung_tu_co():
    from PySide6.QtWidgets import QHeaderView

    from autodub_gui.pages.brand_script_page import BrandScriptPage

    trang = BrandScriptPage(lambda: object())
    assert not trang.history_table._columns[3].width
    assert trang.history_table.table.horizontalHeader().sectionResizeMode(3) \
        == QHeaderView.ResizeMode.ResizeToContents


def test_cot_co_CHU_van_duoc_chot_so(
):
    """Đừng sửa quá tay: cột chữ thường vẫn nên có bề rộng định trước, vì
    `ResizeToContents` trên ô chữ dài sẽ kéo bảng rộng ra vô tận."""
    from autodub_gui.pages.storyboard_page import StoryboardPage

    _bang, cot = _cot(StoryboardPage, 0)          # cột "Đoạn"
    assert cot.width, "cột chữ ngắn cố định thì giữ nguyên số"
