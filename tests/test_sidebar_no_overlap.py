"""V73 — thanh bên không được chồng mục lên nhau khi cửa sổ thấp.

Lỗi thật, người dùng chụp màn hình bản v3.4.0 (2026-08-18): mục cuối nhóm
CÔNG CỤ («Chép lời») vẽ đè lên nhãn HỆ THỐNG và nuốt luôn mục đầu của nhóm
dưới nó.

Cơ chế: cả ba `QListWidget` đều bị khoá cứng chiều cao (`_build_list` đặt
min = max), nên khi thanh bên thấp hơn tổng chiều cao chúng đòi, `QVBoxLayout`
không còn gì để co — nó xếp chồng các widget lên nhau. Đo lúc sửa: thanh bên
cần **1055px** với số mục hiện tại, trong khi màn hình 1080p chỉ còn ~1000px
vùng làm việc → đè 44px. Mỗi công cụ thêm vào ăn thêm 48px nữa, nên đây là
lỗi sẽ tự nặng dần chứ không phải ca hiếm.

`_sync_footer` (ẩn thẻ đáy) KHÔNG cứu được: ẩn cả hai thẻ mà `sizeHint` vẫn
là 1055 — đo được, và ảnh người dùng gửi cũng đã ở trạng thái ẩn cả hai thẻ.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget  # noqa: E402

from autodub_gui import tokens  # noqa: E402
from autodub_gui.app import PAGES, ROW_ACCOUNT  # noqa: E402
from autodub_gui.shell import Sidebar  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def _sidebar(co_vi_vox: bool):
    """Dựng thanh bên đúng như `MainWindow._build_sidebar` dựng."""
    rows = [p for p in PAGES if p[0] != ROW_ACCOUNT or co_vi_vox]
    nhom = lambda k: [(p[0], p[1], p[4]) for p in rows if p[5] == k]  # noqa: E731
    host = QWidget()
    lay = QHBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    sb = Sidebar(nhom("main"), nhom("tools"), nhom("second"), "3.4.0")
    lay.addWidget(sb)
    host.show()
    return host, sb


def _dat_chieu_cao(host, sb, h: int):
    host.setFixedSize(tokens.SIDEBAR_W, h)
    host.layout().activate()
    sb.layout().activate()
    QApplication.processEvents()


# 1000 = màn hình 1080p sau khi trừ thanh tác vụ và thanh tiêu đề (ca của
# người dùng); các mức dưới để chắc rằng cửa sổ nhỏ hơn nữa vẫn lành.
@pytest.mark.parametrize("chieu_cao", [1200, 1000, 900, 700, 500, 300])
@pytest.mark.parametrize("co_vi_vox", [True, False])
def test_khong_muc_nao_de_len_muc_nao(chieu_cao, co_vi_vox):
    host, sb = _sidebar(co_vi_vox)
    _dat_chieu_cao(host, sb, chieu_cao)

    cong_cu = sb.nav_tools.geometry()
    nhan_he_thong = sb._system_label.geometry()
    he_thong = sb.nav2.geometry()

    assert cong_cu.bottom() <= nhan_he_thong.top(), (
        f"nhóm CÔNG CỤ đè lên nhãn HỆ THỐNG "
        f"{cong_cu.bottom() - nhan_he_thong.top()}px ở chiều cao {chieu_cao}")
    assert nhan_he_thong.bottom() <= he_thong.top(), (
        "nhãn HỆ THỐNG đè lên danh sách bên dưới nó")


@pytest.mark.parametrize("co_vi_vox", [True, False])
def test_thanh_ben_co_duoc_xuong_thap(co_vi_vox):
    """Gốc rễ của lỗi là thanh bên đòi một chiều cao tối thiểu lớn hơn màn
    hình. Còn đòi thì layout còn chồng — mọi cách sửa khác chỉ là hoãn."""
    _, sb = _sidebar(co_vi_vox)
    assert sb.minimumSizeHint().height() <= 400, (
        "thanh bên vẫn đòi chiều cao tối thiểu quá lớn — sẽ đè lại khi thêm mục")


def test_thap_qua_thi_cuon_chu_khong_mat_muc():
    """Không đè, nhưng cũng không được âm thầm cắt mất mục nào."""
    host, sb = _sidebar(True)
    _dat_chieu_cao(host, sb, 400)
    noi_dung = sb._nav_scroll.widget().sizeHint().height()
    with_cuon = sb._nav_scroll.verticalScrollBar()
    assert with_cuon.maximum() > 0, "phải cuộn được"
    assert with_cuon.maximum() + sb._nav_scroll.viewport().height() >= noi_dung, \
        "vùng cuộn phải với tới được mục cuối cùng"


def test_the_day_nhuong_cho_truoc_khi_phai_cuon():
    """Cuộn là phương án cuối. Ở màn hình 1080p (ca người dùng), giấu thẻ
    trạng thái là đủ để mọi mục điều hướng hiện ra mà không phải cuộn."""
    host, sb = _sidebar(False)
    _dat_chieu_cao(host, sb, 1000)
    assert sb._nav_scroll.verticalScrollBar().maximum() == 0, \
        "ở 1000px không được bắt người dùng cuộn mới thấy hết mục"
    assert sb._version.isVisibleTo(sb), "số phiên bản vẫn phải hiện"


def test_che_do_chi_bieu_tuong_van_nguyen_ven():
    """Cửa sổ hẹp: thanh bên co còn 64px, các nhãn nhóm phải biến mất."""
    host, sb = _sidebar(True)
    sb.set_width_mode(tokens.SIDEBAR_W_ICON)
    _dat_chieu_cao(host, sb, 900)
    assert sb.width() == tokens.SIDEBAR_W_ICON
    assert not sb._tools_label.isVisibleTo(sb)
    assert not sb._system_label.isVisibleTo(sb)
