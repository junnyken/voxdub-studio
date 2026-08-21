"""Máy không có màn hình thì Qt phải chạy chế độ ẩn — bộ canh cho chốt ở conftest.

Bug thật (21-08): gõ `pytest` trần trong workspace là tiến trình **đổ core
dump**, vì Qt không nạp nổi plugin `xcb` khi thiếu `DISPLAY`. CI không bao giờ
lộ ra vì workflow tự đặt ``QT_QPA_PLATFORM=offscreen``; ai chạy tay thì đọc
thành "bộ test vỡ". `tests/conftest.py` nay tự đặt biến đó khi máy không có
màn hình.

Gỡ chốt đó ra thì test này đỏ *trước khi* cả bộ kịp sập — thay vì để lần sau
lại mất một buổi đi tìm.
"""
import os

import pytest

CO_MAN_HINH = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@pytest.mark.skipif(CO_MAN_HINH, reason="máy có màn hình thật thì chốt cố ý không đụng vào")
def test_may_khong_man_hinh_thi_qt_chay_an():
    assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"


def test_dung_duoc_qapplication():
    """Chứng minh bằng việc làm, không chỉ bằng biến môi trường.

    Đây mới là thứ đã sập: nạp plugin nền tảng. Biến đặt đúng mà plugin vẫn
    không nạp được thì test này đỏ, còn assert ở trên vẫn xanh.
    """
    from PySide6.QtWidgets import QApplication

    assert QApplication.instance() or QApplication([])
