"""V83 — trình cài đặt tự động CHƯA TỪNG chạy được lần nào.

Người dùng bấm nút "Tải giúp tôi" (thêm ở V81) và nhận:

    Không mở được trình cài đặt: module 'autodub_gui.icons' has no attribute
    'brand_logo'

`icons.brand_logo()` được gọi ở BA nơi (`icons.app_logo`, `setup_wizard`,
`app.py`) nhưng **chưa bao giờ được định nghĩa**. Dựng `SetupWizard` là ném
`AttributeError` ngay dòng logo — mà `_maybe_first_run` bọc `except Exception`
rồi bỏ qua im lặng.

Nên trình cài đặt tự động (tải FFmpeg, Whisper, VieNeu) **chưa chạy được lần
nào qua nhiều bản phát hành**, và không ai biết. Đây là lý do sâu xa khiến
người dùng phải tự cài tay mọi thứ rồi liên tục gặp lỗi.

Bài học: `except Exception` không kèm log = một lỗi có thể sống nhiều tháng.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_brand_logo_ton_tai_va_ve_duoc():
    from autodub_gui import icons

    px = icons.brand_logo(48)
    assert not px.isNull()
    assert px.width() == 48


def test_app_logo_khong_gay_khi_thieu_logo_ico(monkeypatch):
    """Đường lui phải thật sự chạy được — trước V83 nó gọi vào hàm không có."""
    from autodub_gui import icons

    monkeypatch.setattr("autodub.utils.bundled_file",
                        lambda *a: "/khong/co/logo.ico")
    assert not icons.app_logo(32).isNull()


def test_dung_duoc_toan_bo_trinh_cai_dat():
    """Chỉ cần dựng được là đủ để chặn lớp lỗi này: mọi trang đều chạy qua
    hàm khởi tạo, đúng chỗ đã gãy."""
    from autodub_gui.setup_wizard import SetupWizard

    wizard = SetupWizard(None)
    assert wizard is not None


def test_moi_ten_goi_trong_icons_deu_co_that():
    """Quét cả gói giao diện: gọi `icons.<gì đó>` mà `icons` không có thì
    lỗi chỉ nổ lúc chạy, đúng kiểu đã lọt qua nhiều bản."""
    import ast
    import os

    from autodub_gui import icons

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    goc = os.path.join(repo, "autodub_gui")
    thieu = []
    for thu_muc, _dirs, files in os.walk(goc):
        for f in files:
            if not f.endswith(".py"):
                continue
            duong = os.path.join(thu_muc, f)
            try:
                cay = ast.parse(open(duong, encoding="utf-8").read())
            except SyntaxError:
                continue
            for node in ast.walk(cay):
                if (isinstance(node, ast.Attribute)
                        and isinstance(node.value, ast.Name)
                        and node.value.id == "icons"
                        and not hasattr(icons, node.attr)):
                    thieu.append(f"{os.path.relpath(duong, repo)}:"
                                 f"{node.lineno} icons.{node.attr}")
    assert not thieu, f"gọi hàm không có trong icons: {thieu}"


def test_khong_nuot_im_lang_loi_cua_trinh_cai_dat():
    """Chính `except Exception` không kèm log đã giấu lỗi này suốt nhiều bản."""
    import os

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(repo, "autodub_gui", "app.py"),
               encoding="utf-8").read()
    i = src.find("maybe_show_setup_wizard(self)")
    assert i > 0
    khuc = src[i:i + 700]
    assert "logger.exception" in khuc, "wizard hỏng phải để lại dấu vết"


def test_kich_hoat_ma_hong_thi_bao_cho_nguoi_dung(qapp):
    """V91 — dán mã kích hoạt, bấm xong, không thấy gì xảy ra.

    Nhánh lỗi ngoài dự tính trước đây chỉ `return`: người dùng không biết mã
    đã dùng được hay chưa. Cùng lớp với V83 (trình cài đặt chết âm thầm).
    """
    import inspect

    from autodub_gui.setup_wizard import SetupWizard

    src = inspect.getsource(SetupWizard._save_api_key)
    sau_except = src.split("except Exception")[1]
    assert "set_status" in sau_except, "lỗi lạ mà không báo gì cho người dùng"
    assert "logger" in sau_except, "cũng phải để lại dấu vết trong nhật ký"
