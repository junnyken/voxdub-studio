"""Đóng app không được ném lỗi vì một worker đã bị huỷ ở tầng C++.

Bug thật, 26/8/2026 — người dùng gửi ảnh chụp:

    File "autodub_gui\\app.py", line 666, in closeEvent
    File "autodub_gui\\pages\\editor_page.py", line 1164, in cleanup
    File "autodub_gui\\pages\\editor_page.py", line 1156, in shutdown
    RuntimeError: libshiboken: Internal C++ object
    (TimelineThumbnailWorker) already deleted.

`worker.finished.connect(worker.deleteLater)` huỷ đối tượng C++, nhưng biến
Python `self._thumb_worker` vẫn trỏ vào cái vỏ. Lúc đóng app, `shutdown()` gọi
`isRunning()` lên nó → nổ, và người dùng nhận hộp "Ứng dụng gặp lỗi không mong
muốn" đúng vào lúc thoát — thời điểm tệ nhất để mất niềm tin.

Hai lớp: buông tham chiếu khi worker xong (gốc), và hỏi "còn sống không"
trước khi gọi (lưới an toàn).
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.qt_song import con_song  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def test_doi_tuong_song_thi_bao_song(_qapp):
    obj = QObject()
    assert con_song(obj) is True


def test_none_thi_khong_song():
    assert con_song(None) is False


def test_doi_tuong_da_huy_o_tang_C_thi_bao_CHET(_qapp):
    """Đây là ca đã làm app nổ: vỏ Python còn, ruột C++ mất."""
    import shiboken6

    obj = QObject()
    shiboken6.delete(obj)
    assert con_song(obj) is False, (
        "không nhận ra đối tượng đã huỷ thì lưới an toàn vô dụng")


def test_shutdown_khong_goi_vao_worker_da_chet():
    """Đọc mã: mọi lượt gọi `isRunning()` trong dọn dẹp phải qua `con_song`."""
    import inspect

    from autodub_gui.pages import editor_page

    for ten in ("shutdown", "cleanup"):
        than = inspect.getsource(getattr(editor_page.EditorPage, ten))
        for dong in than.splitlines():
            if ".isRunning()" in dong:
                assert "con_song" in dong, (
                    f"{ten}(): «{dong.strip()}» gọi thẳng isRunning() — "
                    "worker đã huỷ ở tầng C++ sẽ ném RuntimeError")


def test_worker_thumbnail_buong_tham_chieu_khi_xong():
    """Lưới an toàn là để phòng; gốc vẫn phải là buông tham chiếu."""
    import inspect

    from autodub_gui.pages import editor_page

    nguon = inspect.getsource(editor_page.EditorPage)
    khoi = nguon.split("TimelineThumbnailWorker(", 1)[1][:900]
    assert "finished.connect(_quen)" in khoi, (
        "worker xong mà không xoá tham chiếu thì lần đóng app sau lại nổ")
