"""Giá hiện ra phải nói đúng thứ người dùng sắp trả — H2b.

Đo thật 11/09/2026 trên `youtube.com/shorts/9iB1Io8InXg` (~34 giây):

    104 khung lấy mẫu -> 65 đoạn chữ khác nhau -> gửi 65 khung

65 khung ÷ 6 = 11 lô × 8 Vox = **88 Vox** riêng phần đọc chữ. Màn hình hứa
"khoảng 32 Vox" — tức 3 lô, 18 khung. Lệch 3,7 lần, và người dùng chỉ biết
sau khi tiền đã đi.

Con số quyết định KHÔNG phải độ dài video mà là **lượng chữ trên hình**: một
video 30 giây kín caption tốn nhiều hơn hẳn một video 90 giây không chữ. Hứa
theo giây là hứa sai đại lượng.
"""
from __future__ import annotations

import math
import re

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def _nhan_gia() -> str:
    """Chữ THẬT hiện trên màn hình, không phải mã nguồn.

    Bản đầu của tệp này quét `inspect.getsource(_build)` và đỏ vì khớp vào
    chính CHÚ THÍCH tôi vừa viết ("bản trước hứa khoảng 32 Vox…"). Đó là lớp
    lỗi đã lặp nhiều lần trong dự án: chốt vào mã nguồn thì chốt cả thứ không
    phải hành vi. Đọc nhãn là đọc đúng thứ người dùng thấy.
    """
    from autodub_gui.pages.flow_blueprint_page import FlowBlueprintPage

    trang = FlowBlueprintPage(lambda: object())
    try:
        for nhan in trang.findChildren(QLabel):
            chu = nhan.text()
            if "Vox" in chu and "lô" in chu:
                return chu
    finally:
        trang.deleteLater()
    raise AssertionError("không tìm thấy nhãn báo giá trên trang")


def test_khong_hua_mot_con_so_theo_giay():
    """"Video ~60 giây tốn khoảng 32 Vox" là hứa sai đại lượng."""
    chu = _nhan_gia()
    assert "32 Vox" not in chu, (
        f"vẫn hứa một con số cố định; đo thật ra 88 Vox cho video 34 giây.\n{chu}")
    assert not re.search(r"~?\s*60 giây tốn", chu), (
        "vẫn gắn giá vào độ dài video — đại lượng quyết định là lượng chữ "
        f"trên hình, không phải số giây.\n{chu}")


def test_noi_ra_gia_phu_thuoc_luong_chu():
    chu = _nhan_gia().lower()
    assert "chữ trên hình" in chu, (
        "phải nói RÕ cái gì làm giá tăng, nếu không người dùng không đoán "
        "được lượt chạy của mình rơi vào khoảng nào")


@pytest.mark.parametrize("so_khung,vox", [(6, 8), (18, 24), (65, 88), (66, 88)])
def test_cong_thuc_gia_khop_ma_may_chu(so_khung, vox):
    """Chốt lại số học để không ai đổi một bên mà quên bên kia."""
    from autodub.media.doc_chu_may_chu import SO_KHUNG_MOI_LUOT

    assert SO_KHUNG_MOI_LUOT == 6
    assert math.ceil(so_khung / SO_KHUNG_MOI_LUOT) * 8 == vox


def test_ghi_nhat_ky_du_tinh_tien_TRUOC_khi_tieu(tmp_path, caplog, monkeypatch):
    """Phải ghi ra số Vox SẮP tiêu, trước lượt gọi đầu tiên.

    Ghi sau thì nhật ký chỉ là biên lai. Ghi trước thì người dùng đang xem
    Nhật ký còn kịp bấm Dừng — và khi họ gửi log cho người hỗ trợ, dòng đó
    nói ngay lượt chạy đã nhắm tiêu bao nhiêu.
    """
    import logging

    from autodub.media import doc_chu_may_chu as m

    quan_sat = [{"frame": i, "start_s": i * 0.5, "end_s": i * 0.5 + 0.4,
                 "text": f"chu {i}"} for i in range(65)]

    monkeypatch.setattr(m, "chia_doan", lambda _q: [[i] for i in range(65)])

    class _Khach:
        def assist(self, *a, **kw):
            raise RuntimeError("không gọi thật trong test")

    with caplog.at_level(logging.INFO, logger="autodub.media.doc_chu_may_chu"):
        m.doc_lai_bang_may_chu(quan_sat, [str(tmp_path / f"{i}.jpg")
                                          for i in range(65)],
                               client=_Khach())

    ghi = "\n".join(r.message for r in caplog.records)
    assert "88" in ghi, (
        f"không ghi ra số Vox dự tính trước khi tiêu. Đã ghi:\n{ghi}")
